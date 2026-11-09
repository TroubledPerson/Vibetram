// SPDX-License-Identifier: Apache-2.0
// Vibetram original offline status-only integration/tests; see MODIFICATIONS.json.
//! Offline production writer/lifetime integration; no socket, login or backend traffic.
use super::*;
use super::super::protocol::ServerEvent;
use super::super::status_only_gate::StatusOnlyGate;
use super::super::desired_state::RemoteControlDesiredState;
use super::super::{status_session, status_writer};
use codex_app_server_protocol::{JSONRPCMessage, RemoteControlStatusReadResponse, RequestId};
use crate::outgoing_message::{OutgoingMessage, OutgoingResponse};
use serde_json::json;
use std::pin::Pin;
use std::task::{Context, Poll};
use std::sync::atomic::{AtomicBool, Ordering};
use futures::Sink;
use tokio::sync::watch;
use tokio::time::Duration;
type Error = tungstenite::Error;

fn request(value: serde_json::Value) -> JSONRPCMessage { serde_json::from_value(value).unwrap() }
fn fixture() -> (watch::Sender<RemoteControlDesiredState>, watch::Sender<codex_login::AuthChangeState>,
    CancellationToken, status_writer::Authority) {
    let (desired, rx) = watch::channel(RemoteControlDesiredState::enabled(None));
    let cancel = CancellationToken::new();
    let mut gate = StatusOnlyGate::new(rx, cancel.clone());
    gate.admit("fixture", "stream", Some(1), &request(json!({"id":1,"method":"initialize","params":{
        "clientInfo":{"name":"offline","version":"1"},"capabilities":{"experimentalApi":true}}})), true).unwrap();
    gate.admit("fixture", "stream", Some(2), &request(json!({"method":"initialized"})), true).unwrap();
    gate.admit("fixture", "stream", Some(3), &request(json!({"id":2,"method":"remoteControl/status/read"})), true).unwrap();
    let (owner, auth_rx) = watch::channel(codex_login::AuthChangeState { generation:1, owner_generation:1 });
    let authority = status_writer::Authority { auth: crate::ConnectionAuth::new(auth_rx, 1),
        gate: Arc::new(std::sync::Mutex::new(gate)) };
    (desired, owner, cancel, authority)
}
pub(super) fn writer_authority() -> status_writer::Authority {
    let (d, o, _c, a) = fixture();
    // Legacy tests are not credentials; retain their two finite fixture watches.
    std::mem::forget((d, o)); a
}
fn reply() -> ServerEnvelope {
    ServerEnvelope { client_id: ClientId("fixture".into()), stream_id: StreamId("stream".into()), seq_id:1,
        event: ServerEvent::ServerMessage { message:Box::new(OutgoingMessage::Response(OutgoingResponse {
            id:RequestId::Integer(2),
            result:Box::new(RemoteControlStatusReadResponse {
                status:RemoteControlConnectionStatus::Connected, server_name:"offline fixture".into(),
                installation_id:"offline-installation".into(), environment_id:None,
            }.into()),
        })) } }
}
#[derive(Clone)]
struct MemorySink { accepted:Arc<std::sync::Mutex<Vec<tungstenite::Message>>>,
    ready:Arc<AtomicBool>, flush:Arc<AtomicBool>, fail:Arc<AtomicBool> }
impl MemorySink {
    fn new() -> Self { Self { accepted:Arc::new(std::sync::Mutex::new(Vec::new())),
        ready:Arc::new(AtomicBool::new(true)), flush:Arc::new(AtomicBool::new(true)),
        fail:Arc::new(AtomicBool::new(false)) } }
    fn count(&self)->usize { self.accepted.lock().unwrap().len() }
}
impl Sink<tungstenite::Message> for MemorySink {
    type Error=Error;
    fn poll_ready(self:Pin<&mut Self>,_cx:&mut Context<'_>)->Poll<Result<(),Error>> {
        if self.fail.load(Ordering::SeqCst) { Poll::Ready(Err(Error::ConnectionClosed)) }
        else if self.ready.load(Ordering::SeqCst) { Poll::Ready(Ok(())) } else { Poll::Pending }
    }
    fn start_send(self:Pin<&mut Self>,x:tungstenite::Message)->Result<(),Error> {
        self.accepted.lock().unwrap().push(x); Ok(())
    }
    fn poll_flush(self:Pin<&mut Self>,_cx:&mut Context<'_>)->Poll<Result<(),Error>> {
        if self.fail.load(Ordering::SeqCst) { Poll::Ready(Err(Error::ConnectionClosed)) }
        else if self.flush.load(Ordering::SeqCst) { Poll::Ready(Ok(())) } else { Poll::Pending }
    }
    fn poll_close(self:Pin<&mut Self>,_cx:&mut Context<'_>)->Poll<Result<(),Error>> { Poll::Ready(Ok(())) }
}
async fn settle() { for _ in 0..4 { tokio::task::yield_now().await; } }

#[tokio::test(start_paused=true)]
async fn status_session_idle_expiry_closes_whole_group() {
    let (d, _o, c, _a)=fixture(); let process=CancellationToken::new();
    let task=tokio::spawn(status_session::supervise(d.subscribe(),c.clone(),process.clone()));
    settle().await; tokio::time::advance(Duration::from_millis(119999)).await;
    assert!(!process.is_cancelled()); tokio::time::advance(Duration::from_millis(1)).await;
    task.await.unwrap(); assert!(c.is_cancelled() && process.is_cancelled());
}
#[tokio::test(start_paused=true)]
async fn status_session_repeated_enable_does_not_renew() {
    let (d,_o,c,_a)=fixture();let process=CancellationToken::new();
    let task=tokio::spawn(status_session::supervise(d.subscribe(),c.clone(),process.clone()));
    settle().await;tokio::time::advance(Duration::from_secs(90)).await;
    let current=*d.borrow();d.send_replace(current.with_persistence_preference(Some(false)));
    settle().await;tokio::time::advance(Duration::from_secs(30)).await;task.await.unwrap();
    assert!(process.is_cancelled());
}
#[tokio::test(start_paused=true)]
async fn status_session_disable_and_reenable_cannot_revive() {
    let (d,_o,c,a)=fixture();let process=CancellationToken::new();
    let task=tokio::spawn(status_session::supervise(d.subscribe(),c.clone(),process.clone()));
    settle().await;d.send_replace(RemoteControlDesiredState::Disabled);settle().await;
    task.await.unwrap();d.send_replace(RemoteControlDesiredState::enabled(None));
    assert!(process.is_cancelled() && a.admit(&reply()).is_err());
}
#[tokio::test(start_paused=true)]
async fn status_session_default_off_is_inert() {
    let(d,rx)=watch::channel(RemoteControlDesiredState::Disabled);let c=CancellationToken::new();
    let p=CancellationToken::new();let t=tokio::spawn(status_session::supervise(rx,c.clone(),p.clone()));
    settle().await;tokio::time::advance(Duration::from_secs(600)).await;assert!(!p.is_cancelled());
    d.send_replace(RemoteControlDesiredState::enabled(None));settle().await;
    tokio::time::advance(Duration::from_secs(120)).await;t.await.unwrap();assert!(p.is_cancelled());
}
#[tokio::test]
async fn status_session_correlated_response_once_and_forbidden_shape() {
    let(_d,_o,_c,a)=fixture();let e=reply();assert!(a.admit(&e).is_ok());assert!(a.admit(&e).is_err());
    let(_d,_o,_c,a)=fixture();let mut e=reply();e.client_id=ClientId("other".into());assert!(a.admit(&e).is_err());
    let mut e=reply();e.event=ServerEvent::ServerMessageChunk { segment_id:0,segment_count:1,
        message_size_bytes:1,message_chunk_base64:"eA==".into() };assert!(a.admit(&e).is_err());
}
#[tokio::test]
async fn status_session_serialization_and_actual_memory_sink() {
    let(_d,_o,c,a)=fixture();let e=reply();let lease=a.admit(&e).unwrap();
    let payload=serde_json::to_string(&e).unwrap();let mut sink=MemorySink::new();
    status_writer::send(&mut sink,payload.clone(),&lease,&a.auth,&c).await.unwrap();
    let values=sink.accepted.lock().unwrap();assert_eq!(values.len(),1);
    assert_eq!(values[0],tungstenite::Message::Text(payload.into()));
}
#[tokio::test]
async fn status_session_queued_write_cancelled_before_sink() {
    let(_d,_o,c,a)=fixture();let lease=a.admit(&reply()).unwrap();let mut sink=MemorySink::new();
    sink.ready.store(false,Ordering::SeqCst);let observed=sink.clone();
    let task=tokio::spawn(async move {status_writer::send(&mut sink,"{}".into(),&lease,&a.auth,&c).await});
    settle().await;
    // Revoke using the shared lease owner; no ready/send is credited.
    _d.send_replace(RemoteControlDesiredState::Disabled);
    _o.send_replace(codex_login::AuthChangeState{generation:2,owner_generation:2});
    assert!(task.await.unwrap().is_err());assert_eq!(observed.count(),0);
}
#[tokio::test(start_paused=true)]
async fn status_session_backpressure_expires_without_send() {
    let(_d,_o,c,a)=fixture();let lease=a.admit(&reply()).unwrap();let mut sink=MemorySink::new();
    sink.ready.store(false,Ordering::SeqCst);let observed=sink.clone();
    let task=tokio::spawn(async move {status_writer::send(&mut sink,"{}".into(),&lease,&a.auth,&c).await});
    settle().await;tokio::time::advance(Duration::from_secs(120)).await;
    assert!(task.await.unwrap().is_err());assert_eq!(observed.count(),0);
}
#[tokio::test]
async fn status_session_inflight_flush_revocation_has_no_completion_credit() {
    let(_d,_o,c,a)=fixture();let lease=a.admit(&reply()).unwrap();let mut sink=MemorySink::new();
    sink.flush.store(false,Ordering::SeqCst);let observed=sink.clone();let stop=c.clone();
    let task=tokio::spawn(async move {status_writer::send(&mut sink,"{}".into(),&lease,&a.auth,&c).await});
    settle().await;assert_eq!(observed.count(),1);stop.cancel();
    assert!(task.await.unwrap().is_err());assert_eq!(observed.count(),1);
    // Already accepted bytes cannot be recalled. No successful completion is reported.
}
#[tokio::test]
async fn status_session_reconnect_invalidates_old_write() {
    let(_d,_o,c,a)=fixture();let lease=a.admit(&reply()).unwrap();
    a.gate.lock().unwrap().begin_connection(CancellationToken::new());
    let mut sink=MemorySink::new();assert!(status_writer::send(&mut sink,"{}".into(),&lease,&a.auth,&c).await.is_err());
    assert_eq!(sink.count(),0);
}
#[tokio::test]
async fn status_session_failed_sink_is_not_success() {
    let(_d,_o,c,a)=fixture();let lease=a.admit(&reply()).unwrap();let mut sink=MemorySink::new();
    sink.fail.store(true,Ordering::SeqCst);assert!(status_writer::send(&mut sink,"{}".into(),&lease,&a.auth,&c).await.is_err());
    assert_eq!(sink.count(),0);
}
#[tokio::test]
async fn status_session_closed_watch_fails_closed() {
    let(d,_o,c,_a)=fixture();let p=CancellationToken::new();let rx=d.subscribe();
    let task=tokio::spawn(status_session::supervise(rx,c.clone(),p.clone()));settle().await;drop(d);
    task.await.unwrap();assert!(c.is_cancelled()&&p.is_cancelled());
}
#[tokio::test]
async fn status_session_phone_realtime() {
    super::status_session_backend::realtime().await;
}

fn writer_state() -> (Arc<Mutex<WebsocketState>>, watch::Receiver<usize>) {
    let (buffer, used)=BoundedOutboundBuffer::new();
    (Arc::new(Mutex::new(WebsocketState {
        outbound_buffer:buffer, subscribe_cursor:None, next_seq_id_by_stream:HashMap::new(),
        last_completed_client_chunk_seq_id_by_stream:HashMap::new(),
        client_segment_reassembler:ClientSegmentReassembler::default(),
    })),used)
}
#[tokio::test]
async fn status_session_production_writer_serializes_and_credits_once() {
    let(_d,_o,c,a)=fixture();let(state,used)=writer_state();let(tx,rx)=mpsc::channel(4);
    let(done,completion)=tokio::sync::oneshot::channel();
    let e=reply();tx.send(super::super::QueuedServerEnvelope {event:e.event,client_id:e.client_id,
        stream_id:e.stream_id,write_complete_tx:Some(done)}).await.unwrap();
    let sink=MemorySink::new();let observed=sink.clone();let stop=c.clone();
    let t=tokio::spawn(RemoteControlWebsocket::run_server_writer_inner(a,state,Arc::new(Mutex::new(rx)),
        used,sink,std::time::Duration::from_secs(30),c));
    completion.await.unwrap();stop.cancel();assert!(t.await.unwrap().is_ok());assert_eq!(observed.count(),1);
    let values=observed.accepted.lock().unwrap();
    let value:serde_json::Value=serde_json::from_str(values[0].to_text().unwrap()).unwrap();
    assert_eq!(value["message"]["id"],2);assert_eq!(value["type"],"server_message");
}
#[tokio::test]
async fn status_session_production_writer_rejects_queued_after_revocation() {
    let(d,_o,c,a)=fixture();let(state,used)=writer_state();let(tx,rx)=mpsc::channel(4);
    let(done,completion)=tokio::sync::oneshot::channel();let e=reply();
    tx.send(super::super::QueuedServerEnvelope {event:e.event,client_id:e.client_id,
        stream_id:e.stream_id,write_complete_tx:Some(done)}).await.unwrap();
    d.send_replace(RemoteControlDesiredState::Disabled);let sink=MemorySink::new();let observed=sink.clone();
    assert!(RemoteControlWebsocket::run_server_writer_inner(a,state,Arc::new(Mutex::new(rx)),used,sink,
        std::time::Duration::from_secs(30),c).await.is_err());
    assert!(completion.await.is_err());assert_eq!(observed.count(),0);
}
#[tokio::test]
async fn status_session_production_writer_rejects_buffered_replay() {
    let(_d,_o,c,a)=fixture();let(state,used)=writer_state();
    state.lock().await.outbound_buffer.insert(&reply());
    let(_tx,rx)=mpsc::channel(4);let sink=MemorySink::new();let observed=sink.clone();
    assert!(RemoteControlWebsocket::run_server_writer_inner(a,state,Arc::new(Mutex::new(rx)),used,sink,
        std::time::Duration::from_secs(30),c).await.is_err());assert_eq!(observed.count(),0);
}
#[test]
fn status_session_outer_wire_rejects_extra_duplicate_and_callbacks() {
    use super::super::status_only_gate::parse_remote_envelope;
    for text in [
        r#"{"type":"ping","client_id":"fixture","shell":"forbidden"}"#,
        r#"{"type":"ping","client_id":"fixture","client_id":"duplicate"}"#,
        r#"{"type":"client_message","client_id":"fixture","stream_id":"s","seq_id":1,"message":{"id":1,"result":{}}}"#,
        r#"{"type":"client_message","client_id":"fixture","stream_id":"s","seq_id":1,"message":{"id":1,"method":"file/read","params":{}}}"#,
        r#"{"type":"unknown","client_id":"fixture"}"#,
    ] { assert!(parse_remote_envelope(text).is_err()); }
    assert!(parse_remote_envelope(r#"{"type":"ping","client_id":"fixture"}"#).is_ok());
}
