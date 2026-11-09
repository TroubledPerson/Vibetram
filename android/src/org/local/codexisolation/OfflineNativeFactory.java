// SPDX-License-Identifier: Apache-2.0
package org.local.codexisolation;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
import java.util.concurrent.TimeUnit;
final class OfflineNativeFactory implements OfflineAppServerAdapter.ProcessFactory {
 interface Launch { Process start(List<String> command,Map<String,String> environment,File directory) throws IOException; }
 static final String FILTER="transport::remote_control::managed_pairing_tests::managed_pairing_stdio_driver";
 static final class Metrics {
  private int started,exited,forced,lastExit=-1;private boolean live;
  synchronized void started(){started++;live=true;}
  synchronized void exited(int code){exited++;lastExit=code;live=false;}
  synchronized void forced(){forced++;}
  synchronized int[] snapshot(){return new int[]{started,exited,forced,lastExit,live?1:0};}
 }
 private final File expectedBinary,root;private final String expectedSHA;private final Launch launcher;final Metrics metrics;
 OfflineNativeFactory(File binary,String sha,File root,Launch launcher,Metrics m){expectedBinary=binary;expectedSHA=sha;this.root=root;this.launcher=launcher;metrics=m;}
 static String fileSHA(File f)throws IOException{
  try{MessageDigest d=MessageDigest.getInstance("SHA-256");try(InputStream in=new FileInputStream(f)){byte[] b=new byte[65536];int n;while((n=in.read(b))!=-1)d.update(b,0,n);}StringBuilder s=new StringBuilder();for(byte b:d.digest())s.append(String.format(Locale.ROOT,"%02x",b&255));return s.toString();}catch(java.security.NoSuchAlgorithmException e){throw new IOException("HASH_UNAVAILABLE");}
 }
 public Process start(List<String> requested,Map<String,String> authEnv)throws IOException{
  if(!requested.equals(Arrays.asList(expectedBinary.getAbsolutePath(),"--listen","stdio://","-c","cli_auth_credentials_store=\"ephemeral\"","-c","features.plugins=false","-c","features.remote_plugin=false","--disable-plugin-startup-tasks-for-tests")))throw new IOException("OFFLINE_LAUNCH_REQUEST");
  if(!expectedBinary.isFile()||!expectedBinary.canExecute()||!fileSHA(expectedBinary).equals(expectedSHA))throw new IOException("NATIVE_IDENTITY_MISMATCH");
  if(authEnv.size()!=3||!authEnv.keySet().equals(new HashSet<>(Arrays.asList("PATH","HOME","CODEX_HOME"))))throw new IOException("INHERITED_AUTH_ENV_REJECTED");
  File home=new File(authEnv.get("CODEX_HOME")).getCanonicalFile();String base=root.getCanonicalPath()+File.separator;
  if(!home.getPath().startsWith(base)||!home.getPath().equals(authEnv.get("HOME")))throw new IOException("HOME_OUTSIDE_FRESH_FIXTURE");
  File temp=new File(root,"tmp");if(!temp.isDirectory()&&!temp.mkdirs())throw new IOException("TEMP_UNAVAILABLE");
  Map<String,String> env=new HashMap<>();env.put("PATH","/system/bin");env.put("HOME",home.getPath());env.put("CODEX_HOME",home.getPath());
  for(String k:new String[]{"TEMP","TMP","TMPDIR"})env.put(k,temp.getAbsolutePath());
  env.put("OFFLINE_191_DRIVER","1");env.put("OFFLINE_191_PHONE","1");env.put("CODEX_INTERNAL_APP_SERVER_REMOTE_CONTROL_DISABLED","1");
  List<String> command=Arrays.asList(expectedBinary.getAbsolutePath(),"--exact",FILTER,"--ignored","--nocapture","--test-threads=1","--format","terse");
  Process child=launcher.start(command,Collections.unmodifiableMap(env),root);metrics.started();return new Observed(child,metrics);
 }
 private static final class Observed extends Process {
  final Process child;final Metrics metrics;boolean reaped,forceRequested;final InputStream stdout;
  Observed(Process p,Metrics m){child=p;metrics=m;stdout=new InputStream(){final BufferedReader reader=new BufferedReader(new InputStreamReader(child.getInputStream(),StandardCharsets.UTF_8));byte[] pending=new byte[0];int offset,skipped;
   public int read()throws IOException{while(offset==pending.length){String line=reader.readLine();if(line==null)return -1;if(line.length()>16384)throw new IOException("NATIVE_FRAME_LIMIT");if(!line.startsWith("{")){if(++skipped>4||!(line.isEmpty()||line.equals("running 1 test")))throw new IOException("NATIVE_PREFIX_INVALID");continue;}pending=(line+"\n").getBytes(StandardCharsets.UTF_8);offset=0;}return pending[offset++]&255;}};}
  private synchronized void observe(){if(!reaped&&!child.isAlive()){metrics.exited(child.exitValue());reaped=true;}}
  public InputStream getInputStream(){return stdout;}public InputStream getErrorStream(){return child.getErrorStream();}public OutputStream getOutputStream(){return child.getOutputStream();}
  public int waitFor()throws InterruptedException{int n=child.waitFor();observe();return n;}public boolean waitFor(long t,TimeUnit u)throws InterruptedException{boolean b=child.waitFor(t,u);if(b)observe();return b;}
  public int exitValue(){int n=child.exitValue();observe();return n;}public boolean isAlive(){boolean b=child.isAlive();if(!b)observe();return b;}
  public void destroy(){child.destroy();}public synchronized Process destroyForcibly(){if(!forceRequested&&child.isAlive()){forceRequested=true;metrics.forced();}child.destroyForcibly();return this;}
 }
}
