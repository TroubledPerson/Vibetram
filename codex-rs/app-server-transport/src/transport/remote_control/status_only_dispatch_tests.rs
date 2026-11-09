// SPDX-License-Identifier: Apache-2.0
// Vibetram original offline status-only integration/tests; see MODIFICATIONS.json.
// Tests include the actual app-server gate source inside the transport test crate.
// This exercises private owner-watch fixtures without widening a production constructor.
#[path = "../../../../app-server/src/connection_rpc_gate.rs"]
mod production_rpc_gate;
use production_rpc_gate::ConnectionRpcGate;

#[cfg(test)]
mod native_status_gate_dispatch_tests {
    use super::ConnectionRpcGate;
    use std::sync::{Arc, atomic::{AtomicUsize, Ordering}};
    use tokio::sync::{oneshot, watch};
    fn owner() -> (watch::Sender<codex_login::AuthChangeState>, codex_app_server_transport::ConnectionAuth) {
        let (tx,rx)=watch::channel(codex_login::AuthChangeState { generation:1, owner_generation:1 });
        (tx,codex_app_server_transport::ConnectionAuth::new(rx,1))
    }
    #[tokio::test]
    async fn connection_rpc_gate_auth_without_native_lease_rejects_all_remote_dispatch() {
        let (_tx,auth)=owner();
        let mut gate=ConnectionRpcGate::new();gate.auth=Some(auth);
        let mut handlers=0;
        for method in ["initialize","initialized","remoteControl/status/read","command/exec","thread/start","file/read","capture","remoteControl/pairing/start"] {
            let message:codex_app_server_protocol::JSONRPCMessage=serde_json::from_value(serde_json::json!({"id":1,"method":method,"params":{}})).expect("synthetic request");
            if gate.allows_remote_message(&message) { handlers+=1; }
        }
        assert_eq!(handlers,0);
        gate.shutdown().await;
    }
    #[tokio::test]
    async fn connection_rpc_gate_owner_change_drops_queued_body_before_first_poll() {
        let (tx,auth)=owner();
        let mut gate=ConnectionRpcGate::new();gate.auth=Some(auth);
        let calls=AtomicUsize::new(0);
        let queued=async { calls.fetch_add(1,Ordering::SeqCst); };
        tx.send_replace(codex_login::AuthChangeState { generation:2, owner_generation:2 });
        gate.run(queued).await;
        assert_eq!(calls.load(Ordering::SeqCst),0);
        assert!(gate.is_closed());
        gate.shutdown().await;
    }
    #[tokio::test]
    async fn connection_rpc_gate_owner_change_drains_started_body_but_rejects_late_body() {
        let (tx,auth)=owner();
        let mut gate=ConnectionRpcGate::new();gate.auth=Some(auth);let gate=Arc::new(gate);
        let calls=Arc::new(AtomicUsize::new(0));
        let (entered_tx,entered_rx)=oneshot::channel();
        let (finish_tx,finish_rx)=oneshot::channel();
        let active=gate.clone();let active_calls=calls.clone();
        let running=tokio::spawn(async move {
            active.run(async {
                entered_tx.send(()).expect("entered");
                finish_rx.await.expect("finish");
                active_calls.fetch_add(1,Ordering::SeqCst);
            }).await;
        });
        entered_rx.await.expect("started");
        tx.send_replace(codex_login::AuthChangeState { generation:2, owner_generation:2 });
        gate.run(async { calls.fetch_add(100,Ordering::SeqCst); }).await;
        assert_eq!(calls.load(Ordering::SeqCst),0);
        finish_tx.send(()).expect("release cleanup");
        running.await.expect("join");gate.shutdown().await;
        assert_eq!(calls.load(Ordering::SeqCst),1,"only already-admitted completion drains");
    }
}
