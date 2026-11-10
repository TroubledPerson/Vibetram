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




class OptionalSetupContract(unittest.TestCase):
 def text(self,guard='if "%VSCMD_SKIP_SENDTELEMETRY%"=="" (',extra=''):
  module="'%VSINSTALLDIR%Common7\\Tools\\Microsoft.VisualStudio.DevShell.dll'"
  return '\n'.join(['REM synthetic optional setup contract',guard,'start /B "" powershell.exe -NoProfile -Command "& {Import-Module '+module+'; Send-VsDevShellTelemetry -NewInstanceType Cmd; }"',extra,')'])
 def test_empty_variable_guard_recognizes_only_optional_telemetry(self):
  from msvc_env import telemetry_setup_contract
  row=telemetry_setup_contract(self.text());self.assertTrue(row['nonemptyValueSkipsBlock']);self.assertEqual(row['asyncCommands'],1);self.assertFalse(row['requiredBuildStatementsInBlock'])
 def test_not_defined_and_guarded_module_variants(self):
  from msvc_env import telemetry_setup_contract
  text=self.text('if not defined VSCMD_SKIP_SENDTELEMETRY (');module="'%VSINSTALLDIR%Common7\\Tools\\Microsoft.VisualStudio.DevShell.dll'";text=text.replace('& {Import-Module','& {if (Test-Path '+module+') {Import-Module').replace('Cmd; }"','Cmd; }}"');self.assertEqual(telemetry_setup_contract(text)['asyncCommands'],1)
 def test_wrong_guard_polarity_or_duplicate_guards_fail(self):
  from msvc_env import telemetry_setup_contract
  for text in [self.text('if defined VSCMD_SKIP_SENDTELEMETRY ('),self.text('if "%VSCMD_SKIP_SENDTELEMETRY%"=="1" ('),self.text()+'\n'+self.text()]:
   with self.assertRaisesRegex(AssertionError,'GUARD_UNRECOGNIZED'):telemetry_setup_contract(text)
 def test_build_work_and_extra_powershell_commands_are_rejected(self):
  from msvc_env import telemetry_setup_contract
  for text in [self.text(extra='set INCLUDE=required'),self.text().replace('Cmd; }','Cmd; Write-Output required; }'),self.text().replace('Send-VsDevShellTelemetry','Other-RequiredSetup'),self.text().replace('start /B','start /wait')]:
   with self.assertRaises(AssertionError):telemetry_setup_contract(text)
 def test_unbalanced_and_multiline_input_are_rejected(self):
  from msvc_env import telemetry_setup_contract
  for text in [self.text()[:-1],self.text().replace(' -Command',' ^\n -Command')]:
   with self.assertRaises(AssertionError):telemetry_setup_contract(text)
 def fixture(self):
  import os,uuid,hashlib
  root=pathlib.Path(os.environ.get('VIBETRAM_TEST_TMP',os.environ.get('RUNNER_TEMP',str(pathlib.Path(__file__).parents[1]/'ci-unit-output'))))/('setup-contract-'+uuid.uuid4().hex);root.mkdir(parents=True);setup=root/'VsDevCmd.bat';setup.write_text(self.text(),encoding='utf-8');return setup,{'setupSHA256':hashlib.sha256(setup.read_bytes()).hexdigest()}
 def test_job_local_env_change_preserves_inputs_and_script(self):
  from msvc_env import optional_setup_environment
  setup,pins=self.fixture();before=setup.read_bytes();env={'PATH':'qualified','INCLUDE':'same','LIB':'same','LIBPATH':'same'};out,contract=optional_setup_environment(env,setup,pins)
  self.assertEqual(set(out)-set(env),{'VSCMD_SKIP_SENDTELEMETRY'});self.assertEqual(out['VSCMD_SKIP_SENDTELEMETRY'],'1');self.assertEqual({k:out[k] for k in env},env);self.assertNotIn('VSCMD_SKIP_SENDTELEMETRY',env);self.assertEqual(setup.read_bytes(),before);self.assertFalse(contract['securitySettingsChanged'])
 def test_setup_pin_mismatch_does_not_apply_option(self):
  from msvc_env import optional_setup_environment
  setup,pins=self.fixture()
  with self.assertRaisesRegex(AssertionError,'PIN_MISMATCH'):optional_setup_environment({},setup,{'setupSHA256':'0'*64})
 def test_access_denial_and_link_do_not_apply_option(self):
  from msvc_env import optional_setup_environment
  from unittest.mock import patch
  import types
  setup,pins=self.fixture()
  with patch.object(pathlib.Path,'lstat',side_effect=PermissionError(5,'synthetic')):
   with self.assertRaises(PermissionError):optional_setup_environment({},setup,pins)
  original=pathlib.Path.lstat
  def link(path):
   row=original(path)
   return types.SimpleNamespace(st_file_attributes=0x400,st_reparse_tag=0xa000000c,st_mode=row.st_mode) if path==setup else row
  with patch.object(pathlib.Path,'lstat',link):
   with self.assertRaisesRegex(AssertionError,'SCRIPT_LINK'):optional_setup_environment({},setup,pins)
 def test_setup_file_replacement_is_fatal(self):
  from msvc_env import optional_setup_environment
  from unittest.mock import patch
  import types
  setup,pins=self.fixture();original=pathlib.Path.lstat;calls=[0]
  def changed(path):
   row=original(path)
   if path==setup:
    calls[0]+=1
    if calls[0]>=3:return types.SimpleNamespace(st_dev=row.st_dev,st_ino=row.st_ino+1,st_mode=row.st_mode,st_size=row.st_size,st_mtime_ns=row.st_mtime_ns)
   return row
  with patch.object(pathlib.Path,'lstat',changed):
   with self.assertRaisesRegex(AssertionError,'SCRIPT_CHANGED'):optional_setup_environment({},setup,pins)
 def test_probe_stops_before_compilation_and_requires_pins(self):
  import inspect,msvc_probe
  text=inspect.getsource(msvc_probe.setup_only_main);self.assertIn('qualifiedToolPinsVerified',text);self.assertIn('compiledTinyFixtures',text);self.assertIn('optional_setup_environment',text);self.assertIn("pathlib.Path(args[0]).name.lower()=='cl.exe'",text)


class OptionalContractDiagnostics(unittest.TestCase):
 def test_unknown_statement_reports_structure_without_private_payload(self):
  import os,uuid,hashlib
  from msvc_env import optional_setup_environment
  root=pathlib.Path(os.environ.get('VIBETRAM_TEST_TMP',os.environ.get('RUNNER_TEMP',str(pathlib.Path(__file__).parents[1]/'ci-unit-output'))))/('contract-diag-'+uuid.uuid4().hex);root.mkdir(parents=True);setup=root/'VsDevCmd.bat'
  text=OptionalSetupContract().text(extra='call :UnknownTask private_payload_must_not_be_disclosed');setup.write_text(text,encoding='utf-8');pins={'setupSHA256':hashlib.sha256(setup.read_bytes()).hexdigest()}
  with self.assertRaisesRegex(AssertionError,'UNKNOWN_STATEMENT') as caught:optional_setup_environment({},setup,pins)
  row=caught.exception.setup_contract_diagnostic;self.assertTrue(row['unrecognizedStatementsRemainFatal']);self.assertTrue(row['rawScriptNotPublished']);self.assertNotIn('private_payload',str(row));self.assertIn('call',[x['statementKind'] for x in row['branchStatementMetadata']])





class ExactPinnedTelemetryBranch(unittest.TestCase):
 def test_both_vendor_execution_paths_have_one_optional_purpose(self):
  from msvc_env import PINNED_TELEMETRY_LINES,pinned_telemetry_contract
  row=pinned_telemetry_contract(PINNED_TELEMETRY_LINES,249,256)
  self.assertTrue(row['debugNonemptySynchronousTelemetry']);self.assertTrue(row['debugEmptyAsynchronousTelemetry']);self.assertEqual(row['asynchronousPowerShellMajorMinimum'],3);self.assertEqual(row['moduleReference'],'%~dp0');self.assertTrue(row['moduleRelativeToPinnedSetupDirectory']);self.assertFalse(row['requiredBuildStatementsInBlock'])
 def test_each_changed_statement_extra_or_missing_line_fails(self):
  from msvc_env import PINNED_TELEMETRY_LINES,pinned_telemetry_contract
  for i in range(8):
   changed=list(PINNED_TELEMETRY_LINES);changed[i]='0'*64
   with self.assertRaisesRegex(AssertionError,'PINNED_BRANCH_CHANGED'):pinned_telemetry_contract(changed,249,256)
  for changed in [PINNED_TELEMETRY_LINES[:-1],PINNED_TELEMETRY_LINES+('0'*64,)]:
   with self.assertRaises(AssertionError):pinned_telemetry_contract(changed,249,256)
 def test_pinned_window_cannot_hide_extra_work(self):
  from msvc_env import PINNED_TELEMETRY_LINES,pinned_telemetry_contract
  for end in [255,257]:
   with self.assertRaises(AssertionError):pinned_telemetry_contract(PINNED_TELEMETRY_LINES,249,end)
 def test_whole_script_pin_is_still_enforced_before_branch_acceptance(self):
  import inspect,msvc_env
  text=inspect.getsource(msvc_env.optional_setup_environment);self.assertLess(text.index("digest==pins['setupSHA256']"),text.index('telemetry_setup_contract(text)'));self.assertIn("result['VSCMD_SKIP_SENDTELEMETRY']='1'",text)
 def test_no_unrecognized_debug_branch_is_accepted(self):
  from msvc_env import telemetry_setup_contract
  text=OptionalSetupContract().text(extra='if "%VSCMD_DEBUG%" NEQ "" (\necho debug\n) else (\ncall :UnknownWork\n)')
  with self.assertRaises(AssertionError):telemetry_setup_contract(text)




class ProductionOptionalSetupIntegration(unittest.TestCase):
 def test_qualified_helper_is_applied_only_to_setup_child(self):
  import os,uuid,json,types
  from unittest.mock import patch,Mock
  import msvc_env
  root=pathlib.Path(os.environ.get('VIBETRAM_TEST_TMP',os.environ.get('RUNNER_TEMP',str(pathlib.Path(__file__).parents[1]/'ci-unit-output'))))/('setup-seam-'+uuid.uuid4().hex);root.mkdir(parents=True);install=root/'synthetic-vs';base={'PATH':str(root/'bin'),'SystemRoot':'C:/Windows','PROGRAMFILES(X86)':str(root/'programfiles')};captured=[];helperInputs=[]
  class StopSetup(RuntimeError):pass
  def helper(env,setup):helperInputs.append(dict(env));self.assertEqual(setup,install/'Common7/Tools/VsDevCmd.bat');return {**env,'VSCMD_SKIP_SENDTELEMETRY':'1'},{'scope':'ONE_SANITIZED_SETUP_CHILD_ENVIRONMENT'}
  class Guard:
   def run(_,args,**kw):
    name=pathlib.Path(args[0]).name.lower()
    if name in ('pwsh','pwsh.exe'):return types.SimpleNamespace(stdout=json.dumps([{'name':'vswhere.exe','sha256':'synthetic'}]))
    if name=='vswhere.exe':return types.SimpleNamespace(stdout=str(install))
    if name=='cmd.exe':captured.append(dict(kw['env']));raise StopSetup('SYNTHETIC_SETUP_BOUNDARY')
    raise AssertionError('UNEXPECTED_TOOL_IN_SEAM')
   def check(_):return None
  with patch.object(pathlib.Path,'is_file',return_value=True),patch.object(msvc_env.shutil,'which',side_effect=lambda name,path=None:str(root/'bin'/name)),patch.object(msvc_env,'optional_setup_environment',side_effect=helper) as spy,patch.dict(os.environ,{'ProgramData':'C:\\ProgramData','ALLUSERSPROFILE':'C:\\ProgramData'}):
   with self.assertRaisesRegex(StopSetup,'SYNTHETIC_SETUP_BOUNDARY'):msvc_env.qualify_msvc(base,root,Guard())
  self.assertEqual(spy.call_count,1);self.assertEqual(len(captured),1);self.assertEqual(captured[0]['VSCMD_SKIP_SENDTELEMETRY'],'1');self.assertNotIn('VSCMD_SKIP_SENDTELEMETRY',base);self.assertNotIn('VSCMD_SKIP_SENDTELEMETRY',helperInputs[0]);self.assertEqual(captured[0]['PATH'],base['PATH']);self.assertEqual(captured[0]['SystemRoot'],base['SystemRoot'])




class CompilerCompletionProbe(unittest.TestCase):
 def files(self):
  import os,uuid,struct
  root=pathlib.Path(os.environ.get('VIBETRAM_TEST_TMP',os.environ.get('RUNNER_TEMP',str(pathlib.Path(__file__).parents[1]/'ci-unit-output'))))/('compiler-output-'+uuid.uuid4().hex);root.mkdir(parents=True)
  obj=bytearray(64);struct.pack_into('<HHIIIHH',obj,0,0x8664,1,0,0,0,0,0);struct.pack_into('<II',obj,36,4,60)
  exe=bytearray(256);exe[:2]=b'MZ';struct.pack_into('<I',exe,60,64);exe[64:68]=b'PE'+bytes(2);struct.pack_into('<HH',exe,68,0x8664,1);struct.pack_into('<H',exe,84,112);struct.pack_into('<H',exe,88,0x20b);struct.pack_into('<II',exe,216,16,240)
  (root/'tiny-sdk.obj').write_bytes(obj);(root/'tiny-sdk.exe').write_bytes(exe);proof={'processTreeExitIndependentlyVerified':True,'activeMembers':0,'knownHandlesExited':True};return root,proof
 def test_closed_outputs_validate_x64_headers_sections_and_hashes(self):
  from msvc_probe import closed_compiler_outputs
  root,proof=self.files();rows=closed_compiler_outputs(root,proof);self.assertEqual(len(rows),2);self.assertTrue(rows[0]['x64COFFSectionBoundsValidated']);self.assertTrue(rows[1]['x64PESectionBoundsValidated']);self.assertTrue(all(len(r['sha256'])==64 and r['closedOwnedWritersVerified'] for r in rows))
 def test_active_unknown_or_unexited_writers_are_never_accepted(self):
  from msvc_probe import closed_compiler_outputs
  root,proof=self.files()
  for patcher in ({'activeMembers':1},{'processTreeExitIndependentlyVerified':False},{'knownHandlesExited':False}):
   with self.assertRaisesRegex(AssertionError,'WRITERS_UNVERIFIED'):closed_compiler_outputs(root,{**proof,**patcher})
 def test_truncated_pe_and_coff_fail(self):
  from msvc_probe import closed_compiler_outputs
  for name in ('tiny-sdk.obj','tiny-sdk.exe'):
   root,proof=self.files();(root/name).write_bytes((root/name).read_bytes()[:30])
   with self.assertRaises(AssertionError):closed_compiler_outputs(root,proof)
 def test_out_of_bounds_sections_are_rejected(self):
  from msvc_probe import closed_compiler_outputs
  import struct
  for name,offset in [('tiny-sdk.obj',36),('tiny-sdk.exe',216)]:
   root,proof=self.files();data=bytearray((root/name).read_bytes());struct.pack_into('<II',data,offset,1000,2000);(root/name).write_bytes(data)
   with self.assertRaises(AssertionError):closed_compiler_outputs(root,proof)
 def test_output_denial_not_retried(self):
  from msvc_probe import closed_compiler_outputs
  from unittest.mock import patch
  root,proof=self.files()
  with patch.object(pathlib.Path,'lstat',side_effect=PermissionError(5,'synthetic')) as call:
   with self.assertRaises(PermissionError):closed_compiler_outputs(root,proof)
  self.assertEqual(call.call_count,1)
 def test_changed_output_identity_cannot_pass(self):
  from msvc_probe import closed_compiler_outputs
  from unittest.mock import patch
  import types
  root,proof=self.files();original=pathlib.Path.lstat;calls=[0]
  def changed(p):
   row=original(p)
   if p==root/'tiny-sdk.obj':
    calls[0]+=1
    if calls[0]>1:return types.SimpleNamespace(st_dev=row.st_dev,st_ino=row.st_ino+1,st_mode=row.st_mode,st_size=row.st_size,st_mtime_ns=row.st_mtime_ns)
   return row
  with patch.object(pathlib.Path,'lstat',changed):
   with self.assertRaisesRegex(AssertionError,'OUTPUT_CHANGED'):closed_compiler_outputs(root,proof)
 def test_compiler_probe_is_separate_and_stops_before_rust(self):
  import inspect,msvc_probe
  text=inspect.getsource(msvc_probe.setup_only_main);self.assertIn('[compiler-lifecycle-only-191]',text);self.assertIn('COMPILER_ONLY_COMPLETE',text);self.assertIn("'rustc','rustc.exe'",text);self.assertIn('rootCommandPurpose',text);self.assertIn('compilerFailureCleanup',text);self.assertIn("report['productionCompletionChanged']=False",text)
 def test_owned_image_uses_held_identity_and_sanitized_vendor_metadata(self):
  import inspect,msvc_probe
  text=inspect.getsource(msvc_probe.owned_image);self.assertIn('members_held',text);self.assertIn('creationFiletime',text);self.assertIn('QueryFullProcessImageNameW',text);self.assertIn('FileDescription',text);self.assertIn('commandLineNotRead',text);self.assertNotIn('Get-CimInstance',text)

if __name__=='__main__':unittest.main()
