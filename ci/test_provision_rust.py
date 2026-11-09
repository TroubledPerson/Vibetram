import unittest,pathlib
from provision_rust import limits,install_args,child_environment,MIN_FREE,MAX_OUTPUT,MAX_SECONDS,MAX_LOG
class Provision(unittest.TestCase):
 def test_boundaries(self):self.assertIsNone(limits(MIN_FREE,MAX_OUTPUT,MAX_SECONDS,MAX_LOG))
 def test_low_disk(self):self.assertEqual(limits(MIN_FREE-1,0,0,0),'FREE_SPACE_GUARD')
 def test_output(self):self.assertEqual(limits(MIN_FREE,MAX_OUTPUT+1,0,0),'OUTPUT_THRESHOLD')
 def test_timeout(self):self.assertEqual(limits(MIN_FREE,0,MAX_SECONDS+1,0),'TIME_LIMIT')
 def test_log(self):self.assertEqual(limits(MIN_FREE,0,0,MAX_LOG+1),'LOG_LIMIT')
 def test_pins(self):
  a=install_args('rustup');self.assertIn('1.95.0-x86_64-pc-windows-msvc',a);self.assertIn('aarch64-linux-android',a);self.assertIn('--no-self-update',a);self.assertNotIn('stable',a)
 def test_official_source_and_no_credentials(self):
  e=child_environment({'PATH':'tools','GITHUB_TOKEN':'not-a-real-fixture','RUSTUP_DIST_SERVER':'https://invalid.example'},pathlib.Path('owned'));self.assertNotIn('GITHUB_TOKEN',e);self.assertEqual(e['RUSTUP_DIST_SERVER'],'https://static.rust-lang.org');self.assertEqual(e['RUSTUP_AUTO_INSTALL'],'0')
if __name__=='__main__':unittest.main()
