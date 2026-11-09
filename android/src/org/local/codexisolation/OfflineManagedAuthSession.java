package org.local.codexisolation;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Arrays;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.TimeoutException;
import java.util.concurrent.atomic.AtomicBoolean;

/** One bounded parent-UID device-code attempt; native error text never reaches the UI. */
final class OfflineManagedAuthSession {
    static final int MAX_FRAME=16*1024, MAX_STDERR=64*1024, MAX_FRAMES=16;
    private static final String VERIFY_URL="https://auth.openai.com/codex/device";
    private static final byte[] INIT=("{\"id\":1,\"method\":\"initialize\",\"params\":{\"clientInfo\":{\"name\":\"android-core-test\",\"title\":\"Codex Core Test\",\"version\":\"0.1\"}}}\n").getBytes(StandardCharsets.UTF_8);
    private static final byte[] INITIALIZED="{\"method\":\"initialized\"}\n".getBytes(StandardCharsets.UTF_8);
    private static final byte[] ACCOUNT_READ_1="{\"id\":2,\"method\":\"account/read\",\"params\":{\"refreshToken\":false}}\n".getBytes(StandardCharsets.UTF_8);
    private static final byte[] START="{\"id\":3,\"method\":\"account/login/start\",\"params\":{\"type\":\"chatgptDeviceCode\"}}\n".getBytes(StandardCharsets.UTF_8);

    interface PromptSink { void show(String verifiedUrl,String userCode); }
    enum Outcome { OFFLINE_PREFLIGHT, SIGNED_IN_EPHEMERAL }
    static final class GateException extends Exception {
        final String code;
        GateException(String code){super(code);this.code=code;}
    }
    private final OfflineAppServerAdapter.ProcessFactory factory;
    private final AtomicBoolean started=new AtomicBoolean(), cancelled=new AtomicBoolean();
    private volatile Process child;
    private volatile String stage="NOT_STARTED";
    private int frames, notices;
    OfflineManagedAuthSession(OfflineAppServerAdapter.ProcessFactory factory){this.factory=factory;}
    String stage(){return stage;}
    int noticeCount(){return notices;}
    void cancel(){
        cancelled.set(true);
        Process p=child;
        if(p!=null){try{p.destroyForcibly();}catch(RuntimeException ignored){/* run() reports failed cleanup. */}}
    }

    interface AuthenticatedContinuation {void run(AuthenticatedControl control) throws Exception;}
    // This stage has no live adapter: same existing authentication parser, fake factory only.
    Outcome runOfflinePairing(File filesDir,File binary,PromptSink prompt,AuthenticatedContinuation next) throws GateException {
        require(factory!=OfflineAppServerAdapter.SYSTEM,"LIVE_ADAPTER_DISABLED");
        require(next!=null,"CONTINUATION_REQUIRED");
        continuation=next;return run(filesDir,binary,prompt);
    }
    private AuthenticatedContinuation continuation;
    private long generation;
    final class AuthenticatedControl {
        private final InputStream in; private final OutputStream out; private final ExecutorService readers;
        private final long ticket; private boolean active=true,enabled=false,paired=false;private long deadline;private int requestId=20;
        private String environment,installation;
        AuthenticatedControl(InputStream in,OutputStream out,ExecutorService readers){this.in=in;this.out=out;this.readers=readers;ticket=++generation;}
        private void current() throws GateException {require(active&&ticket==generation&&!cancelled.get(),"STALE_AUTH_SESSION");require(!enabled||System.nanoTime()<deadline,"PILOT_EXPIRED");}
        private synchronized Map<?,?> rpc(String method,String params) throws Exception {
            current();require(enabled,"ACTIVATION_REQUIRED");
            require(method.equals("remoteControl/enable")||method.equals("remoteControl/pairing/start")||method.equals("remoteControl/status/read")||method.equals("remoteControl/disable"),"LOCAL_RPC_BLOCKED");
            int id=requestId++;send(out,("{\"id\":"+id+",\"method\":\""+method+"\",\"params\":"+params+"}\n").getBytes(StandardCharsets.UTF_8));
            Map<?,?> response=reply(in,readers,id,5);require(response.size()==2&&response.containsKey("id")&&response.containsKey("result"),"PILOT_REPLY_INVALID");Map<?,?> value=object(response.get("result"),"PILOT_REPLY_INVALID");current();return value;
        }
        synchronized void activate() throws Exception {
            current();require(!enabled,"DUPLICATE_ACTIVATION");
            deadline=System.nanoTime()+TimeUnit.SECONDS.toNanos(120);enabled=true;
            Map<?,?> result=rpc("remoteControl/enable","{\"ephemeral\":true}");
            require(statusShape(result)&&("connecting".equals(result.get("status"))||"connected".equals(result.get("status"))),"ENABLE_REPLY_INVALID");installation=string(result.get("installationId"),"ENABLE_REPLY_INVALID");require(!installation.isEmpty(),"ENABLE_REPLY_INVALID");
        }
        synchronized void pair() throws Exception {
            current();require(enabled&&!paired,"PAIRING_NOT_AVAILABLE");paired=true;
            Map<?,?> p=rpc("remoteControl/pairing/start","{\"manualCode\":true}");
            require(p.size()==4&&p.containsKey("pairingCode")&&p.containsKey("manualPairingCode")&&p.containsKey("environmentId")&&p.containsKey("expiresAt"),"PAIRING_SCHEMA_INVALID");
            require(p.get("pairingCode") instanceof String&&((String)p.get("pairingCode")).length()<=256,"PAIRING_SCHEMA_INVALID");
            require(p.get("manualPairingCode")==null||p.get("manualPairingCode") instanceof String&&((String)p.get("manualPairingCode")).length()<=64,"PAIRING_SCHEMA_INVALID");
            require(p.get("expiresAt") instanceof BigDecimal&&((BigDecimal)p.get("expiresAt")).scale()<=0&&((BigDecimal)p.get("expiresAt")).compareTo(BigDecimal.valueOf(System.currentTimeMillis()/1000))>0,"PAIRING_EXPIRED");
            environment=string(p.get("environmentId"),"PAIRING_SCHEMA_INVALID");require(!environment.isEmpty()&&environment.length()<=128,"PAIRING_SCHEMA_INVALID");
            Map<?,?> status=rpc("remoteControl/status/read","null");
            require(statusShape(status)&&"connected".equals(status.get("status"))&&environment.equals(status.get("environmentId"))&&installation.equals(status.get("installationId")),"PAIRING_BINDING_MISMATCH");
        }
        synchronized long activationDeadlineNanos(){return deadline;}
        synchronized String boundIdentity() throws GateException {current();require(paired&&environment!=null,"PAIRING_NOT_AVAILABLE");return installation;}
        // Fixed offline-child observation only, after authorization expires. It cannot enable,
        // pair, dispatch remote work, or bypass the production admission/write gates.
        synchronized long observeNaturalExpiry() throws Exception {
            require(active&&ticket==generation&&!cancelled.get()&&enabled&&paired,"STALE_AUTH_SESSION");
            require(System.nanoTime()>=deadline,"EXPIRY_OBSERVATION_EARLY");
            int id=requestId++;send(out,("{\"id\":"+id+",\"method\":\"offlineTest/expiry/read\",\"params\":null}\n").getBytes(StandardCharsets.UTF_8));
            Map<?,?> response=reply(in,readers,id,5);require(response.size()==2&&response.containsKey("id")&&response.containsKey("result"),"EXPIRY_REPLY_INVALID");
            Map<?,?> v=object(response.get("result"),"EXPIRY_REPLY_INVALID");
            require(v.size()==4&&Boolean.TRUE.equals(v.get("nativeExpired"))&&Boolean.TRUE.equals(v.get("lateEnableRejected"))&&Boolean.FALSE.equals(v.get("active")),"NATIVE_EXPIRY_UNCONFIRMED");
            require(v.get("elapsedMs") instanceof BigDecimal&&((BigDecimal)v.get("elapsedMs")).scale()<=0,"EXPIRY_TIME_INVALID");
            long elapsed=((BigDecimal)v.get("elapsedMs")).longValueExact();require(elapsed>=120000&&elapsed<=130000,"EXPIRY_TIME_INVALID");
            require(active&&ticket==generation&&!cancelled.get(),"STALE_AUTH_SESSION");invalidate();return elapsed;
        }
        synchronized void finishLocalSession() throws Exception {
            current();try{if(enabled){Map<?,?> status=rpc("remoteControl/disable","{\"ephemeral\":true}");require(statusShape(status)&&"disabled".equals(status.get("status")),"DISABLE_REPLY_INVALID");}}finally{invalidate();}
        }
        private boolean statusShape(Map<?,?> s){return s.size()==4&&s.get("status") instanceof String&&s.get("serverName") instanceof String&&((String)s.get("serverName")).length()<=128&&s.get("installationId") instanceof String&&((String)s.get("installationId")).length()<=128&&s.containsKey("environmentId")&&(s.get("environmentId")==null||s.get("environmentId") instanceof String&&((String)s.get("environmentId")).length()<=128);}
        synchronized void invalidate(){active=false;environment=null;installation=null;generation++;}
    }

    Outcome run(File filesDir,File binary,PromptSink prompt) throws GateException {
        return runSession(filesDir,binary,prompt,false);
    }
    Outcome runOfflinePreflight(File filesDir,File binary) throws GateException {
        return runSession(filesDir,binary,(url,code)->{},true);
    }
    private Outcome runSession(File filesDir,File binary,PromptSink prompt,boolean offlinePreflight) throws GateException {
        if(!started.compareAndSet(false,true))throw new GateException("ALREADY_RUN");
        File home=null;
        boolean cleanCredentialHome=false;
        Process p=null;
        ExecutorService readers=Executors.newFixedThreadPool(2);
        try {
            require(!cancelled.get(),"CANCELLED");
            stage="HOME_CHECK";
            File privateDir=filesDir.getCanonicalFile();
            require(privateDir.isDirectory(),"PRIVATE_FILES_MISSING");
            home=new File(privateDir,"managed-auth-ephemeral-home-v37").getCanonicalFile();
            require(privateDir.equals(home.getParentFile()),"HOME_OUTSIDE_PRIVATE_FILES");
            Files.createDirectories(home.toPath());
            require(!new File(home,"auth.json").exists(),"EXISTING_CREDENTIAL_FILE");
            cleanCredentialHome=true;
            require(binary.isFile()&&binary.canExecute(),"NATIVE_BINARY_UNAVAILABLE");
            Map<String,String> env=new HashMap<>();
            env.put("PATH","/system/bin");env.put("HOME",home.getPath());env.put("CODEX_HOME",home.getPath());
            stage="PROCESS_START";
            p=factory.start(Arrays.asList(binary.getAbsolutePath(),"--listen","stdio://","-c",
                    "cli_auth_credentials_store=\"ephemeral\"","-c","features.plugins=false",
                    "-c","features.remote_plugin=false","--disable-plugin-startup-tasks-for-tests"),env);
            child=p;
            require(!cancelled.get(),"CANCELLED");
            final Process running=p;
            Future<Integer> stderr=readers.submit(()->drainStderr(running.getErrorStream()));
            InputStream stdout=p.getInputStream();OutputStream stdin=p.getOutputStream();
            stage="INITIALIZE";
            send(stdin,INIT);
            Map<?,?> init=reply(stdout,readers,1,15);
            Map<?,?> initResult=object(init.get("result"),"INITIALIZE_FAILED");
            require(home.getPath().equals(initResult.get("codexHome"))
                    && "android".equals(initResult.get("platformOs")),"INITIALIZE_BOUNDARY_FAILED");
            send(stdin,INITIALIZED);
            stage="ACCOUNT_EMPTY_CHECK";
            send(stdin,ACCOUNT_READ_1);
            Map<?,?> empty=object(reply(stdout,readers,2,10).get("result"),"ACCOUNT_READ_FAILED");
            require(empty.containsKey("account")&&empty.get("account")==null,"ACCOUNT_ALREADY_PRESENT");
            if(offlinePreflight){stage="COMPLETE";return Outcome.OFFLINE_PREFLIGHT;}
            stage="DEVICE_CODE_REQUEST";
            send(stdin,START);
            Map<?,?> started=object(reply(stdout,readers,3,15).get("result"),"DEVICE_CODE_UNAVAILABLE");
            require("chatgptDeviceCode".equals(started.get("type")),"DEVICE_CODE_UNAVAILABLE");
            String loginId=string(started.get("loginId"),"LOGIN_ID_INVALID");
            try {UUID.fromString(loginId);}catch(IllegalArgumentException e){throw new GateException("LOGIN_ID_INVALID");}
            String url=string(started.get("verificationUrl"),"VERIFICATION_URL_INVALID");
            require(VERIFY_URL.equals(url),"VERIFICATION_URL_INVALID");
            String userCode=string(started.get("userCode"),"USER_CODE_INVALID");
            require(userCode.matches("[A-Z0-9-]{4,24}"),"USER_CODE_INVALID");
            stage="WAIT_FOR_USER";
            prompt.show(VERIFY_URL,userCode);
            stage="WAIT_FOR_COMPLETION";
            boolean complete=false;
            long deadline=System.nanoTime()+TimeUnit.MINUTES.toNanos(15);
            for(int i=0;i<MAX_FRAMES;i++){
                // Bound the entire user/browser wait, not each individual frame.
                long remaining=deadline-System.nanoTime();
                require(remaining>0,"LOGIN_TIMEOUT");
                int seconds=(int)Math.max(1,TimeUnit.NANOSECONDS.toSeconds(remaining));
                Map<?,?> event;
                try {event=frame(stdout,readers,seconds);}
                catch(TimeoutException e){throw new GateException("LOGIN_TIMEOUT");}
                if("account/login/completed".equals(event.get("method"))){
                    Map<?,?> params=object(event.get("params"),"COMPLETION_INVALID");
                    require(loginId.equals(params.get("loginId")),"LOGIN_ID_MISMATCH");
                    require(Boolean.TRUE.equals(params.get("success")),
                            completionFailureCode(params.get("error")));
                    complete=true;break;
                }
                acceptNotification(event);
            }
            require(complete,"COMPLETION_MISSING");
            // Pinned app-server checks account state before it emits successful
            // login/completed. Stop here to avoid another post-login RPC.
            require(!stderr.isDone() || stderr.get()<=MAX_STDERR,"STDERR_OVERSIZE");
            require(!cancelled.get(),"CANCELLED");
            if(continuation!=null){
                AuthenticatedControl control=new AuthenticatedControl(stdout,stdin,readers);
                try{continuation.run(control);}finally{control.invalidate();}
            }
            stage="COMPLETE";
            return Outcome.SIGNED_IN_EPHEMERAL;
        } catch(GateException e){throw e;}
        catch(Exception e){throw new GateException(cancelled.get()?"CANCELLED":"SESSION_STOPPED");}
        finally {
            boolean stopped=true;
            if(p!=null){
                try {
                    if(continuation!=null&&!cancelled.get()){try{p.getOutputStream().close();}catch(IOException ignored){/* Still wait, then force/reap if necessary. */}stopped=p.waitFor(2,TimeUnit.SECONDS)&&!p.isAlive();}
                    else stopped=false;
                    if(!stopped){p.destroyForcibly();stopped=p.waitFor(2,TimeUnit.SECONDS)&&!p.isAlive();}
                }
                catch(InterruptedException e){Thread.currentThread().interrupt();stopped=false;}
                catch(RuntimeException e){stopped=false;}
            }
            child=null;readers.shutdownNow();
            if(continuation!=null){try{if(!readers.awaitTermination(2,TimeUnit.SECONDS))throw new GateException("READERS_STILL_RUNNING");}catch(InterruptedException e){Thread.currentThread().interrupt();throw new GateException("READERS_REAP_INTERRUPTED");}}
            if(!stopped)throw new GateException("CHILD_STILL_RUNNING");
            if(cleanCredentialHome&&new File(home,"auth.json").exists()){
                try {Files.deleteIfExists(new File(home,"auth.json").toPath());}
                catch(IOException ignored) { /* Report the violation even if removal fails. */ }
                throw new GateException("CREDENTIAL_FILE_CREATED");
            }
        }
    }

    private Map<?,?> reply(InputStream stdout,ExecutorService readers,int id,int seconds) throws Exception {
        for(int i=0;i<MAX_FRAMES;i++){
            Map<?,?> frame=frame(stdout,readers,seconds);
            if(BigDecimal.valueOf(id).equals(frame.get("id"))){
                require(!frame.containsKey("error"),id==3?"DEVICE_CODE_UNAVAILABLE":"RPC_REJECTED");return frame;
            }
            acceptNotification(frame);
        }
        throw new GateException("REPLY_MISSING");
    }
    private Map<?,?> frame(InputStream stdout,ExecutorService readers,int seconds) throws Exception {
        require(!cancelled.get(),"CANCELLED");
        require(++frames<=MAX_FRAMES,"TOO_MANY_FRAMES");
        byte[] line=readers.submit(()->readLine(stdout)).get(seconds,TimeUnit.SECONDS);
        Object parsed=BoundedJson.parse(line);
        return object(parsed,"NON_OBJECT_FRAME");
    }
    private void acceptNotification(Map<?,?> frame) throws GateException {
        require(!frame.containsKey("id"),"MISMATCHED_RESPONSE_ID");
        Object method=frame.get("method");
        // Pinned app-server sends remoteControl/status/changed immediately after
        // initialized and may send configWarning or account/updated as well.
        // Count only these exact protocol notifications; never surface params.
        require("remoteControl/status/changed".equals(method)
                || "configWarning".equals(method)
                || "account/updated".equals(method),"UNEXPECTED_NOTIFICATION");
        require(frame.get("params") instanceof Map,"NOTIFICATION_PARAMS_INVALID");
        notices++;
    }
    private static byte[] readLine(InputStream in) throws IOException {
        ByteArrayOutputStream bytes=new ByteArrayOutputStream();
        while(true){int b=in.read();if(b<0)throw new IOException("EOF");if(b=='\n')return bytes.toByteArray();
            if(bytes.size()>=MAX_FRAME)throw new IOException("FRAME_OVERSIZE");bytes.write(b);}
    }
    private static int drainStderr(InputStream in) throws IOException {
        int count=0,n;byte[] b=new byte[1024];
        while((n=in.read(b))!=-1){count+=n;if(count>MAX_STDERR)throw new IOException("STDERR_OVERSIZE");}
        return count;
    }
    private static void send(OutputStream out,byte[] frame) throws IOException {out.write(frame);out.flush();}
    private static Map<?,?> object(Object value,String code) throws GateException {
        if(!(value instanceof Map))throw new GateException(code);return (Map<?,?>)value;
    }
    private static String string(Object value,String code) throws GateException {
        if(!(value instanceof String))throw new GateException(code);return (String)value;
    }
    private static String completionFailureCode(Object rawError){
        if(!(rawError instanceof String))return "LOGIN_NOT_COMPLETED";
        String error=(String)rawError;
        String typed=NativePollDetail.classify(error);
        if(typed!=null)return typed;
        // These fixed phase markers are emitted by the pinned diagnostic native
        // build. They carry no HTTP body, token, account value, or error text.
        if("CORETEST_AUTH_CLIENT_INIT_FAILED".equals(error))return "AUTH_CLIENT_INIT_FAILED";
        if("CORETEST_DEVICE_POLL_FAILED".equals(error))return "DEVICE_POLL_FAILED";
        if("CORETEST_POLL_REQUEST_BUILD_FAILED".equals(error))return "POLL_REQUEST_BUILD_FAILED";
        if("CORETEST_POLL_TRANSPORT_FAILED".equals(error))return "POLL_TRANSPORT_FAILED";
        if("CORETEST_POLL_TRANSPORT_TIMEOUT".equals(error))return "POLL_TRANSPORT_TIMEOUT";
        if("CORETEST_POLL_CONNECT_AFTER_REDIRECT".equals(error))return "POLL_CONNECT_AFTER_REDIRECT";
        if("CORETEST_POLL_CONNECT_NO_REDIRECT".equals(error))return "POLL_CONNECT_NO_REDIRECT";
        if("CORETEST_POLL_CONNECT_FIRST_SEND_NO_REDIRECT".equals(error))return "POLL_CONNECT_FIRST_SEND_NO_REDIRECT";
        if("CORETEST_POLL_CONNECT_AFTER_PENDING_NO_REDIRECT".equals(error))return "POLL_CONNECT_AFTER_PENDING_NO_REDIRECT";
        if("CORETEST_POLL_CONNECT_FIRST_SEND_AFTER_REDIRECT".equals(error))return "POLL_CONNECT_FIRST_SEND_AFTER_REDIRECT";
        if("CORETEST_POLL_CONNECT_AFTER_PENDING_AFTER_REDIRECT".equals(error))return "POLL_CONNECT_AFTER_PENDING_AFTER_REDIRECT";
        if("CORETEST_POLL_TRANSPORT_OTHER_FAILED".equals(error))return "POLL_TRANSPORT_OTHER_FAILED";
        if("CORETEST_POLL_RESPONSE_SCHEMA_FAILED".equals(error))return "POLL_RESPONSE_SCHEMA_FAILED";
        if("CORETEST_POLL_EXPIRED".equals(error))return "POLL_EXPIRED";
        if("CORETEST_POLL_RATE_LIMITED".equals(error))return "POLL_RATE_LIMITED";
        if("CORETEST_POLL_HTTP_REJECTED".equals(error))return "POLL_HTTP_REJECTED";
        if("CORETEST_TOKEN_EXCHANGE_FAILED".equals(error))return "TOKEN_EXCHANGE_FAILED";
        if("CORETEST_WORKSPACE_REJECTED".equals(error))return "WORKSPACE_REJECTED";
        if("CORETEST_EPHEMERAL_STORE_FAILED".equals(error))return "EPHEMERAL_STORE_FAILED";
        // The pinned server supplies this text. Match known source phrases only;
        // never log, retain, or display its raw content, which may contain secrets.
        if("Login was not completed".equals(error))return "SERVER_CANCELLED_LOGIN";
        if("account changed before sign-in completed".equals(error))return "ACCOUNT_CHANGED_AFTER_AUTH";
        if("device auth timed out after 15 minutes".equals(error))return "DEVICE_POLL_TIMEOUT";
        if(error.startsWith("device auth failed with status "))return "DEVICE_POLL_REJECTED";
        if(error.startsWith("device code exchange failed:"))return "TOKEN_EXCHANGE_FAILED";
        if(error.startsWith("workspace routing ")
                || error.startsWith("selected workspace ")
                || error.startsWith("failed to load workspace requirements")
                || error.startsWith("failed to reload workspace requirements")
                || error.startsWith("configuration changed during workspace routing discovery")){
            return "POST_LOGIN_ACCOUNT_CHECK_FAILED";
        }
        return "LOGIN_NOT_COMPLETED";
    }
    private static void require(boolean ok,String code) throws GateException {if(!ok)throw new GateException(code);}
}
