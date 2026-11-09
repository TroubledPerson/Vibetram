package org.local.codexisolation;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;

/** Runs the existing authentication parser against the real native pairing controller.
 * Authentication, enrollment and transport are synthetic. No SYSTEM factory is used. */
public final class ManagedPairingIntegrationTest {
 static int checks;static void check(boolean v){if(!v)throw new AssertionError("FIXED_CHECK_FAILED_"+checks);checks++;}
 interface Checked {void run() throws Exception;}
 static void reject(Checked work) throws Exception {try{work.run();throw new AssertionError("EXPECTED_REJECTION");}catch(OfflineManagedAuthSession.GateException expected){checks++;}}
 static final class Wrapped extends Process {
  final Process child;final InputStream input;
  Wrapped(Process child,Runnable hook){this.child=child;
   input=new InputStream(){byte[] pending=new byte[0];int offset;final BufferedReader reader=new BufferedReader(new InputStreamReader(child.getInputStream(),StandardCharsets.UTF_8));int skipped;
    public int read()throws IOException{
     while(offset==pending.length){String line=reader.readLine();if(line==null)return -1;if(line.length()>16384)throw new IOException("BOUNDED_NATIVE_FRAME");
      if(!line.startsWith("{")){if(++skipped>4||!(line.isEmpty()||line.equals("running 1 test")))throw new IOException("UNEXPECTED_NATIVE_PREFIX");continue;}
      if(hook!=null&&line.contains("\"pairingCode\""))hook.run();pending=(line+"\n").getBytes(StandardCharsets.UTF_8);offset=0;
     }return pending[offset++]&255;
    }};
  }
  public OutputStream getOutputStream(){return child.getOutputStream();}public InputStream getInputStream(){return input;}public InputStream getErrorStream(){return child.getErrorStream();}
  public int waitFor()throws InterruptedException{return child.waitFor();}public boolean waitFor(long t,TimeUnit u)throws InterruptedException{return child.waitFor(t,u);}public int exitValue(){return child.exitValue();}
  public void destroy(){child.destroy();}public Process destroyForcibly(){child.destroyForcibly();return this;}public boolean isAlive(){return child.isAlive();}
 }
 static final class Factory implements OfflineAppServerAdapter.ProcessFactory {
  final String exe,root;final List<Process> children=new ArrayList<>();boolean bad;Runnable replyHook;
  Factory(String exe,String root){this.exe=exe;this.root=root;}
  public Process start(List<String> ignored,Map<String,String> env)throws IOException{
   check(ignored.contains("cli_auth_credentials_store=\"ephemeral\""));check(env.size()==3);check(!env.containsKey("OPENAI_API_KEY"));
   ProcessBuilder pb=new ProcessBuilder(exe,"--exact","transport::remote_control::managed_pairing_tests::managed_pairing_stdio_driver","--ignored","--nocapture","--format","terse");
   pb.directory(new File(root));Map<String,String> e=pb.environment();e.clear();
   e.put("SystemRoot",System.getenv("SystemRoot"));e.put("PATH","C:\\Windows\\System32;C:\\Windows");e.put("TEMP",root+"\\tmp");e.put("TMP",root+"\\tmp");e.put("HOME",root+"\\home");e.put("USERPROFILE",root+"\\profile");
   e.put("CODEX_HOME",env.get("CODEX_HOME"));e.put("OFFLINE_191_DRIVER","1");
   if(bad)e.put("OFFLINE_191_BAD_PAIR","1");
   Process p=pb.start();children.add(p);return new Wrapped(p,replyHook);
  }
  void reaped(){for(Process p:children)check(!p.isAlive());}
 }

 static final class CloseFailure extends Process {
  boolean alive=true,forced;final InputStream in;
  CloseFailure(String home){
   String quoted=home.replace("\\","\\\\").replace("\"","\\\"");
   String text="{\"id\":1,\"result\":{\"codexHome\":\""+quoted+"\",\"platformOs\":\"android\"}}\n"
    +"{\"id\":2,\"result\":{\"account\":null}}\n"
    +"{\"id\":3,\"result\":{\"type\":\"chatgptDeviceCode\",\"loginId\":\"00000000-0000-4000-8000-000000000191\",\"verificationUrl\":\"https://auth.openai.com/codex/device\",\"userCode\":\"FIXTURE-ONLY\"}}\n"
    +"{\"method\":\"account/login/completed\",\"params\":{\"loginId\":\"00000000-0000-4000-8000-000000000191\",\"success\":true}}\n";
   in=new ByteArrayInputStream(text.getBytes(StandardCharsets.UTF_8));
  }
  public OutputStream getOutputStream(){return new ByteArrayOutputStream(){public void close()throws IOException{throw new IOException("FIXED_SYNTHETIC_CLOSE_FAILURE");}};}
  public InputStream getInputStream(){return in;}public InputStream getErrorStream(){return new ByteArrayInputStream(new byte[0]);}
  public int waitFor(){return 0;}public boolean waitFor(long t,TimeUnit u){return !alive;}public int exitValue(){if(alive)throw new IllegalThreadStateException();return 0;}
  public boolean isAlive(){return alive;}public void destroy(){alive=false;}public Process destroyForcibly(){forced=true;alive=false;return this;}
 }
 public static void main(String[] args)throws Exception{
  String exe=args[0],root=args[1];File binary=new File(exe);Factory f=new Factory(exe,root);
  Path files=Files.createTempDirectory(Path.of(root,"tmp"),"java-auth-fixture-");
  OfflineManagedAuthSession session=new OfflineManagedAuthSession(f);int[] prompts={0};
  OfflineManagedAuthSession.AuthenticatedControl[] stale={null};
  check(session.runOfflinePairing(files.toFile(),binary,(url,code)->{check(url.equals("https://auth.openai.com/codex/device"));check(code.equals("FIXTURE-ONLY"));prompts[0]++;},control->{
   stale[0]=control;reject(()->control.pair());control.activate();reject(()->control.activate());control.pair();reject(()->control.pair());control.finishLocalSession();reject(()->control.pair());
  })==OfflineManagedAuthSession.Outcome.SIGNED_IN_EPHEMERAL);
  check(prompts[0]==1);f.reaped();reject(()->stale[0].activate());check(!Files.exists(files.resolve("managed-auth-ephemeral-home-v37/auth.json")));
  reject(()->session.runOfflinePairing(files.toFile(),binary,(u,c)->{},x->{}));
  OfflineManagedAuthSession cancelled=new OfflineManagedAuthSession(f);int[] invoked={0};
  reject(()->cancelled.runOfflinePairing(files.toFile(),binary,(u,c)->cancelled.cancel(),x->{invoked[0]++;x.activate();}));
  check(invoked[0]==0);f.reaped();
  Factory bad=new Factory(exe,root);bad.bad=true;OfflineManagedAuthSession wrong=new OfflineManagedAuthSession(bad);
  reject(()->wrong.runOfflinePairing(files.toFile(),binary,(u,c)->{},x->{x.activate();x.pair();}));bad.reaped();
  int cancelledChildren=0;
  for(String lifecycle:new String[]{"STOP","FOCUS_LOSS"}){
   Factory late=new Factory(exe,root);OfflineManagedAuthSession dying=new OfflineManagedAuthSession(late);
   late.replyHook=dying::cancel;int[] accepted={0};
   reject(()->dying.runOfflinePairing(files.toFile(),binary,(u,c)->{},x->{x.activate();x.pair();accepted[0]++;}));
   check(accepted[0]==0);late.reaped();check(late.children.size()==1);cancelledChildren+=late.children.size();
  }
  CloseFailure[] close={null};OfflineManagedAuthSession io=new OfflineManagedAuthSession((command,env)->{close[0]=new CloseFailure(env.get("CODEX_HOME"));return close[0];});
  check(io.runOfflinePairing(files.toFile(),binary,(u,c)->{},x->{})==OfflineManagedAuthSession.Outcome.SIGNED_IN_EPHEMERAL);check(close[0].forced&&!close[0].isAlive());
  OfflineManagedAuthSession live=new OfflineManagedAuthSession(OfflineAppServerAdapter.SYSTEM);
  reject(()->live.runOfflinePairing(files.toFile(),binary,(u,c)->{},x->{}));
  System.out.println("PASS_MANAGED_AUTH_TO_PRODUCTION_NATIVE_PAIRING_OFFLINE checks="+checks+" nativeChildren="+(f.children.size()+bad.children.size()+cancelledChildren)+" noNetwork=true noCredentials=true");
 }
}
