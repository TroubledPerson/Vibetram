"""Explicit hosted Python-only Job Object qualification; never production/compiler control."""
import pathlib,sys,os,time,json,uuid,hashlib,shutil,re,stat
from census_supervisor import WindowsOwnedJobAPI,OwnedJobPrototype
FIXTURE=r"""import sys,os,time,json,pathlib,subprocess,ctypes
from ctypes import wintypes as w
k=ctypes.WinDLL('kernel32',use_last_error=True)
class FT(ctypes.Structure):_fields_=[('low',w.DWORD),('high',w.DWORD)]
k.GetCurrentProcess.restype=w.HANDLE;k.GetProcessTimes.argtypes=[w.HANDLE,*([ctypes.POINTER(FT)]*4)];k.GetProcessTimes.restype=w.BOOL
def identity(handle,pid):
 values=[FT() for _ in range(4)]
 if not k.GetProcessTimes(handle,*[ctypes.byref(x) for x in values]):raise OSError(ctypes.get_last_error(),'FIXTURE_IDENTITY')
 return {'pid':pid,'creationFiletime':(values[0].high<<32)|values[0].low}
mode,nonce,folder=sys.argv[1:];root=pathlib.Path(folder)
def save(name,value):
 with (root/name).open('x') as f:json.dump(value,f)
 with (root/(name+'.done')).open('x') as f:f.write('1')
if mode=='leaf':
 save('leaf.json',{'nonce':nonce,'identity':identity(k.GetCurrentProcess(),os.getpid()),'parentPID':os.getppid()});time.sleep(25)
else:
 child=subprocess.Popen([sys.executable,'-B',__file__,'leaf',nonce,folder],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,env=os.environ.copy(),creationflags=subprocess.CREATE_NO_WINDOW)
 save('ready.json',{'nonce':nonce,'parent':identity(k.GetCurrentProcess(),os.getpid()),'child':identity(int(child._handle),child.pid),'declaredDescendants':1})
 if mode=='wait':child.wait(timeout=30)
"""
MIN_FREE=40*1024**3;MAX_OUTPUT=16*1024**2;MAX_SECONDS=90

def resource_check(base,start):
 assert time.monotonic()-start<MAX_SECONDS,'JOB_PROBE_TOTAL_DEADLINE'
 assert shutil.disk_usage(base).free>=MIN_FREE,'JOB_PROBE_FREE_FLOOR'
 total=0;entries=0
 def walk_error(error):raise error
 for folder,dirs,files in os.walk(base,followlinks=False,onerror=walk_error):
  for name in dirs+files:
   p=pathlib.Path(folder)/name;m=p.lstat();assert not m.st_file_attributes&0x400,'JOB_PROBE_OUTPUT_LINK';entries+=1;assert entries<=256,'JOB_PROBE_ENTRY_BOUND'
   assert m.st_reparse_tag==0 and (stat.S_ISREG(m.st_mode) if name in files else stat.S_ISDIR(m.st_mode)),'JOB_PROBE_OUTPUT_TYPE'
   if name in files:total+=m.st_size
 assert total<=MAX_OUTPUT,'JOB_PROBE_OUTPUT_BOUND'
 return total

def test_environment(root):
 env={k:os.environ[k] for k in ('SystemRoot','WINDIR','PATH','PATHEXT') if k in os.environ}
 env.update(TEMP=str(root/'tmp'),TMP=str(root/'tmp'),PYTHONNOUSERSITE='1',PYTHONDONTWRITEBYTECODE='1');return env

def member_image(api,handle):
 api.k.QueryFullProcessImageNameW.argtypes=[api.w.HANDLE,api.w.DWORD,api.w.LPWSTR,api.c.POINTER(api.w.DWORD)];api.k.QueryFullProcessImageNameW.restype=api.w.BOOL
 n=api.w.DWORD(32768);buf=api.c.create_unicode_buffer(n.value);api.ok(api.k.QueryFullProcessImageNameW(handle,0,buf,api.c.byref(n)))
 p=pathlib.Path(buf.value);return {'imageBaseName':p.name,'pinnedPython':p==pathlib.Path(sys.executable),'systemConsole':p.name.lower()=='conhost.exe' and p.is_relative_to(pathlib.Path(os.environ['SystemRoot']))}

def duplicate_owned_handle(api,handle):
 api.k.GetCurrentProcess.restype=api.w.HANDLE;api.k.DuplicateHandle.argtypes=[api.w.HANDLE,api.w.HANDLE,api.w.HANDLE,api.c.POINTER(api.w.HANDLE),api.w.DWORD,api.w.BOOL,api.w.DWORD];api.k.DuplicateHandle.restype=api.w.BOOL
 current=api.k.GetCurrentProcess();copy=api.w.HANDLE();api.ok(api.k.DuplicateHandle(current,handle,current,api.c.byref(copy),0,False,2));return copy.value

class InjectedFailureAPI:
 def __init__(self,api,phase):self.api=api;self.phase=phase;self.duplicate=None;self.initial=None;self.job=None;self.emptyBeforeJobClose=None;self.nativeCleanupErrors=[]
 def __getattr__(self,name):return getattr(self.api,name)
 def create_job(self):self.job=self.api.create_job();return self.job
 def create_suspended(self,*a):
  process,thread=self.api.create_suspended(*a)
  try:self.duplicate=duplicate_owned_handle(self.api,process);self.initial=self.api.snapshot(self.duplicate);return process,thread
  except BaseException:
   try:self.api.terminate_unassigned(process)
   finally:self.api.close(thread);self.api.close(process)
   raise
 def assign(self,*a):
  if self.phase=='assign':raise RuntimeError('INJECTED_ASSIGNMENT_FAILURE')
  return self.api.assign(*a)
 def resume(self,*a):
  if self.phase=='resume':raise RuntimeError('INJECTED_RESUME_FAILURE')
  return self.api.resume(*a)
 def close(self,handle):
  try:
   if handle==self.job:self.emptyBeforeJobClose=self.api.active_count(handle)==0 and self.api.members(handle)==[]
  except OSError as error:
   self.nativeCleanupErrors.append({'errorClass':type(error).__name__,'errno':error.errno,'winerror':getattr(error,'winerror',None)});raise
  finally:self.api.close(handle)

def failure_case(api,base,phase):
 root=base/('failure-'+phase);root.mkdir();(root/'tmp').mkdir();(root/'owned_job_fixture.py').write_text(FIXTURE,encoding='ascii')
 wrapper=InjectedFailureAPI(api,phase);job=OwnedJobPrototype(wrapper);caught=None
 try:
  try:job.start_test([sys.executable,'-B',str(root/'owned_job_fixture.py'),'wait',uuid.uuid4().hex,str(root)],root,test_environment(root))
  except RuntimeError as error:
   if getattr(error,'owned_cleanup_failure',None):raise RuntimeError('JOB_PROBE_FAILURE_CLEANUP_UNCERTAIN')
   caught=str(error)
  expected='INJECTED_ASSIGNMENT_FAILURE' if phase=='assign' else 'INJECTED_RESUME_FAILURE'
  assert caught==expected,'JOB_PROBE_UNEXPECTED_FAILURE'
  assert wrapper.duplicate is not None and wrapper.initial is not None,'JOB_PROBE_MISSING_OWNED_DUPLICATE'
  after=api.snapshot(wrapper.duplicate);assert (after['pid'],after['creationFiletime'])==(wrapper.initial['pid'],wrapper.initial['creationFiletime']) and after['exited'],'JOB_PROBE_FAILURE_PARENT_EXIT'
  assert wrapper.emptyBeforeJobClose is True and not (root/'ready.json').exists(),'JOB_PROBE_FAILURE_EXECUTED_OR_NONEMPTY'
  return {'state':'PASS_INJECTED_'+phase.upper()+'_CLEANUP','injectedNotOSDenial':True,'fixtureCodeRan':False,'ownedParentExited':True,'ownedJobEmptyBeforeClose':True,'events':job.events}
 finally:
  job.close()
  if wrapper.duplicate is not None:api.close(wrapper.duplicate)

def lifecycle_case(api,base,mode,nested,start):
 root=base/('lifecycle-'+mode);root.mkdir();(root/'tmp').mkdir();(root/'owned_job_fixture.py').write_text(FIXTURE,encoding='ascii');outer=None;job=None;nonce=uuid.uuid4().hex
 try:
  if nested:outer=api.create_job()
  job=OwnedJobPrototype(api,outer_job=outer);job.start_test([sys.executable,'-B',str(root/'owned_job_fixture.py'),mode,nonce,str(root)],root,test_environment(root))
  deadline=time.monotonic()+8
  while not (root/'ready.json.done').exists() or not (root/'leaf.json.done').exists():resource_check(base,start);assert time.monotonic()<deadline,'JOB_PROBE_READY_DEADLINE';time.sleep(.02)
  ready=json.loads((root/'ready.json').read_text());leaf=json.loads((root/'leaf.json').read_text());assert ready['nonce']==leaf['nonce']==nonce and ready['declaredDescendants']==1,'JOB_PROBE_NONCE_BINDING'
  assert ready['parent']['pid']==job.initial['pid'] and ready['parent']['creationFiletime']==job.initial['creationFiletime'] and leaf['parentPID']==job.initial['pid'],'JOB_PROBE_PARENT_BINDING'
  assert ready['child']==leaf['identity'],'JOB_PROBE_CHILD_BINDING'
  if mode=='early':
   while not api.snapshot(job.process)['exited']:resource_check(base,start);assert time.monotonic()<deadline,'JOB_PROBE_PARENT_EXIT_DEADLINE';time.sleep(.01)
  rows=job.observe();pinned={ready['child']['pid']}|({job.initial['pid']} if mode=='wait' else set());images=[]
  for member in rows:
   h=job.process if member['pid']==job.initial['pid'] else job.members_held[member['pid']][0];image=member_image(api,h);image['pid']=member['pid'];images.append(image)
  assert pinned.issubset({r['pid'] for r in rows}) and all(x['pinnedPython'] for x in images if x['pid'] in pinned),'JOB_PROBE_PYTHON_IDENTITY'
  extras=[x for x in images if x['pid'] not in pinned];assert len(extras)<=2 and all(x['systemConsole'] for x in extras),'JOB_PROBE_UNKNOWN_MEMBER'
  assert len(rows)==api.active_count(job.job)<=4,'JOB_PROBE_MEMBER_COUNT'
  if nested:assert all(api.in_job(h,outer) for h,_ in job.members_held.values()),'JOB_PROBE_NESTED_MEMBERSHIP'
  parent=api.snapshot(job.process);qpc=time.perf_counter();stopped=job.stop();qpc=time.perf_counter()-qpc
  assert api.active_count(job.job)==0 and api.members(job.job)==[],'JOB_PROBE_NONZERO_INNER'
  if nested:assert api.active_count(outer)==0 and api.members(outer)==[],'JOB_PROBE_NONZERO_OUTER'
  return {'state':'PASS_NESTED_EARLY_PARENT' if nested else 'PASS_WAITING_PARENT','inheritedRunnerJob':job.inherited_outer_job,'explicitNestedJob':nested,'parentExitedBeforeStop':parent['exited'],'parentExitCode':parent['exitCode'],'events':job.events,'activeBefore':len(rows),'consoleHelpersIncluded':len(extras),'noMemberExcluded':True,'stop':stopped,'highResolutionStopSeconds':qpc,'zeroInnerMembers':True,'zeroOuterMembers':True if nested else None,'imageMetadata':images}
 finally:
  if job:job.close()
  if outer is not None:api.close(outer)

def qualify(base,commit):
 assert base.is_absolute() and not base.exists(),'JOB_PROBE_EXCLUSIVE_OUTPUT'
 for p in [base.parent,*base.parent.parents]:assert not p.lstat().st_file_attributes&0x400,'JOB_PROBE_PARENT_LINK'
 assert shutil.disk_usage(base.parent).free>=MIN_FREE+MAX_OUTPUT,'JOB_PROBE_INITIAL_RESERVE'
 base.mkdir();start=time.monotonic();report={'state':'STARTED','commit':commit,'prototypeSourceSHA256':hashlib.sha256(pathlib.Path(__file__).with_name('census_supervisor.py').read_bytes()).hexdigest(),'pythonVersion':sys.version.split()[0],'cases':[],'compilerExecuted':False,'productionRunnerReplaced':False,'credentialsUsed':False,'networkRequested':False,'outputLimitBytes':MAX_OUTPUT,'freeFloorBytes':MIN_FREE,'totalDeadlineSeconds':MAX_SECONDS,'sampledNotQuota':True}
 try:
  api=WindowsOwnedJobAPI()
  for mode,nested in [('wait',False),('early',True)]:report['currentCase']=mode;report['cases'].append(lifecycle_case(api,base,mode,nested,start));resource_check(base,start)
  for phase in ['assign','resume']:report['currentCase']='injected-'+phase;report['cases'].append(failure_case(api,base,phase));resource_check(base,start)
  report['state']='PASS_HOSTED_ISOLATED_OWNED_JOB_ONLY'
 except BaseException as error:
  code=str(error);report.update(state='STOPPED_UNQUALIFIED',errorClass=type(error).__name__,failureCode=code if re.fullmatch('[A-Z0-9_]{1,100}',code) else 'WITHHELD_NONCODE_FAILURE',osError=getattr(error,'winerror',getattr(error,'errno',None)))
 finally:
  retained=None
  if report['state']=='PASS_HOSTED_ISOLATED_OWNED_JOB_ONLY':
   try:retained=resource_check(base,start)
   except BaseException as error:report.update(state='STOPPED_FINAL_RESOURCE_CHECK',resourceErrorClass=type(error).__name__)
  # Never re-enumerate a failed/denied path while producing failure diagnostics.
  report.update(elapsedSeconds=time.monotonic()-start,retainedBytes=retained,monotonicResolutionSeconds=time.get_clock_info('monotonic').resolution)
  text=json.dumps(report,indent=2);assert len(text.encode())<=32768
  qualified_output=report['state']=='PASS_HOSTED_ISOLATED_OWNED_JOB_ONLY' and shutil.disk_usage(base).free>=MIN_FREE+32768
  if qualified_output:
   with (base/'job-qualification.json').open('x') as f:f.write(text)
  print(text,flush=True)
  if qualified_output:
   with open(os.environ['GITHUB_STEP_SUMMARY'],'a',encoding='utf-8') as f:f.write('## Isolated owned Job Object qualification\n\n```json\n'+text+'\n```\n')
 assert report['state']=='PASS_HOSTED_ISOLATED_OWNED_JOB_ONLY','JOB_PROBE_UNQUALIFIED'
 return report

def main():
 assert os.name=='nt' and os.environ.get('GITHUB_REPOSITORY')=='TroubledPerson/Vibetram' and os.environ.get('GITHUB_REF')=='refs/heads/main' and os.environ.get('GITHUB_EVENT_NAME')=='push','JOB_PROBE_TRUSTED_ENTRY'
 event=json.loads(pathlib.Path(os.environ['GITHUB_EVENT_PATH']).read_text(encoding='utf-8'));assert '[owned-job-probe-191]' in event['head_commit']['message'],'JOB_PROBE_MARKER'
 commit=os.environ['GITHUB_SHA'];assert re.fullmatch('[a-f0-9]{40}',commit),'JOB_PROBE_COMMIT'
 from check_source import source_check
 source_check(pathlib.Path(__file__).resolve().parents[1]);qualify(pathlib.Path(os.environ['RUNNER_TEMP'])/('vibetram-owned-job-'+os.environ['GITHUB_RUN_ID']),commit)
if __name__=='__main__':main()
