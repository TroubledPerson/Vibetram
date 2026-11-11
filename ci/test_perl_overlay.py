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
  self.assertEqual(job["permissions"],{"contents":"read"});self.assertEqual(job["steps"][1]["run"],"python -B ci/perl_overlay.py --runtime-configure");self.assertIn("[openssl-probe-191]",job["if"])


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

if __name__=="__main__":unittest.main()
