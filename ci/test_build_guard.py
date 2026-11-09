import unittest,pathlib,json,struct
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
if __name__=='__main__':unittest.main()

