// SPDX-License-Identifier: Apache-2.0
package org.local.codexisolation;
import java.io.*;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import java.util.concurrent.TimeUnit;
final class OfflineMobileWork implements OfflineMobileController.Work {
 static final class Progress {
  final long generation,deadline,nativeExpiryMs;final String stage;final int auth,activation,pairing;final boolean awaiting,active,bound,fresh,cleanup;final int[] child;
  Progress(long g,long d,long e,String s,int a,int x,int p,boolean w,boolean live,boolean b,boolean f,boolean c,int[] child){generation=g;deadline=d;nativeExpiryMs=e;stage=s;auth=a;activation=x;pairing=p;awaiting=w;active=live;bound=b;fresh=f;cleanup=c;this.child=child;}
 }
 private final File binary,cache;private final String binarySHA;private final OfflineNativeFactory.Launch launcher;
 private volatile OfflineManagedAuthSession session;private volatile boolean cancelled,activateRequested;private java.util.function.BooleanSupplier cancellation=()->false;
 private long generation,deadline,nativeExpiryMs;private String stage="NOT_STARTED",previousIdentity;private int auth,activation,pairing;private boolean awaiting,active,bound,fresh,cleanup;private OfflineNativeFactory.Metrics metrics=new OfflineNativeFactory.Metrics();
 OfflineMobileWork(File binary,String sha,File cache,OfflineNativeFactory.Launch l){this.binary=binary;binarySHA=sha;this.cache=cache;launcher=l;}
 synchronized Progress progress(){return new Progress(generation,deadline,nativeExpiryMs,stage,auth,activation,pairing,awaiting,active,bound,fresh,cleanup,metrics.snapshot());}
 public synchronized boolean activate(long g){if(g!=generation||cancelled||!awaiting||activateRequested)return false;activateRequested=true;return true;}
 public synchronized void cancel(long g){if(g!=generation)return;cancelled=true;awaiting=active=false;OfflineManagedAuthSession s=session;if(s!=null)s.cancel();}
 private void current()throws OfflineMobileController.Cancelled {if(cancelled||cancellation.getAsBoolean())throw new OfflineMobileController.Cancelled();}
 private synchronized void phase(String s){stage=s;}
 public void run(long g,java.util.function.BooleanSupplier cancellation)throws Exception{
  synchronized(this){generation=g;this.cancellation=cancellation;cancelled=false;activateRequested=false;deadline=nativeExpiryMs=0;auth=activation=pairing=0;awaiting=active=bound=fresh=cleanup=false;metrics=new OfflineNativeFactory.Metrics();stage="VERIFYING_OFFLINE_NATIVE";}
  File run=null;boolean expiry=false;Exception failed=null;
  try{
   current();if(!cache.isDirectory()&&!cache.mkdirs())throw new OfflineMobileController.FlowFailure("PRIVATE_CACHE_UNAVAILABLE");
   run=Files.createTempDirectory(cache.toPath(),"run-").toFile();
   OfflineNativeFactory f=new OfflineNativeFactory(binary,binarySHA,run,launcher,metrics);
   session=new OfflineManagedAuthSession((command,env)->{
    if(cancelled||cancellation.getAsBoolean())throw new IOException("CANCELLED_BEFORE_CHILD");
    Process p=f.start(command,env);
    if(cancelled||cancellation.getAsBoolean()){
     p.destroyForcibly();try{if(!p.waitFor(2,TimeUnit.SECONDS))throw new IOException("CANCELLED_CHILD_UNCONFIRMED");}catch(InterruptedException e){Thread.currentThread().interrupt();throw new IOException("CANCELLED_CHILD_UNCONFIRMED");}
     throw new IOException("CANCELLED_AFTER_CHILD");
    }
    return p;
   });
   current();
   session.runOfflinePairing(run,binary,(url,code)->{if(!url.equals("https://auth.openai.com/codex/device")||!code.equals("FIXTURE-ONLY"))throw new IllegalStateException("NOT_SYNTHETIC_PROMPT");},control->{
    current();synchronized(this){auth=1;awaiting=true;stage="SYNTHETIC_SIGN_IN_COMPLETE_DEFAULT_OFF";}
    long approvalDeadline=System.nanoTime()+TimeUnit.SECONDS.toNanos(30);
    while(!activateRequested){current();if(System.nanoTime()>=approvalDeadline)throw new OfflineMobileController.FlowFailure("ACTIVATION_WAIT_EXPIRED");Thread.sleep(25);}
    current();synchronized(this){awaiting=false;stage="ACTIVATING_OFFLINE_STATUS_PILOT";}
    control.activate();current();synchronized(this){activation=1;deadline=control.activationDeadlineNanos();}
    control.pair();current();String identity=control.boundIdentity();
    synchronized(this){pairing=1;bound=true;fresh=previousIdentity==null||!previousIdentity.equals(identity);previousIdentity=identity;active=true;stage="ACTIVE_OFFLINE_ONLY";}
    if(!fresh)throw new OfflineMobileController.FlowFailure("REUSED_NATIVE_IDENTITY");
    while(System.nanoTime()<deadline+TimeUnit.MILLISECONDS.toNanos(500)){current();Thread.sleep(25);}
    current();long observed=control.observeNaturalExpiry();current();
    synchronized(this){nativeExpiryMs=observed;active=false;stage="NATIVE_EXPIRY_OBSERVED";}
   });
   current();synchronized(this){expiry=nativeExpiryMs>=120000;}
   if(!expiry)throw new OfflineMobileController.FlowFailure("NATIVE_EXPIRY_UNCONFIRMED");
  }catch(Exception e){failed=e;if(e instanceof OfflineManagedAuthSession.GateException){String code=((OfflineManagedAuthSession.GateException)e).code;if(code.matches("[A-Z0-9_]{1,64}"))phase("SESSION_"+code);}}
  finally{
   session=null;int[] counts=metrics.snapshot();
   if(counts[0]!=counts[1]||counts[4]!=0)throw new OfflineMobileController.CleanupUnconfirmed();
   if(expiry&&(counts[2]!=0||counts[3]!=0))failed=new OfflineMobileController.FlowFailure("NATIVE_EXIT_NOT_CLEAN");
   if(failed instanceof OfflineManagedAuthSession.GateException){String c=((OfflineManagedAuthSession.GateException)failed).code;if(c.equals("READERS_STILL_RUNNING")||c.equals("READERS_REAP_INTERRUPTED")||c.equals("CHILD_STILL_RUNNING"))throw new OfflineMobileController.CleanupUnconfirmed();}
   if(run!=null)try{clearOwnedRun(run);}catch(Exception e){throw new OfflineMobileController.CleanupUnconfirmed();}
   synchronized(this){active=awaiting=false;cleanup=true;}
  }
  if(cancelled||cancellation.getAsBoolean())throw new OfflineMobileController.Cancelled();
  if(failed!=null){if(failed instanceof OfflineMobileController.FlowFailure)throw failed;throw new OfflineMobileController.FlowFailure("SYNTHETIC_AUTH_PAIRING_FLOW");}
  if(!expiry)throw new OfflineMobileController.FlowFailure("NATIVE_EXPIRY_UNCONFIRMED");
 }
 private void clearOwnedRun(File run)throws Exception{
  Path base=cache.getCanonicalFile().toPath(),root=run.getCanonicalFile().toPath();if(!root.getParent().equals(base)||!root.getFileName().toString().startsWith("run-"))throw new IOException("UNOWNED_FIXTURE_ROOT");
  List<Path> paths=new ArrayList<>();long bytes=0;
  try(java.util.stream.Stream<Path> stream=Files.walk(root)){Iterator<Path> it=stream.iterator();while(it.hasNext()){Path p=it.next();if(paths.size()>=1024||Files.isSymbolicLink(p)||!p.normalize().startsWith(root))throw new IOException("FIXTURE_CLEANUP_BOUNDARY");if(Files.isRegularFile(p,LinkOption.NOFOLLOW_LINKS)){bytes+=Files.size(p);if(bytes>16777216)throw new IOException("FIXTURE_CLEANUP_BOUND");}paths.add(p);}}
  paths.sort(Comparator.reverseOrder());for(Path p:paths)Files.delete(p);
 }
}
