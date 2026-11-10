"""Tiny installed-tool qualification only; never invoke Cargo or app compilation."""
import os,pathlib,json,shutil
from check_source import source_check
from build_guard import Guard,clean_env,MIN_FREE,MAX_OUTPUT
from msvc_env import qualify_msvc
ROOT=pathlib.Path(__file__).resolve().parents[1]
def link_main():
 assert os.name=='nt' and os.environ.get('GITHUB_REPOSITORY')=='TroubledPerson/Vibetram' and os.environ.get('GITHUB_REF')=='refs/heads/main'
 event=json.loads(pathlib.Path(os.environ['GITHUB_EVENT_PATH']).read_text())
 assert os.environ['GITHUB_EVENT_NAME']=='push' and '[msvc-probe-191]' in event['head_commit']['message']
 source_check(ROOT);work=ROOT/'msvc-probe-work';out=ROOT/'msvc-probe-output';assert not work.exists() and not out.exists()
 assert shutil.disk_usage(ROOT).free>=MIN_FREE+MAX_OUTPUT
 work.mkdir();out.mkdir()
 for name in ('tmp','home','profile','profile/AppData/Local','profile/AppData/Roaming'):(work/name).mkdir(parents=True,exist_ok=True)
 env=clean_env(os.environ,work);guard=Guard(ROOT,work,out,env)
 _,result=qualify_msvc(env,work,guard)
 assert result['state']=='PASS_INSTALLED_MSVC_X64_AND_WINDOWS_SDK' and result['compiledTinyFixtures']==2 and not result['executedFixture']
 source_check(ROOT)



# Setup-only observation is deliberately outside production completion policy.
# No member is excluded and no compiler is invoked in this probe mode.
def natural_setup_exit(job,sampler,describe,report,seconds=3,clock=None,sleep=None):
 import time
 clock=clock or time.monotonic;sleep=sleep or time.sleep
 assert 0<seconds<=3,'SETUP_NATURAL_BOUND';start=clock();report.update(state='OBSERVING',boundSeconds=seconds,members=[],samples=0)
 seen=set()
 def capture(rows):
  for row in rows:
   key=(row['pid'],row['creationFiletime'])
   if key not in seen:
    assert len(seen)<256,'SETUP_MEMBER_REPORT_BOUND';report['members'].append(describe(job,row));seen.add(key)
 capture(job.observe())
 while True:
  if sampler:sampler.tick()
  rows=job.observe();capture(rows);active=job.api.active_count(job.job);elapsed=clock()-start;report.update(samples=report['samples']+1,elapsedSeconds=elapsed,lastActiveCount=active,lastListedCount=len(rows))
  if not rows and active==0 and elapsed<=seconds:report['state']='NATURAL_ZERO_ACTIVE_MEMBERS';return report
  if elapsed>=seconds:report['state']='NATURAL_EXIT_NOT_VERIFIED_WITHIN_BOUND';raise TimeoutError('SETUP_NATURAL_EXIT_DEADLINE')
  sleep(min(.025,seconds-elapsed))

def owned_image(job,row,sampler=None):
 import ctypes,re
 from build_guard import executable_snapshot
 api=job.api;pid=row['pid'];handle=job.process if pid==job.initial['pid'] else job.members_held[pid][0];before=api.snapshot(handle)
 assert (before['pid'],before['creationFiletime'])==(row['pid'],row['creationFiletime']),'SETUP_MEMBER_IDENTITY'
 api.k.QueryFullProcessImageNameW.argtypes=[api.w.HANDLE,api.w.DWORD,api.w.LPWSTR,ctypes.POINTER(api.w.DWORD)];api.k.QueryFullProcessImageNameW.restype=api.w.BOOL
 n=api.w.DWORD(32768);buffer=ctypes.create_unicode_buffer(n.value);api.ok(api.k.QueryFullProcessImageNameW(handle,0,buffer,ctypes.byref(n)))
 path=pathlib.Path(buffer.value);assert path.is_absolute() and re.fullmatch('[A-Za-z0-9_.-]{1,100}',path.name),'SETUP_IMAGE_FORMAT'
 category=None;relative=None
 for key in ('SystemRoot','ProgramFiles','ProgramFiles(x86)'):
  root=pathlib.Path(os.environ.get(key,''))
  if root.is_absolute() and path.is_relative_to(root):category=key;relative=path.relative_to(root).as_posix();break
 assert category is not None,'SETUP_IMAGE_OUTSIDE_QUALIFIED_ROOTS'
 identity=executable_snapshot(path,sampler.tick if sampler else None)
 # Fixed binary version avoids reading arbitrary owner strings from resources.
 version=ctypes.WinDLL('version',use_last_error=True);w=api.w
 version.GetFileVersionInfoSizeW.argtypes=[w.LPCWSTR,ctypes.POINTER(w.DWORD)];version.GetFileVersionInfoSizeW.restype=w.DWORD
 version.GetFileVersionInfoW.argtypes=[w.LPCWSTR,w.DWORD,w.DWORD,ctypes.c_void_p];version.GetFileVersionInfoW.restype=w.BOOL
 version.VerQueryValueW.argtypes=[ctypes.c_void_p,w.LPCWSTR,ctypes.POINTER(ctypes.c_void_p),ctypes.POINTER(w.UINT)];version.VerQueryValueW.restype=w.BOOL
 ignored=w.DWORD();size=version.GetFileVersionInfoSizeW(str(path),ctypes.byref(ignored));assert 0<size<=1024**2,'SETUP_IMAGE_VERSION_BOUND'
 data=ctypes.create_string_buffer(size);api.ok(version.GetFileVersionInfoW(str(path),0,size,data));value=ctypes.c_void_p();length=w.UINT();api.ok(version.VerQueryValueW(data,chr(92),ctypes.byref(value),ctypes.byref(length)));assert length.value>=52,'SETUP_IMAGE_VERSION_FORMAT'
 fixed=ctypes.cast(value,ctypes.POINTER(w.DWORD));assert fixed[0]==0xfeef04bd,'SETUP_IMAGE_VERSION_SIGNATURE';numbers=[fixed[2]>>16,fixed[2]&65535,fixed[3]>>16,fixed[3]&65535]
 after=api.snapshot(handle);assert (after['pid'],after['creationFiletime'])==(before['pid'],before['creationFiletime']),'SETUP_MEMBER_IDENTITY_CHANGED'
 return {'pid':pid,'creationFiletime':before['creationFiletime'],'imageBaseName':path.name,'locationClass':category,'relativeImage':relative,'fileVersion':'.'.join(map(str,numbers)),'imageSHA256':identity['sha256'],'imageFileIdentity':identity['identity'],'processExitedAfterMetadata':after['exited'],'authenticodeNotCheckedByThisMetadataRead':True}

class SetupOnlyComplete(RuntimeError):pass

def setup_only_main():
 import time,hashlib
 from unittest.mock import patch
 from census_supervisor import OwnedProcess
 from msvc_env import parse_exports
 assert os.name=='nt' and os.environ.get('GITHUB_REPOSITORY')=='TroubledPerson/Vibetram' and os.environ.get('GITHUB_REF')=='refs/heads/main' and os.environ.get('GITHUB_EVENT_NAME')=='push','SETUP_PROBE_TRUSTED_ENTRY'
 event=json.loads(pathlib.Path(os.environ['GITHUB_EVENT_PATH']).read_text());assert '[msvc-probe-191]' in event['head_commit']['message'] and '[setup-lifecycle-only-191]' in event['head_commit']['message'],'SETUP_PROBE_MARKER'
 source_check(ROOT);work=ROOT/'msvc-probe-work';out=ROOT/'msvc-probe-output';assert not work.exists() and not out.exists();assert shutil.disk_usage(ROOT).free>=MIN_FREE+MAX_OUTPUT
 work.mkdir();out.mkdir()
 for name in ('tmp','home','profile','profile/AppData/Local','profile/AppData/Roaming'):(work/name).mkdir(parents=True,exist_ok=True)
 env=clean_env(os.environ,work);observations=[];captured={}
 class ObservedSetup(OwnedProcess):
  def __init__(self):super().__init__();self.setup_target=False
  def start(self,args,cwd,env,**kw):
   self.setup_target=len(args)==4 and pathlib.Path(args[0])==pathlib.Path(env['SystemRoot'])/'System32/cmd.exe' and args[1:3]==['/d','/c'] and pathlib.Path(args[3])==work/'msvc-setup.cmd'
   return super().start(args,cwd,env,**kw)
  def finish(self,terminate=False,sampler=None,seconds=3):
   if self.setup_target and not terminate and self.teardown is None:
    row={};observations.append(row);natural_setup_exit(self,sampler,lambda j,r:owned_image(j,r,sampler),row,seconds)
   result=super().finish(terminate,sampler,seconds)
   if self.setup_target and observations:result['setupNaturalExitObservation']=observations[-1]
   return result
 class SetupGuard(Guard):
  def run(self,args,*a,**kw):
   result=super().run(args,*a,**kw)
   if len(args)==4 and pathlib.Path(args[-1])==work/'msvc-setup.cmd':
    exports=parse_exports(result.stdout);captured.update(requiredExportsPresent=True,x64HostAndTarget=exports['VSCMD_ARG_TGT_ARCH']==exports['VSCMD_ARG_HOST_ARCH']=='x64',stdoutBytes=len(result.stdout.encode()),stdoutSHA256=hashlib.sha256(result.stdout.encode()).hexdigest(),stderrBytes=len(result.stderr.encode()),outputsReadOnlyAfterZeroMemberProof=True)
    raise SetupOnlyComplete('SETUP_ONLY_COMPLETE')
   return result
 guard=SetupGuard(ROOT,work,out,env);report={'state':'STARTED_SETUP_ONLY','compiledAnything':False,'productionCompletionChanged':False,'observations':observations};start=time.monotonic()
 try:
  with patch('build_guard.OwnedProcess',ObservedSetup):
   try:qualify_msvc(env,work,guard)
   except SetupOnlyComplete:report.update(state='PASS_SETUP_ONLY_NATURAL_EXIT',captured=captured)
   else:raise AssertionError('SETUP_PROBE_COMPILATION_BOUNDARY')
 finally:
  report.update(elapsedSeconds=time.monotonic()-start,commands=guard.commands,sampledNotQuota=True)
  text=json.dumps(report,indent=2);assert len(text.encode())<=32768
  print('SETUP_LIFECYCLE_REPORT\n'+text,flush=True)
  summary=os.environ.get('GITHUB_STEP_SUMMARY')
  if summary:
   with open(summary,'a',encoding='utf-8') as f:f.write('## MSVC setup-only lifecycle\n\n```json\n'+text+'\n```\n')
 assert report['state']=='PASS_SETUP_ONLY_NATURAL_EXIT','SETUP_LIFECYCLE_UNQUALIFIED'
 source_check(ROOT)

def main():
 event=json.loads(pathlib.Path(os.environ['GITHUB_EVENT_PATH']).read_text())
 if '[setup-lifecycle-only-191]' in event['head_commit']['message']:setup_only_main()
 else:link_main()
if __name__=='__main__':main()
