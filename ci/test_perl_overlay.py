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

import json
class RuntimeQualification(unittest.TestCase):
 def archive(self,extra=None,requires=None):
  import perl_overlay as x
  meta={"name":"Synthetic","version":"1.00","license":["perl_5"],"prereqs":{"runtime":{"requires":requires or {"strict":"0"}}}}
  content={"Synthetic-1.00/META.json":json.dumps(meta).encode(),"Synthetic-1.00/lib/Fixture/Helper.pm":b"package Fixture::Helper; 1;\n","Synthetic-1.00/README":b"Synthetic licence fixture\n"}
  buf=io.BytesIO()
  with tarfile.open(fileobj=buf,mode="w:gz") as tar:
   for path,body in content.items():
    item=tarfile.TarInfo(path);item.size=len(body);tar.addfile(item,io.BytesIO(body))
   if extra:
    item=tarfile.TarInfo(extra[0]);item.type=extra[1];item.linkname="outside";tar.addfile(item)
  data=buf.getvalue();pin=("S/SY/SYNTHETIC","Synthetic-1.00",hashlib.sha256(data).hexdigest(),"Synthetic","1.00")
  return x.runtime_review(data,pin)
 def test_runtime_archive(self):
  files,report=self.archive();self.assertIn("lib/Fixture/Helper.pm",files);self.assertEqual(report["runtimeRequires"],{"strict":"0"})
 def test_runtime_link(self):
  with self.assertRaisesRegex(AssertionError,"RUNTIME_LINK_OR_SPECIAL"):self.archive(("Synthetic-1.00/link",tarfile.SYMTYPE))
 def test_runtime_escape(self):
  with self.assertRaisesRegex(AssertionError,"RUNTIME_MEMBER_PATH"):self.archive(("Synthetic-1.00/../escape",tarfile.REGTYPE))
 def test_runtime_case_collision(self):
  with self.assertRaisesRegex(AssertionError,"RUNTIME_DUPLICATE"):self.archive(("Synthetic-1.00/readme",tarfile.REGTYPE))
 def test_runtime_documentation_not_executed(self):
  files,_=self.archive(("Synthetic-1.00/lib/Fixture/FAQ.pod",tarfile.REGTYPE));self.assertNotIn("lib/Fixture/FAQ.pod",files)
 def test_runtime_native_library(self):
  with self.assertRaisesRegex(AssertionError,"RUNTIME_NON_PURE_LIBRARY"):self.archive(("Synthetic-1.00/lib/native.dll",tarfile.REGTYPE))
 def test_runtime_requirement_injection(self):
  with self.assertRaisesRegex(AssertionError,"RUNTIME_REQUIREMENT_FIELD"):self.archive(requires={"strict":"0; die"})
 def test_runtime_no_shadow(self):
  from perl_overlay import select_missing
  p={"Fixture":{"sha256":"a"*64}};self.assertEqual(select_missing(p,{"Fixture":[]}),["Fixture"]);self.assertEqual(select_missing(p,{"Fixture":["a"*64]}),[])
  with self.assertRaisesRegex(AssertionError,"NO_SHADOW"):select_missing(p,{"Fixture":["b"*64]})
 def test_runtime_presence_schema(self):
  from perl_overlay import select_missing
  with self.assertRaisesRegex(AssertionError,"SCHEMA"):select_missing({"Fixture":{}},{})
 def test_runtime_presence_not_errors_as_missing(self):
  from perl_overlay import presence_program
  s=presence_program(["Fixture"]);self.assertIn('die "module metadata inaccessible"',s);self.assertIn('ENOENT || $! == ENOTDIR',s);self.assertIn('die "module link or special"',s)
 def test_actual_helpers_not_reflection(self):
  from perl_overlay import runtime_helper_program
  s=runtime_helper_program();self.assertIn("IPC::Cmd::can_run($p)",s);self.assertIn("MM->maybe_command($p)",s);self.assertNotIn('->can("can_run")',s);self.assertNotIn('use ExtUtils::MakeMaker',s);self.assertNotIn('system(',s);self.assertNotIn('`',s)
 def test_runtime_keyword_module_version(self):
  from perl_overlay import runtime_version_program
  s=runtime_version_program({"if":["0"]});self.assertIn('$m->VERSION("0")',s);self.assertNotIn("if->VERSION",s);self.assertIn('require "$f.pm"',s)
 def test_runtime_pins(self):
  from perl_overlay import RUNTIME_PACKAGES
  self.assertEqual(len(RUNTIME_PACKAGES),4);self.assertTrue(all(len(x[2])==64 for x in RUNTIME_PACKAGES));self.assertEqual(RUNTIME_PACKAGES[0][4],"7.76")
 def test_runtime_function_imports_resolve(self):
  import ast,inspect,importlib
  from perl_overlay import runtime_diagnosis
  tree=ast.parse(inspect.getsource(runtime_diagnosis))
  for node in ast.walk(tree):
   if isinstance(node,ast.ImportFrom):
    module=importlib.import_module(node.module)
    for alias in node.names:self.assertTrue(hasattr(module,alias.name),node.module+"."+alias.name)
 def test_runtime_workflow_no_configure(self):
  import pathlib
  w=json.loads((pathlib.Path(__file__).resolve().parents[1]/".github/workflows/offline-android.yml").read_text());job=w["jobs"]["perl-runtime"]
  self.assertEqual(job["permissions"],{"contents":"read"});self.assertIn("[perl-runtime-191]",job["if"]);self.assertEqual(job["steps"][1]["run"],"python -B ci/perl_overlay.py --runtime-diagnosis")


class ConfigureRuntimeQualification(unittest.TestCase):
 def test_environment_keeps_physical_sdk_and_overlay(self):
  from perl_overlay import configure_environment
  from openssl_probe import PHYSICAL_SDK
  import pathlib,os
  tools=PHYSICAL_SDK/"ndk/30.0.16248370/toolchains/llvm/prebuilt/windows-x86_64/bin";perl=pathlib.Path("C:/Program Files/Git/usr/bin/perl.exe")
  e=configure_environment({"PATH":"original","PERL5LIB":"/job/overlay/lib"},PHYSICAL_SDK/"ndk/30.0.16248370",tools,perl)
  self.assertEqual(e["PERL5LIB"],"/job/overlay/lib");self.assertEqual(e["ANDROID_HOME"],str(PHYSICAL_SDK));self.assertEqual(e["ANDROID_SDK_ROOT"],str(PHYSICAL_SDK));self.assertTrue(e["PATH"].startswith(str(tools)+os.pathsep));self.assertEqual(e["CC"],"clang.exe");self.assertEqual(e["AR"],"llvm-ar.exe")
 def test_lookup_uses_real_identity(self):
  from perl_overlay import configure_lookup_program
  s=configure_lookup_program();self.assertIn("IPC::Cmd::can_run($tools[$i])",s);self.assertIn("$a[0]==$b[0] && $a[1]==$b[1]",s);self.assertNotIn('system(',s)
 def configure_fixture(self,lookup_ok=True,cc="clang.exe",cross=""):
  import pathlib,types,subprocess
  from unittest.mock import patch
  from perl_overlay import configure_with_runtime
  from openssl_probe import PHYSICAL_SDK
  calls=[]
  class FakeGuard:
   def run(self,args,**kw):
    calls.append([str(x) for x in args])
    result={"state":"PASS_EXACT_PHYSICAL_NDK_PATH_LOOKUP" if lookup_ok else "WRONG","checks":3,"compilerExecuted":False,"prefix":"/d/a/Vibetram/Vibetram/openssl-probe-work/install"}
    return subprocess.CompletedProcess(args,0,json.dumps(result) if len(calls)==1 else "synthetic Configure output","")
  text="PLATFORM=linux-aarch64\nCROSS_COMPILE="+cross+"\nCC=$(CROSS_COMPILE)"+cc+"\nAR=$(CROSS_COMPILE)llvm-ar.exe\nRANLIB=$(CROSS_COMPILE)llvm-ranlib.exe\nCFLAGS=--target=aarch64-linux-android29\n"
  tools=PHYSICAL_SDK/"ndk/30.0.16248370/toolchains/llvm/prebuilt/windows-x86_64/bin"
  try:
   with patch("pathlib.Path.write_text"),patch("pathlib.Path.read_text",return_value=text),patch("pathlib.Path.read_bytes",return_value=text.encode()),patch("pathlib.Path.is_file",return_value=True),patch("pathlib.Path.stat",return_value=types.SimpleNamespace(st_size=len(text))),patch("builtins.print"):
    result=configure_with_runtime(FakeGuard(),{"PATH":"original","PERL5LIB":"/job/overlay/lib"},pathlib.Path("D:/synthetic/work"),pathlib.Path("D:/synthetic/output"),pathlib.Path("D:/synthetic/source"),pathlib.Path("C:/Program Files/Git/usr/bin/perl.exe"),PHYSICAL_SDK/"ndk/30.0.16248370",tools)
   return result,calls
  except AssertionError as error:return error,calls
 def test_one_configure_no_make(self):
  result,calls=self.configure_fixture();self.assertEqual(result["state"],"PASS_ACTUAL_CONFIGURE_ONLY_NOT_COMPILED");self.assertEqual(sum("./Configure" in x and "-c" not in x for x in calls),1);self.assertEqual(len(calls),4);self.assertFalse(result["makeRequested"]);self.assertTrue(all(not any(v in ("make","nmake","cargo") for v in row) for row in calls))
 def test_bad_lookup_stops_before_configure(self):
  result,calls=self.configure_fixture(lookup_ok=False);self.assertIsInstance(result,AssertionError);self.assertEqual(len(calls),1)
 def test_wrong_generated_compiler_rejected(self):
  result,_=self.configure_fixture(cc="other.exe");self.assertIsInstance(result,AssertionError);self.assertIn("TOOL_SELECTION",str(result))
 def test_nonempty_cross_prefix_rejected(self):
  result,_=self.configure_fixture(cross="unknown-");self.assertIsInstance(result,AssertionError);self.assertIn("TOOL_SELECTION",str(result))
 def test_configure_workflow_reuses_qualified_runtime(self):
  import pathlib
  w=json.loads((pathlib.Path(__file__).resolve().parents[1]/".github/workflows/offline-android.yml").read_text());job=w["jobs"]["openssl-probe"]
  self.assertEqual(job["permissions"],{"contents":"read"});self.assertEqual(job["steps"][1]["run"],"python -B ci/perl_overlay.py --runtime-configure");self.assertIn("[openssl-probe-191]",job["if"])

if __name__=="__main__":unittest.main()
