// Vibetram modification notice: changed for Android compatibility and/or the offline status-only gate/session integration.
// Based on OpenAI Codex rust-v0.156.0; see SOURCE_PROVENANCE.md, MODIFICATIONS.json and applicable licences.
//! Binds a transport connection to the authentication owner that established it.
//! Owner revisions invalidate queued work even before transport closure is delivered.

use codex_login::AuthChangeState;
use codex_login::AuthManager;
use std::io;
use tokio::sync::watch;

#[derive(Clone, Debug)]
pub struct ConnectionAuth {
    changes: watch::Receiver<AuthChangeState>,
    owner_generation: u64,
    remote_status: Option<crate::RemoteStatusLease>,
}

impl ConnectionAuth {
    pub(crate) fn capture(auth_manager: &AuthManager) -> Self {
        let changes = auth_manager.auth_change_state_receiver();
        let owner_generation = changes.borrow().owner_generation;
        Self::new(changes, owner_generation)
    }

    pub(crate) fn ensure_current(&self) -> io::Result<()> {
        if self.is_current() {
            Ok(())
        } else {
            Err(io::Error::new(
                io::ErrorKind::Interrupted,
                "remote control authentication changed",
            ))
        }
    }

    pub(crate) fn new(changes: watch::Receiver<AuthChangeState>, owner_generation: u64) -> Self {
        Self {
            changes,
            owner_generation,
            remote_status: None,
        }
    }

    pub fn is_current(&self) -> bool {
        self.changes.borrow().owner_generation == self.owner_generation
            && self.changes.has_changed().is_ok()
            && self.remote_status.as_ref().is_none_or(crate::RemoteStatusLease::is_current)
    }

    pub(crate) fn with_remote_status(&self, lease: crate::RemoteStatusLease) -> Self {
        let mut bound = self.clone();
        bound.remote_status = Some(lease);
        bound
    }

    /// Consumer-side check: a remote connection without a production lease is never admitted.
    pub fn remote_status_message_allowed(&self, message: &codex_app_server_protocol::JSONRPCMessage) -> bool {
        self.is_current()
            && self.remote_status.as_ref().is_some_and(crate::RemoteStatusLease::is_current)
            && crate::transport::remote_status_message_shape_allowed(message)
    }

    pub(crate) async fn invalidated(&self) {
        let mut changes = self.changes.clone();
        let _ = changes
            .wait_for(|state| state.owner_generation != self.owner_generation)
            .await;
    }
}
