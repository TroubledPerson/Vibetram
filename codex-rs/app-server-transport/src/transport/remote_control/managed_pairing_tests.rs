// SPDX-License-Identifier: Apache-2.0
// Vibetram original offline status-only integration/tests; see MODIFICATIONS.json.
//! Only test builds contain this backend. No sockets/listeners/HTTP/auth service are used.
use super::*;
use std::sync::{Mutex as StdMutex,OnceLock};
use std::sync::atomic::{AtomicUsize,AtomicBool,Ordering};
use serde_json::{Value,json};
use tokio::time::Duration;
use codex_utils_absolute_path::test_support::PathExt;
struct Backend {enrolls:AtomicUsize,pairs:AtomicUsize,hold:AtomicBool,bad:AtomicBool,wake:tokio::sync::Notify}
fn backends()->&'static StdMutex<std::collections::HashMap<String,Arc<Backend>>>{
 static B:OnceLock<StdMutex<std::collections::HashMap<String,Arc<Backend>>>>=OnceLock::new();B.get_or_init(Default::default)
}
fn backend(id:&str)->io::Result<Arc<Backend>>{backends().lock().unwrap().get(id).cloned().ok_or_else(||io::Error::other("missing offline fixture"))}
pub(super) async fn enroll(target:&protocol::RemoteControlTarget,auth:&auth::RemoteControlConnectionAuth,id:&str,name:&str)->io::Result<enroll::RemoteControlEnrollment>{
 let b=backend(id)?;b.enrolls.fetch_add(1,Ordering::SeqCst);
 assert_eq!(name,"Android Status Pilot");assert!(!auth.account_id.is_empty());
 while b.hold.load(Ordering::SeqCst){b.wake.notified().await;}
 Ok(enroll::RemoteControlEnrollment{remote_control_target:target.clone(),account_id:auth.account_id.clone(),environment_id:format!("env-{id}"),server_id:id.to_owned(),server_name:name.to_owned(),remote_control_token:Some("OFFLINE_SYNTHETIC_ONLY".into()),expires_at:Some(time::OffsetDateTime::now_utc()+time::Duration::hours(1)),next_refresh_at:None})
}
pub(super) async fn pair(e:&enroll::RemoteControlEnrollment,manual:bool)->io::Result<Vec<u8>>{
 let b=backend(&e.server_id)?;assert!(manual);b.pairs.fetch_add(1,Ordering::SeqCst);
 let env=if b.bad.load(Ordering::SeqCst){"WRONG_ENVIRONMENT".to_owned()}else{e.environment_id.clone()};
 Ok(serde_json::to_vec(&json!({"pairing_code":"OFFLINE_GENUINE_FIXTURE_RESULT","manual_pairing_code":"FIXTURE-ONLY","server_id":e.server_id,"environment_id":env,"expires_at":"2099-01-01T00:00:00Z"})).unwrap())
}
struct Pilot {home:tempfile::TempDir,handle:RemoteControlHandle,shutdown:CancellationToken,task:tokio::task::JoinHandle<()>,auth:Arc<codex_login::AuthManager>,id:String,b:Arc<Backend>}
impl Pilot {
 async fn new()->Self{let p=Self::signed_out().await;p.sign_in().await;p}
 async fn sign_in(&self){
  let dummy=codex_login::CodexAuth::create_dummy_chatgpt_auth_for_testing();
  let record=codex_login::AuthDotJson{auth_mode:Some(dummy.auth_mode()),tokens:Some(dummy.get_token_data().unwrap()),openai_api_key:None,last_refresh:Some(chrono::Utc::now()),agent_identity:None,personal_access_token:None,bedrock_api_key:None,bedrock_access_keys:None};
  codex_login::save_auth(self.home.path(),&record,codex_login::AuthCredentialsStoreMode::Ephemeral,codex_login::AuthKeyringBackendKind::default()).unwrap();
  assert!(self.auth.reload().await);assert!(self.auth.auth_cached().is_some());assert!(!self.home.path().join("auth.json").exists());
 }
 async fn signed_out()->Self{
  let home=tempfile::TempDir::new().unwrap();let id=format!("fixture191-{}",uuid::Uuid::now_v7());
  let b=Arc::new(Backend{enrolls:AtomicUsize::new(0),pairs:AtomicUsize::new(0),hold:AtomicBool::new(false),bad:AtomicBool::new(false),wake:tokio::sync::Notify::new()});
  backends().lock().unwrap().insert(id.clone(),b.clone());
  websocket::status_session_backend::register_pairing_socket(&id);
  let state=codex_state::StateRuntime::init(codex_state::SqliteConfig::new_for_testing(home.path().abs()),"offline-pairing".into()).await.unwrap();
  let auth=codex_login::AuthManager::shared(home.path().to_path_buf(),false,codex_login::AuthCredentialsStoreMode::Ephemeral,None,None,codex_login::AuthKeyringBackendKind::default(),codex_login::test_support::transport_default_auth_route_config()).await;assert!(auth.auth_cached().is_none());
  let(events,mut rx)=mpsc::channel(32);tokio::spawn(async move{while let Some(event)=rx.recv().await{assert!(!matches!(event,crate::transport::TransportEvent::IncomingMessage{..}));}});
  let shutdown=CancellationToken::new();
  let(task,handle)=start_remote_control(RemoteControlStartConfig{remote_control_url:"https://chatgpt.com/backend-api/".into(),installation_id:id.clone(),policy:RemoteControlPolicy::Allowed},Some(state),auth.clone(),events,shutdown.clone(),None,RemoteControlStartupMode::DisabledEphemeral).await.unwrap();
  Self{home,handle,shutdown,task,auth,id,b}
 }
 async fn pairing(&self)->io::Result<RemoteControlPairingStartResponse>{self.handle.start_pairing(RemoteControlPairingStartParams{manual_code:true},None).await}
 async fn close(self){
  self.handle.disable_ephemeral().await;self.shutdown.cancel();
  tokio::time::timeout(Duration::from_secs(5),self.task).await.unwrap().unwrap();
  assert!(self.handle.enable_ephemeral().is_err());
  assert!(!self.home.path().join("auth.json").exists());
  websocket::status_session_backend::remove_pairing_socket(&self.id);
  backends().lock().unwrap().remove(&self.id);
 }
}
#[tokio::test]
async fn managed_pairing_activation_exact_binding_and_no_restart(){
 let p=Pilot::new().await;assert!(p.pairing().await.is_err());assert_eq!(p.b.enrolls.load(Ordering::SeqCst),0);
 p.handle.enable_ephemeral().unwrap();let at=p.handle.inner.session().desired_state_tx.borrow().activation_time().unwrap();
 let reply=p.pairing().await.unwrap();assert_eq!(reply.environment_id,format!("env-{}",p.id));
 assert_eq!(reply.manual_pairing_code.as_deref(),Some("FIXTURE-ONLY"));assert_eq!(p.handle.status().environment_id.as_deref(),Some(reply.environment_id.as_str()));
 assert_eq!(p.b.enrolls.load(Ordering::SeqCst),1);assert_eq!(p.b.pairs.load(Ordering::SeqCst),1);
 p.handle.enable_ephemeral().unwrap();assert_eq!(p.handle.inner.session().desired_state_tx.borrow().activation_time(),Some(at));p.close().await;
}
#[tokio::test]
async fn managed_pairing_wrong_backend_identity_rejected(){let p=Pilot::new().await;p.b.bad.store(true,Ordering::SeqCst);p.handle.enable_ephemeral().unwrap();assert!(p.pairing().await.is_err());p.close().await;}
#[tokio::test]
async fn managed_pairing_cancel_during_enrollment_no_late_result(){cancel_enrollment(0).await;}
#[tokio::test]
async fn managed_pairing_stop_during_enrollment(){cancel_enrollment(1).await;}
#[tokio::test]
async fn managed_pairing_owner_change_during_enrollment(){cancel_enrollment(2).await;}
async fn cancel_enrollment(mode:u8){
 let p=Pilot::new().await;p.b.hold.store(true,Ordering::SeqCst);p.handle.enable_ephemeral().unwrap();
 {let operation=p.pairing();tokio::pin!(operation);
 tokio::select!{biased;_=tokio::time::sleep(Duration::from_millis(30))=>{},r=&mut operation=>panic!("early result {r:?}")};
 assert_eq!(p.b.enrolls.load(Ordering::SeqCst),1);match mode{0=>p.shutdown.cancel(),1=>{p.handle.disable_ephemeral().await;},_=>{p.auth.logout().await.unwrap();}}assert!(operation.await.is_err());}
 p.b.hold.store(false,Ordering::SeqCst);p.b.wake.notify_waiters();assert_eq!(p.b.pairs.load(Ordering::SeqCst),0);p.close().await;
}
#[tokio::test]
async fn managed_pairing_auth_owner_change_rejects_stale_session(){
 let p=Pilot::new().await;p.handle.enable_ephemeral().unwrap();let old=p.handle.inner.session();
 p.auth.logout().await.unwrap();assert!(!old.auth_manager.owner.is_current());assert!(old.auth_manager.ensure_current().is_err());p.close().await;
}
#[tokio::test]
async fn managed_pairing_idle_expiry_before_first_enrollment(){
 let p=Pilot::new().await;tokio::time::pause();p.handle.enable_ephemeral().unwrap();tokio::time::advance(Duration::from_secs(120)).await;
 assert!(p.pairing().await.is_err());assert_eq!(p.b.enrolls.load(Ordering::SeqCst),0);p.close().await;
}
#[test]
fn managed_pairing_metadata_and_duplicate_schema(){
 let raw=br#"{"x":1,"x":2}"#;assert!(status_only_gate::decode_unique_object(raw).is_err());
 let result=codex_app_server_protocol::InitializeResponse{user_agent:"personal".into(),codex_home:std::env::temp_dir().abs(),platform_family:"unix".into(),platform_os:"android".into()};
 let envelope=protocol::ServerEnvelope{event:protocol::ServerEvent::ServerMessage{message:Box::new(crate::outgoing_message::OutgoingMessage::Response(crate::outgoing_message::OutgoingResponse{id:codex_app_server_protocol::RequestId::Integer(1),result:Box::new(result.into())}))},client_id:protocol::ClientId("c".into()),stream_id:protocol::StreamId("s".into()),seq_id:1};let wire=pilot_metadata::wire(&envelope).unwrap();
 assert!(!wire.contains("personal"));assert!(!wire.contains("private"));let v:Value=serde_json::from_str(&wire).unwrap();assert_eq!(v["message"]["result"]["codexHome"],"/");
}
// Fixed driver for the existing Java managed-auth parser; the auth replies are synthetic,
// while enable/enrollment/pairing/disable execute the real production controller.
#[tokio::test(flavor="multi_thread",worker_threads=2)]
#[ignore]
async fn managed_pairing_stdio_driver(){
 use std::io::{BufRead,Write};
 assert_eq!(std::env::var("OFFLINE_191_DRIVER").as_deref(),Ok("1"));
 let mut pilot=Some(Pilot::signed_out().await);let mut signed_in=false;
 let phone=std::env::var("OFFLINE_191_PHONE").as_deref()==Ok("1");
 let mut activated_at=None;let mut observation=None;
 let stdin=std::io::stdin();
 for line in stdin.lock().lines(){
  let line=line.unwrap();assert!(line.len()<=16384);let v:Value=serde_json::from_str(&line).unwrap();
  let id=v["id"].clone();let method=v["method"].as_str().unwrap();
  let result=match method {
   "initialize"=>Some(json!({"codexHome":std::env::var("CODEX_HOME").unwrap(),"platformOs":"android"})),
   "initialized"=>None,
   "account/read"=>Some(json!({"account":null})),
   "account/login/start"=>{assert!(!signed_in);pilot.as_ref().unwrap().sign_in().await;signed_in=true;Some(json!({"type":"chatgptDeviceCode","loginId":"00000000-0000-4000-8000-000000000191","verificationUrl":"https://auth.openai.com/codex/device","userCode":"FIXTURE-ONLY"}))},
   "remoteControl/enable"=>{assert!(signed_in);let p=pilot.take().unwrap();if std::env::var("OFFLINE_191_BAD_PAIR").as_deref()==Ok("1"){p.b.bad.store(true,Ordering::SeqCst);}p.handle.enable_ephemeral().unwrap();
    if phone {let at=p.handle.inner.session().desired_state_tx.borrow().activation_time().unwrap();assert!(activated_at.is_none());activated_at=Some(at);observation=Some(PhoneExpiryObservation::start(p.shutdown.clone()).await);}
    let r=serde_json::to_value(p.handle.status()).unwrap();pilot=Some(p);Some(r)},
   "remoteControl/pairing/start"=>{let r=pilot.as_ref().unwrap().pairing().await.unwrap();Some(serde_json::to_value(r).unwrap())},
   "remoteControl/status/read"=>{let p=pilot.as_ref().unwrap();Some(serde_json::to_value(p.handle.status()).unwrap())},
   "offlineTest/expiry/read"=>{assert!(phone);let p=pilot.as_ref().unwrap();Some(observation.as_mut().unwrap().evidence(&p.handle,activated_at.unwrap()).await.unwrap())},
   "remoteControl/disable"=>{let p=pilot.take().unwrap();p.handle.disable_ephemeral().await;let r=serde_json::to_value(p.handle.status()).unwrap();p.close().await;Some(r)},
   _=>panic!("forbidden driver RPC"),
  };
  if let Some(result)=result{println!("{}",json!({"id":id,"result":result}));std::io::stdout().flush().unwrap();}
  if method=="account/login/start"{println!("{}",json!({"method":"account/login/completed","params":{"loginId":"00000000-0000-4000-8000-000000000191","success":true}}));std::io::stdout().flush().unwrap();}
 }
 if let Some(p)=pilot{p.close().await;}
}

#[tokio::test]
async fn managed_pairing_shutdown_is_not_server_withdrawal(){
 let p=Pilot::new().await;p.handle.enable_ephemeral().unwrap();p.pairing().await.unwrap();
 let session=p.handle.inner.session();let auth=auth::load_remote_control_auth(&session.auth_manager).await.unwrap();
 let target=protocol::normalize_remote_control_url("https://chatgpt.com/backend-api/").unwrap();
 let db=session.state_db.as_deref().unwrap();
 assert!(enroll::load_persisted_remote_control_enrollment(Some(db),&target,&auth.account_id,None).await.unwrap().is_some());
 p.handle.disable_ephemeral().await;
 // Local disable did not remove the synthetic enrollment metadata. No remote delete
 // route is invented; client revoke and host deletion are distinct operations.
 assert!(enroll::load_persisted_remote_control_enrollment(Some(db),&target,&auth.account_id,None).await.unwrap().is_some());
 assert_eq!(p.b.enrolls.load(Ordering::SeqCst),1);assert!(p.pairing().await.is_err());
 p.close().await;
}
#[tokio::test]
async fn managed_pairing_strict_backend_response_contract(){
 let p=Pilot::new().await;p.handle.enable_ephemeral().unwrap();p.pairing().await.unwrap();
 let e=p.handle.inner.session().current_enrollment.snapshot().unwrap();
 let good=pair(&e,true).await.unwrap();assert!(e.decode_pilot_pairing(&good).is_ok());
 let v:Value=serde_json::from_slice(&good).unwrap();
 for key in ["server_id","environment_id","expires_at","pairing_code"]{
  let mut bad=v.clone();bad[key]=if key=="expires_at"{json!("2000-01-01T00:00:00Z")}else{json!("")};
  assert!(e.decode_pilot_pairing(&serde_json::to_vec(&bad).unwrap()).is_err());
 }
 let mut extra=v.clone();extra["unexpected"]=json!(true);assert!(e.decode_pilot_pairing(&serde_json::to_vec(&extra).unwrap()).is_err());
 assert!(e.decode_pilot_pairing(br#"{"server_id":"a","server_id":"b"}"#).is_err());
 assert!(e.decode_pilot_pairing(&vec![b' ';4097]).is_err());p.close().await;
}

#[tokio::test]
async fn managed_pairing_first_sign_in_stays_off_until_explicit_activation(){
 let p=Pilot::signed_out().await;assert_eq!(p.handle.status().status,RemoteControlConnectionStatus::Disabled);
 p.sign_in().await;tokio::task::yield_now().await;
 assert!(!p.shutdown.is_cancelled());assert_eq!(p.handle.status().status,RemoteControlConnectionStatus::Disabled);
 assert!(p.pairing().await.is_err());assert_eq!(p.b.enrolls.load(Ordering::SeqCst),0);p.close().await;
}

#[tokio::test(flavor="current_thread")]
async fn managed_pairing_stop_before_first_login_cannot_revive(){
 let p=Pilot::signed_out().await;p.handle.disable_ephemeral().await;p.sign_in().await;
 assert!(p.handle.enable_ephemeral().is_err());assert!(p.shutdown.is_cancelled());
 assert_eq!(p.b.enrolls.load(Ordering::SeqCst),0);p.close().await;
}
#[tokio::test(flavor="current_thread")]
async fn managed_pairing_pre_auth_activation_cannot_transfer_to_new_owner(){
 let p=Pilot::signed_out().await;p.handle.enable_ephemeral().unwrap();p.sign_in().await;
 assert!(p.handle.enable_ephemeral().is_err());assert!(p.shutdown.is_cancelled());
 assert_eq!(p.b.enrolls.load(Ordering::SeqCst),0);p.close().await;
}
#[tokio::test]
async fn managed_pairing_missing_fixture_never_falls_through_to_network(){
 let p=Pilot::new().await;websocket::status_session_backend::remove_pairing_socket(&p.id);
 p.handle.enable_ephemeral().unwrap();tokio::time::timeout(Duration::from_secs(5),p.shutdown.cancelled()).await.unwrap();
 assert_eq!(p.b.enrolls.load(Ordering::SeqCst),0);assert!(p.pairing().await.is_err());p.close().await;
}

// Offline local telemetry only. This is not a remotely admitted RPC or a network adapter.
struct PhoneExpiryObservation { closed:tokio::sync::watch::Receiver<Option<tokio::time::Instant>> }
impl PhoneExpiryObservation {
 async fn start(shutdown:CancellationToken)->Self {
  let(tx,closed)=tokio::sync::watch::channel(None);
  let(ready,started)=tokio::sync::oneshot::channel();
  tokio::spawn(async move {let _=ready.send(());shutdown.cancelled().await;tx.send_replace(Some(tokio::time::Instant::now()));});
  started.await.unwrap();Self{closed}
 }
 async fn evidence(&mut self,handle:&RemoteControlHandle,at:tokio::time::Instant)->io::Result<Value> {
  let deadline=at+Duration::from_secs(120);
  if tokio::time::Instant::now()<deadline {return Err(io::Error::other("offline observer before deadline"));}
  let closed=tokio::time::timeout(Duration::from_secs(3),async {
   loop {if let Some(at)=*self.closed.borrow_and_update(){return Ok::<_,io::Error>(at);}self.closed.changed().await.map_err(|_|io::Error::other("offline observer closed"))?;}
  }).await.map_err(|_|io::Error::other("offline native expiry not observed"))??;
  if closed<deadline || handle.enable_ephemeral().is_ok(){return Err(io::Error::other("offline early closure or late enable"));}
  Ok(json!({"nativeExpired":true,"elapsedMs":(closed-at).as_millis() as u64,"lateEnableRejected":true,"active":false}))
 }
}
#[tokio::test]
async fn managed_pairing_phone_expiry_observer_boundary(){
 let p=Pilot::new().await;tokio::time::pause();p.handle.enable_ephemeral().unwrap();
 let at=p.handle.inner.session().desired_state_tx.borrow().activation_time().unwrap();
 let mut o=PhoneExpiryObservation::start(p.shutdown.clone()).await;
 assert!(o.evidence(&p.handle,at).await.is_err());
 tokio::time::advance(Duration::from_millis(119999)).await;assert!(o.evidence(&p.handle,at).await.is_err());
 tokio::time::advance(Duration::from_millis(1)).await;tokio::task::yield_now().await;
 let v=o.evidence(&p.handle,at).await.unwrap();assert_eq!(v,json!({"nativeExpired":true,"elapsedMs":120000,"lateEnableRejected":true,"active":false}));p.close().await;
}
#[tokio::test]
async fn managed_pairing_phone_early_shutdown_is_not_expiry(){
 let p=Pilot::new().await;tokio::time::pause();p.handle.enable_ephemeral().unwrap();
 let at=p.handle.inner.session().desired_state_tx.borrow().activation_time().unwrap();let mut o=PhoneExpiryObservation::start(p.shutdown.clone()).await;
 p.shutdown.cancel();tokio::task::yield_now().await;tokio::time::advance(Duration::from_secs(120)).await;
 assert!(o.evidence(&p.handle,at).await.is_err());p.close().await;
}
