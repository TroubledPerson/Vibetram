// SPDX-License-Identifier: Apache-2.0
package org.local.codexisolation;
import java.util.concurrent.Executor;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;
final class OfflineMobileController {
 interface Work { void run(long generation,java.util.function.BooleanSupplier cancelled) throws Exception; boolean activate(long generation); void cancel(long generation); }
 interface Sink { void changed(); }
 static final class CleanupUnconfirmed extends Exception {}
 static final class Cancelled extends Exception {}
 static final class FlowFailure extends Exception { final String stage; FlowFailure(String stage){this.stage=stage;} }
 static final class Snapshot {final String state;final long generation;final boolean busy,ownActive;Snapshot(String s,long g,boolean b,boolean a){state=s;generation=g;busy=b;ownActive=a;}}
 private static final AtomicReference<Ticket> GLOBAL=new AtomicReference<>();
 private final Executor executor;private final Work work;private final Sink sink;
 private boolean focused,closed;private long generation;private Ticket current;private String state="IDLE_OFFLINE_ONLY";
 OfflineMobileController(Executor e,Work w,Sink s){executor=e;work=w;sink=s;}
 synchronized Snapshot snapshot(){return new Snapshot(state,generation,GLOBAL.get()!=null,current!=null);}
 private void notice(){try{sink.changed();}catch(RuntimeException ignored){}}
 synchronized void focus(boolean value){focused=value;if(!value)cancel();}
 synchronized boolean start(){
  if(closed||!focused||current!=null||GLOBAL.get()!=null)return false;
  Ticket t=new Ticket(this,++generation);if(!GLOBAL.compareAndSet(null,t))return false;
  current=t;state="PREPARING_SYNTHETIC_SIGN_IN";notice();
  try{executor.execute(t);}catch(RuntimeException rejected){t.cancelled=true;t.phase.set(2);GLOBAL.compareAndSet(t,null);current=null;state="FAILED_EXECUTOR_REJECTED";notice();return false;}return true;
 }
 synchronized boolean activate(){
  if(!focused||closed||current==null||current.cancelled)return false;
  return work.activate(current.generation);
 }
 synchronized void cancel(){
  Ticket t=current;if(t==null)return;t.cancelled=true;state="CANCELLING_WAITING_FOR_CHILD_CLEANUP";
  work.cancel(t.generation);
  if(t.phase.compareAndSet(0,2)){GLOBAL.compareAndSet(t,null);current=null;state="CLOSED_CANCELLED_NO_CREDIT";}
  notice();
 }
 synchronized void close(){closed=true;focused=false;cancel();}
 private synchronized void finish(Ticket t,String failure,boolean unsafe){
  if(current!=t||generation!=t.generation)return;
  if(unsafe)state="FAILED_CLEANUP_UNCONFIRMED";
  else if(t.cancelled||closed||!focused)state="CLOSED_CANCELLED_NO_CREDIT";
  else if(failure!=null)state=failure;
  else state="PASS_OFFLINE_AUTH_PAIRING_EXPIRED";
  current=null;notice();
 }
 private static final class Ticket implements Runnable {
  final OfflineMobileController owner;final long generation;final AtomicInteger phase=new AtomicInteger();volatile boolean cancelled;
  Ticket(OfflineMobileController o,long g){owner=o;generation=g;}
  public void run(){
   if(!phase.compareAndSet(0,1))return;boolean unsafe=false;String failure=null;
   try{if(cancelled)throw new Cancelled();owner.work.run(generation,()->cancelled);}
   catch(CleanupUnconfirmed e){unsafe=true;failure="FAILED_CLEANUP_UNCONFIRMED";}
   catch(Cancelled e){failure="CLOSED_CANCELLED_NO_CREDIT";}
   catch(FlowFailure e){failure="FAILED_"+e.stage;}
   catch(Throwable e){failure="FAILED_OFFLINE_FLOW";}
   finally{phase.set(2);if(!unsafe)GLOBAL.compareAndSet(this,null);owner.finish(this,failure,unsafe);Thread.interrupted();}
  }
 }
}
