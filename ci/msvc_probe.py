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
 strings={};translation=ctypes.c_void_p();translation_size=w.UINT()
 api.ok(version.VerQueryValueW(data,chr(92)+'VarFileInfo'+chr(92)+'Translation',ctypes.byref(translation),ctypes.byref(translation_size)))
 assert 4<=translation_size.value<=32 and translation_size.value%4==0,'OWNED_IMAGE_TRANSLATION_BOUND'
 words=ctypes.cast(translation,ctypes.POINTER(w.WORD));pairs=[(words[i],words[i+1]) for i in range(0,translation_size.value//2,2)];language,codepage=next((x for x in pairs if x[0]==0x409),pairs[0])
 for field in ('CompanyName','FileDescription','ProductName','OriginalFilename'):
  item=ctypes.c_void_p();count=w.UINT();key=chr(92)+'StringFileInfo'+chr(92)+f'{language:04x}{codepage:04x}'+chr(92)+field
  if not version.VerQueryValueW(data,key,ctypes.byref(item),ctypes.byref(count)):continue
  assert 0<count.value<=256,'OWNED_IMAGE_RESOURCE_BOUND'
  value_text=ctypes.wstring_at(item,count.value).rstrip(chr(0));assert not any(ord(c)<32 for c in value_text),'OWNED_IMAGE_RESOURCE_CONTROL';strings[field]=value_text
 missing=[key for key in ('CompanyName','FileDescription','ProductName','OriginalFilename') if key not in strings]
 microsoft=strings.get('CompanyName','').strip()=='Microsoft Corporation'
 if not microsoft:strings={'unqualifiedVendorStringsWithheld':True}
 fresh=path.lstat();assert [fresh.st_dev,fresh.st_ino]==identity['identity'] and fresh.st_size==identity['bytes'] and fresh.st_mtime_ns==identity['modifiedNs'],'OWNED_IMAGE_FILE_CHANGED'
 after=api.snapshot(handle);assert (after['pid'],after['creationFiletime'])==(before['pid'],before['creationFiletime']),'SETUP_MEMBER_IDENTITY_CHANGED'
 return {'pid':pid,'creationFiletime':before['creationFiletime'],'imageBaseName':path.name,'locationClass':category,'relativeImage':relative,'fileVersion':'.'.join(map(str,numbers)),'imageSHA256':identity['sha256'],'imageFileIdentity':identity['identity'],'processExitedAfterMetadata':after['exited'],'authenticodeNotCheckedByThisMetadataRead':True,'vendorResourceStrings':strings,'vendorResourceFieldsMissing':missing,'vendorCompanyMetadataMatchesMicrosoft':microsoft,'commandLineNotRead':True}


def closed_compiler_outputs(work,proof,rust=False):
 """Inspect only expected task-owned outputs after kernel zero-member proof.
 Retaining a valid file after forced cleanup does not make completion a pass.
 """
 import struct,stat,hashlib
 assert proof.get('processTreeExitIndependentlyVerified') is True and proof.get('activeMembers')==0 and proof.get('knownHandlesExited') is True,'COMPILER_OUTPUT_WRITERS_UNVERIFIED'
 rows=[]
 assert type(rust) is bool,'FIXED_COMPILER_OUTPUT_SCOPE'
 for name in (('tiny-msvc.exe',) if rust else ('tiny-sdk.obj','tiny-sdk.exe')):
  path=work/name;before=path.lstat();assert stat.S_ISREG(before.st_mode) and not getattr(before,'st_file_attributes',0)&0x400 and not getattr(before,'st_reparse_tag',0) and 0<before.st_size<=8*1024**2,'COMPILER_OUTPUT_TYPE_OR_BOUND'
  data=path.read_bytes();after=path.lstat();key=lambda m:(m.st_dev,m.st_ino,m.st_size,m.st_mtime_ns)
  assert key(before)==key(after),'COMPILER_OUTPUT_CHANGED'
  row={'name':name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'closedOwnedWritersVerified':True}
  if name.endswith('.exe'):
   assert len(data)>=64 and data[:2]==b'MZ','COMPILER_OUTPUT_DOS';at=struct.unpack_from('<I',data,60)[0];assert 64<=at<=len(data)-24 and data[at:at+4]==b'PE'+bytes(2),'COMPILER_OUTPUT_PE'
   machine,sections=struct.unpack_from('<HH',data,at+4);optional=struct.unpack_from('<H',data,at+20)[0];start=at+24+optional
   assert machine==0x8664 and 0<sections<=96 and optional>=112 and start+sections*40<=len(data) and struct.unpack_from('<H',data,at+24)[0]==0x20b,'COMPILER_OUTPUT_X64_HEADERS'
   for i in range(sections):
    size,offset=struct.unpack_from('<II',data,start+i*40+16);assert offset+size<=len(data),'COMPILER_OUTPUT_SECTION_TRUNCATED'
   row['x64PESectionBoundsValidated']=True
  else:
   assert len(data)>=20,'COMPILER_OUTPUT_COFF_HEADER'
   machine,sections,stamp,symbols,count,optional,flags=struct.unpack_from('<HHIIIHH',data,0)
   assert machine==0x8664 and 0<sections<=96 and optional==0 and 20+sections*40<=len(data),'COMPILER_OUTPUT_COFF_X64'
   for i in range(sections):
    size,offset=struct.unpack_from('<II',data,20+i*40+16);assert offset+size<=len(data),'COMPILER_OUTPUT_COFF_SECTION'
   assert count==0 or symbols>=20+sections*40 and symbols+count*18<=len(data),'COMPILER_OUTPUT_COFF_SYMBOLS'
   row['x64COFFSectionBoundsValidated']=True
  rows.append(row)
 return rows


# Narrow normal-completion contract for the pinned tiny SDK compiler only.
# Optional vendor telemetry is never excluded from ownership or zero-member proof.
VCTIP_SHA256='41fe46f8a0b41f6dd94c68c85fba20a10aacb662a9ef04784a632e37f3692371'
VCTIP_RELATIVE='Microsoft Visual Studio/18/Enterprise/VC/Tools/MSVC/14.51.36231/bin/Hostx64/x64/vctip.exe'

def validate_telemetry_member(row):
 assert row['imageBaseName'].lower()=='vctip.exe' and row['locationClass']=='ProgramFiles','COMPILER_HELPER_IMAGE'
 assert row['relativeImage']==VCTIP_RELATIVE and row['imageSHA256']==VCTIP_SHA256 and row['fileVersion']=='14.51.36260.0','COMPILER_HELPER_PIN'
 assert row['vendorCompanyMetadataMatchesMicrosoft'] is True and not row['vendorResourceFieldsMissing'],'COMPILER_HELPER_PROVENANCE'
 assert row['vendorResourceStrings']['OriginalFilename']=='VCTIP.EXE' and row['vendorResourceStrings']['FileDescription']=='Microsoft\u00ae VC compiler and tools experience improvement data uploader','COMPILER_HELPER_PURPOSE'
 return (row['pid'],row['creationFiletime'])

def compiler_completion(proc,args,env,work,stdout,stderr,sampler,describe=None,validate_outputs=None):
 if not env.get('VIBETRAM_VERIFIED_VCTIP'):return None
 rust=pathlib.Path(args[0]).name.lower() in ('rustc','rustc.exe')
 if rust:
  if env.get('VIBETRAM_QUALIFIED_RUST_VCTIP')!='1' or str(work/'tiny-msvc.rs') not in [str(x) for x in args]:return None
  linker=env['CARGO_TARGET_X86_64_PC_WINDOWS_MSVC_LINKER']
  assert pathlib.Path(linker).is_absolute() and pathlib.Path(linker).name.lower()=='link.exe','RUST_COMPLETION_EXPLICIT_LINKER'
  expected=['--edition','2024','--target','x86_64-pc-windows-msvc','-C','linker='+linker,str(work/'tiny-msvc.rs'),'-o',str(work/'tiny-msvc.exe')]
 elif pathlib.Path(args[0]).name.lower()=='cl.exe':
  expected=['/nologo','/WX','/W4','/MT',str(work/'tiny-sdk.c'),'/Fo'+str(work/'tiny-sdk.obj'),'/Fe'+str(work/'tiny-sdk.exe')]
 else:return None
 assert [str(x) for x in args[1:]]==expected,'COMPILER_COMPLETION_SCOPE'
 assert env['VIBETRAM_VERIFIED_VCTIP']==VCTIP_SHA256,'COMPILER_COMPLETION_SIGNATURE_ATTESTATION'
 assert proc.poll()==0,'COMPILER_COMPLETION_ROOT_EXIT'
 describe=describe or owned_image;validate_outputs=validate_outputs or (lambda w,p:closed_compiler_outputs(w,p,rust=rust))
 import hashlib,stat
 def captured():
  result=[]
  for path in (stdout,stderr):
   a=path.lstat();assert stat.S_ISREG(a.st_mode) and not getattr(a,'st_file_attributes',0)&0x400 and not getattr(a,'st_reparse_tag',0) and a.st_size<=1024**2,'COMPILER_CAPTURE_TYPE_OR_BOUND'
   data=path.read_bytes();b=path.lstat()
   assert (a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns)==(b.st_dev,b.st_ino,b.st_size,b.st_mtime_ns),'COMPILER_CAPTURE_CHANGED'
   result.append((a.st_dev,a.st_ino,len(data),hashlib.sha256(data).hexdigest()))
  return result
 logs=captured();rows=proc.observe();active=proc.api.active_count(proc.job)
 if not rows and active==0:return None
 assert len(rows)==active==1 and not rows[0]['exited'],'COMPILER_COMPLETION_UNKNOWN_MEMBERS'
 member=describe(proc,rows[0],sampler);identity=validate_telemetry_member(member)
 assert identity==(rows[0]['pid'],rows[0]['creationFiletime']),'COMPILER_COMPLETION_HELD_IDENTITY'
 fresh=proc.observe();active=proc.api.active_count(proc.job)
 assert (not fresh and active==0) or (len(fresh)==active==1 and (fresh[0]['pid'],fresh[0]['creationFiletime'])==identity),'COMPILER_COMPLETION_MEMBERS_CHANGED'
 proof=proc.finish(terminate=True,sampler=sampler)
 assert not proc.cleanup_errors and proof.get('processTreeExitIndependentlyVerified') is True and proof.get('activeMembers')==0 and proof.get('knownHandlesExited') is True,'COMPILER_COMPLETION_ZERO_UNVERIFIED'
 allowed={(proc.initial['pid'],proc.initial['creationFiletime']),identity}
 assert all((r['pid'],r['creationFiletime']) in allowed for r in proof['heldIdentities']+proof['observedBefore']),'COMPILER_COMPLETION_LATE_UNKNOWN_MEMBER'
 assert {(r['pid'],r['creationFiletime']) for r in proof['heldIdentities']}==allowed,'COMPILER_COMPLETION_HELD_PROOF_INCOMPLETE'
 assert all(r['exited'] for r in proof['heldIdentities']),'COMPILER_COMPLETION_SURVIVING_HANDLE'
 assert captured()==logs,'COMPILER_CAPTURE_CHANGED_AFTER_STOP'
 outputs=validate_outputs(work,proof)
 proof['optionalCompilerCompletion']={'state':'VERIFIED_OPTIONAL_TELEMETRY_CLEANUP','rootExit':0,'fixture':'TINY_RUST_MSVC' if rust else 'TINY_C_MSVC','helperIdentity':member,'capturedLogsUnchanged':True,'outputs':outputs,'allMembersAccounted':True,'purposeGuidanceURL':'https://developercommunity.visualstudio.com/t/11157272','guidanceScope':'14.50; exact 14.51 separately tested','normalWorkloadSuccessNotInferredFromTermination':True}
 return proof['optionalCompilerCompletion']



def isolated_rust_cleanup(proc,args,env,work,stdout,stderr,sampler):
 # Called only inside the trusted, tiny probe class; never export this flag.
 assert os.environ.get('GITHUB_REPOSITORY')=='TroubledPerson/Vibetram' and os.environ.get('GITHUB_REF')=='refs/heads/main' and os.environ.get('GITHUB_EVENT_NAME')=='push','RUST_CLEANUP_PROBE_TRUST'
 event_path=pathlib.Path(os.environ['GITHUB_EVENT_PATH']);assert event_path.is_absolute() and 0<event_path.stat().st_size<=1024**2,'RUST_CLEANUP_PROBE_EVENT_BOUND'
 message=json.loads(event_path.read_text(encoding='utf-8'))['head_commit']['message']
 assert '[rust-cleanup-qualification-only-191]' in message and '[unsigned-trial-191]' not in message and '[qualified-rust-vctip-cleanup-191]' not in message,'RUST_CLEANUP_PROBE_ONLY'
 assert pathlib.Path(args[0]).name.lower() in ('rustc','rustc.exe') and str(work/'tiny-msvc.rs') in [str(x) for x in args],'RUST_CLEANUP_PROBE_FIXED_SCOPE'
 assert env.get('VIBETRAM_VERIFIED_VCTIP')==VCTIP_SHA256 and 'VIBETRAM_QUALIFIED_RUST_VCTIP' not in env,'RUST_CLEANUP_PROBE_PRODUCTION_OFF'
 local=env.copy();local['VIBETRAM_QUALIFIED_RUST_VCTIP']='1'
 assert proc.poll()==0,'RUST_CLEANUP_PROBE_PARENT_SUCCESS'
 import stat,hashlib
 def captured_logs():
  rows=[]
  for path in (stdout,stderr):
   before=path.lstat();assert stat.S_ISREG(before.st_mode) and not getattr(before,'st_file_attributes',0)&0x400 and not getattr(before,'st_reparse_tag',0) and before.st_size<=1024**2,'RUST_PROBE_CAPTURE_TYPE'
   data=path.read_bytes();after=path.lstat();key=lambda m:(m.st_dev,m.st_ino,m.st_size,m.st_mtime_ns)
   assert key(before)==key(after),'RUST_PROBE_CAPTURE_RACE'
   rows.append((key(after),hashlib.sha256(data).hexdigest()))
  return rows
 logs=captured_logs()
 proc.isolatedRustObservedImages=[]
 def capture_member(job,row,active_sampler):
  image=owned_image(job,row,active_sampler);proc.isolatedRustObservedImages.append(image);return image
 result=compiler_completion(proc,args,local,work,stdout,stderr,sampler,describe=capture_member)
 if result is None:
  # Verify normal completion directly; calling this probe override recursively
  # would confuse classification and must never stand in for kernel proof.
  from census_supervisor import OwnedProcess
  proof=OwnedProcess.finish(proc,sampler=sampler)
  assert proof.get('directJobTermination') is False,'RUST_PROBE_NATURAL_RESULT_FORCED'
  result={'state':'VERIFIED_NATURAL_EMPTY_JOB','fixture':'TINY_RUST_MSVC'}
 else:
  assert result.get('state')=='VERIFIED_OPTIONAL_TELEMETRY_CLEANUP' and result.get('fixture')=='TINY_RUST_MSVC','RUST_CLEANUP_PROBE_NOT_QUALIFIED'
  proof=proc.teardown
 assert proof and proof.get('processTreeExitIndependentlyVerified') is True and proof.get('completeActiveMemberAccounting') is True and proof.get('activeMembers')==0 and proof.get('knownHandlesExited') is True and not proc.cleanup_errors and not proof.get('supervisionFailures'),'RUST_PROBE_COMPLETION_UNVERIFIED'
 held=proof['heldIdentities'];assert held and all(r['exited'] for r in held),'RUST_PROBE_HELD_SURVIVOR'
 root=[r for r in held if (r['pid'],r['creationFiletime'])==(proc.initial['pid'],proc.initial['creationFiletime'])]
 assert len(root)==1 and root[0]['exitCode']==0,'RUST_PROBE_ROOT_IDENTITY_OR_EXIT'
 outputs=closed_compiler_outputs(work,proof,rust=True)
 assert captured_logs()==logs,'RUST_PROBE_OUTPUT_CHANGED'
 result.update(rootExit=0,capturedLogsUnchanged=True,outputs=outputs,zeroOwnedMembersVerified=True)
 return result



def isolated_rust_measurement(qualification,command,outputs):
 """Classify only this fixture and this held job, never an earlier process."""
 assert qualification['state']=='PASS_INSTALLED_MSVC_X64_AND_WINDOWS_SDK' and qualification['qualifiedToolPinsVerified'] is True and qualification['compiledTinyFixtures']==2 and qualification['executedFixture'] is False,'ISOLATED_RUST_COMPILER_QUALIFICATION'
 assert qualification['rustVersion'].startswith('rustc 1.95.0 '),'ISOLATED_RUST_PIN'
 signed=qualification['optionalCompilerHelperIdentity']
 assert signed['authenticode']=='Valid' and signed['company']=='Microsoft Corporation' and signed['sha256']==VCTIP_SHA256,'ISOLATED_RUST_HELPER_SIGNATURE'
 assert pathlib.Path(command['tool']).name.lower() in ('rustc','rustc.exe') and command['exit']==0,'ISOLATED_RUST_ROOT_SUCCESS'
 proof=command['ownedJobTeardown'];held=proof['heldIdentities']
 assert proof['treeState']=='VERIFIED_OWNED_JOB_ZERO_MEMBERS' and proof['processTreeExitIndependentlyVerified'] is True and proof['completeActiveMemberAccounting'] is True and proof['activeMembers']==0 and proof['knownHandlesExited'] is True and not proof['supervisionFailures'],'ISOLATED_RUST_ZERO_PROOF'
 assert held and proof['heldIdentityCount']==len(held) and all(h['exited'] for h in held) and held[0]['exitCode']==0,'ISOLATED_RUST_HELD_IDENTITIES'
 assert all(x in proof['events'] for x in ('CREATED_SUSPENDED_IN_OWNED_JOB','JOB_LIST_NO_BREAKAWAY','RESUMED_AFTER_ASSIGNMENT')),'ISOLATED_RUST_OWNERSHIP_ORIGIN'
 import re
 assert len(outputs)==1 and type(outputs[0]['bytes']) is int and 0<outputs[0]['bytes']<=8*1024**2 and re.fullmatch('[a-f0-9]{64}',outputs[0]['sha256']) and outputs[0]['name']=='tiny-msvc.exe' and outputs[0]['closedOwnedWritersVerified'] is True and outputs[0]['x64PESectionBoundsValidated'] is True,'ISOLATED_RUST_PE_PROOF'
 expected=[x for x in qualification['fixtures'] if x['name']=='tiny-msvc.exe'];assert len(expected)==1 and expected[0]['bytes']==outputs[0]['bytes'] and expected[0]['sha256']==outputs[0]['sha256'],'ISOLATED_RUST_OUTPUT_BINDING'
 detail=proof.get('optionalCompilerCompletion')
 if detail is None:
  assert proof['directJobTermination'] is False,'ISOLATED_RUST_UNCLASSIFIED_TERMINATION'
  return {'branch':'NATURAL_EMPTY_NO_FORCED_RUST_BRANCH','forcedCleanupQualified':False,'rootExit':0,'zeroMembersVerified':True,'outputs':outputs}
 assert detail['state']=='VERIFIED_OPTIONAL_TELEMETRY_CLEANUP' and detail['fixture']=='TINY_RUST_MSVC' and proof['directJobTermination'] is True,'ISOLATED_RUST_CLEANUP_CONTRACT'
 image=detail['helperIdentity'];identity=validate_telemetry_member(image)
 helper=[h for h in held if (h['pid'],h['creationFiletime'])==identity]
 assert len(held)==2 and len(helper)==1,'ISOLATED_RUST_UNKNOWN_HELD_MEMBER'
 before=proof['observedBefore']
 assert len(before)<=1 and all((h['pid'],h['creationFiletime'])==identity for h in before),'ISOLATED_RUST_UNKNOWN_PRESTOP_MEMBER'
 exercised=len(before)==1 and before[0]['exited'] is False and helper[0]['exitCode']==7
 return {'branch':'FORCED_PINNED_HELPER_CLEANUP_EXERCISED' if exercised else 'HELPER_EXIT_RACE_FORCED_KILL_UNPROVEN','forcedCleanupQualified':exercised,'rootExit':0,'zeroMembersVerified':True,'helperIdentity':image,'helperExitCode':helper[0]['exitCode'],'outputs':outputs}

def qualify_isolated_rust_report(guard,qualification,outputs,out):
 from runtime_report import write_runtime_report,read_runtime_report
 monitor=guard.report();assert monitor['commands'],'ISOLATED_RUST_COMMAND_EVIDENCE_MISSING'
 measurement=isolated_rust_measurement(qualification,monitor['commands'][-1],outputs)
 payload={'state':'PASS_ISOLATED_RUST_LIFECYCLE_AND_REPORT','measurement':measurement,'fullBuildGatesDisabled':True,'productionRustCleanupEnabled':False,'monitor':monitor}
 summary=write_runtime_report(payload,out,guard._resource_sample)
 actual,reconstructed=read_runtime_report(out)
 assert actual==summary and reconstructed==monitor,'ISOLATED_RUST_REPORT_RECONSTRUCTION'
 return {'state':'PASS','measurement':measurement,'index':summary['monitor']['index'],'originalMonitorSHA256':summary['monitor']['originalSHA256'],'fullBuildGatesDisabled':True,'productionRustCleanupEnabled':False}

class SetupOnlyComplete(RuntimeError):pass

def setup_only_main():
 import time,hashlib,re
 from unittest.mock import patch
 from census_supervisor import OwnedProcess
 from msvc_env import parse_exports
 assert os.name=='nt' and os.environ.get('GITHUB_REPOSITORY')=='TroubledPerson/Vibetram' and os.environ.get('GITHUB_REF')=='refs/heads/main' and os.environ.get('GITHUB_EVENT_NAME')=='push','SETUP_PROBE_TRUSTED_ENTRY'
 event=json.loads(pathlib.Path(os.environ['GITHUB_EVENT_PATH']).read_text());assert '[msvc-probe-191]' in event['head_commit']['message'] and any(x in event['head_commit']['message'] for x in ('[setup-lifecycle-only-191]','[compiler-lifecycle-only-191]')),'SETUP_PROBE_MARKER'
 source_check(ROOT);work=ROOT/'msvc-probe-work';out=ROOT/'msvc-probe-output';assert not work.exists() and not out.exists();assert shutil.disk_usage(ROOT).free>=MIN_FREE+MAX_OUTPUT
 work.mkdir();out.mkdir()
 for name in ('tmp','home','profile','profile/AppData/Local','profile/AppData/Roaming'):(work/name).mkdir(parents=True,exist_ok=True)
 env=clean_env(os.environ,work);observations=[];captured={};contracts=[];optional='[setup-optional-191]' in event['head_commit']['message'];compiler_only='[compiler-lifecycle-only-191]' in event['head_commit']['message'];rust_only='[rust-lifecycle-only-191]' in event['head_commit']['message']
 class ObservedSetup(OwnedProcess):
  def __init__(self):super().__init__();self.setup_target=False;self.compiler_target=False
  def start(self,args,cwd,env,**kw):
   self.rust_target=rust_only and pathlib.Path(args[0]).name.lower() in ('rustc','rustc.exe') and str(work/'tiny-msvc.rs') in [str(x) for x in args]
   self.rust_cleanup_probe=self.rust_target and '[rust-cleanup-qualification-only-191]' in event['head_commit']['message']
   if self.rust_cleanup_probe:self.rust_invocation=([str(x) for x in args],env.copy(),pathlib.Path(cwd),pathlib.Path(kw['stdout'].name),pathlib.Path(kw['stderr'].name))
   self.compiler_target=compiler_only and pathlib.Path(args[0]).name.lower()=='cl.exe' and str(work/'tiny-sdk.c') in [str(x) for x in args]
   self.compiler_target=self.compiler_target or self.rust_target
   self.setup_target=not compiler_only and len(args)==4 and pathlib.Path(args[0])==pathlib.Path(env['SystemRoot'])/'System32/cmd.exe' and args[1:3]==['/d','/c'] and pathlib.Path(args[3])==work/'msvc-setup.cmd'
   return super().start(args,cwd,env,**kw)
  def finish(self,terminate=False,sampler=None,seconds=3):
   if getattr(self,'rust_cleanup_probe',False) and not terminate and self.teardown is None:
    try:
     a,e,w,o,err=self.rust_invocation;verified=isolated_rust_cleanup(self,a,e,w,o,err,sampler);observations.append({'phase':'rust-cleanup-only','state':'PASS_'+verified['state'],'fixture':verified['fixture'],'zeroOwnedMembersVerified':verified['zeroOwnedMembersVerified'],'observedImages':getattr(self,'isolatedRustObservedImages',[])})
    except BaseException:
     observations.append({'phase':'rust-cleanup-only','state':'FAILED_CLOSED','observedImages':getattr(self,'isolatedRustObservedImages',[])})
     raise
   if (self.setup_target or self.compiler_target) and not terminate and self.teardown is None:
    row={'phase':'rust' if self.rust_target else ('compiler' if self.compiler_target else 'setup')};observations.append(row);natural_setup_exit(self,sampler,lambda j,r:owned_image(j,r,sampler),row,seconds)
   result=super().finish(terminate,sampler,seconds)
   if (self.setup_target or self.compiler_target) and observations:result['ownedCompletionObservation']=observations[-1]
   return result
 class SetupGuard(Guard):
  def run(self,args,*a,**kw):
   if compiler_only and not rust_only and pathlib.Path(args[0]).name.lower() in ('rustc','rustc.exe'):
    assert captured.get('compilerOutputsValidated'),'COMPILER_OUTPUTS_NOT_VALIDATED';raise SetupOnlyComplete('COMPILER_ONLY_COMPLETE')
   is_compiler=compiler_only and pathlib.Path(args[0]).name.lower()=='cl.exe' and str(work/'tiny-sdk.c') in [str(x) for x in args]
   if is_compiler:captured['compilerInvoked']=True;captured['rootCommandPurpose']='TINY_SDK_C_COMPILE_AND_LINK_WITHOUT_DEBUG_FLAGS'
   is_rust=rust_only and pathlib.Path(args[0]).name.lower() in ('rustc','rustc.exe') and str(work/'tiny-msvc.rs') in [str(x) for x in args]
   if is_rust:captured['rustInvoked']=True;captured['rustCommandPurpose']='TINY_PINNED_RUST_X64_MSVC_LINK_NO_APP_OR_CARGO'
   if optional and pathlib.Path(args[0]).name.lower()=='cl.exe' and str(work/'tiny-sdk.c') in [str(x) for x in args]:
    assert captured.get('requiredExportsPresent') and contracts,'SETUP_CONTRACT_NOT_QUALIFIED';raise SetupOnlyComplete('SETUP_ONLY_COMPLETE')
   if optional and len(args)==4 and pathlib.Path(args[-1])==work/'msvc-setup.cmd':
    from msvc_env import optional_setup_environment
    lines=(work/'msvc-setup.cmd').read_text().splitlines();calls=[re.fullmatch(r'call "([^"]+)" -no_logo -arch=x64 -host_arch=x64 >nul',line) for line in lines if line.lower().startswith('call ')]
    assert len(calls)==1 and calls[0],'SETUP_WRAPPER_CONTRACT'
    try:kw['env'],contract=optional_setup_environment(kw['env'],pathlib.Path(calls[0].group(1)));contracts.append(contract)
    except BaseException as error:contracts.append(getattr(error,'setup_contract_diagnostic',{'failureClass':type(error).__name__}));raise
   result=super().run(args,*a,**kw)
   if is_compiler:
    captured.update(compilerOutputsValidated=True,outputs=closed_compiler_outputs(work,guard.commands[-1]['ownedJobTeardown']),normalCompletionWithoutTermination=not guard.commands[-1]['ownedJobTeardown']['directJobTermination'])
   if is_rust:captured.update(rustOutputs=closed_compiler_outputs(work,guard.commands[-1]['ownedJobTeardown'],rust=True),rustOutputsValidated=True)
   if len(args)==4 and pathlib.Path(args[-1])==work/'msvc-setup.cmd':
    exports=parse_exports(result.stdout);captured.update(requiredExportsPresent=True,x64HostAndTarget=exports['VSCMD_ARG_TGT_ARCH']==exports['VSCMD_ARG_HOST_ARCH']=='x64',stdoutBytes=len(result.stdout.encode()),stdoutSHA256=hashlib.sha256(result.stdout.encode()).hexdigest(),stderrBytes=len(result.stderr.encode()),outputsReadOnlyAfterZeroMemberProof=True)
    if not optional and not compiler_only:raise SetupOnlyComplete('SETUP_ONLY_COMPLETE')
   return result
 guard=SetupGuard(ROOT,work,out,env);report={'state':'STARTED_COMPILER_ONLY' if compiler_only else 'STARTED_SETUP_ONLY','compiledAnything':False,'productionCompletionChanged':False,'observations':observations,'optionalSetupContract':contracts};start=time.monotonic()
 try:
  with patch('build_guard.OwnedProcess',ObservedSetup):
   try:qualify_msvc(env,work,guard)
   except SetupOnlyComplete:
    if compiler_only:
     pins=json.loads((work/'msvc-qualification.json').read_text());assert pins.get('qualifiedToolPinsVerified') is True and pins['compiledTinyFixtures']==1,'COMPILER_PROBE_PIN_OR_BOUNDARY'
     report.update(compilerOnly=True,pinnedInputsVerifiedBeforeCompile=True,stoppedBeforeRust=True)
    if optional:
     pins=json.loads((work/'msvc-qualification.json').read_text());assert pins.get('qualifiedToolPinsVerified') is True and pins['compiledTinyFixtures']==0,'SETUP_PINNED_INPUTS_NOT_VERIFIED'
     report.update(pinnedInputsVerifiedBeforeCompile=True,compilerBoundaryStoppedIntentionally=True)
    report.update(state=('PASS_COMPILER_ONLY_QUALIFIED_TELEMETRY_CLEANUP' if any(r['ownedJobTeardown'].get('optionalCompilerCompletion') for r in guard.commands) else 'PASS_COMPILER_ONLY_NATURAL_EXIT') if compiler_only else 'PASS_SETUP_ONLY_NATURAL_EXIT',captured=captured)
   else:
    assert rust_only and captured.get('rustOutputsValidated'),'SETUP_PROBE_COMPILATION_BOUNDARY'
    report.update(state='PASS_RUST_ONLY_NATURAL_OR_QUALIFIED_COMPLETION',stoppedBeforeCargo=True,captured=captured,fullBuildGatesDisabled=True,productionRustCleanupEnabled=False)
  if rust_only and '[rust-forced-evidence-only-191]' in event['head_commit']['message']:
   report['state']='ISOLATED_RUST_REPORT_PENDING'
   pins=json.loads((work/'msvc-qualification.json').read_text())
   report['isolatedEvidence']=qualify_isolated_rust_report(guard,pins,captured['rustOutputs'],out)
   report['state']='PASS_ISOLATED_RUST_LIFECYCLE_AND_REPORT'
 finally:
  report.update(elapsedSeconds=time.monotonic()-start,commands=guard.commands,sampledNotQuota=True,compiledAnything=captured.get('compilerInvoked',False),captured=captured)
  if compiler_only and captured.get('compilerInvoked') and report['state'] not in ('PASS_COMPILER_ONLY_NATURAL_EXIT','PASS_COMPILER_ONLY_QUALIFIED_TELEMETRY_CLEANUP'):
   failure=work/'failure-summary.json'
   if failure.is_file():
    failed=json.loads(failure.read_text());proof=failed.get('teardownDiagnostic',{});report['compilerFailureCleanup']=proof
    if proof.get('processTreeExitIndependentlyVerified') and proof.get('activeMembers')==0:
     try:report['retainedOutputsAfterFailureStop']=closed_compiler_outputs(work,proof)
     except BaseException as error:report['outputValidationFailureClass']=type(error).__name__
     if captured.get('rustInvoked'):
      try:report['retainedRustOutputsAfterFailureStop']=closed_compiler_outputs(work,proof,rust=True)
      except BaseException as error:report['rustOutputValidationFailureClass']=type(error).__name__
  report['productionCompletionChanged']=any(r['ownedJobTeardown'].get('optionalCompilerCompletion') for r in guard.commands)
  text=json.dumps(report,indent=2);assert len(text.encode())<=32768
  print('SETUP_LIFECYCLE_REPORT\n'+text,flush=True)
  summary=os.environ.get('GITHUB_STEP_SUMMARY')
  if summary:
   with open(summary,'a',encoding='utf-8') as f:f.write('## MSVC setup-only lifecycle\n\n```json\n'+text+'\n```\n')
 assert report['state'] in ('PASS_SETUP_ONLY_NATURAL_EXIT','PASS_COMPILER_ONLY_NATURAL_EXIT','PASS_COMPILER_ONLY_QUALIFIED_TELEMETRY_CLEANUP','PASS_RUST_ONLY_NATURAL_OR_QUALIFIED_COMPLETION','PASS_ISOLATED_RUST_LIFECYCLE_AND_REPORT'),'SETUP_LIFECYCLE_UNQUALIFIED'
 source_check(ROOT)

def main():
 event=json.loads(pathlib.Path(os.environ['GITHUB_EVENT_PATH']).read_text())
 if any(x in event['head_commit']['message'] for x in ('[setup-lifecycle-only-191]','[compiler-lifecycle-only-191]')):setup_only_main()
 else:link_main()
if __name__=='__main__':main()
