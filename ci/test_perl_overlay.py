import unittest,io,tarfile,hashlib
from unittest.mock import patch
from perl_overlay import review,parse_overlay_path,focused_program,MODULE_SHA
class Overlay(unittest.TestCase):
 def archive(self,extra=None,meta=None,base="Locale::Maketext"):
  body=("package Locale::Maketext::Simple;\nuse strict;\nsub load_loc {\n eval { require Locale::Maketext::Lexicon; 1 } or return;\n eval \"\n use base '"+base+"';\n \";\n}\n# COPYRIGHT MIT synthetic fixture\n1;\n").encode()
  files={"lib/Locale/Maketext/Simple.pm":body,"README":b"Synthetic notice.\n","META.yml":meta or b"name: Locale-Maketext-Simple\nversion: 0.21\nlicense: perl\nrequires: {}\n","Makefile.PL":b"# Never executed fixture.\n"}
  b=io.BytesIO()
  with tarfile.open(fileobj=b,mode="w:gz") as t:
   for name,value in files.items():
    m=tarfile.TarInfo("Locale-Maketext-Simple-0.21/"+name);m.size=len(value);t.addfile(m,io.BytesIO(value))
   if extra:
    m=tarfile.TarInfo(extra[0]);m.type=extra[1];m.size=0;t.addfile(m,io.BytesIO())
  return b.getvalue(),body
 def reviewed(self,extra=None,meta=None,base="Locale::Maketext"):
  data,body=self.archive(extra,meta,base)
  with patch.multiple("perl_overlay",ARCHIVE_SHA=hashlib.sha256(data).hexdigest(),ARCHIVE_BYTES=len(data),MODULE_SHA=hashlib.sha256(body).hexdigest()):return review(data)
 def test_good(self):
  files,report=self.reviewed();self.assertEqual(len(files),4);self.assertTrue(report["sourceReviewedBeforeCopy"]);self.assertEqual(report["observedCoreImports"],["strict"])
 def test_wrong_optional_base(self):
  with self.assertRaisesRegex(AssertionError,"UNREVIEWED_MODULE_IMPORT"):self.reviewed(base="Exporter")
 def test_checksum(self):
  data,_=self.archive()
  with self.assertRaisesRegex(AssertionError,"PINNED_CPAN_ARCHIVE_MISMATCH"):review(data)
 def test_escape(self):
  with self.assertRaises(AssertionError):self.reviewed(("Locale-Maketext-Simple-0.21/../escape",tarfile.REGTYPE))
 def test_absolute(self):
  with self.assertRaises(AssertionError):self.reviewed(("/outside",tarfile.REGTYPE))
 def test_colon(self):
  with self.assertRaises(AssertionError):self.reviewed(("Locale-Maketext-Simple-0.21/C:outside",tarfile.REGTYPE))
 def test_symlink(self):
  with self.assertRaises(AssertionError):self.reviewed(("Locale-Maketext-Simple-0.21/link",tarfile.SYMTYPE))
 def test_hardlink(self):
  with self.assertRaises(AssertionError):self.reviewed(("Locale-Maketext-Simple-0.21/link",tarfile.LNKTYPE))
 def test_fifo(self):
  with self.assertRaises(AssertionError):self.reviewed(("Locale-Maketext-Simple-0.21/fifo",tarfile.FIFOTYPE))
 def test_case_duplicate(self):
  with self.assertRaises(AssertionError):self.reviewed(("Locale-Maketext-Simple-0.21/readme",tarfile.REGTYPE))
 def test_native_file(self):
  with self.assertRaises(AssertionError):self.reviewed(("Locale-Maketext-Simple-0.21/payload.xs",tarfile.REGTYPE))
 def test_dependency(self):
  with self.assertRaisesRegex(AssertionError,"NEW_RUNTIME_DEPENDENCIES"):self.reviewed(meta=b"name: Locale-Maketext-Simple\nversion: 0.21\nlicense: perl\nrequires: {Unknown: 1}\n")
 def path(self,value="/d/a/Vibetram/Vibetram/openssl-probe-work/perl-overlay/lib",pin=MODULE_SHA):return "OVERLAY\t"+value+"\t"+pin+"\n"
 def test_posix_path(self):self.assertTrue(parse_overlay_path(self.path()).startswith("/d/"))
 def test_path_escape(self):
  with self.assertRaises(AssertionError):parse_overlay_path(self.path("/d/a/../openssl-probe-work/perl-overlay/lib"))
 def test_unc(self):
  with self.assertRaises(AssertionError):parse_overlay_path(self.path("//server/openssl-probe-work/perl-overlay/lib"))
 def test_pin(self):
  with self.assertRaises(AssertionError):parse_overlay_path(self.path(pin="0"*64))
 def test_multiple_lines(self):
  with self.assertRaises(AssertionError):parse_overlay_path(self.path()+self.path())
 def test_no_ipc_run(self):
  s=focused_program();self.assertNotIn("IPC::Cmd::run(",s);self.assertIn('IPC::Cmd->can("run")',s)
if __name__=="__main__":unittest.main()
