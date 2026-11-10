"""Bounded census transport and independent parent supervision; no quota claim."""
import subprocess,threading,queue,time,json,os,pathlib,re
TARGET_SAMPLE=.25
MAX_SUPERVISION_GAP=1.0
CENSUS_SECONDS=30
TEARDOWN_SECONDS=3
MAX_FRAME=2*1024**2
MAX_STREAM=4*1024**2
def safe_diagnostic_relative(value):
 if not isinstance(value,str) or len(value)>240 or value.startswith("/") or not re.fullmatch(r"[A-Za-z0-9_./+ -]+",value):return None
 if value!="." and any(x in ("",".","..") for x in value.split("/")):return None
 return value

def census_error_code(error):
 code='CENSUS_PERMISSION_DENIED' if isinstance(error,PermissionError) else str(error).split(':',1)[0]
 if not code or len(code)>100 or any(not(c.isupper() or c.isdigit() or c=='_') for c in code):code='CENSUS_'+type(error).__name__.upper()
 return code

def census_diagnostic(error,roots,location):
 location=location if isinstance(location,dict) else {}
 phase=location.get("phase","UNKNOWN")
 if not isinstance(phase,str) or not re.fullmatch(r"[A-Z_]{1,64}",phase):phase="UNKNOWN"
 index=location.get("rootIndex");relative=safe_diagnostic_relative(location.get("relative"));source="LAST_OPERATION_CONTEXT"
 if type(index) is not int or not 0<=index<len(roots):index=None;relative=None
 filename=getattr(error,"filename",None)
 if filename is not None:
  source="OS_FILENAME_OUTSIDE_OWNED_ROOTS";index=None;relative=None
  try:
   path=pathlib.Path(filename)
   if path.is_absolute() and ".." not in path.parts:
    for i,root in enumerate(roots):
     if path.is_relative_to(root):index=i;relative=safe_diagnostic_relative(path.relative_to(root).as_posix());source="OS_FILENAME";break
  except (TypeError,ValueError):source="INVALID_OS_FILENAME"
 name=type(error).__name__;name=name if re.fullmatch(r"[A-Za-z_]{1,80}",name) else "UNRECOGNIZED_ERROR_CLASS"
 number=lambda value:value if type(value) is int and -2147483648<=value<=2147483647 else None
 return {"failureCode":census_error_code(error),"phase":phase,"rootIndex":index,"relative":relative,"entrySource":source,"errorClass":name,"errno":number(getattr(error,"errno",None)),"winerror":number(getattr(error,"winerror",None)),"partialTotalAccepted":False}

def validate_census_diagnostic(row):
 assert isinstance(row,dict) and set(row)=={"failureCode","phase","rootIndex","relative","entrySource","errorClass","errno","winerror","partialTotalAccepted"},"INVALID_CENSUS_DIAGNOSTIC_SCHEMA"
 assert isinstance(row["failureCode"],str) and re.fullmatch(r"[A-Z0-9_]{1,100}",row["failureCode"]),"INVALID_CENSUS_DIAGNOSTIC_CODE"
 assert isinstance(row["phase"],str) and re.fullmatch(r"[A-Z_]{1,64}",row["phase"]),"INVALID_CENSUS_DIAGNOSTIC_PHASE"
 assert row["rootIndex"] is None or type(row["rootIndex"]) is int and 0<=row["rootIndex"]<4,"INVALID_CENSUS_DIAGNOSTIC_ROOT"
 assert row["relative"] is None or safe_diagnostic_relative(row["relative"])==row["relative"],"INVALID_CENSUS_DIAGNOSTIC_PATH"
 assert row["entrySource"] in ("LAST_OPERATION_CONTEXT","OS_FILENAME","OS_FILENAME_OUTSIDE_OWNED_ROOTS","INVALID_OS_FILENAME"),"INVALID_CENSUS_DIAGNOSTIC_SOURCE"
 assert isinstance(row["errorClass"],str) and re.fullmatch(r"[A-Za-z_]{1,80}",row["errorClass"]),"INVALID_CENSUS_DIAGNOSTIC_CLASS"
 assert all(row[k] is None or type(row[k]) is int and -2147483648<=row[k]<=2147483647 for k in ("errno","winerror")) and row["partialTotalAccepted"] is False,"INVALID_CENSUS_DIAGNOSTIC_VALUE"
 return dict(row)

def classify_teardown(parent_exit,taskkill_exit,children=None,inventory_complete=False):
 # Parent status/taskkill return codes never establish descendant termination.
 children=children if isinstance(children,list) else None
 live=bool(children and any(x.get("identityBound") is True and x.get("exited") is False for x in children))
 verified=inventory_complete is True and children is not None and all(x.get("identityBound") is True and x.get("exited") is True for x in children) and parent_exit is not None
 return {"parentState":"EXITED" if parent_exit is not None else "RUNNING_OR_UNOBSERVED","parentExitCode":parent_exit,"taskkillExitCode":taskkill_exit,"treeState":"SURVIVING_KNOWN_CHILD" if live else "VERIFIED_KNOWN_TREE_EXITED" if verified else "UNKNOWN_DESCENDANT_STATE","processTreeExitIndependentlyVerified":verified,"completeDescendantInventory":inventory_complete is True,"knownChildObservations":len(children) if children is not None else None}

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
  proc=OwnedProcess();proc.start(argv,pathlib.Path(request['spec']['root']),env,pipes=True)
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
  if proc is not None:
   try:proof=proc.finish(terminate=primary is not None,sampler=sampler)
   except BaseException as error:cleanup.append(type(error).__name__);proof=getattr(error,'owned_teardown',None)
   if primary is not None:primary.census_teardown=proof
  while any(t.is_alive() for t in threads) and time.monotonic()<end:
   try:sampler.tick()
   except BaseException as error:cleanup.append(type(error).__name__)
   for t in threads:t.join(.01)
  if any(t.is_alive() for t in threads):cleanup.append('UNCONFIRMED_CENSUS_READERS')
  elif proc is not None:
   for stream in (proc.stdin,proc.stdout):
    if stream is not None:
     try:stream.close()
     except OSError as error:cleanup.append(type(error).__name__)
  if proc is not None:
   cleanup.extend(proc.cleanup_errors)
   try:proc.close()
   except BaseException as error:cleanup.append(type(error).__name__)
  if cleanup:
   if primary is not None:primary.cleanup_failures=cleanup
   else:raise CensusFailure('CENSUS_TEARDOWN_FAILED')

def stop_compiler_tree(proc,sampler,system_root):
 """One taskkill attempt for the known live Popen tree; report uncertain cleanup."""
 if proc is None:return []
 def observe(killer_exit=None):
  row=classify_teardown(proc.poll(),killer_exit);row.update(parentIdentitySource="OWNED_POPEN_PROCESS_HANDLE",parentPID=proc.pid,descendantObserver="UNAVAILABLE")
  proc._vibetram_teardown_diagnostic=row
 observe()
 if proc.poll() is not None:
  proc._vibetram_teardown_diagnostic["parentAlreadyExitedBeforeStop"]=True;return []
 import pathlib
 failures=[]
 try:killer=subprocess.Popen([str(pathlib.Path(system_root)/'System32/taskkill.exe'),'/PID',str(proc.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,env={k:os.environ[k] for k in ('SystemRoot','WINDIR','PATH','PATHEXT') if k in os.environ})
 except OSError as error:
  observe();proc._vibetram_teardown_diagnostic['stopLaunchErrorClass']=type(error).__name__;return ['COMPILER_STOP_'+type(error).__name__]
 end=time.monotonic()+TEARDOWN_SECONDS
 while (proc.poll() is None or killer.poll() is None) and time.monotonic()<end:
  try:sampler.tick()
  except BaseException as error:failures.append(type(error).__name__)
  time.sleep(.025)
 if proc.poll() is None or killer.poll() is None:failures.append('UNCONFIRMED_COMPILER_TEARDOWN')
 if killer.poll() not in (0,None):failures.append('TREE_STOP_NONZERO_'+str(killer.returncode))
 observe(killer.poll())
 return failures


def owned_job_test_environment(env):
 allowed={'SystemRoot','WINDIR','PATH','PATHEXT','TEMP','TMP','PYTHONNOUSERSITE','PYTHONDONTWRITEBYTECODE'}
 assert isinstance(env,dict) and set(env)<=allowed and env.get('PYTHONNOUSERSITE')=='1' and env.get('PYTHONDONTWRITEBYTECODE')=='1','OWNED_JOB_TEST_ENV'
 assert all(isinstance(v,str) and chr(0) not in v for v in env.values()),'OWNED_JOB_ENV_NUL'
 return chr(0).join(k+'='+v for k,v in sorted(env.items(),key=lambda x:x[0].upper()))+chr(0)*2

# Shared native primitives; fixture-only prototype remains separate from production startup.
class WindowsOwnedJobAPI:
 def __init__(self):
  assert os.name=='nt','WINDOWS_JOB_PROTOTYPE_ONLY'
  import ctypes
  from ctypes import wintypes as w
  self.c=ctypes;self.w=w;self.k=ctypes.WinDLL('kernel32',use_last_error=True);size=ctypes.c_size_t
  class Basic(ctypes.Structure):_fields_=[('processTime',ctypes.c_longlong),('jobTime',ctypes.c_longlong),('flags',w.DWORD),('minWS',size),('maxWS',size),('processLimit',w.DWORD),('affinity',size),('priority',w.DWORD),('scheduling',w.DWORD)]
  class IO(ctypes.Structure):_fields_=[(n,ctypes.c_ulonglong) for n in ('readOps','writeOps','otherOps','readBytes','writeBytes','otherBytes')]
  class Extended(ctypes.Structure):_fields_=[('basic',Basic),('io',IO),('processMemory',size),('jobMemory',size),('peakProcessMemory',size),('peakJobMemory',size)]
  class Startup(ctypes.Structure):_fields_=[('cb',w.DWORD),('reserved',w.LPWSTR),('desktop',w.LPWSTR),('title',w.LPWSTR),*[(n,w.DWORD) for n in ('x','y','xSize','ySize','xChars','yChars','fill','flags')],('show',w.WORD),('reservedBytes',w.WORD),('reservedData',ctypes.POINTER(w.BYTE)),('stdin',w.HANDLE),('stdout',w.HANDLE),('stderr',w.HANDLE)]
  class Process(ctypes.Structure):_fields_=[('process',w.HANDLE),('thread',w.HANDLE),('pid',w.DWORD),('tid',w.DWORD)]
  class Members(ctypes.Structure):_fields_=[('assigned',w.DWORD),('listed',w.DWORD),('pids',size*16)]
  class FT(ctypes.Structure):_fields_=[('low',w.DWORD),('high',w.DWORD)]
  self.Extended=Extended;self.Startup=Startup;self.Process=Process;self.Members=Members;self.FT=FT
  signatures={'CreateJobObjectW':([ctypes.c_void_p,w.LPCWSTR],w.HANDLE),'SetInformationJobObject':([w.HANDLE,ctypes.c_int,ctypes.c_void_p,w.DWORD],w.BOOL),'QueryInformationJobObject':([w.HANDLE,ctypes.c_int,ctypes.c_void_p,w.DWORD,ctypes.POINTER(w.DWORD)],w.BOOL),'AssignProcessToJobObject':([w.HANDLE,w.HANDLE],w.BOOL),'IsProcessInJob':([w.HANDLE,w.HANDLE,ctypes.POINTER(w.BOOL)],w.BOOL),'TerminateJobObject':([w.HANDLE,w.UINT],w.BOOL),'CreateProcessW':([w.LPCWSTR,w.LPWSTR,ctypes.c_void_p,ctypes.c_void_p,w.BOOL,w.DWORD,ctypes.c_void_p,w.LPCWSTR,ctypes.POINTER(Startup),ctypes.POINTER(Process)],w.BOOL),'ResumeThread':([w.HANDLE],w.DWORD),'TerminateProcess':([w.HANDLE,w.UINT],w.BOOL),'WaitForSingleObject':([w.HANDLE,w.DWORD],w.DWORD),'CloseHandle':([w.HANDLE],w.BOOL),'OpenProcess':([w.DWORD,w.BOOL,w.DWORD],w.HANDLE),'GetProcessId':([w.HANDLE],w.DWORD),'GetExitCodeProcess':([w.HANDLE,ctypes.POINTER(w.DWORD)],w.BOOL),'GetProcessTimes':([w.HANDLE,*([ctypes.POINTER(FT)]*4)],w.BOOL)}
  for name,(args,result) in signatures.items():f=getattr(self.k,name);f.argtypes=args;f.restype=result
 def ok(self,value,stage='OWNED_JOB_API'):
  if not value:
   code=self.c.get_last_error();error=OSError(code,'OWNED_JOB_API_FAILURE');error.api_stage=stage;error.raw_winerror=code;raise error
  return value
 def create_job(self):
  h=self.ok(self.k.CreateJobObjectW(None,None))
  try:
   info=self.Extended();info.basic.flags=0x2000 # KILL_ON_JOB_CLOSE; neither breakaway flag.
   self.ok(self.k.SetInformationJobObject(h,9,self.c.byref(info),self.c.sizeof(info)))
   actual=self.Extended();self.ok(self.k.QueryInformationJobObject(h,9,self.c.byref(actual),self.c.sizeof(actual),None));assert actual.basic.flags==0x2000,'OWNED_JOB_LIMIT_FLAGS'
   return h
  except BaseException:self.close(h);raise
 def create_suspended(self,argv,cwd,env):
  block=self.c.create_unicode_buffer(owned_job_test_environment(env))
  command=self.c.create_unicode_buffer(subprocess.list2cmdline([str(x) for x in argv]));si=self.Startup();si.cb=self.c.sizeof(si);pi=self.Process()
  self.ok(self.k.CreateProcessW(str(argv[0]),command,None,None,False,0x4|0x400|0x08000000,block,str(cwd),self.c.byref(si),self.c.byref(pi)))
  return pi.process,pi.thread
 def assign(self,job,process):self.ok(self.k.AssignProcessToJobObject(job,process))
 def in_job(self,process,job=None):
  value=self.w.BOOL();self.ok(self.k.IsProcessInJob(process,job,self.c.byref(value)));return bool(value.value)
 def resume(self,thread):
  previous=self.k.ResumeThread(thread)
  if previous==0xffffffff:raise OSError(self.c.get_last_error(),'OWNED_JOB_RESUME')
  assert previous==1,'OWNED_JOB_UNEXPECTED_SUSPEND_COUNT'
 def members(self,job):
  row=self.Members();self.ok(self.k.QueryInformationJobObject(job,3,self.c.byref(row),self.c.sizeof(row),None))
  assert row.assigned==row.listed and row.listed<=16,'OWNED_JOB_MEMBER_BOUND'
  pids=list(row.pids[:row.listed]);assert len(set(pids))==len(pids),'OWNED_JOB_DUPLICATE_MEMBER';return pids
 def active_count(self,job):
  class Accounting(self.c.Structure):_fields_=[(n,self.c.c_longlong) for n in ('user','kernel','periodUser','periodKernel')]+[(n,self.w.DWORD) for n in ('faults','total','active','terminated')]
  row=Accounting();self.ok(self.k.QueryInformationJobObject(job,1,self.c.byref(row),self.c.sizeof(row),None));assert row.active<=16,'OWNED_JOB_ACTIVE_BOUND';return row.active
 def snapshot(self,process):
  values=[self.FT() for _ in range(4)];self.ok(self.k.GetProcessTimes(process,*[self.c.byref(x) for x in values]),'GetProcessTimes');pid=self.ok(self.k.GetProcessId(process),'GetProcessId');wait=self.k.WaitForSingleObject(process,0);assert wait in (0,258),'OWNED_JOB_PROCESS_WAIT'
  code=self.w.DWORD();self.ok(self.k.GetExitCodeProcess(process,self.c.byref(code)),'GetExitCodeProcess')
  return {'pid':pid,'creationFiletime':(values[0].high<<32)|values[0].low,'exited':wait==0,'exitCode':code.value if wait==0 else None}
 def open_member(self,job,pid):
  h=self.ok(self.k.OpenProcess(0x100000|0x1000,False,pid))
  try:assert self.in_job(h,job),'OWNED_JOB_MEMBER_IDENTITY';return h
  except BaseException:self.close(h);raise
 def terminate(self,job):self.ok(self.k.TerminateJobObject(job,7))
 def terminate_unassigned(self,process):
  self.ok(self.k.TerminateProcess(process,7));assert self.k.WaitForSingleObject(process,3000)==0,'OWNED_UNASSIGNED_EXIT_UNKNOWN'
 def close(self,handle):self.ok(self.k.CloseHandle(handle))

class OwnedJobPrototype:
 """Explicit test-only native job lifecycle; never used by the compiler runner."""
 def __init__(self,api=None,outer_job=None):
  self.api=api or WindowsOwnedJobAPI();self.job=self.api.create_job();self.outer_job=outer_job;self.process=None;self.thread=None;self.assigned=False;self.members_held={};self.closed=False;self.events=[];self.stop_attempted=False
 def start_test(self,argv,cwd,env):
  import sys
  assert self.process is None and len(argv)==6 and argv[:2]==[sys.executable,'-B'] and pathlib.Path(argv[2])==pathlib.Path(cwd)/'owned_job_fixture.py' and argv[3] in ('wait','early') and re.fullmatch('[a-f0-9]{32}',argv[4]) and pathlib.Path(argv[5])==pathlib.Path(cwd),'OWNED_JOB_FIXED_FIXTURE_SCOPE'
  try:
   self.process,self.thread=self.api.create_suspended(argv,cwd,env);self.initial=self.api.snapshot(self.process);self.events.append('CREATED_SUSPENDED')
   self.inherited_outer_job=self.api.in_job(self.process)
   if self.outer_job is not None:self.api.assign(self.outer_job,self.process);self.events.append('ASSIGNED_OWNED_OUTER')
   self.api.assign(self.job,self.process);self.assigned=True;self.events.append('ASSIGNED_OWNED_INNER')
   assert self.api.in_job(self.process,self.job),'OWNED_JOB_ASSIGNMENT_NOT_OBSERVED'
   self.api.resume(self.thread);self.events.append('RESUMED_AFTER_ASSIGNMENT')
  except BaseException as error:
   try:self.close()
   except BaseException as cleanup:error.owned_cleanup_failure=type(cleanup).__name__
   raise
 def observe(self):
  pids=self.api.members(self.job);rows=[]
  for pid in pids:
   if pid==self.initial['pid']:h=self.process;before=self.initial
   elif pid in self.members_held:h,before=self.members_held[pid]
   else:
    h=self.api.open_member(self.job,pid);before=self.api.snapshot(h);assert before['pid']==pid,'OWNED_JOB_PID_MISMATCH';self.members_held[pid]=(h,before)
    if getattr(self,'image_capture',None) and not before['exited']:self.image_evidence[(pid,before['creationFiletime'])]=self.image_capture(self,h,before)
   now=self.api.snapshot(h);assert (now['pid'],now['creationFiletime'])==(before['pid'],before['creationFiletime']),'OWNED_JOB_IDENTITY_CHANGED';rows.append(now)
  return rows
 def stop(self,seconds=3):
  assert 0<seconds<=3 and self.assigned and not self.closed,'OWNED_JOB_STOP_SCOPE'
  self.stop_attempted=True
  before=self.observe();start=time.monotonic();self.api.terminate(self.job)
  while True:
   pids=self.api.members(self.job);active=self.api.active_count(self.job);pairs=[(self.process,self.initial)]+list(self.members_held.values());observed=[]
   for h,before_identity in pairs:
    now=self.api.snapshot(h);assert (now['pid'],now['creationFiletime'])==(before_identity['pid'],before_identity['creationFiletime']),'OWNED_JOB_STOP_IDENTITY_CHANGED';observed.append(now)
   exited=all(row['exited'] for row in observed)
   elapsed=time.monotonic()-start
   if not pids and active==0 and exited and elapsed<=seconds:return {'state':'PASS_OWNED_JOB_ZERO_MEMBERS','seconds':elapsed,'before':before,'activeMembers':0,'knownHandlesExited':True,'after':observed,'deadlineSeconds':seconds}
   if elapsed>=seconds:raise TimeoutError('OWNED_JOB_TEARDOWN_DEADLINE')
   time.sleep(.01)
 def close(self):
  if self.closed:return
  failures=[]
  try:
   if self.process is not None and not self.assigned and not self.api.snapshot(self.process)['exited']:self.api.terminate_unassigned(self.process)
   elif self.assigned and self.job is not None and not self.stop_attempted and (self.api.members(self.job) or self.api.active_count(self.job)):self.stop()
  except BaseException as error:failures.append(type(error).__name__)
  handles=[self.thread]+[h for h,_ in self.members_held.values()]+[self.process,self.job]
  self.closed=True
  for h in handles:
   if h is None:continue
   try:self.api.close(h)
   except BaseException as error:failures.append(type(error).__name__)
  if failures:raise RuntimeError('OWNED_JOB_CLEANUP_UNCERTAIN:'+','.join(failures))


# Production startup uses the documented Windows JOB_LIST + HANDLE_LIST attributes.
# The child belongs to our kill-on-close job at creation and remains suspended
# until held identity/membership checks pass. No breakaway or PID-only fallback.
# Job membership queries are live, bounded observations, not a historic census of
# already-exited children. Zero active members after stop proves none survive.
def production_environment(env):
 assert isinstance(env,dict) and 0<len(env)<=96,'OWNED_PROCESS_ENV_BOUND'
 names=set()
 for k,v in env.items():
  assert isinstance(k,str) and re.fullmatch('[A-Za-z_][A-Za-z0-9_()]*',k) and isinstance(v,str) and chr(0) not in v,'OWNED_PROCESS_ENV_FORMAT'
  name=k.upper();assert name not in names,'OWNED_PROCESS_ENV_DUPLICATE';names.add(name)
  assert not re.search('TOKEN|PASSWORD|SECRET|CREDENTIAL|ASKPASS|COOKIE|AUTHORIZATION',name) and not name.startswith(('AWS_','AZURE_','ACTIONS_','GITHUB_')),'OWNED_PROCESS_CREDENTIAL_ENV'
 block=chr(0).join(k+'='+v for k,v in sorted(env.items(),key=lambda x:x[0].upper()))+chr(0)*2
 assert len(block)<=65536,'OWNED_PROCESS_ENV_SIZE'
 return block

class WindowsProductionJobAPI(WindowsOwnedJobAPI):
 def __init__(self):
  super().__init__();c=self.c;w=self.w
  class ExtendedStartup(c.Structure):_fields_=[('startup',self.Startup),('attributes',c.c_void_p)]
  class ProductionMembers(c.Structure):_fields_=[('assigned',w.DWORD),('listed',w.DWORD),('pids',c.c_size_t*256)]
  self.ExtendedStartup=ExtendedStartup;self.Members=ProductionMembers
  signatures={'GetCurrentProcess':([],w.HANDLE),'DuplicateHandle':([w.HANDLE,w.HANDLE,w.HANDLE,c.POINTER(w.HANDLE),w.DWORD,w.BOOL,w.DWORD],w.BOOL),'InitializeProcThreadAttributeList':([c.c_void_p,w.DWORD,w.DWORD,c.POINTER(c.c_size_t)],w.BOOL),'UpdateProcThreadAttribute':([c.c_void_p,w.DWORD,c.c_size_t,c.c_void_p,c.c_size_t,c.c_void_p,c.c_void_p],w.BOOL),'DeleteProcThreadAttributeList':([c.c_void_p],None),'CreatePipe':([c.POINTER(w.HANDLE),c.POINTER(w.HANDLE),c.c_void_p,w.DWORD],w.BOOL)}
  for n,(args,result) in signatures.items():f=getattr(self.k,n);f.argtypes=args;f.restype=result
 def duplicate(self,h,inheritable):
  out=self.w.HANDLE();current=self.k.GetCurrentProcess();self.ok(self.k.DuplicateHandle(current,h,current,self.c.byref(out),0,inheritable,2));return out.value
 def pipe(self):
  r=self.w.HANDLE();w=self.w.HANDLE();self.ok(self.k.CreatePipe(self.c.byref(r),self.c.byref(w),None,0));return r.value,w.value
 def members(self,job):
  row=self.Members();self.ok(self.k.QueryInformationJobObject(job,3,self.c.byref(row),self.c.sizeof(row),None))
  assert row.assigned==row.listed and row.listed<=256,'OWNED_JOB_MEMBER_BOUND'
  pids=list(row.pids[:row.listed]);assert len(set(pids))==len(pids),'OWNED_JOB_DUPLICATE_MEMBER';return pids
 def active_count(self,job):
  class Accounting(self.c.Structure):_fields_=[(n,self.c.c_longlong) for n in ('user','kernel','periodUser','periodKernel')]+[(n,self.w.DWORD) for n in ('faults','total','active','terminated')]
  row=Accounting();self.ok(self.k.QueryInformationJobObject(job,1,self.c.byref(row),self.c.sizeof(row),None));assert row.active<=256,'OWNED_JOB_ACTIVE_BOUND';return row.active
 def create_in_job(self,job,argv,cwd,env,stdio):
  assert len(stdio)==3 and len(set(stdio))==3,'OWNED_PROCESS_STDIO_HANDLES'
  c=self.c;size=c.c_size_t();self.k.InitializeProcThreadAttributeList(None,2,0,c.byref(size))
  assert c.get_last_error()==122 and 0<size.value<=65536,'OWNED_PROCESS_ATTRIBUTE_SIZE'
  storage=c.create_string_buffer(size.value);attributes=c.cast(storage,c.c_void_p);initialized=False
  try:
   self.ok(self.k.InitializeProcThreadAttributeList(attributes,2,0,c.byref(size)));initialized=True
   handles=(self.w.HANDLE*3)(*stdio);jobs=(self.w.HANDLE*1)(job)
   self.ok(self.k.UpdateProcThreadAttribute(attributes,0,0x20002,c.cast(handles,c.c_void_p),c.sizeof(handles),None,None))
   self.ok(self.k.UpdateProcThreadAttribute(attributes,0,0x2000d,c.cast(jobs,c.c_void_p),c.sizeof(jobs),None,None))
   si=self.ExtendedStartup();si.startup.cb=c.sizeof(si);si.startup.flags=0x100;si.startup.stdin,si.startup.stdout,si.startup.stderr=stdio;si.attributes=attributes
   pi=self.Process();block=c.create_unicode_buffer(production_environment(env));command=c.create_unicode_buffer(subprocess.list2cmdline([str(x) for x in argv]))
   self.ok(self.k.CreateProcessW(str(argv[0]),command,None,None,True,0x4|0x400|0x08000000|0x80000,block,str(cwd),c.cast(c.byref(si),c.POINTER(self.Startup)),c.byref(pi)))
   return pi.process,pi.thread
  finally:
   if initialized:self.k.DeleteProcThreadAttributeList(attributes)

class OwnedProcess(OwnedJobPrototype):
 """Production command/census process. All descendants remain in an owned job.
 Complete means zero kernel-reported members and exit of all held identities.
 A denial is terminal: no retry through taskkill or another process mechanism.
 """
 def __init__(self,api=None):
  super().__init__(api or WindowsProductionJobAPI());self.returncode=None;self.stdin=None;self.stdout=None;self.teardown=None;self.cleanup_errors=[];self.image_capture=None;self.image_evidence={};self.image_failures={}
 def start(self,argv,cwd,env,stdout=None,stderr=None,pipes=False,image_capture=None):
  import msvcrt
  assert self.process is None and isinstance(argv,(list,tuple)) and argv and pathlib.Path(argv[0]).is_absolute() and pathlib.Path(cwd).is_absolute(),'OWNED_PROCESS_START_SCOPE'
  assert all(isinstance(x,(str,pathlib.Path)) and chr(0) not in str(x) for x in argv),'OWNED_PROCESS_ARGV'
  self.image_capture=image_capture;production_environment(env);owned=[];child=[];streams=[]
  def duplicate(h):
   value=self.api.duplicate(h,True);child.append(value);return value
  def wrap(h,mode):
   fd=msvcrt.open_osfhandle(h,os.O_BINARY|os.O_NOINHERIT|(os.O_RDONLY if mode=='rb' else os.O_WRONLY));owned.remove(h)
   try:return os.fdopen(fd,mode)
   except BaseException:os.close(fd);raise
  try:
   if pipes:
    read,write=self.api.pipe();owned.extend((read,write));si=duplicate(read);self.stdin=wrap(write,'wb');streams.append(self.stdin)
    read,write=self.api.pipe();owned.extend((read,write));so=duplicate(write);self.stdout=wrap(read,'rb');streams.append(self.stdout)
    null=open(os.devnull,'wb');streams.append(null);se=duplicate(msvcrt.get_osfhandle(null.fileno()))
   else:
    assert stdout is not None and stderr is not None,'OWNED_PROCESS_LOGS_REQUIRED'
    null=open(os.devnull,'rb');streams.append(null);si=duplicate(msvcrt.get_osfhandle(null.fileno()));so=duplicate(msvcrt.get_osfhandle(stdout.fileno()));se=duplicate(msvcrt.get_osfhandle(stderr.fileno()))
   self.process,self.thread=self.api.create_in_job(self.job,argv,cwd,env,(si,so,se));self.assigned=True;self.initial=self.api.snapshot(self.process);self.pid=self.initial['pid'];self.events.extend(['CREATED_SUSPENDED_IN_OWNED_JOB','JOB_LIST_NO_BREAKAWAY'])
   assert self.api.in_job(self.process,self.job),'OWNED_PROCESS_ASSIGNMENT_NOT_OBSERVED'
   if self.image_capture:self.image_evidence[(self.initial['pid'],self.initial['creationFiletime'])]=self.image_capture(self,self.process,self.initial)
   self.api.resume(self.thread);self.events.append('RESUMED_AFTER_ASSIGNMENT')
  except BaseException as error:
   try:self.finish(terminate=True)
   except BaseException as cleanup:error.owned_cleanup_failure=type(cleanup).__name__
   try:self.close()
   except BaseException as cleanup:error.owned_close_failure=type(cleanup).__name__
   for stream in streams:
    if not stream.closed:stream.close()
   raise
  finally:
   for h in child+owned:
    try:self.api.close(h)
    except BaseException as error:self.cleanup_errors.append(type(error).__name__)
   for stream in streams:
    if stream not in (self.stdin,self.stdout) and not stream.closed:stream.close()
  assert not self.cleanup_errors,'OWNED_PROCESS_START_HANDLE_CLEANUP'
  return self
 def poll(self):
  if self.process is None or self.closed:return self.returncode
  row=self.api.snapshot(self.process);assert (row['pid'],row['creationFiletime'])==(self.initial['pid'],self.initial['creationFiletime']),'OWNED_PROCESS_PARENT_IDENTITY'
  self.returncode=row['exitCode'] if row['exited'] else None;return self.returncode
 def finish(self,terminate=False,sampler=None,seconds=TEARDOWN_SECONDS):
  assert 0<seconds<=TEARDOWN_SECONDS and not self.closed,'OWNED_PROCESS_FINISH_SCOPE'
  if self.teardown is not None:return self.teardown
  if self.stop_attempted:raise RuntimeError('OWNED_PROCESS_PREVIOUS_TEARDOWN_UNVERIFIED')
  self.stop_attempted=True;start=time.monotonic();before=[];terminated=False
  try:
   if self.process is not None:before=self.observe()
   if terminate:self.api.terminate(self.job);terminated=True
   while True:
    if sampler:
     try:sampler.tick()
     except BaseException as error:
      # Supervision failure cannot prevent owned-job termination. It is retained
      # separately, so cleanup proof never grants a resource-safety pass.
      self.cleanup_errors.append(type(error).__name__)
    rows=self.observe() if self.process is not None else [];active=self.api.active_count(self.job)
    pairs=([(self.process,self.initial)] if self.process is not None else [])+list(self.members_held.values());held=[]
    for h,identity in pairs:
     now=self.api.snapshot(h);assert (now['pid'],now['creationFiletime'])==(identity['pid'],identity['creationFiletime']),'OWNED_PROCESS_STOP_IDENTITY';held.append(now)
    elapsed=time.monotonic()-start
    if not rows and active==0 and all(x['exited'] for x in held) and elapsed<=seconds:
     self.poll();self.teardown={'treeState':'VERIFIED_OWNED_JOB_ZERO_MEMBERS','processTreeExitIndependentlyVerified':True,'completeActiveMemberAccounting':True,'activeMembers':0,'knownHandlesExited':True,'heldIdentityCount':len(held),'heldIdentities':held,'observedBefore':before,'directJobTermination':terminated,'seconds':elapsed,'deadlineSeconds':seconds,'events':list(self.events),'supervisionFailures':list(self.cleanup_errors)};return self.teardown
    if elapsed>=seconds:raise TimeoutError('OWNED_PROCESS_TEARDOWN_DEADLINE')
    if not terminate:raise RuntimeError('OWNED_PROCESS_DESCENDANTS_AFTER_PARENT')
    time.sleep(.01)
  except BaseException as error:
   # If a normal-exit check discovers children, perform one direct owned-job
   # termination while preserving the command failure. No observation retry
   # after denial/identity failure; kill-on-close remains exceptional cleanup.
   if not terminate and isinstance(error,RuntimeError) and str(error)=='OWNED_PROCESS_DESCENDANTS_AFTER_PARENT':
    self.stop_attempted=False
    try:self.finish(True,sampler,seconds)
    except BaseException as cleanup:error.owned_cleanup_failure=type(cleanup).__name__
   error.owned_teardown=self.teardown or {'treeState':'UNKNOWN_OWNED_JOB_STATE','processTreeExitIndependentlyVerified':False,'errorClass':type(error).__name__,'osError':getattr(error,'winerror',getattr(error,'errno',None))}
   raise
 def close(self):
  if self.closed:return
  failures=[]
  if not self.stop_attempted:
   try:self.finish(True)
   except BaseException as error:failures.append(type(error).__name__)
  self.closed=True
  for h in [self.thread]+[h for h,_ in self.members_held.values()]+[self.process,self.job]:
   if h is not None:
    try:self.api.close(h)
    except BaseException as error:failures.append(type(error).__name__)
  if failures:raise RuntimeError('OWNED_PROCESS_CLOSE_UNCERTAIN:'+','.join(failures))
