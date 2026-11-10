import unittest,struct,pathlib
from msvc_env import parse_exports,apply_exports,pe_x64,EXPORTS,discovery_env,required_inputs,library_directories
class MsvcPolicy(unittest.TestCase):
 def good(self):
  return {'PATH':'official;git','INCLUDE':'sdk','LIB':'libs','LIBPATH':'libs','VCToolsInstallDir':'tools','VCToolsVersion':'14.44.1','WindowsSdkDir':'sdk','WindowsSDKVersion':'10.0.26100.0','VSCMD_ARG_TGT_ARCH':'x64','VSCMD_ARG_HOST_ARCH':'x64'}
 def text(self,d):return '\n'.join(k+'='+v for k,v in d.items())
 def test_complete_export(self):self.assertEqual(parse_exports(self.text(self.good())),self.good())
 def test_environment_names_case_insensitive(self):self.assertEqual(parse_exports(self.text({k.lower():v for k,v in self.good().items()})),self.good())
 def test_missing_rejected(self):
  for k in self.good():
   d=self.good();del d[k]
   with self.assertRaises(AssertionError):parse_exports(self.text(d))
 def test_wrong_target_rejected(self):
  d=self.good();d['VSCMD_ARG_TGT_ARCH']='x86'
  with self.assertRaises(AssertionError):parse_exports(self.text(d))
 def test_wrong_host_rejected(self):
  d=self.good();d['VSCMD_ARG_HOST_ARCH']='arm64'
  with self.assertRaises(AssertionError):parse_exports(self.text(d))
 def test_duplicate_rejected(self):
  with self.assertRaises(AssertionError):parse_exports(self.text(self.good())+'\npath=other')
 def test_unapproved_environment_not_imported(self):
  e=apply_exports({'CARGO_HOME':'job-private'},{**self.good(),'GITHUB_TOKEN':'synthetic','PASSWORD':'synthetic'},'exact-link','exact-cl','exact-lib')
  self.assertNotIn('GITHUB_TOKEN',e);self.assertNotIn('PASSWORD',e);self.assertEqual(e['CARGO_HOME'],'job-private')
 def test_explicit_host_linker(self):
  e=apply_exports({},self.good(),'exact-link','exact-cl','exact-lib')
  self.assertEqual(e['CARGO_TARGET_X86_64_PC_WINDOWS_MSVC_LINKER'],'exact-link');self.assertEqual(e['CC_x86_64_pc_windows_msvc'],'exact-cl')
 def test_android_tool_selection_preserved(self):
  e=apply_exports({'CC_aarch64_linux_android':'ndk-clang'},self.good(),'link','cl','lib');self.assertEqual(e['CC_aarch64_linux_android'],'ndk-clang')
 def test_x64_pe(self):
  b=bytearray(90);b[:2]=b'MZ';struct.pack_into('<I',b,60,64);b[64:68]=b'PE\0\0';struct.pack_into('<H',b,68,0x8664);pe_x64(b)
  struct.pack_into('<H',b,68,0x14c)
  with self.assertRaises(AssertionError):pe_x64(b)
 def test_non_pe_denied(self):
  with self.assertRaises(AssertionError):pe_x64(b'not an executable')
 def test_discovery_adds_only_public_registration_locations(self):
  base={'PATH':'tools'};env=discovery_env(base,{'ProgramData':r'C:\ProgramData','ALLUSERSPROFILE':r'C:\ProgramData','GITHUB_TOKEN':'synthetic'})
  self.assertEqual(base,{'PATH':'tools'});self.assertNotIn('GITHUB_TOKEN',env);self.assertEqual(set(env),{'PATH','ProgramData','ALLUSERSPROFILE'})
 def test_unexpected_discovery_location_rejected(self):
  with self.assertRaises(AssertionError):discovery_env({}, {'ProgramData':r'D:\unexpected','ALLUSERSPROFILE':r'C:\ProgramData'})
 def test_identical_prefix_export_repeats_are_idempotent(self):
  self.assertEqual(parse_exports(self.text(self.good())+'\nLIBPATH=libs\nPath=official;git'),self.good())
 def test_ucrt_headers_are_sdk_inputs(self):
  files=required_inputs(pathlib.Path('vc'),pathlib.Path('sdk'),'10.0.1.0')
  self.assertIn(pathlib.Path('sdk/Include/10.0.1.0/ucrt/stdio.h'),files);self.assertIn(pathlib.Path('vc/include/vcruntime.h'),files);self.assertNotIn(pathlib.Path('vc/include/stdio.h'),files)
 def test_windows_library_normalization(self):
  dirs=library_directories('C:/SDK//lib/10.0.1.0/um/x64;C:/VC/lib/x64/')
  self.assertIn(pathlib.PureWindowsPath('c:/sdk/lib/10.0.1.0/um/x64'),dirs);self.assertIn(pathlib.PureWindowsPath('C:/VC/lib/x64'),dirs)
 def test_relative_library_path_rejected(self):
  with self.assertRaises(AssertionError):library_directories('relative/lib')



class SetupLifecycleObservation(unittest.TestCase):
 def fake(self,duration=.2,active_override=None):
  import types
  clock=[0];job=types.SimpleNamespace(job=1);job.observe=lambda:[{'pid':10,'creationFiletime':20}] if clock[0]<duration else [];job.api=types.SimpleNamespace(active_count=lambda _:int(clock[0]<duration) if active_override is None else active_override)
  def sleep(n):clock[0]+=n
  return job,clock,sleep
 def run_observation(self,duration=.2,seconds=.3):
  from msvc_probe import natural_setup_exit
  job,clock,sleep=self.fake(duration);report={};samples=[];sampler=type('Sampler',(),{'tick':lambda _:samples.append(clock[0])})()
  result=natural_setup_exit(job,sampler,lambda _,r:dict(r),report,seconds,lambda:clock[0],sleep);return result,samples
 def test_natural_exit_within_bound_requires_zero_counts(self):
  row,samples=self.run_observation();self.assertEqual(row['state'],'NATURAL_ZERO_ACTIVE_MEMBERS');self.assertGreaterEqual(len(samples),3);self.assertEqual(row['lastActiveCount'],0);self.assertEqual(len(row['members']),1)
 def test_no_members_is_not_enough_without_zero_active(self):
  from msvc_probe import natural_setup_exit
  job,clock,sleep=self.fake(0,1);report={}
  with self.assertRaisesRegex(TimeoutError,'NATURAL_EXIT_DEADLINE'):natural_setup_exit(job,None,lambda _,r:r,report,.1,lambda:clock[0],sleep)
  self.assertEqual(report['state'],'NATURAL_EXIT_NOT_VERIFIED_WITHIN_BOUND')
 def test_persistent_children_do_not_become_success(self):
  from msvc_probe import natural_setup_exit
  job,clock,sleep=self.fake(10);report={}
  with self.assertRaises(TimeoutError):natural_setup_exit(job,None,lambda _,r:r,report,.1,lambda:clock[0],sleep)
  self.assertLessEqual(clock[0],.1);self.assertNotEqual(report['state'],'NATURAL_ZERO_ACTIVE_MEMBERS')
 def test_metadata_time_is_inside_natural_exit_window(self):
  from msvc_probe import natural_setup_exit
  job,clock,sleep=self.fake(.05)
  def metadata(_,r):clock[0]=.2;return r
  with self.assertRaises(TimeoutError):natural_setup_exit(job,None,metadata,{},.1,lambda:clock[0],sleep)
 def test_every_later_observed_member_is_recorded(self):
  from msvc_probe import natural_setup_exit
  job,clock,sleep=self.fake(.2);job.observe=lambda:[] if clock[0]>=.2 else [{'pid':10,'creationFiletime':20}]+([{'pid':11,'creationFiletime':21}] if clock[0]>.05 else []);report={}
  natural_setup_exit(job,None,lambda _,r:r,report,.3,lambda:clock[0],sleep);self.assertEqual([r['pid'] for r in report['members']],[10,11])
 def test_denial_and_identity_errors_are_not_retried(self):
  from msvc_probe import natural_setup_exit
  for error in [PermissionError(5,'synthetic'),AssertionError('SYNTHETIC_IDENTITY_CHANGE')]:
   job,clock,sleep=self.fake();calls=[]
   def observe():calls.append(1);raise error
   job.observe=observe
   with self.assertRaises(type(error)):natural_setup_exit(job,None,lambda _,r:r,{},.1,lambda:clock[0],sleep)
   self.assertEqual(len(calls),1)
 def test_supervision_failure_is_fatal(self):
  from msvc_probe import natural_setup_exit
  job,clock,sleep=self.fake()
  def tick(_):raise AssertionError('SYNTHETIC_FLOOR')
  sampler=type('Sampler',(),{'tick':tick})()
  with self.assertRaisesRegex(AssertionError,'SYNTHETIC_FLOOR'):natural_setup_exit(job,sampler,lambda _,r:r,{},.1,lambda:clock[0],sleep)
 def test_invalid_bound_is_rejected(self):
  from msvc_probe import natural_setup_exit
  job,clock,sleep=self.fake()
  for seconds in [0,3.01]:
   with self.assertRaises(AssertionError):natural_setup_exit(job,None,lambda _,r:r,{},seconds,lambda:clock[0],sleep)
 def test_production_policy_unchanged_probe_stops_before_compiler(self):
  import inspect,msvc_probe
  text=inspect.getsource(msvc_probe.setup_only_main);self.assertIn('SetupOnlyComplete',text);self.assertIn('parse_exports(result.stdout)',text);self.assertIn('outputsReadOnlyAfterZeroMemberProof',text);self.assertIn("patch('build_guard.OwnedProcess'",text)
 def test_real_late_child_output_is_captured_after_all_owned_members_exit(self):
  import os,sys,uuid,time
  from census_supervisor import OwnedProcess,Sampler
  from msvc_probe import natural_setup_exit
  base=pathlib.Path(os.environ.get('VIBETRAM_TEST_TMP',os.environ.get('RUNNER_TEMP',str(pathlib.Path(__file__).parents[1]/'ci-unit-output'))))/('late-output-'+uuid.uuid4().hex);base.mkdir(parents=True)
  env={k:os.environ[k] for k in ('SystemRoot','WINDIR','PATH','PATHEXT') if k in os.environ};env.update(TEMP=str(base),TMP=str(base),PYTHONNOUSERSITE='1',PYTHONDONTWRITEBYTECODE='1')
  child='import time;time.sleep(.2);print("late owned output",flush=True)';parent='import subprocess,sys;subprocess.Popen([sys.executable,"-B","-c",'+repr(child)+'],stdout=sys.stdout,stderr=sys.stderr,creationflags=subprocess.CREATE_NO_WINDOW);print("parent complete",flush=True)';job=OwnedProcess()
  try:
   with (base/'out.log').open('xb') as out,(base/'err.log').open('xb') as err:
    job.start([sys.executable,'-B','-c',parent],base,env,stdout=out,stderr=err);deadline=time.monotonic()+3
    while job.poll() is None:self.assertLess(time.monotonic(),deadline);time.sleep(.01)
    report={};natural_setup_exit(job,Sampler(lambda:None),lambda _,r:r,report);proof=job.finish();self.assertTrue(proof['processTreeExitIndependentlyVerified']);self.assertEqual(proof['activeMembers'],0)
   text=(base/'out.log').read_text();self.assertIn('parent complete',text);self.assertIn('late owned output',text);self.assertEqual((base/'err.log').read_bytes(),b'')
  finally:job.close()

if __name__=='__main__':unittest.main()
