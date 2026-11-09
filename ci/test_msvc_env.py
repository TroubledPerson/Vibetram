import unittest,struct,pathlib
from msvc_env import parse_exports,apply_exports,pe_x64,EXPORTS,discovery_env,required_inputs
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
if __name__=='__main__':unittest.main()
