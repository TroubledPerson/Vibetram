import unittest,tarfile,pathlib,os
from openssl_probe import safe_member,validate_members,configure_args,PREFIX,CHECKSUM,probe_layout,probe_environment,validate_perl_metadata,perl_metadata_program,PHYSICAL_SDK,with_physical_ndk_inputs
class ProbePolicy(unittest.TestCase):
 def member(self,name,size=1,kind=tarfile.REGTYPE):
  x=tarfile.TarInfo(name);x.size=size;x.type=kind;return x
 def test_safe(self):self.assertEqual(safe_member(PREFIX+"openssl/Configure").name,"Configure")
 def test_traversal(self):
  with self.assertRaises(AssertionError):safe_member(PREFIX+"../escape")
 def test_absolute(self):
  with self.assertRaises(AssertionError):safe_member("/"+PREFIX+"x")
 def test_backslash(self):
  with self.assertRaises(AssertionError):safe_member(PREFIX+"a\\\\b")
 def test_drive(self):
  with self.assertRaises(AssertionError):safe_member(PREFIX+"C:x")
 def test_other_crate(self):
  with self.assertRaises(AssertionError):safe_member("other/Configure")
 def test_duplicate(self):
  m=self.member(PREFIX+"x")
  with self.assertRaises(AssertionError):validate_members([m,m])
 def test_symlink(self):
  with self.assertRaises(AssertionError):validate_members([self.member(PREFIX+"x",kind=tarfile.SYMTYPE)])
 def test_hardlink(self):
  with self.assertRaises(AssertionError):validate_members([self.member(PREFIX+"x",kind=tarfile.LNKTYPE)])
 def test_fifo(self):
  with self.assertRaises(AssertionError):validate_members([self.member(PREFIX+"x",kind=tarfile.FIFOTYPE)])
 def test_file_size(self):
  with self.assertRaises(AssertionError):validate_members([self.member(PREFIX+"x",17*1024**2)])
 def test_count(self):
  with self.assertRaises(AssertionError):validate_members([self.member(PREFIX+"x")]*50001)
 def test_total(self):
  with self.assertRaises(AssertionError):validate_members([self.member(PREFIX+str(i),16*1024**2) for i in range(17)])
 def test_regular_total(self):self.assertEqual(validate_members([self.member(PREFIX+"x",7),self.member(PREFIX+"y",4)]),11)
 def test_exact_args(self):
  args=configure_args("D:/owned/install")
  self.assertEqual(args[:3],["./Configure","--prefix=D:/owned/install","--openssldir=/usr/local/ssl"])
  self.assertIn("linux-aarch64",args);self.assertIn("--target=aarch64-linux-android29",args)
  self.assertNotIn("no-asm",args);self.assertNotIn("no-ssl",args)
 @unittest.skipUnless(os.name=="nt","Windows environment semantics")
 def test_environment(self):
  roots=probe_layout(pathlib.Path.cwd());env=probe_environment(roots[0],roots[2],roots[3])
  self.assertEqual(env["SystemRoot"],os.environ["SystemRoot"])
  self.assertEqual(env["WINDIR"],os.environ["WINDIR"])
  self.assertEqual(env["CARGO_HOME"],str(roots[2]));self.assertEqual(env["RUSTUP_HOME"],str(roots[3]))
  self.assertNotIn("GITHUB_TOKEN",env);self.assertNotIn("ACTIONS_RUNTIME_TOKEN",env)
 def metadata(self):return {"version":"5.40.3","arch":"x86_64-cygwin-thread-multi","os":"cygwin","unixPaths":True}
 def test_metadata(self):self.assertTrue(validate_perl_metadata(self.metadata())["unixPaths"])
 def test_metadata_nonunix(self):
  d=self.metadata();d["unixPaths"]=False
  with self.assertRaises(AssertionError):validate_perl_metadata(d)
 def test_metadata_boolean(self):
  d=self.metadata();d["unixPaths"]=1
  with self.assertRaises(AssertionError):validate_perl_metadata(d)
 def test_metadata_extra(self):
  d=self.metadata();d["path"]="unneeded"
  with self.assertRaises(AssertionError):validate_perl_metadata(d)
 def test_metadata_private_path(self):
  d=self.metadata();d["arch"]="C:/private"
  with self.assertRaises(AssertionError):validate_perl_metadata(d)
 def test_perl_program(self):
  self.assertIn("use JSON::PP;",perl_metadata_program());self.assertNotIn("-e",perl_metadata_program())
 def test_layout(self):
  roots=probe_layout(pathlib.Path.cwd())
  self.assertEqual(len(set(roots)),4)
  self.assertEqual({p.name for p in roots},{"openssl-probe-work","openssl-probe-output","openssl-probe-cargo","openssl-probe-rustup"})
  for i,a in enumerate(roots):
   for b in roots[i+1:]:self.assertFalse(a.is_relative_to(b) or b.is_relative_to(a))
 def test_checksum(self):self.assertEqual(CHECKSUM,"46eb8fb9fb3b61ce1c0f8a026c4c1a0714d3a9e138e7fbde78753ce2babc3846")

 @unittest.skipUnless(os.name=="nt","Windows SDK environment")
 def test_physical_sdk_environment(self):
  roots=probe_layout(pathlib.Path.cwd());env=probe_environment(roots[0],roots[2],roots[3])
  self.assertEqual(env["ANDROID_HOME"],str(PHYSICAL_SDK));self.assertEqual(env["ANDROID_SDK_ROOT"],str(PHYSICAL_SDK))
 def test_physical_sdk_constant(self):self.assertEqual(PHYSICAL_SDK,pathlib.Path("C:/Program Files (x86)/Android/android-sdk"))
 def test_physical_lease_order(self):
  from unittest.mock import patch
  calls=[];configured=[]
  def fake(root,tool,**kw):
   calls.append((root,tool,kw.get("directory"),kw.get("expected_target")))
   kw["callback"]()
   return {"qualified":True,"callbackSucceeded":True}
  with patch("ndk_input_metadata.capture_one",fake),patch("pathlib.Path.read_text",return_value="Pkg.Revision = 30.0.16248370"),patch("pathlib.Path.write_text"),patch("builtins.print"):
   with_physical_ndk_inputs(None,{},pathlib.Path("D:/synthetic-not-created"),lambda n,t:configured.append((n,t)))
  self.assertEqual(len(calls),5);self.assertEqual(len(configured),1)
  self.assertEqual(calls[0][1],pathlib.Path("C:/Android/android-sdk"));self.assertEqual(calls[0][3],PHYSICAL_SDK)
  self.assertTrue(all(x[1].is_relative_to(PHYSICAL_SDK) for x in calls[1:]))
 def test_no_configure_before_qualified_mapping(self):
  from unittest.mock import patch
  configured=[]
  with patch("ndk_input_metadata.capture_one",return_value={"qualified":False}),patch("pathlib.Path.write_text"),patch("builtins.print"):
   with self.assertRaises(AssertionError):with_physical_ndk_inputs(None,{},pathlib.Path("D:/synthetic-not-created"),lambda n,t:configured.append(True))
  self.assertEqual(configured,[])

if __name__=="__main__":unittest.main()
