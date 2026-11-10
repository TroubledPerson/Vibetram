import unittest,pathlib,json,struct
from build_guard import qualified_license_link,NUCLEO_LICENSE_BLOB,H3_LICENSE_BLOB,LICENSE_RULES,license_rule,git_blob_identity,normalized_license_blob
from build_guard import limits,MIN_FREE,MAX_OUTPUT,MAX_SECONDS,MAX_LOG,android_env,clean_env,artifact,test_count,redact
from cloud_build import elf_check
class BuildPolicy(unittest.TestCase):
 def test_limits_boundary(self):self.assertIsNone(limits(MIN_FREE,MAX_OUTPUT,MAX_SECONDS,MAX_LOG))
 def test_disk(self):self.assertEqual(limits(MIN_FREE-1,0,0,0),'FREE_SPACE_GUARD')
 def test_output(self):self.assertEqual(limits(MIN_FREE,MAX_OUTPUT+1,0,0),'OUTPUT_THRESHOLD')
 def test_time(self):self.assertEqual(limits(MIN_FREE,0,MAX_SECONDS+1,0),'TRIAL_DEADLINE')
 def test_log(self):self.assertEqual(limits(MIN_FREE,0,0,MAX_LOG+1),'COMMAND_LOG_THRESHOLD')
 def test_no_child_credentials(self):
  e=clean_env({'PATH':'tools','GITHUB_TOKEN':'synthetic-fixture','ACTIONS_RUNTIME_TOKEN':'synthetic-fixture'},pathlib.Path('owned'));self.assertNotIn('GITHUB_TOKEN',e);self.assertNotIn('ACTIONS_RUNTIME_TOKEN',e);self.assertEqual(e['CARGO_BUILD_JOBS'],'2')
 def test_explicit_android_compiler(self):
  e=android_env({},pathlib.Path('ndk'));self.assertTrue(e['CC_aarch64_linux_android'].endswith('clang.exe'));self.assertIn('android29',e['CFLAGS_aarch64_linux_android']);self.assertEqual(e['CXXSTDLIB_aarch64_linux_android'],'c++_static');self.assertNotIn('CC',e)
 def test_one_artifact(self):
  x={'reason':'compiler-artifact','target':{'name':'codex_app_server_transport'},'profile':{'test':True},'executable':'native.exe'};self.assertEqual(artifact(json.dumps(x)),pathlib.Path('native.exe'))
 def test_missing_artifact(self):
  with self.assertRaises(AssertionError):artifact('{}')
 def test_ambiguous_artifact(self):
  def x(p):return json.dumps({'reason':'compiler-artifact','target':{'name':'codex_app_server_transport'},'profile':{'test':True},'executable':p})
  with self.assertRaises(AssertionError):artifact(x('one.exe')+'\n'+x('two.exe'))
 def test_nonempty_tests(self):self.assertEqual(test_count('test result: ok. 19 passed; 0 failed; 0 ignored;'),19)
 def test_empty_or_ignored_tests(self):
  for t in ('test result: ok. 0 passed; 0 failed; 0 ignored;','test result: ok. 2 passed; 0 failed; 1 ignored;'):
   with self.assertRaises(AssertionError):test_count(t)
 def test_elf_alignment(self):
  b=bytearray(120);b[:5]=b'\x7fELF\x02';struct.pack_into('<H',b,16,3);struct.pack_into('<H',b,18,183);struct.pack_into('<Q',b,32,64);struct.pack_into('<HH',b,54,56,1);struct.pack_into('<IIQQQQQQ',b,64,1,5,0,0,0,0,0,16384);elf_check(b);struct.pack_into('<Q',b,112,4096)
  with self.assertRaises(AssertionError):elf_check(b)
 def test_redaction(self):self.assertNotIn('sk-'+'a'*30,redact('sk-'+'a'*30))
 def test_pinned_license_link(self):self.assertTrue(qualified_license_link('git/checkouts/nucleo-a123/4253de9/matcher/LICENSE','../LICENSE',NUCLEO_LICENSE_BLOB))
 def test_link_wrong_target(self):self.assertFalse(qualified_license_link('git/checkouts/nucleo-a123/4253de9/matcher/LICENSE','../../outside',NUCLEO_LICENSE_BLOB))
 def test_link_wrong_blob(self):self.assertFalse(qualified_license_link('git/checkouts/nucleo-a123/4253de9/matcher/LICENSE','../LICENSE','0'*40))
 def test_link_wrong_checkout(self):self.assertFalse(qualified_license_link('git/checkouts/nucleo-a123/deadbee/matcher/LICENSE','../LICENSE',NUCLEO_LICENSE_BLOB))
 def test_link_wrong_repo(self):self.assertFalse(qualified_license_link('git/checkouts/other-a123/4253de9/matcher/LICENSE','../LICENSE',NUCLEO_LICENSE_BLOB))
 def test_link_escape(self):self.assertFalse(qualified_license_link('../git/checkouts/nucleo-a123/4253de9/matcher/LICENSE','../LICENSE',NUCLEO_LICENSE_BLOB))
 def test_link_absolute_target(self):self.assertFalse(qualified_license_link('git/checkouts/nucleo-a123/4253de9/matcher/LICENSE','C:/private',NUCLEO_LICENSE_BLOB))
 def test_link_windows_separators(self):self.assertTrue(qualified_license_link(chr(92).join(('git','checkouts','nucleo-a123','4253de9','matcher','LICENSE')),'..'+chr(92)+'LICENSE',NUCLEO_LICENSE_BLOB))
 def test_git_blob_known_vector(self):self.assertEqual(git_blob_identity(b'hello'+bytes([10])),'ce013625030ba8dba906f756967f9e9ca394464a')
 def test_license_line_endings_only(self):self.assertEqual(normalized_license_blob(b'hello'+bytes([13,10])),normalized_license_blob(b'hello'+bytes([10])));self.assertNotEqual(normalized_license_blob(b'hello '),normalized_license_blob(b'hello'))
 def test_license_non_utf8_rejected(self):
  with self.assertRaises(UnicodeDecodeError):normalized_license_blob(bytes([255]))
 def test_all_five_exact_license_rules(self):
  self.assertEqual(len(LICENSE_RULES),5)
  for repo,commit,path,identity,size in LICENSE_RULES:
   relative='/'.join(('git','checkouts',repo+'-a123',commit[:7],*path))
   self.assertTrue(qualified_license_link(relative,'../LICENSE',identity))
   self.assertEqual(license_rule(relative,'../LICENSE')[4],size)
 def test_h3_unknown_subpackage_denied(self):self.assertFalse(qualified_license_link('git/checkouts/h3-a123/e07e694/unknown/LICENSE','../LICENSE',H3_LICENSE_BLOB))
 def test_h3_wrong_commit_denied(self):self.assertFalse(qualified_license_link('git/checkouts/h3-a123/deadbee/h3/LICENSE','../LICENSE',H3_LICENSE_BLOB))
 def test_cross_repository_blob_denied(self):self.assertFalse(qualified_license_link('git/checkouts/h3-a123/e07e694/h3/LICENSE','../LICENSE',NUCLEO_LICENSE_BLOB))
 def test_h3_wrong_target_denied(self):self.assertIsNone(license_rule('git/checkouts/h3-a123/e07e694/h3/LICENSE','../../LICENSE'))
 def test_h3_nonlicense_link_denied(self):self.assertIsNone(license_rule('git/checkouts/h3-a123/e07e694/h3/code','../LICENSE'))




class QualifiedRustExecutables(unittest.TestCase):
 def fixture(self):
  import os,uuid
  base=pathlib.Path(os.environ.get('VIBETRAM_TEST_TMP',os.environ.get('RUNNER_TEMP',str(pathlib.Path(__file__).parents[1]/'ci-unit-output'))))/('resolver-'+uuid.uuid4().hex);base.mkdir(parents=True)
  shim=base/'proxy bin';shim.mkdir();native=base/'rustup/toolchains/1.95.0-x86_64-pc-windows-msvc/bin';native.mkdir(parents=True);cargo=base/'cargo';cargo.mkdir()
  body=b'MZ'+b'synthetic nonexecutable fixture'*8
  for n in ('rustup.exe','cargo.exe','rustc.exe'):(shim/n).write_bytes(body)
  for n in ('cargo.exe','rustc.exe'):(native/n).write_bytes(body+b'pinned native synthetic')
  env={'PATH':str(shim),'RUSTUP_HOME':str(base/'rustup'),'CARGO_HOME':str(cargo),'RUSTUP_TOOLCHAIN':'1.95.0-x86_64-pc-windows-msvc','RUSTUP_AUTO_INSTALL':'0'}
  return base,shim,native,env
 def test_both_rust_entry_points_bind_selected_and_pinned_identity(self):
  from build_guard import qualified_executable
  _,shim,_,env=self.fixture()
  for name in ('cargo','rustc','cargo.exe','RUSTC.EXE'):
   args,binding=qualified_executable([name,'--version'],env);self.assertEqual(pathlib.Path(args[0]),shim/(name.lower().removesuffix('.exe')+'.exe'));self.assertEqual(args[1: ],['--version']);self.assertEqual(binding['route'],'PINNED_RUSTUP_PROXY_ON_PATH');self.assertTrue(binding['versionRecheckRequired']);self.assertEqual(len(binding['selected']['sha256']),64)
 def test_native_exact_pinned_path_is_supported(self):
  from build_guard import qualified_executable
  _,_,native,env=self.fixture();env['PATH']=str(native);args,binding=qualified_executable(['cargo'],env);self.assertEqual(pathlib.Path(args[0]),native/'cargo.exe');self.assertEqual(binding['route'],'PINNED_NATIVE_ON_PATH')
 def test_duplicate_same_path_and_trailing_separator_do_not_search_cwd(self):
  from build_guard import qualified_executable
  import os
  _,shim,_,env=self.fixture();env['PATH']=str(shim)+os.pathsep+str(shim)+os.pathsep;self.assertEqual(pathlib.Path(qualified_executable(['cargo'],env)[0][0]),shim/'cargo.exe')
 def test_distinct_matching_path_entries_are_ambiguous(self):
  from build_guard import qualified_executable
  import os
  base,_,native,env=self.fixture();env['PATH']+=os.pathsep+str(native)
  with self.assertRaisesRegex(AssertionError,'AMBIGUOUS'):qualified_executable(['cargo'],env)
 def test_parent_path_is_never_used(self):
  from build_guard import qualified_executable
  from unittest.mock import patch
  base,shim,_,env=self.fixture();empty=base/'empty';empty.mkdir();env['PATH']=str(empty)
  with patch.dict('os.environ',{'PATH':str(shim)}):
   with self.assertRaisesRegex(AssertionError,'AMBIGUOUS'):qualified_executable(['cargo'],env)
 def test_relative_script_unknown_tool_and_empty_path_rejected(self):
  from build_guard import qualified_executable
  _,_,_,env=self.fixture()
  for name in ('other','cargo.cmd','./cargo','../cargo','cargo --version'):
   with self.assertRaisesRegex(AssertionError,'UNQUALIFIED_BARE'):qualified_executable([name],env)
  for path in ('','relative'):
   with self.assertRaisesRegex(AssertionError,'QUALIFIED_PATH'):qualified_executable(['cargo'],{**env,'PATH':path})
 def test_missing_or_changed_toolchain_and_auto_install_rejected(self):
  from build_guard import qualified_executable
  _,_,_,env=self.fixture()
  for values in ({'RUSTUP_TOOLCHAIN':'stable'},{'RUSTUP_AUTO_INSTALL':'1'},{'RUSTUP_HOME':'relative'}):
   with self.assertRaises(AssertionError):qualified_executable(['cargo'],{**env,**values})
 def test_unqualified_proxy_hash_and_missing_pinned_binary_rejected(self):
  from build_guard import qualified_executable
  base,shim,_,env=self.fixture();(shim/'cargo.exe').write_bytes(b'MZ'+b'different synthetic fixture'*8)
  with self.assertRaisesRegex(AssertionError,'UNQUALIFIED_RUSTUP_PROXY'):qualified_executable(['cargo'],env)
  with self.assertRaises(FileNotFoundError):qualified_executable(['rustc'],{**env,'RUSTUP_HOME':str(base/'missing')})
 def test_file_replacement_and_denial_fail_closed(self):
  from build_guard import executable_snapshot
  from unittest.mock import patch
  import types,stat
  _,shim,_,env=self.fixture();target=shim/'cargo.exe';original=pathlib.Path.lstat;calls=[0]
  def changed(p):
   row=original(p)
   if p==target:
    calls[0]+=1
    if calls[0]>1:return types.SimpleNamespace(st_dev=row.st_dev,st_ino=row.st_ino+1,st_size=row.st_size,st_mtime_ns=row.st_mtime_ns,st_mode=row.st_mode,st_reparse_tag=0)
   return row
  with patch.object(pathlib.Path,'lstat',changed):
   with self.assertRaisesRegex(AssertionError,'IDENTITY_CHANGED'):executable_snapshot(target)
  with patch.object(pathlib.Path,'lstat',side_effect=PermissionError(5,'synthetic')):
   with self.assertRaises(PermissionError):executable_snapshot(target)
 def test_reparse_candidate_and_ancestor_are_rejected(self):
  from build_guard import executable_snapshot
  from unittest.mock import patch
  import types
  _,shim,_,env=self.fixture();target=shim/'cargo.exe';original=pathlib.Path.lstat
  for changed in (target,shim):
   def link(p):
    row=original(p)
    return types.SimpleNamespace(st_mode=row.st_mode,st_file_attributes=0x400,st_reparse_tag=0xa000000c) if p==changed else row
   with patch.object(pathlib.Path,'lstat',link):
    with self.assertRaisesRegex(AssertionError,'LINK_OR_TYPE'):executable_snapshot(target)
 def test_supervision_is_sampled_during_input_hashing(self):
  from build_guard import qualified_executable
  _,_,_,env=self.fixture();samples=[];qualified_executable(['cargo'],env,lambda:samples.append(1));self.assertGreaterEqual(len(samples),6)
 def test_absolute_calls_remain_explicit_and_other_launchers_not_broadened(self):
  from build_guard import qualified_executable,Guard
  import inspect
  command=[str(pathlib.Path(__file__).absolute()),'argument'];self.assertEqual(qualified_executable(command,{}),(command,None))
  text=inspect.getsource(Guard.run);self.assertLess(text.index('qualified_executable('),text.index('proc.start('));self.assertIn('executableBinding',text)

if __name__=='__main__':unittest.main()
