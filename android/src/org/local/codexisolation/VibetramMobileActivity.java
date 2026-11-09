// SPDX-License-Identifier: Apache-2.0
package org.local.codexisolation;
import android.app.Activity;
import android.os.Bundle;
import android.content.pm.PackageManager;
import android.widget.*;
import java.io.File;
import java.util.concurrent.*;
public final class VibetramMobileActivity extends Activity {
 private final android.os.Handler handler=new android.os.Handler(android.os.Looper.getMainLooper());
 private ExecutorService executor;private OfflineMobileController controller;private OfflineMobileWork work;
 private TextView status;private Button start,activate,stop;private boolean resumed,destroyed;
 private final Runnable tick=new Runnable(){public void run(){if(!destroyed&&resumed&&controller!=null){render();handler.postDelayed(this,200);}}};
 @Override public void onCreate(Bundle state){super.onCreate(state);
  LinearLayout box=new LinearLayout(this);box.setOrientation(1);box.setPadding(24,24,24,24);
  box.setOnApplyWindowInsetsListener((v,i)->{v.setPadding(24+i.getSystemWindowInsetLeft(),24+i.getSystemWindowInsetTop(),24+i.getSystemWindowInsetRight(),24+i.getSystemWindowInsetBottom());return i;});
  TextView title=new TextView(this);title.setText("Vibetram Mobile Alpha 1.91\nOFFLINE TEST ONLY - NOT A REAL ACCOUNT\n\nThe existing sign-in parser receives a synthetic sign-in result. Enrollment, pairing and transport are fake; the native controller and its status-only gates are real code. No ChatGPT connection, Internet permission, account login, device tools or capture.\n\n1. Start the offline test.\n2. After SYNTHETIC SIGN-IN COMPLETE, press ACTIVATE within 30 seconds.\n3. Wait for ACTIVE, then test Stop or leave the app. For expiry, keep it focused about two minutes after activation. Each run needs both explicit buttons.\n\nStop or any focus loss cancels. Cancelled runs earn no PASS. The existing cancellation path may force the native test child; counters report the actual exit. Returning never restarts. Only fresh synthetic local fixture files are created, then discarded after verified cleanup.");box.addView(title);
  start=new Button(this);start.setText("START OFFLINE AUTH + PAIRING TEST");box.addView(start);
  activate=new Button(this);activate.setText("ACTIVATE OFFLINE STATUS PILOT ONCE");box.addView(activate);
  stop=new Button(this);stop.setText("STOP OFFLINE SESSION");box.addView(stop);
  status=new TextView(this);box.addView(status);ScrollView scroll=new ScrollView(this);scroll.addView(box);setContentView(scroll);
  executor=Executors.newSingleThreadExecutor();
  OfflineNativeFactory.Launch launch=(command,env,directory)->{ProcessBuilder p=new ProcessBuilder(command);p.directory(directory);p.environment().clear();p.environment().putAll(env);return p.start();};
  work=new OfflineMobileWork(new File(getApplicationInfo().nativeLibraryDir,"libvibetramoffline.so"),BuildPins.NATIVE_SHA256,new File(getCacheDir(),"vibetram-191-offline-fixtures"),launch);
  controller=new OfflineMobileController(executor,work,()->runOnUiThread(()->{if(!destroyed)render();}));
  start.setOnClickListener(v->{if(checkSelfPermission("android.permission.INTERNET")==PackageManager.PERMISSION_GRANTED){status.setText("FAILED_UNEXPECTED_NETWORK_PERMISSION");start.setEnabled(false);return;}controller.focus(resumed&&hasWindowFocus());controller.start();render();});
  activate.setOnClickListener(v->{controller.activate();render();});stop.setOnClickListener(v->{controller.cancel();render();});render();
 }
 private void render(){
  OfflineMobileController.Snapshot c=controller.snapshot();OfflineMobileWork.Progress p=work.progress();boolean same=p.generation==c.generation;
  long remaining=same&&p.deadline>0?Math.max(0,TimeUnit.NANOSECONDS.toMillis(p.deadline-System.nanoTime())):0;
  String phase=!c.busy?"INACTIVE":same&&p.active?"ACTIVE - Stop or leave the app now, or wait for expiry":same&&p.awaiting?"SYNTHETIC SIGN-IN COMPLETE - activation required":"PREPARING / CLEANING UP";
  int[] child=same?p.child:new int[]{0,0,0,-1,0};
  status.setText("State: "+c.state+"\nPhase: "+phase+"\nRun: "+c.generation+
   "\nFixed stage: "+(same?p.stage:"NOT_STARTED")+
   "\nSynthetic sign-in accepted: "+(same?p.auth:0)+"\nExplicit activations: "+(same?p.activation:0)+"\nSynthetic pairing results accepted: "+(same?p.pairing:0)+
   "\nExact identity binding: "+(same&&p.bound)+"\nFresh synthetic identity: "+(same&&p.fresh)+
   "\nRemaining activation lifetime ms: "+remaining+"\nNative expiry observed at ms: "+(same?p.nativeExpiryMs:0)+
   "\nNative children started: "+child[0]+"\nNative children exited: "+child[1]+"\nForced exits: "+child[2]+"\nLast child exit: "+(child[3]<0?"UNOBSERVED":Integer.toString(child[3]))+
   "\nNative process alive: "+(child[4]!=0)+"\nCleanup: "+(same&&p.cleanup?"VERIFIED_EXIT_READERS_AND_FIXTURE_CLEAR":"UNCONFIRMED / NOT_COMPLETE")+
   "\nReal authentication: DISABLED\nExternal transport: ABSENT\nLive pairing: DISABLED\nNo user image/file/shell/model access. These offline results do not establish live ChatGPT or Android network-service compatibility.");
  boolean focused=resumed&&hasWindowFocus();start.setEnabled(!c.busy&&focused);activate.setEnabled(c.ownActive&&same&&p.awaiting&&focused);stop.setEnabled(c.ownActive);
 }
 @Override public void onWindowFocusChanged(boolean value){super.onWindowFocusChanged(value);if(controller!=null){controller.focus(value&&resumed);render();}}
 @Override protected void onResume(){super.onResume();resumed=true;if(controller!=null)controller.focus(hasWindowFocus());handler.post(tick);}
 @Override protected void onPause(){resumed=false;handler.removeCallbacks(tick);if(controller!=null)controller.focus(false);super.onPause();}
 @Override protected void onDestroy(){destroyed=true;handler.removeCallbacks(tick);if(controller!=null)controller.close();if(executor!=null)executor.shutdown();super.onDestroy();}
}
