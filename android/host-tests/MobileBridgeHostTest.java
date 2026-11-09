// SPDX-License-Identifier: Apache-2.0
package org.local.codexisolation;
import java.io.*;import java.nio.file.*;import java.util.*;import java.util.concurrent.*;
public final class MobileBridgeHostTest {
 static int checks;static void check(boolean b){if(!b)throw new AssertionError("BRIDGE_CHECK_"+checks);checks++;}
 interface Ready {boolean ready();}
 static void await(Ready r,long millis)throws Exception{long end=System.nanoTime()+TimeUnit.MILLISECONDS.toNanos(millis);while(!r.ready()){if(System.nanoTime()>end)throw new AssertionError("HOST_PHASE_DEADLINE");Thread.sleep(10);}}
 public static void main(String[] args)throws Exception{
  File binary=new File(args[0]),root=new File(args[1]);String sha=OfflineNativeFactory.fileSHA(binary);
  OfflineNativeFactory.Launch launch=(command,env,dir)->{ProcessBuilder p=new ProcessBuilder(command);p.directory(dir);p.environment().clear();p.environment().putAll(env);p.environment().put("SystemRoot",System.getenv("SystemRoot"));p.environment().put("WINDIR",System.getenv("WINDIR"));p.environment().put("PATH","C:\\Windows\\System32;C:\\Windows");p.environment().put("USERPROFILE",new File(root,"profile").getAbsolutePath());p.environment().put("APPDATA",new File(root,"profile/AppData/Roaming").getAbsolutePath());p.environment().put("LOCALAPPDATA",new File(root,"profile/AppData/Local").getAbsolutePath());return p.start();};
  ExecutorService executor=Executors.newSingleThreadExecutor();OfflineMobileWork w=new OfflineMobileWork(binary,sha,new File(root,"mobile-host-fixtures"),launch);OfflineMobileController c=new OfflineMobileController(executor,w,()->{});c.focus(true);
  try{
   check(c.start());await(()->w.progress().awaiting,15000);check(w.progress().auth==1&&w.progress().activation==0&&w.progress().pairing==0);c.cancel();await(()->!c.snapshot().busy,7000);check(c.snapshot().state.equals("CLOSED_CANCELLED_NO_CREDIT"));check(w.progress().cleanup);check(w.progress().child[0]==1&&w.progress().child[1]==1&&w.progress().child[4]==0);
   check(c.start());await(()->w.progress().awaiting,15000);check(c.activate());check(!c.activate());await(()->w.progress().active,10000);check(w.progress().activation==1&&w.progress().pairing==1&&w.progress().bound);c.focus(false);await(()->!c.snapshot().busy,7000);check(c.snapshot().state.equals("CLOSED_CANCELLED_NO_CREDIT"));check(!c.activate());check(w.progress().cleanup);check(w.progress().child[0]==1&&w.progress().child[1]==1&&w.progress().child[4]==0);
   c.focus(true);check(c.start());await(()->w.progress().awaiting,15000);check(c.activate());await(()->w.progress().active,10000);check(w.progress().fresh);System.out.println("ACTUAL_COMBINED_NATIVE_AUTH_PAIRING_ACTIVE_WAITING_REAL_120_SECONDS");System.out.flush();
   await(()->!c.snapshot().busy,133000);check(c.snapshot().state.equals("PASS_OFFLINE_AUTH_PAIRING_EXPIRED"));check(w.progress().nativeExpiryMs>=120000&&w.progress().nativeExpiryMs<=130000);check(w.progress().cleanup&&w.progress().child[0]==1&&w.progress().child[1]==1&&w.progress().child[2]==0&&w.progress().child[3]==0&&w.progress().child[4]==0);check(!c.activate());
   File[] remains=new File(root,"mobile-host-fixtures").listFiles();check(remains!=null&&remains.length==0);
   System.out.println("PASS_COMBINED_MOBILE_HOST checks="+checks+" nativeExpiryMs="+w.progress().nativeExpiryMs+" children=3 reaped=3 noLiveAccount=true");
  }finally{c.close();executor.shutdown();check(executor.awaitTermination(7,TimeUnit.SECONDS));}
 }
}
