import unittest,pathlib,json,struct
from build_guard import qualified_license_link,NUCLEO_LICENSE_BLOB,git_blob_identity,normalized_license_blob
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
if __name__=='__main__':unittest.main()

