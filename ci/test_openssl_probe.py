import unittest,tarfile,pathlib
from openssl_probe import safe_member,validate_members,configure_args,PREFIX,CHECKSUM
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
 def test_checksum(self):self.assertEqual(CHECKSUM,"46eb8fb9fb3b61ce1c0f8a026c4c1a0714d3a9e138e7fbde78753ce2babc3846")
if __name__=="__main__":unittest.main()
