// SPDX-License-Identifier: Apache-2.0
// Vibetram original offline status-only integration/tests; see MODIFICATIONS.json.
//! Test-only backend/duplex. The production controller, ingress, dispatcher gate and writer run unchanged.
use super::*;
use super::super::{start_remote_control, RemoteControlStartConfig, RemoteControlPolicy, RemoteControlStartupMode};
use crate::outgoing_message::{OutgoingMessage, OutgoingResponse, QueuedOutgoingMessage};
use crate::transport::TransportEvent;
use codex_app_server_protocol::{InitializeResponse, RemoteControlStatusReadResponse, JSONRPCMessage};
use codex_utils_absolute_path::test_support::PathExt;
use std::sync::{OnceLock, Mutex as StdMutex};
use std::sync::atomic::{AtomicUsize, AtomicBool, Ordering};
use std::pin::Pin;
use std::task::{Context, Poll};
use futures::{Stream, Sink};
use tokio::time::{Duration, Instant};

#[path = "../../../../app-server/src/connection_rpc_gate.rs"]
mod dispatcher_gate;

type SocketMap=HashMap<String,Box<dyn StatusSocket>>;
fn sockets()->&'static StdMutex<SocketMap> {
    static MAP:OnceLock<StdMutex<SocketMap>>=OnceLock::new();
    MAP.get_or_init(||StdMutex::new(HashMap::new()))
}
pub(super) fn take(id:&str)->Option<Box<dyn StatusSocket>> { sockets().lock().unwrap().remove(id) }
struct Duplex {
    incoming:mpsc::Receiver<Result<tungstenite::Message,tungstenite::Error>>,
    backend:mpsc::Sender<Result<tungstenite::Message,tungstenite::Error>>,
    replies:Arc<AtomicUsize>,
}
impl Stream for Duplex {
    type Item=Result<tungstenite::Message,tungstenite::Error>;
    fn poll_next(mut self:Pin<&mut Self>,cx:&mut Context<'_>)->Poll<Option<Self::Item>> {
        self.incoming.poll_recv(cx)
    }
}
impl Sink<tungstenite::Message> for Duplex {
    type Error=tungstenite::Error;
    fn poll_ready(self:Pin<&mut Self>,_:&mut Context<'_>)->Poll<Result<(),Self::Error>> {Poll::Ready(Ok(()))}
    fn start_send(self:Pin<&mut Self>,item:tungstenite::Message)->Result<(),Self::Error> {
        match item {
            tungstenite::Message::Ping(payload)=>{
                self.backend.try_send(Ok(tungstenite::Message::Pong(payload)))
                    .map_err(|_|tungstenite::Error::ConnectionClosed)?;
            }
            tungstenite::Message::Text(text)=>{
                assert!(text.len()<=super::super::status_only_gate::MAX_REMOTE_WIRE_BYTES);
                let v:serde_json::Value=serde_json::from_str(&text).unwrap();
                if v["type"]=="server_message" {
                    if v["message"]["result"].get("codexHome").is_some(){assert_eq!(v["message"]["result"]["codexHome"],"/");assert_eq!(v["message"]["result"]["userAgent"],"Codex Status Pilot");}
                    self.replies.fetch_add(1,Ordering::SeqCst);
                }
                let ack=serde_json::json!({"type":"ack","client_id":v["client_id"],
                    "stream_id":v["stream_id"],"seq_id":v["seq_id"]});
                self.backend.try_send(Ok(tungstenite::Message::Text(ack.to_string().into())))
                    .map_err(|_|tungstenite::Error::ConnectionClosed)?;
            }
            _=>return Err(tungstenite::Error::ConnectionClosed),
        }
        Ok(())
    }
    fn poll_flush(self:Pin<&mut Self>,_:&mut Context<'_>)->Poll<Result<(),Self::Error>> {Poll::Ready(Ok(()))}
    fn poll_close(self:Pin<&mut Self>,_:&mut Context<'_>)->Poll<Result<(),Self::Error>> {Poll::Ready(Ok(()))}
}
enum Mode { Stop, Forbidden, Reconnect, Realtime }
async fn exercise(mode:Mode) {
    let home=tempfile::TempDir::new().unwrap();
    let state=codex_state::StateRuntime::init(
        codex_state::SqliteConfig::new_for_testing(home.path().abs()),"offline-fixture".into()).await.unwrap();
    // Fixed in-memory test authentication, never loaded from the owner's accounts or persisted.
    let auth=codex_core::test_support::auth_manager_from_auth(
        codex_login::CodexAuth::create_dummy_chatgpt_auth_for_testing());
    let id=format!("offline-fixture-{}",uuid::Uuid::now_v7());
    let(tx,rx)=mpsc::channel(32);let replies=Arc::new(AtomicUsize::new(0));
    assert!(sockets().lock().unwrap().insert(id.clone(),Box::new(Duplex {
        incoming:rx,backend:tx.clone(),replies:replies.clone(),
    })).is_none());
    let(events,mut received)=mpsc::channel(32);let shutdown=CancellationToken::new();
    let(task,handle)=start_remote_control(RemoteControlStartConfig {
        remote_control_url:"offline://never-network".into(),installation_id:id.clone(),
        policy:RemoteControlPolicy::Allowed,
    },Some(state),auth,events,shutdown.clone(),None,RemoteControlStartupMode::DisabledEphemeral).await.unwrap();
    assert_eq!(handle.status().status,RemoteControlConnectionStatus::Disabled);
    let home_path=home.path().abs();let bodies=Arc::new(AtomicUsize::new(0));let forbidden=Arc::new(AtomicUsize::new(0));
    let body_count=bodies.clone();let forbidden_count=forbidden.clone();let close=shutdown.clone();
    let backend=tokio::spawn(async move {
        let mut connections=HashMap::new();
        loop {
            let event=tokio::select! {biased;_=close.cancelled()=>break,event=received.recv()=>event};
            match event {
                Some(TransportEvent::ConnectionOpened {connection_id,auth,writer,..})=>{
                    let mut gate=dispatcher_gate::ConnectionRpcGate::new();gate.auth=auth;
                    connections.insert(connection_id,(gate,writer));
                }
                Some(TransportEvent::IncomingMessage {connection_id,message})=>{
                    let(gate,writer)=connections.get(&connection_id).unwrap();
                    if !gate.allows_remote_message(&message) {continue;}
                    let result=match message {
                        JSONRPCMessage::Request(r) if r.method=="initialize"=>{
                            Some((r.id,InitializeResponse{user_agent:"offline fixture".into(),
                                codex_home:home_path.clone(),platform_family:"offline".into(),platform_os:"fixture".into()}.into()))
                        }
                        JSONRPCMessage::Request(r) if r.method=="remoteControl/status/read"=>{
                            Some((r.id,RemoteControlStatusReadResponse{status:RemoteControlConnectionStatus::Connected,
                                server_name:"offline fixture".into(),installation_id:"offline-fixture".into(),environment_id:None}.into()))
                        }
                        JSONRPCMessage::Notification(n) if n.method=="initialized"=>None,
                        _=>{forbidden_count.fetch_add(1,Ordering::SeqCst);None}
                    };
                    if let Some((id,result))=result {
                        gate.run(async {
                            body_count.fetch_add(1,Ordering::SeqCst);
                            writer.send(QueuedOutgoingMessage::new(OutgoingMessage::Response(OutgoingResponse{
                                id,result:Box::new(result),
                            }))).await.unwrap();
                        }).await;
                    }
                }
                Some(TransportEvent::ConnectionClosed{connection_id})=>{
                    if let Some((gate,_))=connections.remove(&connection_id){gate.shutdown().await;}
                }
                None=>break,
                _=>panic!("unexpected fixture transport event"),
            }
        }
        for(_, (gate,_))in connections {gate.shutdown().await;}
    });
    handle.enable_ephemeral().unwrap();
    let session=handle.inner.session();
    let activation=session.desired_state_tx.borrow().activation_time().unwrap();
    assert_eq!(sockets().lock().unwrap().len(),0);
    for(seq,message)in [
        serde_json::json!({"id":1,"method":"initialize","params":{
            "clientInfo":{"name":"offline","version":"1"},"capabilities":{"experimentalApi":true}}}),
        serde_json::json!({"method":"initialized"}),
        serde_json::json!({"id":2,"method":"remoteControl/status/read"}),
    ].into_iter().enumerate() {
        tx.send(Ok(tungstenite::Message::Text(serde_json::json!({
            "type":"client_message","client_id":"fixture","stream_id":"fixture-stream",
            "seq_id":seq+1,"message":message,
        }).to_string().into()))).await.unwrap();
    }
    tokio::time::timeout(Duration::from_secs(10),async{
        while replies.load(Ordering::SeqCst)<2 {tokio::task::yield_now().await;}
    }).await.unwrap();
    assert_eq!(bodies.load(Ordering::SeqCst),2);
    assert_eq!(forbidden.load(Ordering::SeqCst),0);
    handle.enable_ephemeral().unwrap();
    assert_eq!(session.desired_state_tx.borrow().activation_time(),Some(activation));
    let stopped=Arc::new(AtomicBool::new(false));
    match mode {
        Mode::Stop=>{handle.disable_ephemeral().await;}
        Mode::Forbidden=>{
            tx.send(Ok(tungstenite::Message::Text(serde_json::json!({
                "type":"client_message","client_id":"fixture","stream_id":"fixture-stream",
                "seq_id":4,"message":{"id":3,"method":"file/read","params":{}}
            }).to_string().into()))).await.unwrap();
        }
        Mode::Reconnect=>{tx.send(Err(tungstenite::Error::ConnectionClosed)).await.unwrap();}
        Mode::Realtime=>{
            // Only the app's fixed STOP line is accepted. No shell, paths or arbitrary commands.
            let cancel=shutdown.clone();let stop=stopped.clone();
            std::thread::spawn(move||{
                use std::io::Read;
                let mut line=[0u8;5];
                if std::io::stdin().read_exact(&mut line).is_ok() {
                    stop.store(true,Ordering::SeqCst);
                    cancel.cancel();
                    assert_eq!(&line,b"STOP\n");
                }
            });
            println!("ACTUAL_OFFLINE_SESSION_ACTIVE_120_SECONDS");
        }
    }
    let wait=if matches!(mode,Mode::Realtime){125}else{5};
    tokio::time::timeout(Duration::from_secs(wait),shutdown.cancelled()).await.unwrap();
    if matches!(mode,Mode::Realtime)&&!stopped.load(Ordering::SeqCst) {
        assert!(Instant::now()-activation>=Duration::from_secs(120));
    }
    assert!(handle.enable_ephemeral().is_err());
    tokio::time::timeout(Duration::from_secs(5),task).await.unwrap().unwrap();
    tokio::time::timeout(Duration::from_secs(5),backend).await.unwrap().unwrap();
    assert_eq!(forbidden.load(Ordering::SeqCst),0);
    assert_eq!(replies.load(Ordering::SeqCst),2);
    assert!(sockets().lock().unwrap().is_empty());
    println!("ACTUAL_OFFLINE_SESSION_CLOSED_LATE_ENABLE_REJECTED");
}
#[tokio::test]
async fn status_session_whole_controller_stop() {exercise(Mode::Stop).await;}
#[tokio::test]
async fn status_session_whole_controller_forbidden_request() {exercise(Mode::Forbidden).await;}
#[tokio::test]
async fn status_session_whole_controller_reconnect_failure_closes() {exercise(Mode::Reconnect).await;}
pub(super) async fn realtime() {exercise(Mode::Realtime).await;}

#[tokio::test(flavor="current_thread")]
async fn status_session_stop_before_supervisor_poll_cannot_reactivate() {
    let home=tempfile::TempDir::new().unwrap();
    let state=codex_state::StateRuntime::init(
        codex_state::SqliteConfig::new_for_testing(home.path().abs()),"offline-fixture".into()).await.unwrap();
    let auth=codex_core::test_support::auth_manager_from_auth(
        codex_login::CodexAuth::create_dummy_chatgpt_auth_for_testing());
    let(events,_received)=mpsc::channel(32);let shutdown=CancellationToken::new();
    let(task,handle)=start_remote_control(RemoteControlStartConfig {
        remote_control_url:"offline://never-network".into(),installation_id:"offline-no-poll".into(),
        policy:RemoteControlPolicy::Allowed,
    },Some(state),auth,events,shutdown.clone(),None,RemoteControlStartupMode::DisabledEphemeral).await.unwrap();
    // No yielding operation occurs between activation, Stop and attempted renewal.
    handle.enable_ephemeral().unwrap();
    handle.disable_ephemeral().await;
    assert!(handle.inner.session().shutdown_token.is_cancelled());
    assert!(handle.enable_ephemeral().is_err());
    shutdown.cancel();
    tokio::time::timeout(Duration::from_secs(5),task).await.unwrap().unwrap();
}

pub(in super::super) fn register_pairing_socket(id:&str) {
    let(tx,rx)=mpsc::channel(32);
    // Retain a sender: fixture stays inert until its production cancellation token closes.
    assert!(sockets().lock().unwrap().insert(id.to_owned(),Box::new(Duplex {incoming:rx,backend:tx,replies:Arc::new(AtomicUsize::new(0))})).is_none());
}

pub(in super::super) fn remove_pairing_socket(id:&str) {sockets().lock().unwrap().remove(id);}
