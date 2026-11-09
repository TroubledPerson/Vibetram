// SPDX-License-Identifier: Apache-2.0
// Vibetram original offline status-only integration/tests; see MODIFICATIONS.json.
//! The same guarded writer is used by the real websocket and offline memory sinks.
use super::status_only_gate::RemoteStatusLease;
use futures::{Sink, SinkExt};
use std::io;
use std::pin::Pin;
use std::task::{Context, Poll};
use tokio_tungstenite::tungstenite::Message;
use tokio_util::sync::CancellationToken;

#[derive(Clone)]
pub(super) struct Authority {
    pub(super) auth: crate::ConnectionAuth,
    pub(super) gate: std::sync::Arc<std::sync::Mutex<super::status_only_gate::StatusOnlyGate>>,
}
impl Authority {
    pub(super) fn admit(&self, envelope: &super::protocol::ServerEnvelope) -> Result<RemoteStatusLease, ()> {
        if !self.auth.is_current() { return Err(()); }
        self.gate.lock().map_err(|_| ())?.authorize_write(envelope)
    }
}
struct GuardedSink<'a, S> { sink: &'a mut S, lease: &'a RemoteStatusLease, auth: &'a crate::ConnectionAuth }
impl<S: Sink<Message, Error=tokio_tungstenite::tungstenite::Error> + Unpin> Sink<Message> for GuardedSink<'_, S> {
    type Error = tokio_tungstenite::tungstenite::Error;
    fn poll_ready(mut self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<Result<(), Self::Error>> {
        if !self.auth.is_current() || !self.lease.is_current() { return Poll::Ready(Err(Self::Error::ConnectionClosed)); }
        Pin::new(&mut *self.sink).poll_ready(cx)
    }
    fn start_send(mut self: Pin<&mut Self>, item: Message) -> Result<(), Self::Error> {
        if !self.auth.is_current() || !self.lease.is_current() { return Err(Self::Error::ConnectionClosed); }
        Pin::new(&mut *self.sink).start_send(item)
    }
    fn poll_flush(mut self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<Result<(), Self::Error>> {
        if !self.auth.is_current() || !self.lease.is_current() { return Poll::Ready(Err(Self::Error::ConnectionClosed)); }
        Pin::new(&mut *self.sink).poll_flush(cx)
    }
    fn poll_close(mut self: Pin<&mut Self>, cx: &mut Context<'_>) -> Poll<Result<(), Self::Error>> {
        Pin::new(&mut *self.sink).poll_close(cx)
    }
}

pub(super) async fn send<S>(
    sink: &mut S, payload: String, lease: &RemoteStatusLease, auth: &crate::ConnectionAuth, cancel: &CancellationToken,
) -> io::Result<()>
where S: Sink<Message, Error=tokio_tungstenite::tungstenite::Error> + Unpin {
    if !auth.is_current() || !lease.is_current() { return Err(io::Error::other("status write revoked")); }
    let mut guarded = GuardedSink { sink, lease, auth };
    tokio::select! {
        biased;
        _ = auth.invalidated() => Err(io::Error::other("status owner revoked")),
        _ = cancel.cancelled() => Err(io::Error::other("status write cancelled")),
        _ = tokio::time::sleep_until(lease.deadline()) => Err(io::Error::other("status write expired")),
        result = guarded.send(Message::Text(payload.into())) => result.map_err(io::Error::other),
    }
}
