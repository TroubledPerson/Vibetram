// SPDX-License-Identifier: Apache-2.0
// Vibetram original offline status-only integration/tests; see MODIFICATIONS.json.
//! Fixed remote-only admission. No account, filesystem, model or execution handler is reachable.
use super::desired_state::RemoteControlDesiredState;
use codex_app_server_protocol::JSONRPCMessage;
use serde::Deserialize;
use serde::de::{self, MapAccess, SeqAccess, Visitor};
use serde_json::Value;
use std::collections::{HashMap, HashSet};
use std::fmt;
use tokio::sync::watch;
use tokio::time::{Duration, Instant};
use tokio_util::sync::CancellationToken;

pub(crate) const MAX_REMOTE_RPC_BYTES: usize = 16 * 1024;
pub(crate) const MAX_REMOTE_WIRE_BYTES: usize = 24 * 1024;
const PILOT_LIFETIME: Duration = Duration::from_secs(120);
const MAX_STREAMS: usize = 2;
const MAX_REQUESTS: usize = 64;
const MAX_SEEN_STREAMS: usize = 64;

#[derive(Clone, Debug)]
pub struct RemoteStatusLease {
    desired: watch::Receiver<RemoteControlDesiredState>,
    shutdown: CancellationToken,
    client_closed: CancellationToken,
    deadline: Instant,
}
impl RemoteStatusLease {
    pub fn is_current(&self) -> bool {
        // Pin both the value and watch version under the read guard; a disable/re-enable
        // cannot occur between the version check and the enabled-state observation.
        let desired = self.desired.borrow();
        !self.shutdown.is_cancelled()
            && !self.client_closed.is_cancelled()
            && Instant::now() < self.deadline
            && self.desired.has_changed().is_ok_and(|changed| !changed)
            && desired.is_enabled()
    }
    pub(super) fn deadline(&self) -> Instant { self.deadline }
    pub(super) fn close(&self) { self.client_closed.cancel(); }
    pub(super) fn cancellation_token(&self) -> CancellationToken { self.client_closed.clone() }
}

/// No credentials are held here. The caller must supply current captured-owner admission.
pub(super) struct StatusOnlyGate {
    desired: watch::Receiver<RemoteControlDesiredState>,
    shutdown: CancellationToken,
    deadline: Option<Instant>,
    connection: CancellationToken,
    clients: HashMap<(String, String), ClientAdmission>,
    generation: u64,
    seen_streams: HashMap<(String, String), SeenStream>,
}
struct SeenStream { generation: u64, closed: bool }
struct ClientAdmission {
    lease: RemoteStatusLease,
    phase: u8,
    last_seq: u64,
    ids: HashSet<String>,
    pending: HashMap<String, Shape>,
}
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Shape { Initialize, Initialized, Status }

impl StatusOnlyGate {
    pub(super) fn new(mut desired: watch::Receiver<RemoteControlDesiredState>, shutdown: CancellationToken) -> Self {
        let deadline = desired.borrow_and_update().activation_time().map(|at| at + PILOT_LIFETIME);
        let connection = shutdown.child_token();
        Self { desired, shutdown, deadline, connection, clients: HashMap::new(), generation: 0, seen_streams: HashMap::new() }
    }
    /// A socket cancellation invalidates queued leases without waiting for tracker locks.
    pub(super) fn begin_connection(&mut self, connection: CancellationToken) {
        for state in self.clients.values() { state.lease.close(); }
        for seen in self.seen_streams.values_mut() { seen.closed = true; }
        self.connection = connection;
        // Preserve the absolute grant deadline and every old stream tombstone.
    }
    fn refresh(&mut self) -> Result<(), ()> {
        if self.desired.has_changed().map_err(|_| ())? {
            // Every older lease pins the previous watch version. Disabled->enabled cannot revive it.
            for state in self.clients.values() { state.lease.close(); }
            self.clients.clear();
            self.generation = self.generation.checked_add(1).ok_or(())?;
            self.deadline = self.desired.borrow_and_update().activation_time().map(|at| at + PILOT_LIFETIME);
        }
        if self.shutdown.is_cancelled() || self.connection.is_cancelled() || !self.desired.borrow().is_enabled() { return Err(()); }
        let deadline = self.deadline.ok_or(())?;
        if Instant::now() >= deadline { return Err(()); }
        Ok(())
    }
    pub(super) fn admit(&mut self, client: &str, stream: &str, seq: Option<u64>, message: &JSONRPCMessage, owner_current: bool) -> Result<RemoteStatusLease, ()> {
        self.observe_ingress(client, stream, owner_current)?;
        let seq = seq.filter(|n| *n > 0).ok_or(())?;
        let value = serde_json::to_value(message).map_err(|_| ())?;
        let shape = shape(&value)?;
        let key = (client.to_owned(), stream.to_owned());
        if !self.clients.contains_key(&key) {
            if shape != Shape::Initialize || self.clients.len() >= MAX_STREAMS { return Err(()); }
            // A newer initialized stream also invalidates older partial streams for this client.
            for ((existing_client, existing_stream), seen) in &mut self.seen_streams {
                if existing_client == client && existing_stream != stream { seen.closed = true; }
            }
            for ((existing_client, _), state) in &self.clients {
                if existing_client == client { state.lease.close(); }
            }
            // Preserve refresh's watch version. Never adopt a newer grant during admission.
            let desired = self.desired.clone();
            let lease = RemoteStatusLease {
                desired, shutdown: self.shutdown.clone(), client_closed: self.connection.child_token(),
                deadline: self.deadline.ok_or(())?,
            };
            self.clients.insert(key.clone(), ClientAdmission { lease, phase: 0, last_seq: 0, ids: HashSet::new(), pending: HashMap::new() });
        }
        let state = self.clients.get_mut(&key).ok_or(())?;
        if !state.lease.is_current() || seq <= state.last_seq { return Err(()); }
        let next = match (state.phase, shape) {
            (0, Shape::Initialize) => 1,
            (1, Shape::Initialized) => 2,
            (2, Shape::Status) => 2,
            _ => return Err(()),
        };
        if let Some(id) = value.get("id") {
            let id = serde_json::to_string(id).map_err(|_| ())?;
            if state.ids.len() >= MAX_REQUESTS || !state.ids.insert(id.clone()) { return Err(()); }
            state.pending.insert(id, shape);
        }
        state.last_seq = seq;
        state.phase = next;
        Ok(state.lease.clone())
    }
    pub(super) fn authorize_write(
        &mut self, envelope: &super::protocol::ServerEnvelope,
    ) -> Result<RemoteStatusLease, ()> {
        self.refresh()?;
        let key = (envelope.client_id.0.clone(), envelope.stream_id.0.clone());
        let state = self.clients.get_mut(&key).ok_or(())?;
        if !state.lease.is_current() { return Err(()); }
        match &envelope.event {
            super::protocol::ServerEvent::Ack | super::protocol::ServerEvent::Pong { .. } => return Ok(state.lease.clone()),
            super::protocol::ServerEvent::ServerMessage { message } => {
                let value = serde_json::to_value(message).map_err(|_| ())?;
                if serde_json::to_vec(&value).map_err(|_| ())?.len() > MAX_REMOTE_RPC_BYTES
                    || !only_keys(&value, &["id", "result"])
                    || !valid_id(value.get("id")) { return Err(()); }
                let id = serde_json::to_string(value.get("id").ok_or(())?).map_err(|_| ())?;
                let shape = state.pending.get(&id).ok_or(())?;
                let result = value.get("result").ok_or(())?;
                let valid = match shape {
                    Shape::Initialize => only_keys(result, &["userAgent", "codexHome", "platformFamily", "platformOs"])
                        && ["userAgent", "codexHome", "platformFamily", "platformOs"].iter()
                            .all(|key| bounded_string(result.get(*key), 256)),
                    Shape::Status => only_keys(result, &["status", "serverName", "installationId", "environmentId"])
                        && result.get("status").and_then(Value::as_str).is_some_and(|s|
                            ["disabled", "connecting", "connected", "errored"].contains(&s))
                        && bounded_string(result.get("serverName"), 128)
                        && bounded_string(result.get("installationId"), 128)
                        && result.get("environmentId").is_some_and(|v| v.is_null() || bounded_string(Some(v), 128)),
                    Shape::Initialized => false,
                };
                if !valid { return Err(()); }
                state.pending.remove(&id);
                Ok(state.lease.clone())
            }
            super::protocol::ServerEvent::ServerMessageChunk { .. } => Err(()),
        }
    }

    /// Bind the identity before buffering even the first fragment.
    pub(super) fn observe_ingress(&mut self, client: &str, stream: &str, owner_current: bool) -> Result<(), ()> {
        self.refresh()?;
        if !owner_current || client.is_empty() || client.len() > 128 || stream.is_empty() || stream.len() > 128
            || client.chars().any(char::is_control) || stream.chars().any(char::is_control) { return Err(()); }
        let key = (client.to_owned(), stream.to_owned());
        match self.seen_streams.get(&key) {
            Some(seen) if seen.generation == self.generation && !seen.closed => Ok(()),
            Some(_) => Err(()),
            None if self.seen_streams.len() < MAX_SEEN_STREAMS => {
                self.seen_streams.insert(key, SeenStream { generation: self.generation, closed: false });
                Ok(())
            }
            None => Err(()),
        }
    }
    pub(super) fn close(&mut self, client: &str, stream: &str) {
        let key = (client.to_owned(), stream.to_owned());
        if let Some(state) = self.clients.get(&key) { state.lease.close(); }
        if let Some(seen) = self.seen_streams.get_mut(&key) {
            seen.closed = true;
        } else if self.seen_streams.len() < MAX_SEEN_STREAMS {
            self.seen_streams.insert(key, SeenStream { generation: self.generation, closed: true });
        }
        // Tombstones survive desired-state changes, including closure before initialization.
    }
    pub(super) fn close_client(&mut self, client: &str) {
        for ((known_client, _), seen) in &mut self.seen_streams {
            if known_client == client { seen.closed = true; }
        }
        for ((known_client, _), state) in &self.clients {
            if known_client == client { state.lease.close(); }
        }
    }
}

fn only_keys(value: &Value, keys: &[&str]) -> bool {
    value.as_object().is_some_and(|m| m.keys().all(|k| keys.contains(&k.as_str())))
}
fn bounded_string(v: Option<&Value>, max: usize) -> bool {
    v.and_then(Value::as_str).is_some_and(|s| !s.is_empty() && s.len() <= max && !s.chars().any(char::is_control))
}
fn valid_id(v: Option<&Value>) -> bool {
    v.is_some_and(|v| v.as_i64().is_some_and(|n| n > 0) || bounded_string(Some(v), 64))
}
fn shape(value: &Value) -> Result<Shape, ()> {
    if serde_json::to_vec(value).map_err(|_| ())?.len() > MAX_REMOTE_RPC_BYTES
        || !only_keys(value, &["jsonrpc", "id", "method", "params"])
        || value.get("jsonrpc").is_some_and(|v| v != "2.0") { return Err(()); }
    match value.get("method").and_then(Value::as_str) {
        Some("initialize") => {
            let p = value.get("params").ok_or(())?;
            let c = p.get("clientInfo").ok_or(())?;
            let caps = p.get("capabilities").ok_or(())?;
            if !valid_id(value.get("id"))
                || !only_keys(p, &["clientInfo", "capabilities"])
                || !only_keys(c, &["name", "version", "title"])
                || !bounded_string(c.get("name"), 64) || !bounded_string(c.get("version"), 32)
                || c.get("title").is_some_and(|t| !t.is_null() && !bounded_string(Some(t), 128))
                || !only_keys(caps, &["experimentalApi"])
                || caps.get("experimentalApi") != Some(&Value::Bool(true)) { return Err(()); }
            Ok(Shape::Initialize)
        }
        Some("initialized") if value.get("id").is_none() && value.get("params").is_none_or(Value::is_null) => Ok(Shape::Initialized),
        Some("remoteControl/status/read") if valid_id(value.get("id")) && value.get("params").is_none_or(Value::is_null) => Ok(Shape::Status),
        _ => Err(()),
    }
}
pub(crate) fn message_shape_allowed(message: &JSONRPCMessage) -> bool {
    serde_json::to_value(message).ok().is_some_and(|v| shape(&v).is_ok())
}

// This visitor rejects duplicate keys before typed JSON-RPC deserialization could discard them.
// serde_json's normal recursion limit remains enabled; the wire/reassembly bounds apply as well.
struct UniqueValue(Value);
impl<'de> Deserialize<'de> for UniqueValue {
    fn deserialize<D: serde::Deserializer<'de>>(d: D) -> Result<Self, D::Error> {
        struct V;
        impl<'de> Visitor<'de> for V {
            type Value = UniqueValue;
            fn expecting(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result { f.write_str("bounded unique-key JSON") }
            fn visit_bool<E: de::Error>(self, v: bool) -> Result<Self::Value,E> { Ok(UniqueValue(Value::Bool(v))) }
            fn visit_i64<E: de::Error>(self, v: i64) -> Result<Self::Value,E> { Ok(UniqueValue(v.into())) }
            fn visit_u64<E: de::Error>(self, v: u64) -> Result<Self::Value,E> { Ok(UniqueValue(v.into())) }
            fn visit_f64<E: de::Error>(self, v: f64) -> Result<Self::Value,E> { serde_json::Number::from_f64(v).map(|n| UniqueValue(Value::Number(n))).ok_or_else(|| E::custom("invalid number")) }
            fn visit_str<E: de::Error>(self, v: &str) -> Result<Self::Value,E> { Ok(UniqueValue(v.into())) }
            fn visit_string<E: de::Error>(self, v: String) -> Result<Self::Value,E> { Ok(UniqueValue(v.into())) }
            fn visit_none<E: de::Error>(self) -> Result<Self::Value,E> { Ok(UniqueValue(Value::Null)) }
            fn visit_unit<E: de::Error>(self) -> Result<Self::Value,E> { Ok(UniqueValue(Value::Null)) }
            fn visit_seq<A: SeqAccess<'de>>(self, mut a:A) -> Result<Self::Value,A::Error> {
                let mut out=Vec::new();while let Some(v)=a.next_element::<UniqueValue>()? { out.push(v.0); }
                Ok(UniqueValue(Value::Array(out)))
            }
            fn visit_map<A: MapAccess<'de>>(self, mut a:A) -> Result<Self::Value,A::Error> {
                let mut out=serde_json::Map::new();
                while let Some((k,v))=a.next_entry::<String,UniqueValue>()? {
                    if out.insert(k,v.0).is_some() { return Err(de::Error::custom("duplicate remote RPC key")); }
                }
                Ok(UniqueValue(Value::Object(out)))
            }
        }
        d.deserialize_any(V)
    }
}
pub(crate) fn deserialize_remote_message<'de,D:serde::Deserializer<'de>>(d:D)->Result<JSONRPCMessage,D::Error> {
    let v=UniqueValue::deserialize(d)?.0;
    shape(&v).map_err(|_| de::Error::custom("remote status-only RPC rejected"))?;
    serde_json::from_value(v).map_err(|_| de::Error::custom("invalid remote status-only RPC"))
}
pub(crate) fn parse_remote_message(bytes:&[u8])->serde_json::Result<JSONRPCMessage>{
    if bytes.len()>MAX_REMOTE_RPC_BYTES {return Err(<serde_json::Error as de::Error>::custom("remote RPC size rejected"));}
    let mut d=serde_json::Deserializer::from_slice(bytes);
    let message=deserialize_remote_message(&mut d)?;
    d.end()?;
    Ok(message)
}

#[cfg(test)]
#[path = "status_only_gate_tests.rs"]
mod tests;

/// Validate the entire envelope before typed decoding can discard unknown/duplicate fields.
pub(crate) fn parse_remote_envelope(text: &str) -> serde_json::Result<super::protocol::ClientEnvelope> {
    let reject = || <serde_json::Error as de::Error>::custom("remote envelope rejected");
    if text.len() > MAX_REMOTE_WIRE_BYTES { return Err(reject()); }
    let mut decoder = serde_json::Deserializer::from_str(text);
    let value = UniqueValue::deserialize(&mut decoder)?.0;
    decoder.end()?;
    let common = ["type", "client_id", "stream_id", "seq_id", "cursor"];
    let keys = match value.get("type").and_then(Value::as_str) {
        Some("client_message") => [common.as_slice(), &["message"]].concat(),
        Some("client_message_chunk") => [common.as_slice(), &["segment_id", "segment_count", "message_size_bytes", "message_chunk_base64"]].concat(),
        Some("ack") => [common.as_slice(), &["segment_id"]].concat(),
        Some("ping" | "client_closed") => common.to_vec(),
        _ => return Err(reject()),
    };
    if !only_keys(&value, &keys)
        || value.get("cursor").is_some_and(|v| !v.is_null() && !bounded_string(Some(v), 512)) { return Err(reject()); }
    serde_json::from_value(value)
}

pub(super) fn decode_unique_object(bytes:&[u8])->serde_json::Result<Value>{
    let mut d=serde_json::Deserializer::from_slice(bytes);
    let v=UniqueValue::deserialize(&mut d)?.0;d.end()?;Ok(v)
}
