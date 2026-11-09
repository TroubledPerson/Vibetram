"""Bounded census transport and independent parent supervision; no quota claim."""
import subprocess,threading,queue,time,json,os,pathlib
TARGET_SAMPLE=.25
MAX_SUPERVISION_GAP=1.0
CENSUS_SECONDS=30
TEARDOWN_SECONDS=3
MAX_FRAME=2*1024**2
MAX_STREAM=4*1024**2
class CensusFailure(RuntimeError):
 def __init__(self,code,payload=None):super().__init__(code);self.payload=payload
class Sampler:
 def __init__(self,callback,clock=time.monotonic):self.callback=callback;self.clock=clock;self.last=None;self.count=0;self.max_gap=0
 def tick(self):
  before=self.clock()
  if self.last is not None:
   gap=before-self.last;self.max_gap=max(self.max_gap,gap)
   if gap>MAX_SUPERVISION_GAP:raise CensusFailure('MISSED_SUPERVISION_INTERVAL')
  self.callback();after=self.clock()
  if after-before>MAX_SUPERVISION_GAP:raise CensusFailure('SUPERVISION_SAMPLE_BLOCKED')
  self.last=after;self.count+=1
def run_census(argv,request,sampler,on_progress,seconds=CENSUS_SECONDS):
 assert 0<seconds<=CENSUS_SECONDS
 started=time.monotonic();deadline=started+seconds
 request={**request,'deadline':deadline}
 wire=(json.dumps(request,separators=(',',':'))+'\n').encode();assert len(wire)<=MAX_FRAME,'CENSUS_REQUEST_BOUND'
 messages=queue.Queue(maxsize=16);reader_error=[];writer_error=[];total=[0];proc=None;threads=[];terminal=None;primary=None;cleanup=[]
 def reader():
  try:
   while True:
    line=proc.stdout.readline(MAX_FRAME+1)
    if not line:break
    total[0]+=len(line)
    if len(line)>MAX_FRAME or not line.endswith(b'\n') or total[0]>MAX_STREAM:raise CensusFailure('CENSUS_STREAM_BOUND')
    messages.put_nowait(json.loads(line))
  except BaseException as error:reader_error.append(type(error).__name__)
 def writer():
  try:proc.stdin.write(wire);proc.stdin.flush()
  except BaseException as error:writer_error.append(type(error).__name__)
  finally:
   try:proc.stdin.close()
   except OSError:pass
 try:
  sampler.tick()
  env={k:os.environ[k] for k in ('SystemRoot','WINDIR','PATH','PATHEXT') if k in os.environ}
  temp=str(pathlib.Path(request['spec']['work'])/'tmp');env.update(TEMP=temp,TMP=temp,PYTHONNOUSERSITE='1',PYTHONDONTWRITEBYTECODE='1')
  proc=subprocess.Popen(argv,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,env=env)
  threads=[threading.Thread(target=reader,daemon=True),threading.Thread(target=writer,daemon=True)]
  for t in threads:t.start()
  while True:
   sampler.tick()
   if time.monotonic()>=deadline:raise CensusFailure('CENSUS_TOTAL_DEADLINE')
   if reader_error or writer_error:raise CensusFailure('CENSUS_PIPE_FAILURE')
   try:item=messages.get(timeout=min(TARGET_SAMPLE,max(.001,deadline-time.monotonic())))
   except queue.Empty:item=None
   if item is not None:
    if not isinstance(item,dict) or item.get('nonce')!=request['nonce'] or item.get('generation')!=request['generation'] or item.get('specHash')!=request['specHash']:raise CensusFailure('STALE_OR_UNBOUND_CENSUS_FRAME')
    kind=item.get('kind')
    if terminal is not None:raise CensusFailure('FRAME_AFTER_CENSUS_TERMINAL')
    if kind=='progress':
     n=item.get('confirmedPeakBytes');assert type(n) is int and n>=0,'INVALID_PARTIAL_PEAK'
     on_progress(n)
    elif kind=='error':raise CensusFailure(item.get('code','CENSUS_FAILED'),item.get('payload'))
    elif kind=='complete':terminal=item
    else:raise CensusFailure('UNKNOWN_CENSUS_FRAME')
   if proc.poll() is not None and all(not t.is_alive() for t in threads) and messages.empty():break
  sampler.tick()
  if terminal is None:raise CensusFailure('MISSING_CENSUS_TERMINAL')
  if terminal['kind']!='complete':raise CensusFailure(terminal.get('code','CENSUS_FAILED'),terminal.get('payload'))
  if proc.returncode!=0 or terminal.get('complete') is not True:raise CensusFailure('INCOMPLETE_CENSUS_TERMINAL')
  if time.monotonic()>=deadline:raise CensusFailure('STALE_CENSUS_COMPLETION')
  return terminal['payload']
 except BaseException as error:primary=error;raise
 finally:
  end=time.monotonic()+TEARDOWN_SECONDS
  if proc is not None and proc.poll() is None:
   try:proc.terminate()
   except OSError as error:cleanup.append(type(error).__name__)
  while proc is not None and proc.poll() is None and time.monotonic()<end:
   try:sampler.tick()
   except BaseException as error:cleanup.append(type(error).__name__)
   time.sleep(.025)
  while any(t.is_alive() for t in threads) and time.monotonic()<end:
   try:sampler.tick()
   except BaseException as error:cleanup.append(type(error).__name__)
   for t in threads:t.join(.01)
  if proc is not None and not any(t.is_alive() for t in threads):
   try:proc.stdout.close()
   except OSError as error:cleanup.append(type(error).__name__)
  if proc is not None and (proc.poll() is None or any(t.is_alive() for t in threads)):cleanup.append('UNCONFIRMED_CENSUS_TEARDOWN')
  if cleanup:
   if primary is not None:primary.cleanup_failures=cleanup
   else:raise CensusFailure('CENSUS_TEARDOWN_FAILED')

def stop_compiler_tree(proc,sampler,system_root):
 """One taskkill attempt for the known live Popen tree; report uncertain cleanup."""
 if proc is None or proc.poll() is not None:return []
 import pathlib
 failures=[]
 try:killer=subprocess.Popen([str(pathlib.Path(system_root)/'System32/taskkill.exe'),'/PID',str(proc.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,env={k:os.environ[k] for k in ('SystemRoot','WINDIR','PATH','PATHEXT') if k in os.environ})
 except OSError as error:return ['COMPILER_STOP_'+type(error).__name__]
 end=time.monotonic()+TEARDOWN_SECONDS
 while (proc.poll() is None or killer.poll() is None) and time.monotonic()<end:
  try:sampler.tick()
  except BaseException as error:failures.append(type(error).__name__)
  time.sleep(.025)
 if proc.poll() is None or killer.poll() is None:failures.append('UNCONFIRMED_COMPILER_TEARDOWN')
 if killer.poll() not in (0,None):failures.append('TREE_STOP_NONZERO_'+str(killer.returncode))
 return failures
