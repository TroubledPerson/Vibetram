import unittest,json,io,tarfile,hashlib,pathlib
from unittest.mock import patch
from perl_prerequisites import imports,program,parse,cpan_proposal
class Prerequisites(unittest.TestCase):
 def report(self,mods=("Config",),loaded="1",unix="1"):
  return "META\t5.42.3\tx86_64-cygwin-thread-multi\tcygwin\t"+unix+"\n"+"".join("MODULE\t"+m+"\t"+loaded+"\t1.0\t-\n" for m in mods)+"END\t"+str(len(mods))+"\n"
 def test_complete(self):self.assertTrue(parse(self.report(),["Config"])["complete"])
 def test_native_windows(self):self.assertFalse(parse(self.report(unix="0"),["Config"])["complete"])
 def test_missing(self):self.assertFalse(parse(self.report(loaded="0"),["Config"])["complete"])
 def test_transitive_missing(self):
  d=parse(self.report(loaded="0").replace("\t1.0\t-","\t-\tLocale::Maketext::Simple"),["Config"])
  self.assertEqual(d["modules"]["Config"]["missing"],["Locale::Maketext::Simple"])
 def test_truncated(self):
  with self.assertRaises(AssertionError):parse(self.report().replace("END\t1\n",""),["Config"])
 def test_duplicate(self):
  with self.assertRaises(AssertionError):parse(self.report(("Config","Config")),["Config","Carp"])
 def test_extra(self):
  with self.assertRaises(AssertionError):parse(self.report(("Config","Carp")),["Config"])
 def test_wrong_boolean(self):
  with self.assertRaises(AssertionError):parse(self.report(loaded="yes"),["Config"])
 def test_private_path_rejected(self):
  with self.assertRaises(AssertionError):parse(self.report().replace("cygwin\t1","C:/unapproved\t1"),["Config"])
 def test_protocol_size(self):
  with self.assertRaises(AssertionError):parse("x"*65537,["Config"])
 def test_injection(self):
  with self.assertRaises(AssertionError):program(["Config);system"])
 def test_module_count(self):
  with self.assertRaises(AssertionError):program(["Module"+str(i) for i in range(129)])
 def test_imports_skip_pod(self):
  self.assertEqual(imports("use Config;\n=head1 Example\n use NotRequired;\n=cut\nrequire File::Spec;\n__END__\nuse Ignore;"),{"Config","File::Spec"})
 def test_template_imports(self):self.assertEqual(imports("{-\n use Time::Piece;\n use OpenSSL::Util;\n-}"),{"Time::Piece","OpenSSL::Util"})
 def test_versions_and_dynamic_require(self):self.assertEqual(imports("use 5.10.0;\nrequire $dynamic;\nuse OpenSSL::Template;"),{"OpenSSL::Template"})
 def test_program_checks_template_version(self):self.assertIn("Text::Template->VERSION(1.46)",program(["Text::Template"]))
 def fixture(self):
  b=io.BytesIO();prefix="Locale-Maketext-Simple-0.21/"
  files={"META.yml":b"name: Locale-Maketext-Simple\nversion: 0.21\nrequires: {}\nlicense: perl\n","lib/Locale/Maketext/Simple.pm":b"package Locale::Maketext::Simple;\nuse strict;\n1;\n","README":b"Synthetic licence metadata fixture only.\n"}
  with tarfile.open(fileobj=b,mode="w:gz") as t:
   for name,data in files.items():m=tarfile.TarInfo(prefix+name);m.size=len(data);t.addfile(m,io.BytesIO(data))
  return b.getvalue()
 def cpan(self,mismatch=False):
  data=self.fixture();digest="0"*64 if mismatch else hashlib.sha256(data).hexdigest();checks=("'Locale-Maketext-Simple-0.21.tar.gz' => {\n 'sha256' => '"+digest+"',\n},\n").encode()
  class Response(io.BytesIO):
   status=200
   def __init__(self,url,data):super().__init__(data);self.url=url
  def opened(url,timeout):return Response(url,checks if url.endswith("CHECKSUMS") else data)
  with patch("urllib.request.urlopen",side_effect=opened),patch("pathlib.Path.write_text") as write,patch("builtins.print"):
   cpan_proposal(pathlib.Path("D:/synthetic-not-created"))
  return json.loads(write.call_args.args[0])
 def test_cpan_proposal_only(self):
  d=self.cpan();self.assertEqual(d["state"],"CPAN_PROPOSAL_ONLY");self.assertFalse(d["installed"]);self.assertFalse(d["executedPackageCode"]);self.assertTrue(d["purePerl"])
 def test_cpan_checksum_failure(self):self.assertEqual(self.cpan(True)["reason"],"CPAN_CHECKSUM_MISMATCH")
if __name__=="__main__":unittest.main()
