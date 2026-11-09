// SPDX-License-Identifier: Apache-2.0
package org.local.codexisolation;
import java.util.*;import java.util.concurrent.*;import java.util.function.BooleanSupplier;
public final class MobileControllerTest {
 static int checks;static void check(boolean b){checks++;if(!b)throw new AssertionError("CONTROLLER_CHECK_"+checks);}
 static final class Queue implements Executor {final List<Runnable> tasks=new ArrayList<>();public void execute(Runnable r){tasks.add(r);}void next(){tasks.remove(0).run();}}
 static final class Work implements OfflineMobileController.Work {int runs,activations,cancels;boolean ready;BooleanSupplier cancellation;Runnable hook;
  public void run(long g,BooleanSupplier c)throws Exception{runs++;cancellation=c;if(hook!=null)hook.run();if(c.getAsBoolean())throw new OfflineMobileController.Cancelled();}
  public boolean activate(long g){if(!ready)return false;activations++;ready=false;return true;}public void cancel(long g){cancels++;}}
 public static void main(String[] args){
  Queue q=new Queue();Work w=new Work();OfflineMobileController c=new OfflineMobileController(q,w,()->{});
  check(!c.start());check(!c.activate());c.focus(true);check(c.start());check(!c.start());check(!c.activate());
  c.cancel();check(c.snapshot().state.equals("CLOSED_CANCELLED_NO_CREDIT"));q.next();check(w.runs==0);check(!c.snapshot().busy);
  check(c.start());w.hook=()->{w.ready=true;check(c.activate());check(!c.activate());c.focus(false);check(w.cancellation.getAsBoolean());};q.next();
  check(c.snapshot().state.equals("CLOSED_CANCELLED_NO_CREDIT"));check(!c.snapshot().busy);check(!c.activate());check(!c.start());check(w.activations==1);
  c.focus(true);check(c.start());c.close();q.next();check(w.runs==1);check(!c.start());check(!c.activate());
  Work live=new Work();Queue other=new Queue();OfflineMobileController d=new OfflineMobileController(other,live,()->{});d.focus(true);check(d.start());other.next();check(d.snapshot().state.equals("PASS_OFFLINE_AUTH_PAIRING_EXPIRED"));check(!d.snapshot().busy);
  System.out.println("PASS_MOBILE_CONTROLLER checks="+checks);
 }
}
