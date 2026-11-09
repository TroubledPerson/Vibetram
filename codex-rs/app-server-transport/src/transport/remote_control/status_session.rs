// SPDX-License-Identifier: Apache-2.0
// Vibetram original offline status-only integration/tests; see MODIFICATIONS.json.
//! Non-renewable lifetime shared by enrollment, dispatch and writer tasks.
use super::desired_state::RemoteControlDesiredState;
use tokio::sync::watch;
use tokio::time::{Duration, Instant};
use tokio_util::sync::CancellationToken;

pub(super) const LIFETIME: Duration = Duration::from_secs(120);

/// A session is never renewed by traffic, reconnect or another enable request.
pub(super) async fn supervise(
    mut desired: watch::Receiver<RemoteControlDesiredState>,
    session: CancellationToken,
    process: CancellationToken,
) {
    let deadline = loop {
        let activation = desired.borrow_and_update().activation_time();
        if let Some(activation) = activation { break activation + LIFETIME; }
        tokio::select! {
            biased;
            _ = session.cancelled() => return,
            _ = process.cancelled() => return,
            changed = desired.changed() => if changed.is_err() { session.cancel(); process.cancel(); return; },
        }
    };
    loop {
        let current = *desired.borrow_and_update();
        if !current.is_enabled() || current.activation_time().is_none_or(|at| at + LIFETIME != deadline)
            || Instant::now() >= deadline {
            session.cancel();
            process.cancel();
            return;
        }
        tokio::select! {
            biased;
            _ = session.cancelled() => { process.cancel(); return; },
            _ = process.cancelled() => { session.cancel(); return; },
            _ = tokio::time::sleep_until(deadline) => { session.cancel(); process.cancel(); return; },
            changed = desired.changed() => if changed.is_err() { session.cancel(); process.cancel(); return; },
        }
    }
}

pub(super) fn active(desired: &watch::Receiver<RemoteControlDesiredState>, shutdown: &CancellationToken) -> bool {
    !shutdown.is_cancelled() && desired.borrow().activation_time()
        .is_some_and(|at| Instant::now() < at + LIFETIME)
}
