import unittest,io,tarfile,hashlib,pathlib
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
  self.assertEqual(len(RUNTIME_PACKAGES),8);self.assertTrue(all(len(x[2])==64 for x in RUNTIME_PACKAGES));self.assertEqual(RUNTIME_PACKAGES[0][4],"7.76")
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
    if len(calls)==1:stdout=json.dumps(result)
    elif any(str(x).endswith("generated-helper-checks.pl") for x in args):stdout=json.dumps({"state":"PASS_ACTUAL_GENERATED_CONFIGURATION_HELPERS","checks":5,"target":"linux-aarch64"})
    elif "--help" in args:stdout="configdata synthetic local help text with enough documentation for the fixture"
    elif "--build-parameters" in args:stdout="Configurations/common0.tmpl Configurations/unix-Makefile.tmpl"
    elif "--options" in args:stdout="Disabled features: synthetic"
    else:stdout="synthetic Configure output"
    return subprocess.CompletedProcess(args,0,stdout,"")
  text="PLATFORM=linux-aarch64\nCROSS_COMPILE="+cross+"\nCC=$(CROSS_COMPILE)"+cc+"\nAR=$(CROSS_COMPILE)llvm-ar.exe\nRANLIB=$(CROSS_COMPILE)llvm-ranlib.exe\nCFLAGS=--target=aarch64-linux-android29\n"
  tools=PHYSICAL_SDK/"ndk/30.0.16248370/toolchains/llvm/prebuilt/windows-x86_64/bin"
  try:
   with patch("pathlib.Path.write_text"),patch("pathlib.Path.read_text",return_value=text),patch("pathlib.Path.read_bytes",return_value=text.encode()),patch("pathlib.Path.is_file",return_value=True),patch("pathlib.Path.stat",return_value=types.SimpleNamespace(st_size=len(text))),patch("builtins.print"):
    result=configure_with_runtime(FakeGuard(),{"PATH":"original","PERL5LIB":"/job/overlay/lib"},pathlib.Path("D:/synthetic/work"),pathlib.Path("D:/synthetic/output"),pathlib.Path("D:/synthetic/source"),pathlib.Path("C:/Program Files/Git/usr/bin/perl.exe"),PHYSICAL_SDK/"ndk/30.0.16248370",tools)
   return result,calls
  except AssertionError as error:return error,calls
 def test_one_configure_no_make(self):
  result,calls=self.configure_fixture();self.assertEqual(result["state"],"PASS_ACTUAL_CONFIGURE_ONLY_NOT_COMPILED");self.assertEqual(sum("./Configure" in x and "-c" not in x for x in calls),1);self.assertEqual(len(calls),9);self.assertTrue(result["generatedExecution"]["syntaxChecked"]);self.assertFalse(result["makeRequested"]);self.assertTrue(all(not any(v in ("make","nmake","cargo") for v in row) for row in calls))
 def test_bad_lookup_stops_before_configure(self):
  result,calls=self.configure_fixture(lookup_ok=False);self.assertIsInstance(result,AssertionError);self.assertEqual(len(calls),1)
 def test_wrong_generated_compiler_rejected(self):
  result,_=self.configure_fixture(cc="other.exe");self.assertIsInstance(result,AssertionError);self.assertIn("TOOL_SELECTION",str(result))
 def test_nonempty_cross_prefix_rejected(self):
  result,_=self.configure_fixture(cross="unknown-");self.assertIsInstance(result,AssertionError);self.assertIn("TOOL_SELECTION",str(result))
 def test_configure_workflow_reuses_qualified_runtime(self):
  import pathlib
  w=json.loads((pathlib.Path(__file__).resolve().parents[1]/".github/workflows/offline-android.yml").read_text());job=w["jobs"]["openssl-probe"]
  self.assertEqual(job["permissions"],{"contents":"read"});self.assertEqual(job["steps"][1]["run"],"python -B ci/perl_overlay.py --runtime-direct-output");self.assertIn("[openssl-probe-191]",job["if"])


class EndToEndConfiguration(unittest.TestCase):
 def catalogue(self,ambiguous=False):
  import pathlib,types
  from unittest.mock import patch
  from perl_overlay import CONFIGURATION_ROOTS,configuration_source_closure
  root=pathlib.Path("D:/synthetic-source-not-created")
  files={root/name:"use strict;\n" for name in CONFIGURATION_ROOTS}
  files[root/"Configure"]="use OpenSSL::Template;\n"
  files[root/"configdata.pm.in"]="use Pod::Usage;\nuse configdata;\nuse platform;\nuse gentemplate;\n"
  files[root/"Configurations/platform/Unix.pm"]="require platform::BASE;\nuse configdata;\n"
  files[root/"util/perl/OpenSSL/Template.pm"]="use Text::Template;\n"
  files[root/"Configurations/unix-checker.pm"]="use Config;\n"
  if ambiguous:files[root/"Configurations/OpenSSL/Template.pm"]="use strict;\n"
  with patch("pathlib.Path.read_text",side_effect=lambda self,*a,**k:files[self],autospec=True),patch("pathlib.Path.read_bytes",side_effect=lambda self:files[self].encode(),autospec=True),patch("pathlib.Path.is_file",side_effect=lambda self:self in files,autospec=True),patch("pathlib.Path.stat",return_value=types.SimpleNamespace(st_size=100)),patch("pathlib.Path.glob",return_value=[]):return configuration_source_closure(root)
 def test_generated_and_dynamic_roots(self):
  d=self.catalogue();names={x["path"] for x in d["sourceFiles"]};self.assertIn("configdata.pm.in",names);self.assertIn("Configurations/platform/BASE.pm",names);self.assertIn("Configurations/common0.tmpl",names);self.assertIn("Pod::Usage",d["externalModules"]);self.assertNotIn("configdata",d["externalModules"]);self.assertNotIn("platform",d["externalModules"]);self.assertEqual(d["dynamicPlatform"],"platform::Unix")
 def test_ambiguous_module_fails_closed(self):
  with self.assertRaisesRegex(AssertionError,"AMBIGUOUS_LOCAL_PERL_MODULE"):self.catalogue(ambiguous=True)
 def test_catalogue_not_runtime_claim(self):self.assertEqual(self.catalogue()["state"],"STATIC_CONFIGURATION_CATALOG_REQUIRES_DYNAMIC_EXECUTION")
 def test_pod_function_not_only_loading(self):
  from perl_overlay import pod_runtime_program
  s=pod_runtime_program();self.assertIn("Pod::Usage::pod2usage(",s);self.assertIn('-noperldoc=>1',s);self.assertIn('-exitval=>"NOEXIT"',s);self.assertNotIn('system(',s)
 def test_generated_helpers_are_actual_functions(self):
  from perl_overlay import generated_helper_program
  s=generated_helper_program();self.assertIn('platform->bin("offline_fixture")',s);self.assertIn('OpenSSL::Template->new',s);self.assertIn('$t->fill_in(HASH=>{})',s);self.assertIn('Configurations/common0.tmpl',s);self.assertNotIn('system(',s)
 def test_provider_inventory_bound(self):
  from perl_overlay import presence_program
  self.assertIn('Fixture511',presence_program(['Fixture'+str(i) for i in range(512)]))
  with self.assertRaises(AssertionError):presence_program(['Fixture'+str(i) for i in range(513)])
 def test_recursive_exact_pins(self):
  from perl_overlay import RUNTIME_PACKAGES
  self.assertEqual([x[4] for x in RUNTIME_PACKAGES[4:]],["2.05","3.28","1.302210","0.024"])


class CargoRuntimeIntegration(unittest.TestCase):
 def test_two_exact_owned_pairs(self):
  import pathlib
  from perl_overlay import owned_pair
  root=pathlib.Path("D:/synthetic")
  self.assertTrue(owned_pair(root,root/"ci-work",root/"dist"));self.assertTrue(owned_pair(root,root/"openssl-probe-work",root/"openssl-probe-output"))
  for a,b in (("other","dist"),("ci-work","other"),("ci-work","openssl-probe-output")):
   self.assertFalse(owned_pair(root,root/a,root/b))
 def test_build_overlay_resolver_suffix(self):
  from perl_overlay import parse_overlay_path
  s="/d/a/Vibetram/Vibetram/ci-work/perl-overlay/lib"
  self.assertEqual(parse_overlay_path("OVERLAY\t"+s+"\t"+MODULE_SHA+"\n"),s)
 def test_cross_path_keeps_microsoft_linker_priority(self):
  import pathlib,os
  from perl_overlay import build_android_environment
  from openssl_probe import PHYSICAL_SDK
  link=pathlib.Path("C:/qualified-vs/bin/link.exe");perl=pathlib.Path("C:/Program Files/Git/usr/bin/perl.exe");ndk=PHYSICAL_SDK/"ndk/30.0.16248370";tools=ndk/"toolchains/llvm/prebuilt/windows-x86_64/bin"
  env={"PATH":"original","CARGO_TARGET_X86_64_PC_WINDOWS_MSVC_LINKER":str(link),"VIBETRAM_OPENSSL_CARGO_BRIDGE":"1","PERL5OPT":"-MVibetram::ConfigurePaths","PERL5LIB":"/job/lib"}
  out=build_android_environment(env,ndk,tools,perl);parts=out["PATH"].split(os.pathsep)
  self.assertLess(parts.index(str(link.parent)),parts.index(str(perl.parent)));self.assertEqual(parts[0],str(ndk/"prebuilt/windows-x86_64/bin"));self.assertEqual(out["CC_aarch64_linux_android"],str(tools/"clang.exe"));self.assertEqual(out["PERL"],"perl.exe");self.assertEqual(out["MAKEFLAGS"],"-j1");self.assertEqual(env["PATH"],"original");self.assertEqual(out["PERL5OPT"],env["PERL5OPT"])
 def test_tiny_recipe_actual_tabs_and_no_execution(self):
  from perl_overlay import tiny_makefile
  s=tiny_makefile("D:/a/Vibetram/Vibetram/ci-work/tool-smoke space")
  commands=[x for x in s.splitlines() if x.startswith("\t")];self.assertEqual(len(commands),5);self.assertIn("--target=aarch64-linux-android29 -shared",s);self.assertIn("$(AR) crs",s);self.assertNotIn("./probe.so",s)
 def test_tiny_output_scope(self):
  from perl_overlay import tiny_makefile
  for p in ("/other/output","/d/a/ci-work/../tool-smoke","/d/a/ci-work/tool-smoke;command"):
   with self.assertRaises(AssertionError):tiny_makefile(p)
 def test_bridge_narrow_and_read_only(self):
  from perl_overlay import cargo_prefix_bridge_program
  s=cargo_prefix_bridge_program();self.assertIn('unless $hash eq $pin',s);self.assertIn('prefix traversal',s);self.assertIn('openssl-sys-[a-f0-9]{1,64}',s);self.assertIn('$ARGV[$prefix[0]]="--prefix=".$posix',s);self.assertNotIn('File::Spec::',s);self.assertNotIn('system(',s);self.assertNotIn('open my $f,">"',s)
 def test_bootstrap_uses_shared_implementation_once(self):
  import pathlib,types
  from unittest.mock import patch
  import perl_overlay as p
  from openssl_probe import ROOT
  calls=[]
  class G:
   def run(self,args,**kwargs):calls.append(args)
  original={"CARGO_TARGET_X86_64_PC_WINDOWS_MSVC_LINKER":"synthetic-link"}
  report={"state":"PASS_RUNTIME_CONFIGURE_ONLY"}
  with patch("perl_overlay.qualify_prepared_runtime",return_value=({"path":"C:/qualified/perl.exe"},{"PERL5LIB":"/synthetic/job/lib"},report)) as shared:
   _,_,_,result=p.bootstrap_for_cargo(G(),original,ROOT/"ci-work",ROOT/"dist")
  self.assertIs(result,report);self.assertEqual(shared.call_count,1);self.assertEqual(len(calls),1);self.assertIn("--materialize",calls[0]);self.assertNotIn("VIBETRAM_OPENSSL_CARGO_BRIDGE",original)
 def test_build_calls_production_shared_path(self):
  import ast,inspect,cloud_build
  tree=ast.parse(inspect.getsource(cloud_build.main));calls=[n.func.id for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)]
  self.assertEqual(calls.count("bootstrap_for_cargo"),1);self.assertEqual(calls.count("qualify_make_link"),1);self.assertIn("build_android_environment",calls)
 def test_build_imports_resolve(self):
  import ast,inspect,importlib,cloud_build
  tree=ast.parse(inspect.getsource(cloud_build))
  for node in tree.body:
   if isinstance(node,ast.ImportFrom):
    module=importlib.import_module(node.module)
    for alias in node.names:self.assertTrue(hasattr(module,alias.name),node.module+"."+alias.name)
 def test_unsigned_lock_preflight_and_release_gate(self):
  import pathlib
  w=json.loads((pathlib.Path(__file__).resolve().parents[1]/".github/workflows/offline-android.yml").read_text());self.assertIn("[unsigned-trial-191]",w["jobs"]["lock-diagnostic"]["if"]);self.assertEqual(w["jobs"]["release"]["if"],chr(36)+"{{ false }}");self.assertEqual(w["jobs"]["unsigned-qualification"]["permissions"],{"contents":"read"})


class LeaseFailureDiagnostics(unittest.TestCase):
 def failed(self,**kwargs):return dict({"qualified":False,"callbackInvoked":True,"callbackSucceeded":True,"state":"INTERNAL_METADATA_QUALIFICATION_STOP","reason":"METADATA_CHANGED","metadataPhase":"POST_CALLBACK_INPUT","closeFailures":0},**kwargs)
 def test_nested_cause_saved_before_same_failure(self):
  import json
  from unittest.mock import patch
  from openssl_probe import ROOT
  from perl_overlay import require_lease
  inner=self.failed(metadataDifferences=[{"componentIndex":4,"directory":True,"changedFields":["bytes"],"before":{"bytes":4096},"after":{"bytes":8192}}])
  with patch("pathlib.Path.open") as opened,patch("builtins.print") as printed:
   with self.assertRaisesRegex(AssertionError,"OVERLAY_INTERPRETER_OR_SMOKE_FAILED"):require_lease(self.failed(reason="OVERLAY_MODULE_INPUT_FAILED"),"OVERLAY_INTERPRETER_OR_SMOKE_FAILED",ROOT/"dist","overlay-interpreter",nested={"moduleInput":inner},progress={"focusedOutputMatched":True})
  report=json.loads(opened.return_value.__enter__.return_value.write.call_args.args[0]);self.assertEqual(report["nested"]["moduleInput"]["reason"],"METADATA_CHANGED");self.assertEqual(report["nested"]["moduleInput"]["metadataDifferences"][0]["after"]["bytes"],8192);self.assertTrue(report["smokeProgress"]["focusedOutputMatched"]);opened.assert_called_once_with("x",encoding="utf-8");printed.assert_called_once()
 def test_success_does_not_write_or_raise(self):
  from perl_overlay import require_lease
  from openssl_probe import ROOT
  with patch("pathlib.Path.open") as opened,patch("builtins.print") as printed:require_lease({"qualified":True,"callbackSucceeded":True},"SYNTHETIC",ROOT/"dist","synthetic")
  opened.assert_not_called();printed.assert_not_called()
 def test_missing_callback_still_fails(self):
  from perl_overlay import require_lease
  from openssl_probe import ROOT
  with patch("pathlib.Path.open"),patch("builtins.print"):
   with self.assertRaisesRegex(AssertionError,"SYNTHETIC"):require_lease({"qualified":True},"SYNTHETIC",ROOT/"dist","synthetic")
 def test_access_denial_and_close_failure_not_hidden(self):
  from perl_overlay import sanitized_lease
  for row in ({"state":"OS_ACCESS_DENIED_STOP","osError":5,"qualified":False},{"state":"HANDLE_CLOSE_FAILURE_STOP","closeFailures":2,"qualified":False}):self.assertEqual(sanitized_lease(row),row)
 def test_private_text_paths_not_disclosed(self):
  import json
  from perl_overlay import sanitized_lease
  d=sanitized_lease({"state":"INTERNAL_METADATA_QUALIFICATION_STOP","reason":"synthetic-private@example.invalid","input":"C:/Users/synthetic-private/file","target":"synthetic-private","qualified":False});text=json.dumps(d)
  self.assertNotIn("synthetic-private",text);self.assertNotIn("@",text);self.assertEqual(d["reason"],"WITHHELD_NONCODE_VALUE");self.assertEqual(len(d["reasonSHA256"]),64)
 def test_stdout_cause_survives_report_write_failure(self):
  from perl_overlay import require_lease
  from openssl_probe import ROOT
  order=[]
  def opening(*a,**k):order.append("write");raise OSError(5,"synthetic report denial")
  with patch("pathlib.Path.open",side_effect=opening),patch("builtins.print",side_effect=lambda *a,**k:order.append("print")):
   with self.assertRaises(OSError):require_lease(self.failed(),"SYNTHETIC",ROOT/"dist","synthetic")
  self.assertEqual(order,["print","write"])
 def test_invalid_scope_does_not_write(self):
  import pathlib
  from perl_overlay import require_lease
  with patch("pathlib.Path.open") as opened:
   with self.assertRaisesRegex(AssertionError,"SCOPE"):require_lease(self.failed(),"SYNTHETIC",pathlib.Path("D:/unapproved-not-created"),"synthetic")
  opened.assert_not_called()
 def test_malformed_report_still_fails_safely(self):
  from perl_overlay import sanitized_lease,require_lease
  from openssl_probe import ROOT
  self.assertEqual(sanitized_lease(None)["state"],"UNAVAILABLE_LEASE_REPORT")
  self.assertTrue(sanitized_lease({"metadataDifferences":None})["metadataDiagnosticsInvalid"])
  with patch("pathlib.Path.open"),patch("builtins.print"):
   with self.assertRaisesRegex(AssertionError,"SYNTHETIC"):require_lease(None,"SYNTHETIC",ROOT/"dist","synthetic")
 def test_overlay_mode_returns_before_project_build(self):
  import ast,inspect,cloud_build
  tree=ast.parse(inspect.getsource(cloud_build.main));branches=[n for n in tree.body[0].body if isinstance(n,ast.If) and isinstance(n.test,ast.Name) and n.test.id=="overlay_probe"]
  probe=next(n for n in branches if any(isinstance(x,ast.Return) for x in n.body));calls=[x.func.id for x in ast.walk(probe) if isinstance(x,ast.Call) and isinstance(x.func,ast.Name)];self.assertIn("overlay_only_probe",calls);self.assertNotIn("bootstrap_for_cargo",calls);self.assertNotIn("qualify_make_link",calls)
 def test_probe_workflow_safe_entry(self):
  import pathlib,json
  w=json.loads((pathlib.Path(__file__).resolve().parents[1]/".github/workflows/offline-android.yml").read_text());j=w["jobs"]["overlay-probe"]
  self.assertIn("[overlay-probe-191]",j["if"]);self.assertEqual(j["permissions"],{"contents":"read"});self.assertEqual(j["steps"][3]["run"],"python -B ci/cloud_build.py --make-probe");self.assertIn("dist/lease-*.json",j["steps"][-1]["with"]["path"])

class ConfigureProbeEntry(unittest.TestCase):
 def test_configure_returns_before_make_and_cargo(self):
  import ast,inspect,cloud_build
  tree=ast.parse(inspect.getsource(cloud_build.main));branch=next(n for n in tree.body[0].body if isinstance(n,ast.If) and isinstance(n.test,ast.Name) and n.test.id=="configure_probe")
  self.assertTrue(any(isinstance(n,ast.Return) for n in branch.body));calls=[n.func.id for n in ast.walk(branch) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)]
  self.assertNotIn("qualify_make_link",calls);self.assertNotIn("run",calls)
  bootstrap=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=="bootstrap_for_cargo"];make=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=="qualify_make_link"]
  self.assertEqual(len(bootstrap),1);self.assertLess(bootstrap[0].lineno,branch.lineno);self.assertLess(branch.lineno,make[0].lineno)
 def test_mutable_scope_only_module_lease(self):
  import ast,inspect,perl_overlay
  tree=ast.parse(inspect.getsource(perl_overlay));calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=="capture_one" and any(k.arg=="mutable_ci_work" for k in n.keywords)]
  self.assertEqual(len(calls),1);self.assertEqual(calls[0].args[1].id,"module")
  expr=next(k.value for k in calls[0].keywords if k.arg=="mutable_ci_work");self.assertIsInstance(expr,ast.Compare);self.assertEqual(expr.left.id,"work");self.assertIn("ci-work",ast.unparse(expr))

class NativeArgumentBoundary(unittest.TestCase):
 def test_native_quoted_space_operands(self):
  from perl_overlay import tiny_makefile
  recipe=tiny_makefile("D:/a/Vibetram/Vibetram/ci-work/tool-smoke space")
  for name in ("probe source.c","probe object.o","probe archive.a","probe native.so"):self.assertIn('"$(VIBETRAM_SMOKE_DIR)/'+name+'"',recipe)
  self.assertNotIn("/d/a/",recipe);self.assertEqual(len([x for x in recipe.splitlines() if x.startswith("\t")]),5)
 def test_native_scope_injection_and_posix_rejected(self):
  from perl_overlay import tiny_makefile
  for value in ["/d/a/Vibetram/ci-work/tool-smoke space","D:/a/../ci-work/tool-smoke space","D:/a/./ci-work/tool-smoke space","D:/a/$x/ci-work/tool-smoke space",'D:/a/"x"/ci-work/tool-smoke space',"D:/a/ci-work/other","D:/a/ci-work/tool-smoke space;exit"]:
   with self.subTest(value=value),self.assertRaises(AssertionError):tiny_makefile(value)
 def test_roundtrip_schema_exact_path_and_identities(self):
  import pathlib
  from perl_overlay import validate_native_conversion
  p=pathlib.Path("D:/a/Vibetram/ci-work/tool-smoke space");native=p.as_posix();row={"native":native,"posix":"/d/a/Vibetram/ci-work/tool-smoke space","identityChecks":2};self.assertEqual(validate_native_conversion(row,p),native)
  for patcher in ({"native":"D:/other/ci-work/tool-smoke space"},{"posix":"/d/a/../ci-work/tool-smoke space"},{"identityChecks":1},{"unknown":"x"}):
   with self.subTest(patcher=patcher),self.assertRaises(AssertionError):validate_native_conversion({**row,**patcher},p)
 def recipe(self):return 'clang.exe -I. -Iinclude -fPIC --target=aarch64-linux-android29 -DOPENSSLDIR=\"\\\"/usr/local/ssl\\\"\" -MMD -MF crypto/libcrypto-lib-ctype.d.tmp -c -o crypto/libcrypto-lib-ctype.o crypto/ctype.c'
 def test_actual_recipe_relative_paths_and_directory_macros(self):
  from perl_overlay import validate_openssl_recipe
  args=validate_openssl_recipe(self.recipe());self.assertIn('-DOPENSSLDIR="/usr/local/ssl"',args);self.assertEqual(args[-1],"crypto/ctype.c")
 def test_recipe_wrong_source_output_target_or_extra_compiler_fatal(self):
  from perl_overlay import validate_openssl_recipe
  recipe=self.recipe()
  for changed in [recipe.replace("crypto/ctype.c","/d/a/crypto/ctype.c"),recipe.replace("crypto/libcrypto-lib-ctype.o","elsewhere.o"),recipe.replace("android29","android28"),recipe+"\n"+recipe,recipe+";touch forbidden",recipe.replace("-Iinclude","-I/d/include")]:
   with self.subTest(changed=changed),self.assertRaises(AssertionError):validate_openssl_recipe(changed)
 def test_conversion_real_helpers_and_identity_comparison(self):
  from perl_overlay import native_path_conversion_program
  s=native_path_conversion_program();self.assertIn("Cygwin::posix_to_win_path",s);self.assertIn("Cygwin::win_to_posix_path",s);self.assertIn("$a[1]==$c[1]",s);self.assertNotIn("system(",s)
 def test_probe_returns_after_tiny_qualification_before_cargo(self):
  import ast,inspect,cloud_build
  t=ast.parse(inspect.getsource(cloud_build.main));b=next(n for n in t.body[0].body if isinstance(n,ast.If) and isinstance(n.test,ast.Name) and n.test.id=="make_probe")
  self.assertTrue(any(isinstance(n,ast.Return) for n in b.body));calls=[n for n in ast.walk(t) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)]
  make=next(n for n in calls if n.func.id=="qualify_make_link");cargo=[n for n in calls if n.func.id=="run" and "cargo" in ast.unparse(n)]
  self.assertLess(make.lineno,b.lineno);self.assertTrue(all(n.lineno>b.lineno for n in cargo))

class SmokeArtifactIdentity(unittest.TestCase):
 def row(self,**kw):
  import types,stat
  return types.SimpleNamespace(**{**dict(st_dev=7,st_ino=10,st_mode=stat.S_IFREG,st_size=3,st_mtime_ns=1,st_ctime_ns=1,st_file_attributes=0),**kw})
 def test_fresh_regular_identity_and_hash(self):
  from unittest.mock import Mock
  from perl_overlay import smoke_artifact_identity
  p=Mock();p.lstat.return_value=self.row();p.read_bytes.return_value=b"abc";r=smoke_artifact_identity(p);self.assertEqual(r["identity"],[7,10]);self.assertEqual(r["sha256"],hashlib.sha256(b"abc").hexdigest())
 def test_reparse_and_replacement_and_mutation_fatal(self):
  from unittest.mock import Mock
  from perl_overlay import smoke_artifact_identity
  for row in (self.row(st_ino=11),self.row(st_size=4),self.row(st_file_attributes=0x400),self.row(st_mtime_ns=2)):
   p=Mock();p.lstat.side_effect=[self.row(),row];p.read_bytes.return_value=b"abc"
   with self.assertRaises(AssertionError):smoke_artifact_identity(p)
 def test_denial_not_zeroed(self):
  from unittest.mock import Mock
  from perl_overlay import smoke_artifact_identity
  p=Mock();p.lstat.side_effect=OSError(5,"synthetic")
  with self.assertRaises(OSError):smoke_artifact_identity(p)


class CargoPerlPathContract(unittest.TestCase):
 def env(self):return {'VIBETRAM_OPENSSL_CARGO_BRIDGE':'1','PERL5LIB':'/d/job space/ci-work/runtime-overlay/lib:/d/job space/ci-work/perl-overlay/lib','PATH':'host-unchanged'}
 def test_exact_exclusion_copy_and_spaces_preserved(self):
  from perl_overlay import preserve_cargo_perl_paths as f
  e=self.env();r=f(e);self.assertEqual(r['MSYS2_ENV_CONV_EXCL'],'PERL5LIB=');self.assertEqual(r['PERL5LIB'],e['PERL5LIB']);self.assertEqual(r['PATH'],e['PATH']);self.assertNotIn('MSYS2_ENV_CONV_EXCL',e)
 def test_drive_colon_backslash_and_semicolon_lists_rejected(self):
  from perl_overlay import preserve_cargo_perl_paths as f
  for value in ('D:/job/runtime-overlay/lib;D:/job/perl-overlay/lib',r'D:\job\runtime-overlay\lib;D:\job\perl-overlay\lib','/d/job/runtime-overlay/lib;/d/job/perl-overlay/lib'):
   with self.subTest(value=value),self.assertRaises(AssertionError):f({**self.env(),'PERL5LIB':value})
 def test_missing_extra_empty_and_swapped_entries_rejected(self):
  from perl_overlay import preserve_cargo_perl_paths as f
  entries=self.env()['PERL5LIB'].split(':')
  for value in ('',entries[0],':'.join(entries+entries[:1]),':'.join(reversed(entries)),':'.join([entries[0],''])):
   with self.subTest(value=value),self.assertRaises(AssertionError):f({**self.env(),'PERL5LIB':value})
 def test_traversal_other_root_and_unc_scope_rejected(self):
  from perl_overlay import preserve_cargo_perl_paths as f
  for value in (self.env()['PERL5LIB'].replace('/d/','//d/'),self.env()['PERL5LIB'].replace('job space','../job'),self.env()['PERL5LIB'].replace('/d/job space/ci-work/perl','/e/other/ci-work/perl')):
   with self.subTest(value=value),self.assertRaises(AssertionError):f({**self.env(),'PERL5LIB':value})
 def test_host_call_rejected_and_unrelated_environment_untouched(self):
  from perl_overlay import preserve_cargo_perl_paths as f
  with self.assertRaisesRegex(AssertionError,'BRIDGE_SCOPE'):f({'PERL5LIB':self.env()['PERL5LIB']})
  e={**self.env(),'MSYS2_ARG_CONV_EXCL':'unchanged','HOST_CC':'host-cl'};r=f(e);self.assertEqual(r['MSYS2_ARG_CONV_EXCL'],'unchanged');self.assertEqual(r['HOST_CC'],'host-cl')
 def test_wildcard_or_prefix_widening_not_accepted(self):
  from perl_overlay import preserve_cargo_perl_paths as f
  for value in ('*','PERL5LIB','PATH;PERL5LIB=','PERL5LIB_OTHER='):
   with self.subTest(value=value),self.assertRaises(AssertionError):f({**self.env(),'MSYS2_ENV_CONV_EXCL':value})
 def test_reentry_exact_exclusion_idempotent(self):
  from perl_overlay import preserve_cargo_perl_paths as f
  e=self.env();self.assertEqual(f(f(e)),f(e))
 def test_actual_android_builder_propagates_child_only_exclusion(self):
  from perl_overlay import preserve_cargo_perl_paths,build_android_environment
  from ndk_linker import NDK
  import pathlib
  e=self.env();r=build_android_environment(preserve_cargo_perl_paths(e),NDK,NDK/'toolchains/llvm/prebuilt/windows-x86_64/bin',pathlib.Path('C:/Program Files/Git/usr/bin/perl.exe'))
  self.assertEqual(r['MSYS2_ENV_CONV_EXCL'],'PERL5LIB=');self.assertEqual(r['PERL5LIB'],e['PERL5LIB']);self.assertNotIn('MSYS2_ENV_CONV_EXCL',e);self.assertTrue(r['CC_aarch64_linux_android'].endswith('clang.exe'))


class OpenSSLShellCommandBoundary(unittest.TestCase):
 def paths(self):
  from ndk_compilers import PATHS
  from ndk_linker import NDK
  return {"CC":PATHS["clang.exe"],"CXX":PATHS["clang++.exe"],"AR":NDK/"toolchains/llvm/prebuilt/windows-x86_64/bin/llvm-ar.exe","RANLIB":NDK/"toolchains/llvm/prebuilt/windows-x86_64/bin/llvm-ranlib.exe"}
 def test_exact_roles_shell_encoded_without_canonical_mutation(self):
  from perl_overlay import openssl_shell_tool
  for role,path in self.paths().items():
   raw=str(path);self.assertEqual(openssl_shell_tool(role,raw),"'"+path.as_posix()+"'");self.assertEqual(str(path),raw)
 def test_basename_standalone_qualification_is_unchanged(self):
  from perl_overlay import openssl_shell_tool
  for role,path in self.paths().items():self.assertEqual(openssl_shell_tool(role,path.name),path.name)
 def test_quoted_or_alternate_input_not_a_canonical_identity(self):
  from perl_overlay import openssl_shell_tool
  p=self.paths()["CC"]
  for v in ('"'+str(p)+'"',str(p).lower(),str(p).replace("Program Files (x86)","Android"),str(p).replace("30.0.16248370","30.0.0")):
   with self.subTest(value=v),self.assertRaises(AssertionError):openssl_shell_tool("CC",v)
 def test_command_arguments_and_metacharacters_are_not_accepted(self):
  from perl_overlay import openssl_shell_tool
  raw=str(self.paths()["CC"])
  for suffix in (' -DNAME=x','; false',' && false','| false','\nfalse','$(false)',chr(96)+'false'+chr(96),'"'):
   with self.subTest(suffix=suffix),self.assertRaises(AssertionError):openssl_shell_tool("CC",raw+suffix)
 def test_swapped_compiler_or_unselected_clang_cl_is_rejected(self):
  from perl_overlay import openssl_shell_tool
  for role,value in (("CC",str(self.paths()["CXX"])),("CXX",str(self.paths()["CC"])),("CC",str(self.paths()["CC"].with_name("clang-cl.exe")))):
   with self.subTest(role=role,value=value),self.assertRaises(AssertionError):openssl_shell_tool(role,value)
 def test_unknown_roles_and_nonstring_inputs_are_rejected(self):
  from perl_overlay import openssl_shell_tool
  for role,value in (("HOST_CC","clang.exe"),("LD","ld.lld.exe"),("CC",None),("CC",self.paths()["CC"])):
   with self.subTest(role=role,value=str(value)),self.assertRaises(AssertionError):openssl_shell_tool(role,value)
 def test_bridge_checks_configure_scope_hash_target_and_prefix_before_encoding(self):
  from perl_overlay import cargo_prefix_bridge_program
  s=cargo_prefix_bridge_program()
  self.assertLess(s.index('Configure identity changed'),s.index('my %shell_tools='))
  self.assertLess(s.index('unexpected OpenSSL install scope'),s.index('my %shell_tools='))
  self.assertIn('return unless grep {$_ eq "linux-aarch64"} @ARGV',s)
  self.assertIn('Configure target tool mismatch',s)
  self.assertNotIn('__VIBETRAM_OPENSSL_COMMANDS__',s)
 def test_encoding_does_not_rewrite_flags_or_target_identity_variables(self):
  from perl_overlay import openssl_shell_tools_program
  s=openssl_shell_tools_program()
  self.assertIn('$ENV{$role}=$encoded',s)
  self.assertNotIn('$ENV{$target}=',s)
  self.assertNotIn('CFLAGS=',s)
  self.assertNotIn('PATH}=',s)
 def test_generated_table_keeps_distinct_compilers_and_no_host_roles(self):
  from perl_overlay import openssl_shell_tools_program
  s=openssl_shell_tools_program()
  for value in ('clang.exe','clang++.exe','llvm-ar.exe','llvm-ranlib.exe','CC_aarch64_linux_android','CXX_aarch64_linux_android'):self.assertIn(value,s)
  for value in ('clang-cl','HOST_CC',"'link.exe'","'lib.exe'"):self.assertNotIn(value,s)
 def test_cargo_environment_remains_raw_and_host_separate(self):
  from perl_overlay import build_android_environment
  from ndk_linker import NDK
  from ndk_compilers import environment
  import pathlib
  parent={"PATH":"host","HOST_CC":"host-cl"};original=parent.copy()
  env=build_android_environment(parent,NDK,NDK/"toolchains/llvm/prebuilt/windows-x86_64/bin",pathlib.Path("C:/Program Files/Git/usr/bin/perl.exe"))
  environment(env);self.assertEqual(parent,original);self.assertEqual(env["HOST_CC"],"host-cl")
  for key in ("CC_aarch64_linux_android","CXX_aarch64_linux_android","CARGO_TARGET_AARCH64_LINUX_ANDROID_LINKER"):self.assertNotIn('"',env[key])


class TargetedCargoOpenSSLProbe(unittest.TestCase):
 def test_exact_configured_absolute_fields(self):
  from perl_overlay import configured_tool_fields,openssl_shell_tool
  from ndk_linker import NDK
  tools=NDK/"toolchains/llvm/prebuilt/windows-x86_64/bin"
  fields={"CROSS_COMPILE":"",**{role:"$(CROSS_COMPILE)"+openssl_shell_tool(role,str(tools/name)) for role,name in (("CC","clang.exe"),("CXX","clang++.exe"),("AR","llvm-ar.exe"),("RANLIB","llvm-ranlib.exe"))}}
  configured_tool_fields(fields,True)
  for role in ("CC","CXX","AR","RANLIB"):
   bad=dict(fields);bad[role]=bad[role].replace("'",'')
   with self.subTest(role=role),self.assertRaises(AssertionError):configured_tool_fields(bad,True)
 def recipe(self,target="crypto/libcrypto-lib-ctype.o",source="crypto/ctype.c"):
  from perl_overlay import openssl_shell_tool
  from ndk_compilers import PATHS
  return openssl_shell_tool("CC",str(PATHS["clang.exe"]))+" -I. -Iinclude --target=aarch64-linux-android29 -O2 -DANDROID -c -o "+target+" "+source
 def test_both_exact_targets_and_shell_decoding(self):
  from perl_overlay import cargo_recipe_arguments
  from ndk_compilers import PATHS
  for target,source in (("crypto/libcrypto-lib-ctype.o","crypto/ctype.c"),("crypto/aes/libcrypto-lib-aes-sha1-armv8.o","crypto/aes/aes-sha1-armv8.S")):
   args=cargo_recipe_arguments(self.recipe(target,source),target,source);self.assertEqual(args[0],PATHS["clang.exe"].as_posix());self.assertEqual(args[-1],source)
 def test_unquoted_compiler_path_rejected(self):
  from perl_overlay import cargo_recipe_arguments
  with self.assertRaises(AssertionError):cargo_recipe_arguments(self.recipe().replace("'",''),"crypto/libcrypto-lib-ctype.o","crypto/ctype.c")
 def test_duplicate_compiler_or_other_target_rejected(self):
  from perl_overlay import cargo_recipe_arguments
  for text,target,src in ((self.recipe()+"\n"+self.recipe(),"crypto/libcrypto-lib-ctype.o","crypto/ctype.c"),(self.recipe(),"other.o","crypto/ctype.c")):
   with self.subTest(target=target),self.assertRaises(AssertionError):cargo_recipe_arguments(text,target,src)
 def test_command_injection_and_wrong_roles_rejected(self):
  from perl_overlay import cargo_recipe_arguments
  for text in (self.recipe()+"; false",self.recipe().replace("clang.exe","clang++.exe"),self.recipe().replace("-Iinclude","-I/unknown"),self.recipe().replace("-O2","$(unexpected)")):
   with self.subTest(text=text[:60]),self.assertRaises(AssertionError):cargo_recipe_arguments(text,"crypto/libcrypto-lib-ctype.o","crypto/ctype.c")
 def test_target_environment_requires_bridge_and_fresh_pins(self):
  import perl_overlay as p,pathlib,types
  from unittest.mock import patch
  from ndk_linker import NDK
  from ndk_compilers import PATHS
  g=types.SimpleNamespace(_resource_sample=lambda:None)
  with self.assertRaises(AssertionError):p.cargo_command_environment(g,{},NDK,PATHS["clang.exe"].parent,pathlib.Path("C:/Program Files/Git/usr/bin/perl.exe"))
  env={"PATH":"host","VIBETRAM_OPENSSL_CARGO_BRIDGE":"1","HOST_CC":"unchanged"}
  with patch("ndk_linker.qualify",return_value={"link-pin":"fresh"}) as ld,patch("ndk_compilers.qualify",return_value={"compiler-pin":"fresh"}) as cc:
   result=p.cargo_command_environment(g,env,NDK,PATHS["clang.exe"].parent,pathlib.Path("C:/Program Files/Git/usr/bin/perl.exe"))
  self.assertEqual(result["CC"],str(PATHS["clang.exe"]));self.assertEqual(result["CXX"],str(PATHS["clang++.exe"]));self.assertEqual(result["HOST_CC"],"unchanged");self.assertEqual(ld.call_count,1);self.assertEqual(cc.call_count,1);self.assertNotIn("CC",env)
 def test_workflow_is_targeted_and_bounded(self):
  import pathlib
  w=json.loads((pathlib.Path(__file__).resolve().parents[1]/".github/workflows/offline-android.yml").read_text());j=w["jobs"]["openssl-probe"]
  self.assertEqual(j["timeout-minutes"],12);self.assertEqual(j["permissions"],{"contents":"read"});self.assertEqual(j["steps"][1]["run"],"python -B ci/perl_overlay.py --runtime-direct-output");self.assertEqual(j["steps"][1]["timeout-minutes"],10);self.assertEqual(j["steps"][2]["with"]["retention-days"],3)
  self.assertFalse(any("provision" in str(s).lower() for s in j["steps"]));self.assertIn("[unsigned-trial-191]",w["jobs"]["unsigned-qualification"]["if"]);self.assertEqual(w["jobs"]["release"]["if"],chr(36)+"{{ false }}")


class IntegratedCommandEvidence(unittest.TestCase):
 def work(self):
  import pathlib
  return pathlib.Path("D:/a/Vibetram/Vibetram/openssl-probe-work")
 def recipe(self,assembly=False):
  from perl_overlay import openssl_shell_tool
  from ndk_compilers import PATHS
  target="crypto/aes/libcrypto-lib-aes-sha1-armv8.o" if assembly else "crypto/libcrypto-lib-ctype.o"
  source="crypto/aes/aes-sha1-armv8.S" if assembly else "crypto/ctype.c"
  return openssl_shell_tool("CC",str(PATHS["clang.exe"]))+" -I. --target=aarch64-linux-android29 -c -o "+target+" "+source,target,source
 def generator(self):
  from perl_overlay import openssl_shell_tool
  from ndk_compilers import PATHS
  return 'CC="'+openssl_shell_tool("CC",str(PATHS["clang.exe"]))+'" perl.exe -I. -Iutil/perl crypto/aes/asm/aes-sha1-armv8.pl "linux64" -Icrypto -DANDROID crypto/aes/aes-sha1-armv8.S'
 def test_compiler_and_generator_classified_separately(self):
  from perl_overlay import cargo_recipe_arguments
  cc,t,s=self.recipe(True);args=cargo_recipe_arguments(self.generator()+"\n"+cc,t,s,True);self.assertTrue(args[0].endswith("/clang.exe"))
 def test_generator_presence_bound_to_source_state(self):
  from perl_overlay import cargo_recipe_arguments
  cc,t,s=self.recipe(True);cargo_recipe_arguments(cc,t,s,False)
  with self.assertRaises(AssertionError):cargo_recipe_arguments(cc,t,s,True)
  with self.assertRaises(AssertionError):cargo_recipe_arguments(self.generator()+"\n"+cc,t,s,False)
 def test_duplicate_unknown_or_other_generator_commands_fatal(self):
  from perl_overlay import cargo_recipe_arguments
  cc,t,s=self.recipe(True)
  for output in (self.generator()+"\n"+self.generator()+"\n"+cc,self.generator().replace("aes-sha1-armv8.pl","unknown.pl")+"\n"+cc,cc+"\necho unknown",cc.replace("clang.exe","clang-cl.exe")):
   with self.subTest(output=output[:50]),self.assertRaises(AssertionError):cargo_recipe_arguments(output,t,s,True)
 def test_normal_command_complete_with_normalized_root(self):
  from perl_overlay import command_evidence
  cc,t,s=self.recipe();r=command_evidence(cc,t,self.work());self.assertTrue(r["completeForQualification"]);self.assertIn("<ndk>",r["normalizedCommandText"]);self.assertNotIn("Program Files",r["normalizedCommandText"])
 def test_generator_command_complete(self):
  from perl_overlay import command_evidence
  cc,t,s=self.recipe(True);self.assertTrue(command_evidence(self.generator()+"\n"+cc,t,self.work())["completeForQualification"])
 def test_work_relative_macro_is_normalized(self):
  from perl_overlay import command_evidence
  cc,t,s=self.recipe();text=cc.replace("-I.",'-I. -DENGINESDIR=\\"/d/a/Vibetram/Vibetram/openssl-probe-work/install/lib\\"');r=command_evidence(text,t,self.work());self.assertTrue(r["completeForQualification"]);self.assertIn("<work>",r["normalizedCommandText"])
 def test_package_constant_openssldir_is_allowed(self):
  from perl_overlay import command_evidence
  cc,t,s=self.recipe();r=command_evidence(cc.replace("-I.",'-I. -DOPENSSLDIR=\\"/usr/local/ssl\\"'),t,self.work());self.assertTrue(r["completeForQualification"])
 def test_outside_root_forms_are_withheld_and_fatal(self):
  from perl_overlay import command_evidence
  cc,t,s=self.recipe()
  paths=["E:/private/file","D:/outside/file","C:/Users/synthetic-person/file",r"C:\Users\synthetic-person\file",r"\\server\share\file",r"\\?\C:\outside",r"\\.\C:\outside","//server/share/file","/etc/private","-I/outside","~/private","C:relative","D:/a/Vibetram/Vibetram/openssl-probe-work-other/file","D:/a/Vibetram/Vibetram/openssl-probe-work/../outside","D:/a/Vibetram/Vibetram/openssl-probe-work/../../outside","c:/program files (x86)/Android/android-sdk/ndk/30.0.16248370/toolchains/llvm/prebuilt/windows-x86_64/bin/clang.exe"]
  for value in paths:
   with self.subTest(value=value):
    r=command_evidence(cc+" "+value,t,self.work());self.assertFalse(r["completeForQualification"]);self.assertNotIn("normalizedCommandText",r)
 def test_control_unicode_malformed_and_markers_fatal(self):
  from perl_overlay import command_evidence
  cc,t,s=self.recipe()
  for suffix in ("\x00","\u202eprivate"," 'unterminated"," <ndk>/spoof"," $(PRIVATE)"," "+chr(96)+"unknown"+chr(96)):
   with self.subTest(suffix=repr(suffix)):
    r=command_evidence(cc+suffix,t,self.work());self.assertFalse(r["completeForQualification"]);self.assertNotIn("normalizedCommandText",r)
 def test_private_values_never_retained(self):
  from perl_overlay import command_evidence
  cc,t,s=self.recipe()
  for suffix in (" TOKEN=synthetic-private-value"," PASSWORD=synthetic-private-value"," owner@example.invalid"):
   r=command_evidence(cc+suffix,t,self.work());self.assertFalse(r["completeForQualification"]);self.assertNotIn("synthetic-private-value",json.dumps(r));self.assertNotIn("owner@example.invalid",json.dumps(r))
 def test_oversize_and_line_bound_fail_with_metadata_only(self):
  from perl_overlay import command_evidence
  cc,t,s=self.recipe()
  for output in (cc+"x"*32769,"\n".join([cc]*129)):
   r=command_evidence(output,t,self.work());self.assertFalse(r["completeForQualification"]);self.assertNotIn("normalizedCommandText",r);self.assertLess(len(json.dumps(r)),1024)
 def store(self,deny=False):
  import io
  values={}
  class File:
   def __init__(self,name):self.name=name
   def open(self,mode):
    if deny:raise PermissionError(5,"synthetic")
    if self.name in values:raise FileExistsError
    class Buffer(io.BytesIO):
     def __enter__(b):return b
     def __exit__(b,*args):values[self.name]=b.getvalue();b.close()
    return Buffer()
  class Out:
   def __truediv__(self,name):return File(name)
  return Out(),values
 def test_prevalidation_receipt_survives_unknown_command_failure(self):
  from perl_overlay import validated_command_evidence
  cc,t,s=self.recipe();out,values=self.store()
  with self.assertRaises(AssertionError):validated_command_evidence(out,"dryrun",cc+"\nunknown",t,s,self.work(),False)
  self.assertEqual(len(values),2);initial=json.loads(values["command-ctype-dryrun.json"]);failure=json.loads(values["command-ctype-dryrun-failure.json"])
  self.assertFalse(initial["completeForQualification"]);self.assertFalse(failure["partialBuildAccepted"]);self.assertEqual(failure["code"],"COMMAND_EVIDENCE_INCOMPLETE")
 def test_parser_failure_retains_safe_complete_input(self):
  from perl_overlay import validated_command_evidence
  cc,t,s=self.recipe();cc=stage_recipe(cc);out,values=self.store()
  with self.assertRaises(AssertionError):validated_command_evidence(out,"dryrun",cc.replace(" -c "," -c -c "),t,s,self.work(),False)
  self.assertTrue(json.loads(values["command-ctype-dryrun.json"])["completeForQualification"]);self.assertEqual(json.loads(values["command-ctype-dryrun-failure.json"])["code"],"TARGETED_RECIPE_IDENTITY")
 def test_receipt_denial_stops_without_fallback(self):
  from perl_overlay import validated_command_evidence
  cc,t,s=self.recipe();out,values=self.store(True)
  with self.assertRaises(PermissionError):validated_command_evidence(out,"dryrun",cc,t,s,self.work(),False)
  self.assertEqual(values,{})
 def test_error_codes_preserved_without_arbitrary_exception_text(self):
  import perl_overlay as p
  from unittest.mock import patch
  cc,t,s=self.recipe();cc=stage_recipe(cc);out,values=self.store();err=OSError(5,"synthetic-private-message");err.winerror=32
  with patch("perl_overlay.cargo_recipe_arguments",side_effect=err),self.assertRaises(OSError):p.validated_command_evidence(out,"dryrun",cc,t,s,self.work(),False)
  failure=json.loads(values["command-ctype-dryrun-failure.json"]);self.assertEqual(failure["errno"],5);self.assertEqual(failure["winerror"],32);self.assertNotIn("synthetic-private-message",json.dumps(failure))
 def test_receipt_scope_and_size_fail_closed(self):
  from perl_overlay import put_command_evidence
  out,values=self.store()
  for stage,target,row in (("other","crypto/libcrypto-lib-ctype.o",{}),("dryrun","outside",{}),("object","crypto/libcrypto-lib-ctype.o",{"x":"a"*50000})):
   with self.subTest(stage=stage),self.assertRaises(AssertionError):put_command_evidence(out,stage,target,row)
  self.assertEqual(values,{})
 def test_live_call_wiring_before_parse_and_each_object_checkpoint(self):
  import inspect,perl_overlay as p
  text=inspect.getsource(p.qualify_cargo_objects)
  self.assertIn('validated_command_evidence(out,"dryrun"',text);self.assertIn('validated_command_evidence(out,"executed"',text);self.assertIn('put_command_evidence(out,"object"',text);self.assertIn('TARGETED_GENERATOR_CHANGED',text)
  text=inspect.getsource(p.validated_command_evidence);self.assertLess(text.index("put_command_evidence(out,stage"),text.index("return cargo_recipe_arguments"))

class StructuralCommandEvidence(unittest.TestCase):

    def setUp(self):
        from perl_overlay import command_evidence
        self.evidence = command_evidence
        fixture = IntegratedCommandEvidence()
        self.cc, self.target, _ = fixture.recipe()
        self.work = fixture.work()

    def unknown(self, text):
        r = self.evidence(text, self.target, self.work)
        self.assertEqual(r['state'], 'COMMAND_UNCLASSIFIED_FATAL')
        self.assertFalse(r['completeForQualification'])
        self.assertNotIn('normalizedCommandText', r)
        return r

    def test_known_compiler_unchanged(self):
        self.assertTrue(self.evidence(self.cc, self.target, self.work)['completeForQualification'])

    def test_unknown_line_index(self):
        r = self.unknown('\n' + self.cc + '\n\nunknown value')
        self.assertEqual(r['rejectedLineIndex'], 4)
        self.assertEqual(r['tokenCount'], 2)

    def test_hash_exact_normalized_line(self):
        self.assertEqual(self.unknown('unknown value')['lineSHA256'], hashlib.sha256(b'unknown value').hexdigest())

    def test_arbitrary_text_not_retained(self):
        r = self.unknown('owner-private-name confidential-value')
        self.assertNotIn('owner-private-name', json.dumps(r))
        self.assertNotIn('confidential-value', json.dumps(r))

    def test_fixed_shape_labels_only(self):
        r = self.unknown('perl.exe -I. arbitrary=value private')
        self.assertEqual(r['commandShape'], {'head': 'perl', 'arguments': ['option', 'assignment', 'value'], 'omittedArguments': 0})

    def test_shape_truncated(self):
        r = self.unknown('unknown ' + ' '.join(['private'] * 100))
        self.assertEqual(len(r['commandShape']['arguments']), 16)
        self.assertEqual(r['commandShape']['omittedArguments'], 84)
        self.assertLess(len(json.dumps(r)), 1200)

    def test_outside_windows_withheld(self):
        r = self.evidence('unknown C:/Users/private/file', self.target, self.work)
        self.assertEqual(r['state'], 'COMMAND_UNAPPROVED_PATH_FATAL')
        self.assertNotIn('commandShape', r)

    def test_posix_private_unknown_not_retained(self):
        self.assertNotIn('/private/owner/file', json.dumps(self.unknown('unknown /private/owner/file')))

    def test_secret_before_classification(self):
        r = self.evidence('unknown TOKEN=synthetic-secret', self.target, self.work)
        self.assertEqual(r['state'], 'COMMAND_PRIVATE_FIELD_FATAL')
        self.assertNotIn('synthetic-secret', json.dumps(r))

    def test_unterminated_quotes_unchanged(self):
        self.assertEqual(self.evidence("unknown 'private", self.target, self.work)['state'], 'COMMAND_QUOTING_FATAL')

    def test_size_guard_unchanged(self):
        self.assertEqual(self.evidence('x' * 32769, self.target, self.work)['state'], 'COMMAND_TEXT_SIZE_FATAL')

    def test_unsafe_metacharacter_unchanged(self):
        self.assertEqual(self.evidence('unknown $(private)', self.target, self.work)['state'], 'COMMAND_UNAPPROVED_PATH_FATAL')

    def test_blank_and_valid_lines(self):
        self.assertTrue(self.evidence('\n' + self.cc + '\n', self.target, self.work)['completeForQualification'])

    def test_empty_quoted_head_is_fatal(self):
        self.assertEqual(self.unknown("'' private")['commandShape']['head'], 'other')


class TargetBoundDependencySequence(unittest.TestCase):
 def setUp(self):
  import perl_overlay as p
  self.p=p;f=IntegratedCommandEvidence();self.cc,self.target,self.source=f.recipe();self.work=f.work()
  self.dep="crypto/libcrypto-lib-ctype.d"
  self.cc=self.cc.replace(" -c "," -MMD -MF "+self.dep+".tmp -c ")
  self.tail=["touch "+self.dep+".tmp","if cmp "+self.dep+".tmp "+self.dep+" > /dev/null 2> /dev/null; then "+chr(92),"rm -f "+self.dep+".tmp; "+chr(92),"else "+chr(92),"mv "+self.dep+".tmp "+self.dep+"; "+chr(92),"fi"]
  self.dry="\n".join([self.cc]+self.tail)
 def parse(self,text=None,stage="dryrun"):
  return self.p.cargo_recipe_arguments(self.dry if text is None else text,self.target,self.source,False,stage)
 def rejected(self,text,stage="dryrun"):
  with self.assertRaises(AssertionError):self.parse(text,stage)
  r=self.p.command_evidence(text,self.target,self.work,stage);self.assertFalse(r["completeForQualification"]);self.assertNotIn("normalizedCommandText",r)
 def test_exact_sequence(self):self.assertEqual(self.parse(),self.parse(self.cc,"executed"))
 def test_evidence_normalizes_complete_selected_sequence(self):
  r=self.p.command_evidence(self.dry,self.target,self.work,"dryrun");self.assertTrue(r["completeForQualification"]);self.assertNotIn("touch",r["normalizedCommandText"])
 def test_hash_proven_touch_line(self):
  import hashlib
  self.assertEqual(hashlib.sha256(self.tail[0].encode()).hexdigest(),"23433cb6db792feb76c7a05baf1e2dea1f1ad3666df8d8f48d9714daf742e585")
 def test_missing_touch(self):self.rejected("\n".join([self.cc]+self.tail[1:]))
 def test_touch_alone_not_allowed(self):self.rejected(self.cc+"\n"+self.tail[0])
 def test_wrong_target(self):self.rejected(self.dry.replace(self.dep,"crypto/other.d"))
 def test_outside_path(self):self.rejected(self.dry.replace(self.dep,"/outside/private"))
 def test_parent_escape(self):self.rejected(self.dry.replace(self.dep,"crypto/../outside"))
 def test_extra_command(self):self.rejected(self.dry+"\necho private")
 def test_reordered_block(self):self.rejected("\n".join([self.cc]+self.tail[::-1]))
 def test_duplicate_block(self):self.rejected(self.dry+"\n"+"\n".join(self.tail))
 def test_wrong_cmp_redirection(self):self.rejected(self.dry.replace("2> /dev/null","2> /outside/private"))
 def test_missing_backslash(self):self.rejected(self.dry.replace(chr(92),"",1))
 def test_changed_remove_flags(self):self.rejected(self.dry.replace("rm -f ","rm -rf "))
 def test_changed_rename_target(self):self.rejected(self.dry.replace("mv "+self.dep+".tmp "+self.dep,"mv "+self.dep+".tmp crypto/unrelated.d"))
 def test_executed_silent_output(self):self.assertTrue(self.p.command_evidence(self.cc,self.target,self.work,"executed")["completeForQualification"])
 def test_executed_echoed_block_fatal(self):self.rejected(self.dry,"executed")
 def test_unknown_compiler_fatal(self):self.rejected(self.dry.replace("clang.exe","unexpected.exe"))
 def test_wrong_compiler_dep_destination(self):
  with self.assertRaisesRegex(AssertionError,"TARGETED_DEPENDENCY_COMPILER_OUTPUT"):self.parse(self.dry.replace("-MF "+self.dep+".tmp","-MF crypto/other.d.tmp"))
 def test_duplicate_dependency_flags(self):
  with self.assertRaisesRegex(AssertionError,"TARGETED_DEPENDENCY_COMPILER_OUTPUT"):self.parse(self.dry.replace("-MMD","-MMD -MMD"))
 def test_stage_required_enum(self):
  with self.assertRaises(AssertionError):self.parse(stage="other")
 def test_assembly_still_rejects_maintenance(self):
  cc,t,source=IntegratedCommandEvidence().recipe(True)
  with self.assertRaises(AssertionError):self.p.cargo_recipe_arguments(cc+"\n"+self.tail[0],t,source,False,"dryrun")
 def test_crlf_and_recipe_indentation(self):self.assertEqual(self.parse(),self.parse("\r\n".join("\t"+x for x in [self.cc]+self.tail)))
 def test_unknown_text_withheld(self):
  r=self.p.command_evidence(self.dry+"\nowner-private-value",self.target,self.work,"dryrun");self.assertNotIn("owner-private-value",json.dumps(r))
 def test_default_classifier_still_rejects_maintenance(self):self.assertFalse(self.p.command_evidence(self.dry,self.target,self.work)["completeForQualification"])


def stage_recipe(cc):
 dep="crypto/libcrypto-lib-ctype.d"
 cc=cc.replace(" -c "," -MMD -MF "+dep+".tmp -c ")
 return "\n".join([cc,"touch "+dep+".tmp","if cmp "+dep+".tmp "+dep+" > /dev/null 2> /dev/null; then "+chr(92),"rm -f "+dep+".tmp; "+chr(92),"else "+chr(92),"mv "+dep+".tmp "+dep+"; "+chr(92),"fi"])

def admitted_test_root(environ=None,api=None):
 import contextlib,os,pathlib,re
 @contextlib.contextmanager
 def lease():
  env=os.environ if environ is None else environ
  if "VIBETRAM_TEST_TMP" in env:raw=env["VIBETRAM_TEST_TMP"]
  else:
   assert env.get("GITHUB_ACTIONS")=="true" and env.get("RUNNER_OS")=="Windows","FIXTURE_ROOT_NOT_ADMITTED"
   raw=env.get("RUNNER_TEMP")
  assert type(raw) is str and 0<len(raw)<=1024 and not any(ord(c)<32 for c in raw),"FIXTURE_ROOT_VALUE"
  assert not any(c in raw for c in ("%","$","~")) and not any(x in (".","..") for x in raw.replace(chr(92),"/").split("/")),"FIXTURE_ROOT_SYNTAX"
  path=pathlib.Path(raw)
  assert path.is_absolute() and re.fullmatch("[A-Za-z]:",path.drive) and 3<=len(path.parts)<=24,"FIXTURE_ROOT_SCOPE"
  for part in path.parts[1:]:
   assert not part.endswith((" ",".")) and ":" not in part and not re.fullmatch(r"(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?",part),"FIXTURE_ROOT_COMPONENT"
  import perl_overlay
  reader=api or perl_overlay.TemplateInputAPI();held=[];rows=[];primary=None
  def opened(part):
   h=reader.open(part);held.append(h);row=reader.info(h)
   assert row["tag"]==0 and not row["attributes"]&0x400 and row["attributes"]&0x10,"FIXTURE_ROOT_NOT_REGULAR_DIRECTORY"
   return h,row
  try:
   part=pathlib.Path(path.anchor)
   for i,name in enumerate(path.parts):
    if i:part=part/name
    h,row=opened(part);rows.append((part,h,row))
   yield path
   for part,h,before in rows:
    current=reader.info(h);_,fresh=opened(part)
    assert all(before[k]==current[k]==fresh[k] for k in ("identity","attributes","tag")),"FIXTURE_ROOT_IDENTITY_CHANGED"
  except BaseException as e:primary=e;raise
  finally:
   failed=False
   for h in reversed(held):
    try:failed=not reader.close(h) or failed
    except BaseException:failed=True
   if failed:
    if primary is not None:primary.add_note("FIXTURE_ROOT_HANDLE_CLOSE_FAILED")
    else:raise AssertionError("FIXTURE_ROOT_HANDLE_CLOSE_FAILED")
 return lease()

class TemplateAndStageIntegration(unittest.TestCase):
 def setUp(self):
  import perl_overlay as p
  from unittest.mock import patch
  self.p=p;self.payload=b"bounded-template-fixture";self.patches=[patch.object(p,"OPENSSL_TEMPLATE_BYTES",len(self.payload)),patch.object(p,"OPENSSL_TEMPLATE_SHA256",hashlib.sha256(self.payload).hexdigest())]
  for x in self.patches:x.start()
  self.addCleanup(lambda:[x.stop() for x in reversed(self.patches)])
  self.src=pathlib.Path("D:/owned/crate/openssl")
 def api(self,mode=None):
  payload=self.payload
  class Fake:
   def __init__(self):self.handles={};self.opened=[];self.closed=[];self.done=False;self.ids={}
   def open(self,path,read=False):
    if mode=="missing" and path.name=="unix-Makefile.tmpl":raise FileNotFoundError(2,"synthetic")
    if mode=="denied":raise PermissionError(13,"synthetic")
    key=str(path);self.ids.setdefault(key,len(self.ids)+1);h=len(self.opened)+1;self.handles[h]=path;self.opened.append(h);return h
   def info(self,h):
    path=self.handles[h];leaf=path.name=="unix-Makefile.tmpl";index=self.ids[str(path)]
    r={"identity":[1,index,0],"attributes":0x80 if leaf else 0x10,"tag":0,"bytes":len(payload) if leaf else 64}
    if mode=="reparse" and leaf or mode=="ancestor-reparse" and not leaf:r.update(attributes=r["attributes"]|0x400,tag=0xA000000C)
    if mode=="leaf-directory" and leaf:r["attributes"]=0x10
    if mode=="ancestor-file" and not leaf:r["attributes"]=0x80
    if mode=="wrong-size" and leaf:r["bytes"]+=1
    if self.done and (mode=="replacement" and leaf or mode=="ancestor-change" and not leaf):r["identity"]=[1,index+100,0]
    if self.done and mode=="directory-growth" and not leaf:r["bytes"]+=4096
    return r
   def read(self,h,limit):
    self.done=True
    if mode=="read-denied":raise PermissionError(13,"synthetic")
    return b"x"*len(payload) if mode=="wrong-hash" else payload+b"x" if mode=="long-read" else payload
   def close(self,h):
    self.closed.append(h)
    if mode=="close-exception" and len(self.closed)==1:raise OSError(5,"synthetic")
    return mode!="close-false"
  return Fake()
 def check(self,mode=None):
  a=self.api(mode)
  try:return self.p.qualify_openssl_template(self.src,api=a)
  finally:self.assertEqual(set(a.opened),set(a.closed))
 def test_exact_file_and_ancestors(self):self.assertTrue(self.check()["noFollowRegularChain"])
 def test_missing(self):
  with self.assertRaises(FileNotFoundError):self.check("missing")
 def test_denial(self):
  with self.assertRaises(PermissionError):self.check("denied")
 def test_wrong_hash(self):
  with self.assertRaisesRegex(AssertionError,"TEMPLATE_HASH_MISMATCH"):self.check("wrong-hash")
 def test_wrong_size(self):
  with self.assertRaisesRegex(AssertionError,"TEMPLATE_SIZE_MISMATCH"):self.check("wrong-size")
 def test_replacement(self):
  with self.assertRaisesRegex(AssertionError,"TEMPLATE_IDENTITY_CHANGED"):self.check("replacement")
 def test_ancestor_identity(self):
  with self.assertRaisesRegex(AssertionError,"TEMPLATE_IDENTITY_CHANGED"):self.check("ancestor-change")
 def test_leaf_reparse(self):
  with self.assertRaisesRegex(AssertionError,"TEMPLATE_REPARSE"):self.check("reparse")
 def test_ancestor_reparse(self):
  with self.assertRaisesRegex(AssertionError,"TEMPLATE_REPARSE"):self.check("ancestor-reparse")
 def test_wrong_component_type(self):
  for mode in ("leaf-directory","ancestor-file"):
   with self.subTest(mode=mode),self.assertRaisesRegex(AssertionError,"TEMPLATE_COMPONENT_TYPE"):self.check(mode)
 def test_directory_allocation_not_identity(self):self.assertTrue(self.check("directory-growth")["noFollowRegularChain"])
 def test_read_denial_closes_all(self):
  with self.assertRaises(PermissionError):self.check("read-denied")
 def test_read_size_overrun(self):
  with self.assertRaisesRegex(AssertionError,"TEMPLATE_HASH_MISMATCH"):self.check("long-read")
 def test_close_failure(self):
  for mode in ("close-false","close-exception"):
   with self.subTest(mode=mode),self.assertRaisesRegex(AssertionError,"TEMPLATE_HANDLE_CLOSE_FAILED"):self.check(mode)
 def test_metadata_deadline(self):
  a=self.api();ticks=iter([0,6])
  with self.assertRaisesRegex(AssertionError,"TEMPLATE_METADATA_DEADLINE"):self.p.qualify_openssl_template(self.src,api=a,clock=lambda:next(ticks))
  self.assertEqual(a.opened,a.closed)
 def test_scope(self):
  with self.assertRaisesRegex(AssertionError,"TEMPLATE_SOURCE_SCOPE"):self.p.qualify_openssl_template(pathlib.Path("relative"),api=self.api())
 def test_explicit_wrapper_stages(self):
  f=IntegratedCommandEvidence();cc,t,source=f.recipe();dry=stage_recipe(cc);out,_=f.store()
  argv=self.p.validated_command_evidence(out,"dryrun",dry,t,source,f.work(),False)
  cc=dry.splitlines()[0];out,_=f.store()
  self.assertEqual(argv,self.p.validated_command_evidence(out,"executed",cc,t,source,f.work(),False))
 def test_wrong_stage(self):
  f=IntegratedCommandEvidence();cc,t,source=f.recipe();out,_=f.store()
  with self.assertRaisesRegex(AssertionError,"COMMAND_STAGE"):self.p.validated_command_evidence(out,"other",cc,t,source,f.work(),False)
 def test_executed_maintenance_remains_fatal(self):
  f=IntegratedCommandEvidence();cc,t,source=f.recipe();out,values=f.store()
  with self.assertRaisesRegex(AssertionError,"COMMAND_EVIDENCE_INCOMPLETE"):self.p.validated_command_evidence(out,"executed",stage_recipe(cc),t,source,f.work(),False)
  self.assertFalse(json.loads(values["command-ctype-executed-failure.json"])["partialBuildAccepted"])
 def test_wiring_and_template_checks(self):
  import inspect
  text=inspect.getsource(self.p.validated_command_evidence)
  self.assertIn("command_evidence(output,target,work,stage)",text);self.assertIn("cargo_recipe_arguments(output,target,source,generator_required,stage,direct_output=direct_output)",text)
  text=inspect.getsource(self.p.qualify_cargo_objects);self.assertGreaterEqual(text.count("verify_template()"),5);self.assertIn("TARGETED_TEMPLATE_SOURCE_SCOPE",text)
 def test_real_windows_held_read(self):
  import os
  if os.name!="nt":self.skipTest("Windows only")
  import uuid
  with admitted_test_root() as admitted:
   root=admitted/("template-real-"+uuid.uuid4().hex);assert not root.exists(),"FIXTURE_CHILD_COLLISION"
   (root/"Configurations").mkdir(parents=True)
   file=root/"Configurations/unix-Makefile.tmpl";file.write_bytes(self.payload)
   result=self.p.qualify_openssl_template(root);self.assertEqual(result["sha256"],hashlib.sha256(self.payload).hexdigest())
   api=self.p.TemplateInputAPI();h=api.open(file,True)
   try:
    with self.assertRaises(OSError):file.write_bytes(b"change")
   finally:self.assertTrue(api.close(h))
   self.assertEqual(file.read_bytes(),self.payload)


class FixtureRootAdmission(unittest.TestCase):
 def setUp(self):
  self.root=pathlib.Path("D:/owned/admitted-fixtures")
  self.explicit={"VIBETRAM_TEST_TMP":str(self.root)}
  self.hosted={"GITHUB_ACTIONS":"true","RUNNER_OS":"Windows","RUNNER_TEMP":str(self.root)}
 def api(self,mode=None):
  root=self.root
  class Fake:
   def __init__(self):self.opened=[];self.closed=[];self.paths={};self.ids={};self.changed=False
   def open(self,path,read=False):
    if mode=="denied":raise PermissionError(13,"synthetic")
    if mode=="missing" and path==root:raise FileNotFoundError(2,"synthetic")
    self.ids.setdefault(str(path),len(self.ids)+1);h=len(self.opened)+1;self.opened.append(h);self.paths[h]=path;return h
   def info(self,h):
    path=self.paths[h];r={"identity":[1,self.ids[str(path)],0],"attributes":0x10,"tag":0,"bytes":4096 if self.changed else 64}
    if mode=="reparse" and path==root:r.update(attributes=0x410,tag=0xA000000C)
    if mode=="ancestor-reparse" and path!=root:r.update(attributes=0x410,tag=0xA000000C)
    if mode=="file" and path==root:r["attributes"]=0x80
    if mode=="replacement" and self.changed and path==root:r["identity"]=[1,999,0]
    return r
   def close(self,h):
    self.closed.append(h)
    return mode!="close-false"
  return Fake()
 def selected(self,env,mode=None,mutate=False):
  a=self.api(mode)
  try:
   with admitted_test_root(env,a) as root:
    self.assertEqual(root,self.root)
    if mutate:a.changed=True
  finally:self.assertEqual(set(a.opened),set(a.closed))
 def test_explicit_root(self):self.selected(self.explicit)
 def test_hosted_root(self):self.selected(self.hosted)
 def test_explicit_precedence(self):self.selected({**self.hosted,"RUNNER_TEMP":"C:/outside/unused","VIBETRAM_TEST_TMP":str(self.root)})
 def test_no_environment(self):
  with self.assertRaisesRegex(AssertionError,"FIXTURE_ROOT_NOT_ADMITTED"):self.selected({})
 def test_local_runner_temp_not_implicitly_admitted(self):
  with self.assertRaisesRegex(AssertionError,"FIXTURE_ROOT_NOT_ADMITTED"):self.selected({"RUNNER_TEMP":str(self.root)})
 def test_wrong_host_platform(self):
  with self.assertRaisesRegex(AssertionError,"FIXTURE_ROOT_NOT_ADMITTED"):self.selected({**self.hosted,"RUNNER_OS":"Linux"})
 def test_host_marker_exact(self):
  with self.assertRaisesRegex(AssertionError,"FIXTURE_ROOT_NOT_ADMITTED"):self.selected({**self.hosted,"GITHUB_ACTIONS":"TRUE"})
 def test_missing_host_root(self):
  with self.assertRaisesRegex(AssertionError,"FIXTURE_ROOT_VALUE"):self.selected({"GITHUB_ACTIONS":"true","RUNNER_OS":"Windows"})
 def test_invalid_explicit_no_host_fallback(self):
  with self.assertRaisesRegex(AssertionError,"FIXTURE_ROOT_VALUE"):self.selected({**self.hosted,"VIBETRAM_TEST_TMP":""})
 def test_relative_drive_root_and_traversal_rejected(self):
  for value in ("relative","D:relative","D:/","D:/owned/../outside","D:/owned/./fixtures"):
   with self.subTest(value=value),self.assertRaises(AssertionError):self.selected({"VIBETRAM_TEST_TMP":value})
 def test_unc_devices_and_ambiguous_components_rejected(self):
  for value in (r"\\server\share\root",r"\\?\D:\owned\root","D:/owned/NUL","D:/owned/COM1.txt","D:/owned/fixtures.","D:/owned/fixtures ","D:/owned/root:stream"):
   with self.subTest(value=value),self.assertRaises(AssertionError):self.selected({"VIBETRAM_TEST_TMP":value})
 def test_invalid_values_rejected(self):
  for value in (None,123,"D:/owned/"+chr(0),"D:/owned/%TMP%","D:/owned/$TMP","D:/owned/~root","D:/owned/"+"x"*1024):
   with self.subTest(value=str(value)[:24]),self.assertRaises(AssertionError):self.selected({"VIBETRAM_TEST_TMP":value})
 def test_root_file_rejected(self):
  with self.assertRaisesRegex(AssertionError,"FIXTURE_ROOT_NOT_REGULAR_DIRECTORY"):self.selected(self.explicit,"file")
 def test_leaf_reparse(self):
  with self.assertRaisesRegex(AssertionError,"FIXTURE_ROOT_NOT_REGULAR_DIRECTORY"):self.selected(self.explicit,"reparse")
 def test_ancestor_reparse(self):
  with self.assertRaisesRegex(AssertionError,"FIXTURE_ROOT_NOT_REGULAR_DIRECTORY"):self.selected(self.explicit,"ancestor-reparse")
 def test_denial(self):
  with self.assertRaises(PermissionError):self.selected(self.explicit,"denied")
 def test_missing_root(self):
  with self.assertRaises(FileNotFoundError):self.selected(self.explicit,"missing")
 def test_identity_replacement(self):
  with self.assertRaisesRegex(AssertionError,"FIXTURE_ROOT_IDENTITY_CHANGED"):self.selected(self.explicit,"replacement",True)
 def test_directory_growth_not_identity_change(self):self.selected(self.explicit,mutate=True)
 def test_cleanup_failure_fatal(self):
  with self.assertRaisesRegex(AssertionError,"FIXTURE_ROOT_HANDLE_CLOSE_FAILED"):self.selected(self.explicit,"close-false")
 def test_body_failure_kept_with_cleanup_note(self):
  a=self.api("close-false")
  with self.assertRaisesRegex(RuntimeError,"SYNTHETIC_BODY") as caught:
   with admitted_test_root(self.explicit,a):raise RuntimeError("SYNTHETIC_BODY")
  self.assertIn("FIXTURE_ROOT_HANDLE_CLOSE_FAILED",caught.exception.__notes__);self.assertEqual(set(a.opened),set(a.closed))
 def test_real_hosted_branch_uses_same_admitted_local_scope(self):
  import os
  with admitted_test_root() as admitted:
   env={"GITHUB_ACTIONS":"true","RUNNER_OS":"Windows","RUNNER_TEMP":str(admitted)}
   with admitted_test_root(env) as root:self.assertEqual(root,admitted)


def _direct_elf(text=b"\0\0\0\x94",debug=b"x",reloc=283,stackflags=0):
 import struct
 names=b"\0.shstrtab\0.text\0.strtab\0.symtab\0.rela.text\0.note.GNU-stack\0.debug_info\0"
 entries=[("",0,0,b"",0,0,0,0),(".shstrtab",3,0,names,0,0,1,0),(".text",1,6,text,0,0,4,0),(".strtab",3,0,b"\0probe\0external\0",0,0,1,0)]
 symbols=bytes(24)+struct.pack("<IBBHQQ",1,18,0,2,0,4)+struct.pack("<IBBHQQ",7,16,0,0,0,0)
 entries += [(".symtab",2,0,symbols,3,1,8,24),(".rela.text",4,64,struct.pack("<QQq",0,(2<<32)|reloc,0),4,2,8,24),(".note.GNU-stack",1,stackflags,b"",0,0,1,0),(".debug_info",1,0,debug,0,0,1,0)]
 data=bytearray(64);data[:7]=b"\x7fELF\x02\x01\x01";struct.pack_into("<HHI",data,16,1,183,1);struct.pack_into("<H",data,52,64)
 rows=[]
 for name,kind,flags,body,link,info,align,size in entries:
  offset=len(data);data.extend(body);rows.append((names.index(name.encode()+b"\0") if name else 0,kind,flags,0,offset,len(body),link,info,align,size))
 while len(data)%8:data.append(0)
 shoff=len(data)
 for row in rows:data.extend(struct.pack("<IIQQQQIIQQ",*row))
 struct.pack_into("<Q",data,40,shoff);struct.pack_into("<HHH",data,58,64,len(rows),1)
 return bytes(data)

class DirectOutputFourObjectProbe(unittest.TestCase):
 def setUp(self):
  import direct_output_probe as d
  self.d=d
 def rows(self,target=None):
  d=self.d;target=target or d.C_TARGET;source="crypto/ctype.c" if target==d.C_TARGET else "crypto/aes/aes-sha1-armv8.S"
  a={"target":target,"source":source,"sourceIdentity":{"sha256":"a"*64},"object":{},"compilerArgv":["clang.exe","--target=aarch64-linux-android29","-c","-o",target,source]}
  import copy
  b=copy.deepcopy(a)
  if target==d.C_TARGET:b["compilerArgv"].insert(1,d.FLAG)
  return a,b
 def test_c_flag_is_one_invocation_only(self):
  d=self.d;fields={"CFLAGS":"-O3 -fPIC --target=aarch64-linux-android29"};before=fields.copy()
  for dry in (True,False):
   args=d.make_command("make",d.C_TARGET,fields,"candidate",dry)
   self.assertEqual(args[-1],"CFLAGS="+fields["CFLAGS"]+" "+d.FLAG);self.assertEqual(args.count("-j1"),1)
  self.assertEqual(fields,before)
 def test_baseline_and_assembly_are_unchanged(self):
  d=self.d
  for arm in ("baseline","candidate"):
   a=d.make_command("make",d.ASM_TARGET,{} ,arm,False)
   self.assertNotIn(d.FLAG," ".join(a));self.assertEqual(a,["make","-f","Makefile","-j1",d.ASM_TARGET])
  self.assertNotIn(d.FLAG," ".join(d.make_command("make",d.C_TARGET,{},"baseline",True)))
 def test_bad_arm_and_target_rejected(self):
  d=self.d
  for target,arm in (("all","candidate"),(d.C_TARGET,"other")):
   with self.assertRaises(AssertionError):d.make_command("make",target,{} ,arm,False)
 def test_cflags_fail_closed(self):
  d=self.d
  for v in ("","-O3\nx","-O3; echo bad","$(BAD)","-O3 "+d.FLAG,"-Xclang -O3","-o bad","-c","-O3 "+chr(96)+"x"):
   with self.subTest(value=v),self.assertRaises(AssertionError):d.make_command("make",d.C_TARGET,{"CFLAGS":v},"candidate",False)
 def test_scope_exact_fresh_arms(self):
  from openssl_probe import ROOT,PREFIX
  d=self.d;work=ROOT/"openssl-probe-work";out=ROOT/"openssl-probe-output"
  for arm,base in (("baseline",work),("candidate",work/"candidate")):self.assertEqual(d.arm_scope(work,out,base/"crate"/PREFIX/"openssl",arm),out/arm)
  with self.assertRaises(AssertionError):d.arm_scope(work,out,work/"crate"/PREFIX/"openssl","candidate")
 def test_valid_elf_and_debug_difference(self):
  d=self.d;a=d.elf_signature(_direct_elf());b=d.elf_signature(_direct_elf(debug=b"different"))
  self.assertEqual(a,b);self.assertEqual(a["symbols"],3);self.assertEqual(a["relocations"],1);self.assertFalse(a["debugCompared"])
 def test_code_difference_detected(self):
  self.assertNotEqual(self.d.elf_signature(_direct_elf())["sha256"],self.d.elf_signature(_direct_elf(text=b"\xc0\x03\x5f\xd6"))["sha256"])
 def test_relocation_difference_detected(self):
  self.assertNotEqual(self.d.elf_signature(_direct_elf())["sha256"],self.d.elf_signature(_direct_elf(reloc=282))["sha256"])
 def test_stack_metadata_difference_detected(self):
  self.assertNotEqual(self.d.elf_signature(_direct_elf())["sha256"],self.d.elf_signature(_direct_elf(stackflags=4))["sha256"])
 def test_header_target_and_bounds_rejected(self):
  import struct
  base=_direct_elf()
  for offset,fmt,value in ((4,"B",1),(5,"B",2),(16,"H",3),(18,"H",62),(20,"I",0),(40,"Q",len(base)+1),(52,"H",0),(58,"H",32),(60,"H",2048),(62,"H",999)):
   data=bytearray(base);struct.pack_into("<"+fmt,data,offset,value)
   with self.subTest(offset=offset),self.assertRaises(AssertionError):self.d.elf_signature(bytes(data))
 def test_oversize_and_truncated_rejected(self):
  for b in (b"",b"x"*63,_direct_elf()[:-1],b"x"*(self.d.OBJECT_LIMIT+1)):
   with self.assertRaises(AssertionError):self.d.elf_signature(b)
 def test_relocation_symbol_and_section_bounds(self):
  import struct
  base=bytearray(_direct_elf());table=struct.unpack_from("<Q",base,40)[0];rel=struct.unpack_from("<Q",base,table+5*64+24)[0]
  for offset,value in ((rel+8,999<<32),(rel,9999)):
   b=bytearray(base);struct.pack_into("<Q",b,offset,value)
   with self.assertRaises(AssertionError):self.d.elf_signature(bytes(b))
 def test_pair_requires_only_c_flag_difference(self):
  a,b=self.rows();row=self.d.compare_pair(a,b,_direct_elf(),_direct_elf(debug=b"y"))
  self.assertEqual(row["semanticSHA256"],self.d.elf_signature(_direct_elf())["sha256"])
  b["compilerArgv"].append("-O0")
  with self.assertRaises(AssertionError):self.d.compare_pair(a,b,_direct_elf(),_direct_elf())
 def test_pair_rejects_assembly_flag_and_source_change(self):
  a,b=self.rows(self.d.ASM_TARGET);self.d.compare_pair(a,b,_direct_elf(),_direct_elf())
  b["compilerArgv"].insert(1,self.d.FLAG)
  with self.assertRaises(AssertionError):self.d.compare_pair(a,b,_direct_elf(),_direct_elf())
  a,b=self.rows();b["sourceIdentity"]["sha256"]="b"*64
  with self.assertRaises(AssertionError):self.d.compare_pair(a,b,_direct_elf(),_direct_elf())
 def test_pair_rejects_target_and_code_change(self):
  a,b=self.rows();b["target"]=self.d.ASM_TARGET
  with self.assertRaises(AssertionError):self.d.compare_pair(a,b,_direct_elf(),_direct_elf())
  a,b=self.rows()
  with self.assertRaises(AssertionError):self.d.compare_pair(a,b,_direct_elf(),_direct_elf(text=b"\0"*4))
 def test_read_object_is_fresh_and_bounded(self):
  from unittest.mock import patch
  import hashlib,pathlib
  data=_direct_elf();expected={"bytes":len(data),"sha256":hashlib.sha256(data).hexdigest()}
  with patch("perl_overlay.smoke_artifact_identity",side_effect=[expected,expected]),patch.object(pathlib.Path,"read_bytes",return_value=data):self.assertEqual(self.d.read_object(pathlib.Path("controlled"),expected),data)
  for after in ({**expected,"bytes":1},{**expected,"sha256":"0"*64}):
   with patch("perl_overlay.smoke_artifact_identity",side_effect=[expected,after]),patch.object(pathlib.Path,"read_bytes",return_value=data),self.assertRaises(AssertionError):self.d.read_object(pathlib.Path("controlled"),expected)
 def test_recipe_flag_role_is_explicit(self):
  from perl_overlay import cargo_recipe_arguments
  base=TargetedCargoOpenSSLProbe().recipe()
  t=self.d.C_TARGET;s="crypto/ctype.c"
  changed=base.replace(" -c "," "+self.d.FLAG+" -c ")
  self.assertNotIn(self.d.FLAG,cargo_recipe_arguments(base,t,s))
  self.assertIn(self.d.FLAG,cargo_recipe_arguments(changed,t,s,direct_output=True))
  for text,kwargs in ((changed,{}),(base,{"direct_output":True}),(changed.replace(self.d.FLAG,self.d.FLAG+" "+self.d.FLAG),{"direct_output":True})):
   with self.assertRaises(AssertionError):cargo_recipe_arguments(text,t,s,**kwargs)
 def test_materialization_rejects_existing_or_bad_archive(self):
  import pathlib
  from unittest.mock import patch
  from openssl_probe import ROOT
  work=ROOT/"openssl-probe-work"
  for existing,digest in ((True,"bad"),(False,"bad")):
   directory_api=DirectMaterializationDirectories().api()
   expected="DIRECT_PRESERVE_CANDIDATE" if existing else "DIRECT_ARCHIVE"
   with patch("perl_overlay.TemplateInputAPI",return_value=directory_api),patch("openssl_probe.regular_chain"),patch("openssl_probe.sha",return_value=digest),patch.object(pathlib.Path,"is_dir",return_value=True),patch.object(pathlib.Path,"iterdir",return_value=iter([pathlib.Path("prior")] if existing else [])),patch("direct_output_probe.tarfile.open") as tar,self.assertRaisesRegex(AssertionError,expected):self.d.materialize_candidate(work)
   tar.assert_not_called()
   self.assertIn(work,directory_api.paths.values());self.assertIn(work/"candidate",directory_api.paths.values())
   self.assertEqual(set(directory_api.opened),set(directory_api.closed))
 def test_materialization_validates_before_writing(self):
  import pathlib
  from unittest.mock import patch,MagicMock
  from openssl_probe import ROOT,CHECKSUM
  work=ROOT/"openssl-probe-work";directory_api=DirectMaterializationDirectories().api()
  tar=MagicMock();tar.__enter__.return_value.getmembers.return_value=[]
  with patch("perl_overlay.TemplateInputAPI",return_value=directory_api),patch("openssl_probe.regular_chain"),patch("openssl_probe.sha",return_value=CHECKSUM),patch.object(pathlib.Path,"is_dir",return_value=True),patch.object(pathlib.Path,"iterdir",return_value=iter([])),patch("direct_output_probe.tarfile.open",return_value=tar),patch("openssl_probe.validate_members",side_effect=AssertionError("BAD_MEMBERS")),patch.object(pathlib.Path,"open") as opened,self.assertRaisesRegex(AssertionError,"BAD_MEMBERS"):self.d.materialize_candidate(work)
  opened.assert_not_called()
  self.assertIn(work,directory_api.paths.values());self.assertIn(work/"candidate",directory_api.paths.values())
  self.assertEqual(set(directory_api.opened),set(directory_api.closed))
 def orchestrate(self,failure=None):
  import pathlib,types,hashlib,copy
  from unittest.mock import patch
  import openssl_probe as op,perl_overlay as po,ndk_input_metadata as ni
  work=op.ROOT/"openssl-probe-work";out=op.ROOT/"openssl-probe-output";src=work/"crate"/op.PREFIX/"openssl"
  g=types.SimpleNamespace(count=1,peak=19,_resource_sample=lambda:None);calls=[];receipts=[]
  def run(*args,**kwargs):
   calls.append("materialize")
   if failure=="extract":raise RuntimeError("EXTRACT_STOP")
  g.run=run
  def objects(*args,**kwargs):
   arm=kwargs["direct_output_arm"];calls.append(arm)
   if failure==arm:raise RuntimeError("ARM_STOP")
   rows=[]
   for target in (self.d.C_TARGET,self.d.ASM_TARGET):
    a,b=self.rows(target);row=copy.deepcopy(a if arm=="baseline" else b)
    if failure=="source" and arm=="candidate":row["sourceIdentity"]["sha256"]="b"*64
    rows.append(row)
   if failure=="count" and arm=="candidate":rows.pop()
   return {"objects":rows}
  def physical(guard,env,dest,callback):callback(pathlib.Path("ndk"),pathlib.Path("tools"));return {"qualified":True}
  def lease(root,leaf,callback):
   calls.append("lease")
   if failure=="lease":return {"qualified":False}
   callback();return {"qualified":True,"callbackSucceeded":True}
  def configured(*a,**k):
   calls.append("configure")
   if failure=="configure":raise RuntimeError("CONFIGURE_STOP")
   return {"makefileFields":{}}
  def put(dest,name,row):receipts.append((name,row))
  result=error=None
  with patch.object(pathlib.Path,"mkdir"),patch.object(op,"sha",return_value="a"*64),patch.object(op,"with_physical_ndk_inputs",side_effect=physical),patch.object(ni,"capture_one",side_effect=lease),patch.object(po,"qualify_cargo_objects",side_effect=objects),patch.object(po,"configure_with_runtime",side_effect=configured),patch.object(self.d,"read_object",return_value=_direct_elf()),patch.object(self.d,"_put",side_effect=put):
   try:result=self.d.qualify_four_objects(g,{},work,out,src,pathlib.Path("perl.exe"),{})
   except BaseException as e:error=e
  return result,error,calls,receipts
 def test_orchestration_is_four_fresh_objects(self):
  row,error,calls,receipts=self.orchestrate();self.assertIsNone(error);self.assertEqual(row["maximumObjects"],4);self.assertTrue(row["flagCOnly"]);self.assertFalse(row["failedOutputsReused"])
  self.assertEqual(calls,["baseline","materialize","lease","configure","candidate"]);self.assertEqual(len(receipts),1);self.assertEqual(len(row["pairs"]),2)
 def test_failure_never_retries_or_returns_partial(self):
  for phase in ("baseline","extract","lease","configure","candidate","count","source"):
   with self.subTest(phase=phase):
    row,error,calls,receipts=self.orchestrate(phase);self.assertIsNone(row);self.assertIsNotNone(error)
    self.assertEqual(receipts[-1][1]["state"],"FATAL_NO_RETRY");self.assertFalse(receipts[-1][1]["partialAccepted"]);self.assertLessEqual(calls.count("baseline"),1);self.assertLessEqual(calls.count("candidate"),1)
 def test_targeted_workflow_excludes_other_builds(self):
  import pathlib,json
  root=pathlib.Path(__file__).resolve().parents[1];wf=json.loads((root/".github/workflows/offline-android.yml").read_text())
  job=wf["jobs"]["openssl-probe"];self.assertEqual(job["steps"][1]["run"],"python -B ci/perl_overlay.py --runtime-direct-output")
  self.assertEqual(job["timeout-minutes"],12);self.assertEqual(job["steps"][1]["timeout-minutes"],10);self.assertEqual(job["permissions"],{"contents":"read"});self.assertEqual(job["steps"][2]["with"]["retention-days"],3)
  self.assertIn("**/*.json",job["steps"][2]["with"]["path"]);self.assertNotIn(".o",job["steps"][2]["with"]["path"])


class DirectOutputResourceBounds(unittest.TestCase):
 def patch_table(self,index,count):
  import struct
  b=bytearray(_direct_elf());table=struct.unpack_from("<Q",b,40)[0];offset=len(b)
  if index==4:body=bytes(count*24)
  else:body=struct.pack("<QQq",0,(2<<32)|283,0)*count
  b.extend(body);struct.pack_into("<QQ",b,table+index*64+24,offset,len(body))
  return bytes(b)
 def test_symbol_count_exact_and_exhausted(self):
  import direct_output_probe as d
  self.assertEqual(d.elf_signature(self.patch_table(4,4096))["symbols"],4096)
  with self.assertRaisesRegex(AssertionError,"DIRECT_ELF_SYMBOL_BOUND"):d.elf_signature(self.patch_table(4,4097))
 def test_relocation_count_exact_and_exhausted(self):
  import direct_output_probe as d
  self.assertEqual(d.elf_signature(self.patch_table(5,8192))["relocations"],8192)
  with self.assertRaisesRegex(AssertionError,"DIRECT_ELF_RELOC_BOUND"):d.elf_signature(self.patch_table(5,8193))
 def test_symbol_name_exact_and_exhausted(self):
  import direct_output_probe as d,struct
  for length in (256,257):
   b=bytearray(_direct_elf());table=struct.unpack_from("<Q",b,40)[0];offset=len(b);body=b"\0"+b"a"*length+b"\0";b.extend(body)
   struct.pack_into("<QQ",b,table+3*64+24,offset,len(body))
   if length==256:self.assertEqual(d.elf_signature(bytes(b))["symbols"],3)
   else:
    with self.assertRaisesRegex(AssertionError,"DIRECT_ELF_STRING"):d.elf_signature(bytes(b))
 def test_relocation_total_across_sections(self):
  import direct_output_probe as d,struct
  b=bytearray(self.patch_table(5,5000));table=struct.unpack_from("<Q",b,40)[0]
  namesoff=struct.unpack_from("<Q",b,table+64+24)[0];nameat=b.index(b".debug_info\0",namesoff);b[nameat:nameat+12]=b".rela.extra\0"
  nameindex=struct.unpack_from("<I",b,table+7*64)[0];offset=len(b);body=struct.pack("<QQq",0,(2<<32)|283,0)*5000;b.extend(body)
  struct.pack_into("<IIQQQQIIQQ",b,table+7*64,nameindex,4,64,0,offset,len(body),4,2,8,24)
  with self.assertRaisesRegex(AssertionError,"DIRECT_ELF_RELOC_BOUND"):d.elf_signature(bytes(b))


class DirectOutputDiagnosticPrivacy(unittest.TestCase):
 _missing=object()
 def failure(self,value=_missing):
  import direct_output_probe as d,perl_overlay as p,json
  from unittest.mock import patch
  from types import SimpleNamespace
  rows=[];error=AssertionError() if value is self._missing else AssertionError(value)
  with patch.object(d,"arm_scope",return_value=SimpleNamespace(mkdir=lambda:None)),patch.object(p,"qualify_cargo_objects",side_effect=error),patch.object(d,"_put",side_effect=lambda out,name,row:rows.append((name,row))):
   with self.assertRaises(AssertionError) as got:d.qualify_four_objects(None,{},object(),object(),object(),None,{})
  self.assertIs(got.exception,error)
  self.assertEqual(len(rows),1);name,row=rows[0]
  self.assertEqual(name,"direct-output-failure.json")
  self.assertEqual(row["state"],"FATAL_NO_RETRY");self.assertEqual(row["stage"],"BASELINE");self.assertFalse(row["partialAccepted"])
  self.assertEqual(row["errorClass"],"AssertionError")
  self.assertLessEqual(len(json.dumps(row)),512);self.assertLessEqual(len(row["code"]),80)
  return row
 def test_valid_ascii_codes_and_boundary(self):
  for value in ("DIRECT_OUTPUT_FAILURE","ERR_2","A"*80):
   with self.subTest(case="valid"):self.assertEqual(self.failure(value)["code"],value)
 def test_uppercase_paths_and_uris_redacted(self):
  for value in (r"X:\PRIVATE\UPPER.TXT","X:/PRIVATE/UPPER.TXT","/PRIVATE/UPPER",r"..\PRIVATE\UPPER","HTTPS://EXAMPLE.INVALID/PRIVATE","PRIVATE.TXT"):
   with self.subTest(case="path"):self.assertEqual(self.failure(value)["code"],"DIRECT_OUTPUT_FAILURE")
 def test_whitespace_quotes_and_shell_redacted(self):
  for value in ("BAD CODE","BAD\nCODE","BAD\tCODE",'"UPPER"',"BAD;CODE","BAD"+chr(96)+"CODE"):
   with self.subTest(case="syntax"):self.assertEqual(self.failure(value)["code"],"DIRECT_OUTPUT_FAILURE")
 def test_unicode_oversize_and_empty_redacted(self):
  for value in ("\u00c9CHEC","A"*81,"A"*20000,""):
   with self.subTest(case="bound"):self.assertEqual(self.failure(value)["code"],"DIRECT_OUTPUT_FAILURE")
 def test_missing_non_string_causes_redacted(self):
  self.assertEqual(self.failure()["code"],"DIRECT_OUTPUT_FAILURE")
  for value in (None,42,{"private":"VALUE"}):
   with self.subTest(case="type"):self.assertEqual(self.failure(value)["code"],"DIRECT_OUTPUT_FAILURE")
 def test_failure_stays_fatal_and_bounded(self):
  row=self.failure("DIRECT_EXPECTED_FAILURE")
  self.assertEqual(set(row),{"state","stage","errorClass","code","errno","winerror","partialAccepted"})
  self.assertIsNone(row["errno"]);self.assertIsNone(row["winerror"])


class DirectMaterializationDirectories(unittest.TestCase):
 def paths(self):
  root=pathlib.Path("D:/owned/probe/openssl-probe-work");return root,root/"candidate"
 def api(self,mode=None):
  root,dest=self.paths()
  class Fake:
   def __init__(self):self.opened=[];self.closed=[];self.paths={};self.ids={};self.changed=False
   def open(self,path):
    if mode in ("denied","missing","io") and len(self.opened)==2:
     raise {"denied":PermissionError,"missing":FileNotFoundError,"io":OSError}[mode](13,"synthetic")
    h=len(self.opened)+1;self.opened.append(h);self.paths[h]=path;self.ids.setdefault(str(path),len(self.ids)+1);return h
   def info(self,h):
    path=self.paths[h];identity=[1,self.ids[str(path)],0];attrs=0x10;tag=0
    if mode=="file" and path==root:attrs=0
    if mode=="reparse" and path==root.parent:attrs|=0x400;tag=0xa0000003
    if mode=="tag" and path==dest:tag=123
    if mode=="zero" and path==dest:identity[1]=0
    if mode=="volume" and path==dest:identity[0]=2
    if mode=="alias" and path==dest:identity=[1,self.ids[str(root)],0]
    if self.changed and ((mode=="replace" and path==root) or (mode=="parent" and path==root.parent)):identity[1]+=1000
    return {"identity":identity,"attributes":attrs,"tag":tag,"bytes":4096 if self.changed else 64}
   def close(self,h):
    self.closed.append(h)
    if mode=="close":return False
    return True
  return Fake()
 def use(self,mode=None,mutate=False,primary=False):
  from direct_output_probe import materialization_directories
  a=self.api(mode);root,dest=self.paths()
  try:
   with materialization_directories(root,dest,a):
    if mutate:a.changed=True
    if primary:raise ValueError("PRIMARY_FIXTURE")
  finally:self.assertEqual(set(a.opened),set(a.closed))
 def test_regular_directory_chain(self):self.use()
 def test_mutable_directory_growth(self):self.use(mutate=True)
 def test_file_rejected(self):
  with self.assertRaisesRegex(AssertionError,"DIRECT_DIRECTORY_NOT_REGULAR"):self.use("file")
 def test_reparse_ancestor_rejected(self):
  with self.assertRaisesRegex(AssertionError,"DIRECT_DIRECTORY_NOT_REGULAR"):self.use("reparse")
 def test_unknown_tag_rejected(self):
  with self.assertRaisesRegex(AssertionError,"DIRECT_DIRECTORY_NOT_REGULAR"):self.use("tag")
 def test_missing_identity_rejected(self):
  with self.assertRaisesRegex(AssertionError,"DIRECT_DIRECTORY_IDENTITY"):self.use("zero")
 def test_volume_and_alias_rejected(self):
  for mode in ("volume","alias"):
   with self.subTest(mode=mode),self.assertRaisesRegex(AssertionError,"DIRECT_DIRECTORY_VOLUME_OR_ALIAS"):self.use(mode)
 def test_denial_missing_unexpected_io_fatal(self):
  for mode,kind in (("denied",PermissionError),("missing",FileNotFoundError),("io",OSError)):
   with self.subTest(mode=mode),self.assertRaises(kind):self.use(mode)
 def test_root_replacement_rejected(self):
  with self.assertRaisesRegex(AssertionError,"DIRECT_DIRECTORY_CHANGED"):self.use("replace",True)
 def test_parent_replacement_rejected(self):
  with self.assertRaisesRegex(AssertionError,"DIRECT_DIRECTORY_CHANGED"):self.use("parent",True)
 def test_cleanup_failure_fatal(self):
  with self.assertRaisesRegex(AssertionError,"DIRECT_DIRECTORY_CLOSE_FAILED"):self.use("close")
 def test_primary_failure_preserved(self):
  with self.assertRaisesRegex(ValueError,"PRIMARY_FIXTURE") as got:self.use("close",primary=True)
  self.assertIn("DIRECT_DIRECTORY_CLOSE_FAILED",got.exception.__notes__)
 def test_wrong_destination_rejected(self):
  from direct_output_probe import materialization_directories
  root,dest=self.paths();a=self.api()
  with self.assertRaisesRegex(AssertionError,"DIRECT_DIRECTORY_SCOPE"):materialization_directories(root,dest.parent/"outside",a)
  self.assertEqual(a.opened,[])
 def test_archive_remains_file_guarded(self):
  import inspect,direct_output_probe as d
  text=inspect.getsource(d.materialize_candidate)
  self.assertIn("regular_chain(archive)",text);self.assertNotIn("regular_chain(work)",text)
  self.assertIn("with materialization_directories(work,destination):",text)
 def test_real_windows_materialization(self):
  import os,io,tarfile,hashlib,direct_output_probe as d,openssl_probe as op
  from unittest.mock import patch
  if os.name!="nt":self.skipTest("Windows only")
  with admitted_test_root() as admitted:
   root=admitted/"direct-materialize-real";assert not root.exists(),"PRESERVE_MATERIALIZATION_FIXTURE"
   root.mkdir();work=root/"openssl-probe-work";work.mkdir();(work/"candidate").mkdir()
   payload=b"fixture-only-configure\n";buffer=io.BytesIO()
   with tarfile.open(fileobj=buffer,mode="w:gz") as tar:
    info=tarfile.TarInfo(op.PREFIX+"openssl/Configure");info.size=len(payload);tar.addfile(info,io.BytesIO(payload))
   archive=buffer.getvalue();self.assertLessEqual(len(archive),2048)
   (work/"openssl-src.crate").write_bytes(archive)
   with patch.object(op,"ROOT",root),patch.object(op,"CHECKSUM",hashlib.sha256(archive).hexdigest()):
    d.materialize_candidate(work)
   self.assertEqual((work/"candidate/crate"/op.PREFIX/"openssl/Configure").read_bytes(),payload)

if __name__=="__main__":unittest.main()
