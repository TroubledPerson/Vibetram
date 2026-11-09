// SPDX-License-Identifier: Apache-2.0
// Vibetram original offline status-only integration/tests; see MODIFICATIONS.json.
use super::desired_state::RemoteControlDesiredState;
use super::status_only_gate::StatusOnlyGate;
use codex_app_server_protocol::JSONRPCMessage;
use serde_json::json;
use std::sync::Arc;
use std::sync::atomic::{AtomicUsize, Ordering};
use tokio::sync::{oneshot, watch};
use tokio::time::Duration;
use tokio_util::sync::CancellationToken;

// Include the actual dispatcher admission implementation, without an auth stub.
#[path = "../../../../app-server/src/connection_rpc_gate.rs"]
mod production_rpc_gate;
use production_rpc_gate::ConnectionRpcGate;

fn init(id: i64) -> JSONRPCMessage {
    serde_json::from_value(json!({"id":id,"method":"initialize","params":{
        "clientInfo":{"name":"unit-fixture","version":"1"},
        "capabilities":{"experimentalApi":true}}})).expect("fixed initialize")
}
fn status(id: i64) -> JSONRPCMessage {
    serde_json::from_value(json!({"id":id,"method":"remoteControl/status/read"}))
        .expect("fixed status")
}
fn setup() -> (watch::Sender<RemoteControlDesiredState>, CancellationToken, StatusOnlyGate) {
    let (tx, rx) = watch::channel(RemoteControlDesiredState::enabled(/*persistence_preference*/ None));
    let cancel = CancellationToken::new();
    let gate = StatusOnlyGate::new(rx, cancel.clone());
    (tx, cancel, gate)
}
fn ready(gate: &mut StatusOnlyGate, stream: &str) -> super::RemoteStatusLease {
    gate.admit("fixture", stream, Some(1), &init(1), true).expect("initialize");
    let initialized = serde_json::from_value(json!({"method":"initialized"}))
        .expect("initialized");
    gate.admit("fixture", stream, Some(2), &initialized, true).expect("initialized");
    gate.admit("fixture", stream, Some(3), &status(2), true).expect("status")
}
fn dispatcher(lease: super::RemoteStatusLease) -> (
    watch::Sender<codex_login::AuthChangeState>, ConnectionRpcGate,
) {
    let (tx, rx) = watch::channel(codex_login::AuthChangeState {
        generation: 1,
        owner_generation: 1,
    });
    let auth = crate::ConnectionAuth::new(rx, 1).with_remote_status(lease);
    let mut gate = ConnectionRpcGate::new();
    gate.auth = Some(auth);
    (tx, gate)
}

#[tokio::test(start_paused = true)]
async fn deadline_is_not_postponed_by_an_idle_enabled_gate() {
    let (_desired, _cancel, mut gate) = setup();
    tokio::time::advance(Duration::from_secs(120)).await;
    assert!(gate.admit("fixture", "idle", Some(1), &init(1), true).is_err(),
        "the enabled pilot must expire even if no request has arrived");
}

#[tokio::test(start_paused = true)]
async fn lease_rejects_at_exact_deadline_after_admission() {
    let (_desired, _cancel, mut gate) = setup();
    let lease = ready(&mut gate, "deadline");
    tokio::time::advance(Duration::from_millis(119_999)).await;
    assert!(lease.is_current());
    tokio::time::advance(Duration::from_millis(1)).await;
    assert!(!lease.is_current());
    assert!(gate.admit("fixture", "new", Some(1), &init(9), true).is_err());
}

#[tokio::test]
async fn reconnect_rejects_stale_lease_and_stream() {
    let (_desired, _cancel, mut gate) = setup();
    let old = ready(&mut gate, "old");
    let connection = CancellationToken::new();
    gate.begin_connection(connection.clone());
    assert!(!old.is_current());
    assert!(gate.admit("fixture", "old", Some(4), &status(3), true).is_err());
    let fresh = ready(&mut gate, "fresh");
    assert!(fresh.is_current());
    connection.cancel();
    assert!(!fresh.is_current());
}

#[tokio::test]
async fn duplicate_status_request_is_admitted_at_most_once() {
    let (_desired, _cancel, mut gate) = setup();
    ready(&mut gate, "duplicates");
    let admitted = (4..7).filter(|seq| {
        gate.admit("fixture", "duplicates", Some(*seq), &status(3), true).is_ok()
    }).count();
    assert_eq!(admitted, 1);
}

#[tokio::test]
async fn cancellation_drops_queued_dispatch_without_polling() {
    let (_desired, cancel, mut gate) = setup();
    let lease = ready(&mut gate, "queued");
    let (_owner, dispatcher) = dispatcher(lease);
    let calls = AtomicUsize::new(0);
    cancel.cancel();
    dispatcher.run(async { calls.fetch_add(1, Ordering::SeqCst); }).await;
    assert_eq!(calls.load(Ordering::SeqCst), 0);
    assert!(!dispatcher.allows_remote_message(&status(3)));
    dispatcher.shutdown().await;
}

#[tokio::test]
async fn started_dispatch_drains_but_late_callback_is_rejected() {
    let (_desired, cancel, mut gate) = setup();
    let lease = ready(&mut gate, "started");
    let (_owner, dispatcher) = dispatcher(lease);
    let dispatcher = Arc::new(dispatcher);
    let calls = Arc::new(AtomicUsize::new(0));
    let (entered_tx, entered_rx) = oneshot::channel();
    let (finish_tx, finish_rx) = oneshot::channel();
    let active = dispatcher.clone();
    let active_calls = calls.clone();
    let running = tokio::spawn(async move {
        active.run(async move {
            entered_tx.send(()).expect("entered");
            finish_rx.await.expect("finish");
            active_calls.fetch_add(1, Ordering::SeqCst);
        }).await;
    });
    entered_rx.await.expect("started");
    cancel.cancel();
    dispatcher.run(async { calls.fetch_add(100, Ordering::SeqCst); }).await;
    assert_eq!(calls.load(Ordering::SeqCst), 0);
    finish_tx.send(()).expect("release admitted cleanup");
    running.await.expect("join");
    dispatcher.shutdown().await;
    assert_eq!(calls.load(Ordering::SeqCst), 1);
}
#[tokio::test(start_paused = true)]
async fn delayed_gate_construction_does_not_restart_activation_deadline() {
    let (tx, rx) = watch::channel(RemoteControlDesiredState::enabled(/*persistence_preference*/ None));
    tokio::time::advance(Duration::from_secs(120)).await;
    let mut gate = StatusOnlyGate::new(rx, CancellationToken::new());
    assert!(gate.admit("fixture", "late-install", Some(1), &init(1), true).is_err());
    drop(tx);
}

#[tokio::test(start_paused = true)]
async fn delayed_first_ingress_after_disabled_to_enabled_still_expires() {
    let (tx, rx) = watch::channel(RemoteControlDesiredState::Disabled);
    let mut gate = StatusOnlyGate::new(rx, CancellationToken::new());
    tokio::time::advance(Duration::from_secs(5)).await;
    tx.send_replace(RemoteControlDesiredState::enabled(/*persistence_preference*/ None));
    tokio::time::advance(Duration::from_secs(120)).await;
    assert!(gate.admit("fixture", "late-observation", Some(1), &init(1), true).is_err());
}

#[tokio::test(start_paused = true)]
async fn repeated_enable_and_preference_upgrade_cannot_extend_deadline() {
    let (tx, _cancel, mut gate) = setup();
    let original = *tx.borrow();
    tokio::time::advance(Duration::from_secs(60)).await;
    let repeated = original.with_persistence_preference(/*persistence_preference*/ None);
    assert_eq!(repeated, original);
    assert_eq!(repeated.activation_time(), original.activation_time());
    let upgraded = repeated.with_persistence_preference(Some(true));
    assert_eq!(upgraded.activation_time(), original.activation_time());
    tx.send_replace(upgraded);
    let lease = ready(&mut gate, "upgrade");
    tokio::time::advance(Duration::from_secs(60)).await;
    assert!(!lease.is_current());
    assert!(gate.admit("fixture", "upgrade-retry", Some(1), &init(5), true).is_err());
}

#[tokio::test(start_paused = true)]
async fn reconnect_before_any_rpc_cannot_extend_deadline() {
    let (_desired, _cancel, mut gate) = setup();
    tokio::time::advance(Duration::from_secs(119)).await;
    gate.begin_connection(CancellationToken::new());
    tokio::time::advance(Duration::from_secs(1)).await;
    gate.begin_connection(CancellationToken::new());
    assert!(gate.admit("fixture", "reconnected", Some(1), &init(1), true).is_err());
}

#[tokio::test(start_paused = true)]
async fn explicit_fresh_activation_gets_new_deadline_without_reviving_old_lease() {
    let (tx, _cancel, mut gate) = setup();
    let first_state = *tx.borrow();
    let old = ready(&mut gate, "old-activation");
    tokio::time::advance(Duration::from_secs(120)).await;
    assert!(!old.is_current());
    tx.send_replace(RemoteControlDesiredState::Disabled);
    let fresh_state = RemoteControlDesiredState::enabled(/*persistence_preference*/ None);
    assert_eq!(fresh_state, first_state, "preference equality stays compatible");
    assert_ne!(fresh_state.activation_time(), first_state.activation_time());
    tx.send_replace(fresh_state);
    let fresh = ready(&mut gate, "fresh-activation");
    assert!(fresh.is_current());
    assert!(!old.is_current(), "same preference must not revive an older watch revision");
    tokio::time::advance(Duration::from_secs(120)).await;
    assert!(!fresh.is_current());
}