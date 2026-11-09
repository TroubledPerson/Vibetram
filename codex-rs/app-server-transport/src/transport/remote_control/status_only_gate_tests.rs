// SPDX-License-Identifier: Apache-2.0
// Vibetram original offline status-only integration/tests; see MODIFICATIONS.json.
use super::*;
use super::super::client_tracker::ClientTracker;
use super::super::protocol::{ClientEnvelope, ClientEvent, ClientId, StreamId};
use super::super::segment::{ClientSegmentReassembler, ClientSegmentObservation};
use crate::transport::TransportEvent;
use base64::Engine;
use serde_json::json;
use tokio::sync::mpsc;

fn initialize(id: i64) -> JSONRPCMessage {
    serde_json::from_value(json!({"id":id,"method":"initialize","params":{
        "clientInfo":{"name":"status-pilot","version":"1.85","title":null},
        "capabilities":{"experimentalApi":true}}})).expect("fixture initialize")
}
fn initialized() -> JSONRPCMessage { serde_json::from_value(json!({"method":"initialized"})).expect("fixture notification") }
fn status(id:i64) -> JSONRPCMessage { serde_json::from_value(json!({"id":id,"method":"remoteControl/status/read"})).expect("fixture status") }
fn setup() -> (watch::Sender<RemoteControlDesiredState>,CancellationToken,StatusOnlyGate) {
    let (tx,rx)=watch::channel(RemoteControlDesiredState::enabled(/*persistence_preference*/ None));
    let token=CancellationToken::new();
    let gate=StatusOnlyGate::new(rx,token.clone());
    (tx,token,gate)
}
fn ready(g:&mut StatusOnlyGate,stream:&str) -> RemoteStatusLease {
    g.admit("client",stream,Some(1),&initialize(1),true).expect("init");
    g.admit("client",stream,Some(2),&initialized(),true).expect("initialized");
    g.admit("client",stream,Some(3),&status(2),true).expect("status")
}
#[tokio::test(start_paused=true)]
async fn status_only_gate_valid_sequence_and_exact_deadline() {
    let (_tx,_token,mut g)=setup();
    let lease=ready(&mut g,"a");
    assert!(lease.is_current());
    tokio::time::advance(PILOT_LIFETIME-Duration::from_millis(1)).await;
    assert!(lease.is_current());
    tokio::time::advance(Duration::from_millis(1)).await;
    assert!(!lease.is_current());
    assert!(g.admit("client","b",Some(1),&initialize(10),true).is_err(),"reconnect cannot renew deadline");
}
#[tokio::test]
async fn status_only_gate_duplicate_and_replay_rejected() {
    let (_tx,_token,mut g)=setup();ready(&mut g,"a");
    assert!(g.admit("client","a",Some(4),&status(2),true).is_err(),"duplicate request id");
    assert!(g.admit("client","a",Some(3),&status(3),true).is_err(),"replayed sequence");
    assert!(g.admit("client","a",None,&status(3),true).is_err(),"unbound sequence");
    assert!(g.admit("other","a",Some(4),&status(4),true).is_err(),"wrong client");
    assert!(g.admit("client","b",Some(4),&status(4),true).is_err(),"wrong stream");
}
#[tokio::test]
async fn status_only_gate_reconnect_revokes_old_stream_and_keeps_tombstone() {
    let (_tx,_token,mut g)=setup();let old=ready(&mut g,"a");
    let next=ready(&mut g,"b");
    assert!(!old.is_current());assert!(next.is_current());
    assert!(g.admit("client","a",Some(5),&initialize(9),true).is_err());
    assert!(g.admit("client","c",Some(1),&initialize(10),true).is_err(),"stream count bounded");
    g.close("client","b");assert!(!next.is_current());
    assert!(g.admit("client","b",Some(8),&initialize(12),true).is_err(),"closed stream cannot reopen");
}
#[tokio::test]
async fn status_only_gate_disable_reenable_cannot_revive_queued_lease() {
    let (tx,_token,mut g)=setup();let old=ready(&mut g,"a");
    tx.send_replace(RemoteControlDesiredState::Disabled);
    assert!(!old.is_current());
    tx.send_replace(RemoteControlDesiredState::enabled(/*persistence_preference*/ None));
    assert!(!old.is_current(),"unchanged owner does not revive old watch generation");
    assert!(ready(&mut g,"b").is_current());assert!(!old.is_current());
}
#[tokio::test]
async fn status_only_gate_cancel_owner_and_phase_rejection() {
    let (_tx,token,mut g)=setup();
    assert!(g.admit("client","a",Some(1),&initialize(1),false).is_err());
    assert!(g.admit("client","a",Some(1),&status(1),true).is_err());
    assert!(g.admit("client","a",Some(1),&initialize(1),true).is_ok());
    assert!(g.admit("client","a",Some(2),&status(2),true).is_err(),"initialized required");
    assert!(g.admit("client","a",Some(2),&initialized(),true).is_ok());
    let lease=g.admit("client","a",Some(3),&status(2),true).expect("status");
    token.cancel();assert!(!lease.is_current());
    assert!(g.admit("client","b",Some(1),&initialize(1),true).is_err());
}
#[test]
fn status_only_gate_strict_raw_decoding_rejects_unknown_extra_duplicate_callbacks() {
    let forbidden=["thread/start","turn/start","command/exec","fs/readFile","file/read","capture","account/read","account/login/start","remoteControl/enable","remoteControl/disable","remoteControl/pairing/start","remoteControl/client/list"];
    for method in forbidden {
        let raw=serde_json::to_vec(&json!({"id":1,"method":method,"params":{}})).expect("json");
        assert!(parse_remote_message(&raw).is_err(),"{method}");
        let typed:JSONRPCMessage=serde_json::from_slice(&raw).expect("typed adversarial message");
        assert!(!message_shape_allowed(&typed));
    }
    for raw in [
        r#"{"id":1,"method":"remoteControl/status/read","params":{"path":"/fixture"}}"#,
        r#"{"id":1,"method":"remoteControl/status/read","extra":true}"#,
        r#"{"id":1,"method":"remoteControl/status/read","method":"remoteControl/status/read"}"#,
        r#"{"id":1,"method":"initialize","params":{"clientInfo":{"name":"a","name":"b","version":"1"},"capabilities":{"experimentalApi":true}}}"#,
        r#"{"id":1,"result":{"status":"disabled"}}"#,
        r#"{"id":1,"error":{"code":1,"message":"fixture"}}"#,
        r#"{"id":1,"method":"initialized"}"#,
        r#"{"method":"remoteControl/status/read"}"#,
        r#"{"id":1,"method":"remoteControl/status/read","params":{}}"#,
        r#"{"jsonrpc":"1.0","id":1,"method":"remoteControl/status/read"}"#,
        r#"{"id":1,"method":"remoteControl/status/read"} {}"#,
    ] { assert!(parse_remote_message(raw.as_bytes()).is_err(),"{raw}"); }
    assert!(parse_remote_message(&vec![b' ';MAX_REMOTE_RPC_BYTES+1]).is_err());
    assert!(parse_remote_message(br#"{"jsonrpc":"2.0","id":1,"method":"remoteControl/status/read"}"#).is_ok());
    assert!(parse_remote_message(&serde_json::to_vec(&initialize(1)).expect("json")).is_ok());
}
#[tokio::test]
async fn status_only_gate_request_budget_is_finite() {
    let (_tx,_token,mut g)=setup();ready(&mut g,"a");
    for n in 3..=64 {assert!(g.admit("client","a",Some(n as u64+1),&status(n),true).is_ok());}
    assert!(g.admit("client","a",Some(99),&status(99),true).is_err());
}
fn envelope(stream:&str,seq:u64,message:JSONRPCMessage)->ClientEnvelope {
    ClientEnvelope{client_id:ClientId("client".into()),stream_id:Some(StreamId(stream.into())),seq_id:Some(seq),cursor:None,event:ClientEvent::ClientMessage{message}}
}
fn owner() -> (watch::Sender<codex_login::AuthChangeState>,crate::ConnectionAuth) {
    let (tx,rx)=watch::channel(codex_login::AuthChangeState{generation:1,owner_generation:1});
    (tx,crate::ConnectionAuth::new(rx,1))
}
#[tokio::test]
async fn status_only_gate_actual_tracker_and_owner_bound_consumer_zero_forbidden_forwarding() {
    let (_desired_tx,desired_rx)=watch::channel(RemoteControlDesiredState::enabled(/*persistence_preference*/ None));
    let token=CancellationToken::new();let (_owner_tx,auth)=owner();
    let (out_tx,_out_rx)=mpsc::channel(32);let (events_tx,mut events)=mpsc::channel(32);
    let mut tracker=ClientTracker::new(out_tx,events_tx,&token);
    tracker.auth=Some(auth);tracker.install_status_only_gate(desired_rx);
    tracker.handle_message(envelope("a",1,initialize(1))).await.expect("initialize");
    let bound=match events.recv().await.expect("opened") {TransportEvent::ConnectionOpened{auth:Some(auth),..}=>auth,_=>panic!("bound opened event required")};
    assert!(bound.remote_status_message_allowed(&initialize(1)));
    assert!(matches!(events.recv().await,Some(TransportEvent::IncomingMessage{..})));
    tracker.handle_message(envelope("a",2,initialized())).await.expect("initialized");
    tracker.handle_message(envelope("a",3,status(2))).await.expect("status");
    let mut allowed=0;
    while let Ok(e)=events.try_recv(){if let TransportEvent::IncomingMessage{message,..}=e {assert!(bound.remote_status_message_allowed(&message));allowed+=1;}}
    assert_eq!(allowed,2);
    let forbidden:JSONRPCMessage=serde_json::from_value(json!({"id":55,"method":"command/exec","params":{"command":"fixture"}})).expect("typed adversarial request");
    assert!(!bound.remote_status_message_allowed(&forbidden));
    tracker.handle_message(envelope("a",4,forbidden)).await.expect("rejected");
    let mut forbidden_handler_calls=0;
    while let Ok(e)=events.try_recv(){if let TransportEvent::IncomingMessage{message,..}=e {
        if let JSONRPCMessage::Request(r)=message {if r.method=="command/exec"{forbidden_handler_calls+=1;}}
    }}
    assert_eq!(forbidden_handler_calls,0);assert!(!bound.is_current());
    tracker.shutdown().await;
}
#[tokio::test]
async fn status_only_gate_owner_replacement_rejects_queued_work_before_dispatch() {
    let (_tx,_token,mut g)=setup();let lease=ready(&mut g,"a");
    let (owner_tx,auth)=owner();let bound=auth.with_remote_status(lease);
    let queued=status(3);assert!(bound.remote_status_message_allowed(&queued));
    owner_tx.send_replace(codex_login::AuthChangeState{generation:2,owner_generation:2});
    let mut handler_calls=0;if bound.remote_status_message_allowed(&queued){handler_calls+=1;}
    assert_eq!(handler_calls,0);assert!(!bound.is_current());
}
#[tokio::test]
async fn status_only_gate_default_auth_without_native_lease_is_denied() {
    let (_tx,auth)=owner();assert!(auth.is_current());
    assert!(!auth.remote_status_message_allowed(&initialize(1)));
    assert!(!auth.remote_status_message_allowed(&status(2)));
}
fn chunk(raw:&[u8],stream:&str,seq:u64,index:usize,count:usize,part:&[u8])->ClientEnvelope {
    ClientEnvelope{client_id:ClientId("client".into()),stream_id:Some(StreamId(stream.into())),seq_id:Some(seq),cursor:None,
        event:ClientEvent::ClientMessageChunk{segment_id:index,segment_count:count,message_size_bytes:raw.len(),message_chunk_base64:base64::engine::general_purpose::STANDARD.encode(part)}}
}
#[tokio::test]
async fn status_only_gate_production_reassembly_does_not_bypass_strict_rpc_validation() {
    let mut assembler=ClientSegmentReassembler::default();
    let raw=serde_json::to_vec(&initialize(1)).expect("json");let half=raw.len()/2;
    assert!(matches!(assembler.observe(chunk(&raw,"a",1,0,2,&raw[..half])),ClientSegmentObservation::Pending));
    let full=match assembler.observe(chunk(&raw,"a",1,1,2,&raw[half..])) {ClientSegmentObservation::Forward(e)=>e,_=>panic!("valid assembly")};
    let (_tx,_token,mut gate)=setup();
    match full.event {ClientEvent::ClientMessage{message}=>assert!(gate.admit("client","a",Some(1),&message,true).is_ok()),_=>panic!("RPC")}
    let bad=br#"{"id":1,"method":"remoteControl/status/read","extra":true}"#;let half=bad.len()/2;
    assert!(matches!(assembler.observe(chunk(bad,"b",2,0,2,&bad[..half])),ClientSegmentObservation::Pending));
    assert!(matches!(assembler.observe(chunk(bad,"b",2,1,2,&bad[half..])),ClientSegmentObservation::Dropped));
    let oversize=vec![b'a';MAX_REMOTE_RPC_BYTES+1];
    assert!(matches!(assembler.observe(chunk(&oversize,"c",3,0,1,&oversize)),ClientSegmentObservation::Dropped));
}
#[test]
fn status_only_gate_direct_envelope_decoder_rejects_extra_fields_before_typed_loss() {
    let raw=r#"{"type":"client_message","client_id":"client","stream_id":"a","seq_id":1,"message":{"id":1,"method":"remoteControl/status/read","extra":true}}"#;
    assert!(serde_json::from_str::<ClientEnvelope>(raw).is_err());
}

#[tokio::test]
async fn status_only_gate_old_stream_identity_cannot_reenter_after_reenable() {
    let (tx,_token,mut gate)=setup();
    let old=ready(&mut gate,"old-stream");
    tx.send_replace(RemoteControlDesiredState::Disabled);
    tx.send_replace(RemoteControlDesiredState::enabled(/*persistence_preference*/ None));
    assert!(!old.is_current());
    assert!(gate.admit("client","old-stream",Some(1),&initialize(10),true).is_err(),
        "a revoked stream identity must not be re-admitted in a new generation");
    assert!(ready(&mut gate,"fresh-stream").is_current());
}

#[tokio::test]
async fn status_only_gate_partial_closed_and_reconnected_identities_stay_dead() {
    let (_tx,_token,mut gate)=setup();
    gate.observe_ingress("client","partial",true).expect("first fragment");
    gate.close("client","partial");
    assert!(gate.admit("client","partial",Some(1),&initialize(1),true).is_err());
    gate.observe_ingress("client","older-partial",true).expect("fragment");
    assert!(ready(&mut gate,"new").is_current());
    assert!(gate.admit("client","older-partial",Some(1),&initialize(1),true).is_err());
}
#[tokio::test]
async fn status_only_gate_seen_identity_budget_is_bounded_across_generations() {
    let (tx,_token,mut gate)=setup();
    for n in 0..MAX_SEEN_STREAMS {
        let stream=format!("fragment-{n}");
        gate.observe_ingress("client",&stream,true).expect("bounded identity");
        tx.send_replace(RemoteControlDesiredState::enabled(/*persistence_preference*/ None));
    }
    assert!(gate.observe_ingress("client","overflow",true).is_err());
    assert!(gate.observe_ingress("client","fragment-0",true).is_err());
}


#[tokio::test(start_paused=true)]
async fn status_only_gate_socket_cancel_restart_never_revives_or_renews() {
    let (_tx,_root,mut gate)=setup();
    let first=CancellationToken::new();
    gate.begin_connection(first.clone());
    let old=ready(&mut gate,"old");
    gate.observe_ingress("client","partial",true).expect("first fragment");
    tokio::time::advance(Duration::from_secs(5)).await;
    first.cancel();
    assert!(!old.is_current(),"socket loss invalidates without acquiring tracker locks");
    assert!(gate.observe_ingress("client","partial",true).is_err(),"no fragment buffered after socket cancellation");
    assert!(gate.observe_ingress("client","late-new",true).is_err(),"cancelled socket cannot bind a new identity");
    let second=CancellationToken::new();
    gate.begin_connection(second.clone());
    assert!(gate.admit("client","old",Some(1),&initialize(10),true).is_err());
    assert!(gate.admit("client","partial",Some(1),&initialize(10),true).is_err());
    let fresh=ready(&mut gate,"fresh");
    assert!(fresh.is_current());
    tokio::time::advance(Duration::from_secs(115)).await;
    assert!(!fresh.is_current(),"reconnect must not renew the generation's deadline");
    second.cancel();
}

#[tokio::test]
async fn status_only_gate_actual_tracker_socket_cancel_drops_queued_and_old_streams() {
    let (_desired_tx,desired_rx)=watch::channel(RemoteControlDesiredState::enabled(/*persistence_preference*/ None));
    let token=CancellationToken::new();let (_owner_tx,auth)=owner();
    let (out_tx,_out_rx)=mpsc::channel(32);let (events_tx,mut events)=mpsc::channel(32);
    let mut tracker=ClientTracker::new(out_tx,events_tx,&token);
    tracker.auth=Some(auth);tracker.install_status_only_gate(desired_rx);
    let first=token.child_token();tracker.begin_status_connection(first.clone());
    tracker.handle_message(envelope("old",1,initialize(1))).await.expect("initialization");
    let bound=match events.recv().await.expect("opened") {
        TransportEvent::ConnectionOpened{auth:Some(auth),..}=>auth,_=>panic!("bound connection required"),
    };
    assert!(matches!(events.recv().await,Some(TransportEvent::IncomingMessage{..})));
    first.cancel();
    let mut queued_handler_calls=0;
    if bound.remote_status_message_allowed(&initialize(1)){queued_handler_calls+=1;}
    assert_eq!(queued_handler_calls,0);
    let second=token.child_token();tracker.begin_status_connection(second);
    tracker.handle_message(envelope("old",1,initialize(10))).await.expect("old stream rejected");
    while let Ok(event)=events.try_recv(){
        assert!(!matches!(event,TransportEvent::IncomingMessage{..}),"old initialization must not dispatch");
    }
    tracker.handle_message(envelope("fresh",1,initialize(11))).await.expect("fresh stream");
    let mut fresh_calls=0;
    while let Ok(event)=events.try_recv(){
        if let TransportEvent::IncomingMessage{..}=event{fresh_calls+=1;}
    }
    assert_eq!(fresh_calls,1);
    assert!(!bound.is_current());
    tracker.shutdown().await;
}
