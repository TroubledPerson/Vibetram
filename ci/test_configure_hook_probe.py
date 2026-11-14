import unittest
import configure_hook_probe as p
def c(target,source):
 return target+b": "+source+b" include/config.h\n\t$(CC) -I. -DTEST=1 $(LIB_CFLAGS) $(LIB_CPPFLAGS) -MMD -MF "+target[:-2]+b".d.tmp -c -o $@ "+source+b"\n\t@touch "+target[:-2]+b".d.tmp\n"
def fixture():
 return b"CFLAGS=-O3\n"+c(p.REQUIRED[0],b"crypto/ctype.c")+c(p.REQUIRED[1],b"crypto/bn/bn_nist.c")+b"crypto/a.o: crypto/a.S\n\t$(CC) -I. $(LIB_CFLAGS) $(LIB_CPPFLAGS) -c -o $@ crypto/a.S\ncrypto/b.o: crypto/b.s\n\t$(CC) $(LIB_CFLAGS) $(LIB_CPPFLAGS) -c -o $@ crypto/b.s\nx.o: x.cpp\n\t$(CXX) $(LIB_CXXFLAGS) -c -o $@ x.cpp\nr.o: r.rc\n\t$(RC) $(RCFLAGS) -o $@ r.rc\nlib.so: a.o\n\t$(CC) $(LIB_CFLAGS) -shared -o lib.so a.o\n"
class DirectCPlanner(unittest.TestCase):
 def reject(self,data,code=None):
  with self.assertRaisesRegex(AssertionError,code or "DIRECT_PLAN_"):p.plan(data)
 def test_only_two_c_recipes_change(self):
  before=fixture();after,row=p.plan(before)
  self.assertEqual(row["cTargets"],2);self.assertEqual(row["assemblyRecipesUnchanged"],2)
  self.assertEqual(after.replace(b" "+p.FLAG,b""),before);self.assertFalse(row["fileWritten"]);self.assertFalse(row["productionEnabled"])
 def test_assembly_cpp_rc_link_and_global_flags_unchanged(self):
  before=fixture();after,_=p.plan(before)
  self.assertEqual(before.split(b"crypto/a.o:")[1],after.split(b"crypto/a.o:")[1]);self.assertTrue(after.startswith(b"CFLAGS=-O3\n"))
 def test_crlf_and_final_line_preserved(self):
  data=fixture().replace(b"\n",b"\r\n").rstrip(b"\r\n");after,_=p.plan(data)
  self.assertEqual(after.replace(b" "+p.FLAG,b""),data)
 def test_dso_and_bin_intents(self):
  for intent in (b"DSO",b"BIN"):
   after,row=p.plan(fixture().replace(b"LIB_CFLAGS",intent+b"_CFLAGS").replace(b"LIB_CPPFLAGS",intent+b"_CPPFLAGS"))
   self.assertEqual(row["cTargets"],2)
 def test_missing_required_target(self):self.reject(c(p.REQUIRED[0],b"crypto/ctype.c"),"DIRECT_PLAN_REQUIRED_TARGETS")
 def test_replay_and_nul(self):
  after,_=p.plan(fixture());self.reject(after,"DIRECT_PLAN_REPLAY_OR_NUL");self.reject(fixture()+b"\0","DIRECT_PLAN_REPLAY_OR_NUL")
 def test_dep_target_mismatch(self):self.reject(fixture().replace(b"crypto/libcrypto-lib-ctype.d.tmp",b"other.d.tmp"),"DIRECT_PLAN_DEPENDENCY")
 def test_c_without_dependency_form(self):self.reject(fixture().replace(b" -MMD -MF crypto/libcrypto-lib-ctype.d.tmp",b""),"DIRECT_PLAN_C_RECIPE")
 def test_source_not_a_prerequisite(self):self.reject(fixture().replace(b": crypto/ctype.c",b": other.c"),"DIRECT_PLAN_SOURCE_BINDING")
 def test_absolute_and_traversal_source(self):
  for src in (b"/crypto/ctype.c",b"../crypto/ctype.c"):
   self.reject(fixture().replace(b"crypto/ctype.c",src),"DIRECT_PLAN_SOURCE_BINDING")
 def test_unsafe_target_path(self):self.reject(fixture().replace(p.REQUIRED[0],b"../"+p.REQUIRED[0]),"DIRECT_PLAN_TARGET_PATH")
 def test_shell_and_unknown_variable_prefix(self):
  for prefix in (b"-I.;echo",b"$(SHELL)",b"-I./x|cmd",b"-I./x"+bytes([96])+b"cmd"):
   self.reject(fixture().replace(b"-I. -DTEST=1",prefix),"DIRECT_PLAN_PREFIX")
 def test_unknown_compile_role(self):self.reject(fixture()+b"x.o: x.cpp\n\t$(CC) $(LIB_CFLAGS) -c -o $@ x.cpp\n","DIRECT_PLAN_COMPILER_ROLE")
 def test_multiple_sources(self):self.reject(fixture().replace(b"-o $@ crypto/ctype.c",b"-o $@ crypto/ctype.c another.c"),"DIRECT_PLAN_SOURCE_BINDING")
 def test_duplicate_target(self):self.reject(fixture()+c(p.REQUIRED[0],b"crypto/ctype.c"),"DIRECT_PLAN_TARGET_BOUND")
 def test_exact_target_bound_and_exhaustion(self):
  base=c(p.REQUIRED[0],b"crypto/ctype.c")+c(p.REQUIRED[1],b"crypto/bn/bn_nist.c")
  data=base+b"".join(c(("extra/x"+str(i)+".o").encode(),("extra/x"+str(i)+".c").encode()) for i in range(p.MAX_TARGETS-2))
  self.assertEqual(p.plan(data)[1]["cTargets"],p.MAX_TARGETS)
  self.reject(data+c(b"extra/overflow.o",b"extra/overflow.c"),"DIRECT_PLAN_TARGET_BOUND")
 def test_input_size_bound(self):self.reject(b"x"*(p.MAX_BYTES+1),"DIRECT_PLAN_INPUT_BOUND")
 def test_line_and_line_count_bounds(self):
  self.reject(b"x"*65537,"DIRECT_PLAN_LINE_BOUND");self.reject(b"\n"*(p.MAX_LINES+1),"DIRECT_PLAN_LINE_BOUND")
 def test_bare_carriage_return(self):self.reject(fixture()+b"\r","DIRECT_PLAN_NEWLINE")
 def test_compile_without_object_rule(self):self.reject(b"\t$(CC) $(LIB_CFLAGS) -c -o $@ x.c\n","DIRECT_PLAN_OBJECT_RULE")

import unittest,copy,pathlib
import configure_hook_probe as w
import configure_hook_probe as hook
def recipe(target,src):
 return target+b": "+src+b"\n\t$(CC) $(LIB_CFLAGS) $(LIB_CPPFLAGS) -MMD -MF "+target[:-2]+b".d.tmp -c -o $@ "+src+b"\n"
DATA=recipe(w.REQUIRED[0],b"crypto/ctype.c")+recipe(w.REQUIRED[1],b"crypto/bn/bn_nist.c")+b"a.o: a.S\n\t$(CC) $(LIB_CFLAGS) -c -o $@ a.S\n"
ROOT=r"D:\owned\fresh"
class Fake:
 def __init__(self):
  self.items={};self.handles={};self.closed=[];self.writes=0;self.mode=None;self.n=0
  for name,b in (("Makefile",DATA),("Configure",b"qualified fixture configure"),("Configurations/unix-Makefile.tmpl",b"qualified fixture template")):
   p=pathlib.PureWindowsPath(ROOT).joinpath(*name.split("/"));self.items[str(p)]={"data":b}
  self.manifest={name:{"bytes":len(self.items[str(pathlib.PureWindowsPath(ROOT).joinpath(*name.split("/")))]["data"]),"sha256":w.sha(self.items[str(pathlib.PureWindowsPath(ROOT).joinpath(*name.split("/")))]["data"])} for name in ("Makefile","Configure","Configurations/unix-Makefile.tmpl")}
 def open(self,path,role):
  if self.mode=="denial":raise PermissionError(13,"not retained")
  self.n+=1;h=self.n;self.handles[h]=(str(path),role)
  if role!="directory":assert str(path) in self.items
  return h
 def info(self,h):
  path,role=self.handles[h];row={"identity":[7,0,h],"created":123456789,"attributes":16 if role=="directory" else 32,"tag":0,"links":1,"bytes":0 if role=="directory" else len(self.items[path]["data"])}
  if self.mode=="reparse" and role=="directory":row["tag"]=0xA0000003
  if self.mode=="hardlink" and role!="directory":row["links"]=2
  if self.mode=="changed" and self.writes and role=="directory":row["identity"][2]+=100
  if self.mode=="created" and self.writes and role=="output":row["created"]+=1
  if self.mode=="growth" and role=="directory":row["bytes"]=self.n*100
  return row
 def read(self,h,limit,tick):
  tick();path,role=self.handles[h];data=self.items[path]["data"]
  if self.mode=="readback" and self.writes and role=="output":data=b"wrong"
  return data[:limit]
 def write(self,h,data,tick):
  tick();self.writes+=1;self.items[self.handles[h][0]]["data"]=data
  if self.mode=="short":raise w.Stop("WRITER_SHORT_WRITE")
 def close(self,h):
  self.closed.append(h);return self.mode!="close"
class Writer(unittest.TestCase):
 def setUp(self):self.api=Fake()
 def runit(self,**kw):return w.transaction(self.api,ROOT,self.api.manifest,fixture=True,**kw)
 def test_plan_never_writes(self):
  out=self.runit();self.assertFalse(out["fileWritten"]);self.assertEqual(self.api.writes,0);self.assertFalse(out["productionEnabled"]);self.assertEqual(len(self.api.closed),len(self.api.handles))
 def test_apply_verified(self):
  out=self.runit(apply=True);self.assertTrue(out["fileWritten"]);self.assertEqual(self.api.writes,1);self.assertEqual(len(self.api.closed),len(self.api.handles))
 def test_production_always_disabled(self):
  with self.assertRaisesRegex(w.Stop,"PRODUCTION_DISABLED"):w.transaction(self.api,ROOT,self.api.manifest,apply=True)
  self.assertEqual(self.api.n,0)
 def test_wrong_hash(self):
  self.api.manifest["Makefile"]["sha256"]="0"*64
  with self.assertRaisesRegex(w.Stop,"PIN_HASH"):self.runit(apply=True)
  self.assertEqual(self.api.writes,0)
 def test_wrong_size(self):
  self.api.manifest["Configure"]["bytes"]+=1
  with self.assertRaisesRegex(w.Stop,"PIN_SIZE"):self.runit()
 def test_missing_pin(self):
  del self.api.manifest["Configure"]
  with self.assertRaisesRegex(w.Stop,"MANIFEST_SCOPE"):self.runit()
 def test_unknown_manifest_path(self):
  self.api.manifest["elsewhere"]=self.api.manifest["Configure"]
  with self.assertRaisesRegex(w.Stop,"MANIFEST_SCOPE"):self.runit()
 def test_denial_fatal(self):
  self.api.mode="denial"
  with self.assertRaises(PermissionError):self.runit()
 def test_reparse_ancestor_fatal(self):
  self.api.mode="reparse"
  with self.assertRaisesRegex(w.Stop,"REPARSE"):self.runit()
  self.assertEqual(len(self.api.closed),len(self.api.handles))
 def test_hardlink_fatal(self):
  self.api.mode="hardlink"
  with self.assertRaisesRegex(w.Stop,"HARDLINK"):self.runit()
 def test_replacement_after_write_fatal(self):
  self.api.mode="changed"
  with self.assertRaisesRegex(w.Stop,"IDENTITY_CHANGED"):self.runit(apply=True)
 def test_creation_identity_changed_fatal(self):
  self.api.mode="created"
  with self.assertRaisesRegex(w.Stop,"IDENTITY_CHANGED"):self.runit(apply=True)
 def test_mutable_directory_size(self):
  self.api.mode="growth";self.assertTrue(self.runit(apply=True)["fileWritten"])
 def test_bad_readback_fatal(self):
  self.api.mode="readback"
  with self.assertRaisesRegex(w.Stop,"READBACK"):self.runit(apply=True)
 def test_write_failure_stays_fatal(self):
  self.api.mode="short"
  with self.assertRaisesRegex(w.Stop,"SHORT_WRITE"):self.runit(apply=True)
  self.assertEqual(len(self.api.closed),len(self.api.handles))
 def test_close_failure_fatal(self):
  self.api.mode="close"
  with self.assertRaises(w.Stop) as caught:self.runit(apply=True)
  self.assertEqual(caught.exception.code,"WRITER_CLEANUP_FAILED");self.assertTrue(caught.exception.cleanup)
 def test_primary_retained_when_cleanup_fails(self):
  self.api.mode="close";self.api.manifest["Makefile"]["sha256"]="0"*64
  with self.assertRaises(w.Stop) as caught:self.runit()
  self.assertEqual(caught.exception.code,"WRITER_PIN_HASH");self.assertTrue(caught.exception.cleanup)
 def test_resource_failure_no_write(self):
  def stop():raise w.Stop("RESOURCE_FLOOR")
  with self.assertRaisesRegex(w.Stop,"RESOURCE_FLOOR"):self.runit(resource=stop)
  self.assertEqual(self.api.writes,0)
 def test_deadline_no_write(self):
  it=iter([0,6])
  with self.assertRaisesRegex(w.Stop,"DEADLINE"):self.runit(clock=lambda:next(it))
  self.assertEqual(self.api.writes,0)
 def test_root_aliases_rejected(self):
  for root in (r"\\server\owned",r"D:\owned\..\fresh",r"D:\owned\.\fresh",r"D:relative",r"D:/owned/fresh"):
   with self.subTest(root=root):
    with self.assertRaisesRegex(w.Stop,"ROOT_SCOPE"):w.transaction(self.api,root,self.api.manifest,fixture=True)
 def test_replay_rejected(self):
  self.runit(apply=True);p=str(pathlib.PureWindowsPath(ROOT)/"Makefile");b=self.api.items[p]["data"];self.api.manifest["Makefile"]={"bytes":len(b),"sha256":w.sha(b)}
  with self.assertRaisesRegex(AssertionError,"REPLAY"):self.runit(apply=True)
class Hook(unittest.TestCase):
 def env(self):return {"VIBETRAM_OPENSSL_CARGO_BRIDGE":"1","VIBETRAM_OPENSSL_WORK":ROOT,"VIBETRAM_OPENSSL_CONFIGURE_SHA":"a"*64,"VIBETRAM_OPENSSL_DIRECT_OUTPUT_MODE":"plan"}
 def test_plan_contract(self):
  env=self.env();old=copy.deepcopy(env);r=hook.hook_contract(env,configure_succeeded=True,android=True,configure_identity_held=True)
  self.assertEqual(old,env);self.assertFalse(r["livePerlQualified"]);self.assertEqual(r["activation"],"DISABLED_PLAN_ONLY")
 def test_apply_rejected(self):
  e=self.env();e["VIBETRAM_OPENSSL_DIRECT_OUTPUT_MODE"]="apply"
  with self.assertRaisesRegex(AssertionError,"APPLY_UNQUALIFIED"):hook.hook_contract(e,configure_succeeded=True,android=True,configure_identity_held=True)
 def test_failed_host_and_unheld_rejected(self):
  for field in ("configure_succeeded","android","configure_identity_held"):
   kw=dict(configure_succeeded=True,android=True,configure_identity_held=True);kw[field]=False
   with self.assertRaisesRegex(AssertionError,"HOOK_SCOPE"):hook.hook_contract(self.env(),**kw)
 def test_missing_and_wrong_env(self):
  e=self.env();del e["VIBETRAM_OPENSSL_WORK"]
  with self.assertRaisesRegex(AssertionError,"ENV_MISSING"):hook.hook_contract(e,configure_succeeded=True,android=True,configure_identity_held=True)

import unittest,hashlib,json
import configure_hook_probe as m
SOURCE=m.OBSERVER_SOURCE
class HookBoundary(unittest.TestCase):
 def setUp(self):
  self.config=b"controlled Configure model";self.pin=hashlib.sha256(self.config).hexdigest();self.root="/d/ci-work";self.cwd=self.root+"/build";self.argv=["linux-aarch64","--prefix="+self.root+"/install"];self.reads=[]
 def arm(self,**change):
  kw=dict(program="./Configure",mode="observe",root=self.root,cwd=self.cwd,argv=self.argv,pin=self.pin,configure=self.config);kw.update(change);return m.arm(**kw)
 def reader(self,name,limit):
  self.reads.append(name);return self.config if name=="Configure" else b"controlled Makefile"
 def test_observe_success_no_write_authority(self):
  row=m.finish(self.arm(),0,self.cwd,self.reader);self.assertEqual(row["exit"],0);self.assertFalse(row["report"]["windowsHeldIdentityQualified"]);self.assertFalse(row["report"]["productionEnabled"])
 def test_failed_exit_preserved_without_read(self):
  for code in (1,2,90,255):
   row=m.finish(self.arm(),code,self.cwd,self.reader);self.assertEqual(row["exit"],code)
  self.assertEqual(self.reads,[])
 def test_unarmed_no_read(self):
  self.assertEqual(m.finish(None,0,self.cwd,self.reader)["exit"],0);self.assertEqual(self.reads,[])
 def test_unrelated_program_unarmed(self):self.assertIsNone(self.arm(program="configdata.pm"))
 def test_missing_mode_unarmed(self):self.assertIsNone(self.arm(mode=""))
 def test_apply_mode_rejected(self):
  with self.assertRaisesRegex(AssertionError,"APPLY_DISABLED"):self.arm(mode="apply")
 def test_host_target_rejected(self):
  with self.assertRaisesRegex(AssertionError,"TARGET"):self.arm(argv=["VC-WIN64A","--prefix="+self.root+"/install"])
 def test_duplicate_android_target_rejected(self):
  with self.assertRaisesRegex(AssertionError,"TARGET"):self.arm(argv=self.argv+["linux-aarch64"])
 def test_missing_prefix_rejected(self):
  with self.assertRaisesRegex(AssertionError,"PREFIX"):self.arm(argv=["linux-aarch64"])
 def test_duplicate_prefix_rejected(self):
  with self.assertRaisesRegex(AssertionError,"PREFIX"):self.arm(argv=self.argv+[self.argv[1]])
 def test_outside_prefix_rejected(self):
  with self.assertRaisesRegex(AssertionError,"SCOPE"):self.arm(argv=["linux-aarch64","--prefix=/d/other/install"])
 def test_cargo_prefix_accepted(self):
  ctx=self.arm(argv=["linux-aarch64","--prefix="+self.root+"/target/aarch64-linux-android/ci-test/build/openssl-sys-ab12/out/openssl-build/install"]);self.assertIsNotNone(ctx)
 def test_wrong_cargo_target_rejected(self):
  with self.assertRaisesRegex(AssertionError,"PREFIX"):self.arm(argv=["linux-aarch64","--prefix="+self.root+"/target/host/ci-test/build/openssl-sys-ab12/out/openssl-build/install"])
 def test_outside_cwd_rejected(self):
  with self.assertRaisesRegex(AssertionError,"SCOPE"):self.arm(cwd="/d/outside/build")
 def test_root_prefix_alias_rejected(self):
  with self.assertRaisesRegex(AssertionError,"SCOPE"):self.arm(cwd="/d/ci-work-alias/build")
 def test_traversal_rejected(self):
  for value in ("/d/ci-work/../outside","/d/ci-work/./build","//server/ci-work","/d//ci-work","/d/ci-work/"):
   with self.assertRaisesRegex(AssertionError,"PATH"):self.arm(cwd=value)
 def test_spaces_and_parentheses_contract(self):
  root="/d/ci work"
  with self.assertRaisesRegex(AssertionError,"PREFIX"):self.arm(root=root,cwd=root+"/build",argv=["linux-aarch64","--prefix="+root+"/install"])
  with self.assertRaisesRegex(AssertionError,"PATH"):self.arm(root="/d/ci(work)")
 def test_wrong_configure_pin_rejected(self):
  with self.assertRaisesRegex(AssertionError,"PIN"):self.arm(pin="0"*64)
 def test_invalid_pin_rejected(self):
  with self.assertRaisesRegex(AssertionError,"PIN"):self.arm(pin="secret/path")
 def test_end_cwd_change_fatal(self):self.assertEqual(m.finish(self.arm(),0,self.cwd+"x",self.reader)["exit"],90);self.assertEqual(self.reads,[])
 def test_end_configure_replacement_fatal(self):
  self.assertEqual(m.finish(self.arm(),0,self.cwd,lambda n,c:b"changed")["exit"],90)
 def test_missing_makefile_fatal(self):
  def reader(n,c):
   if n=="Makefile":raise FileNotFoundError(2,"private value")
   return self.config
  row=m.finish(self.arm(),0,self.cwd,reader);self.assertEqual(row["exit"],90);self.assertNotIn("private",json.dumps(row))
 def test_denial_fatal_redacted(self):
  def reader(n,c):raise PermissionError(13,"outside/private/path")
  row=m.finish(self.arm(),0,self.cwd,reader);self.assertEqual(row["exit"],90);self.assertNotIn("private",json.dumps(row))
 def test_empty_makefile_fatal(self):
  self.assertEqual(m.finish(self.arm(),0,self.cwd,lambda n,c:self.config if n=="Configure" else b"")["exit"],90)
 def test_oversized_makefile_fatal(self):
  self.assertEqual(m.finish(self.arm(),0,self.cwd,lambda n,c:self.config if n=="Configure" else b"x"*(m.MAX+1))["exit"],90)
 def test_unexpected_exit_type_fatal(self):
  for code in (-1,256,True,"0"):
   with self.assertRaisesRegex(AssertionError,"EXIT"):m.finish(self.arm(),code,self.cwd,self.reader)
 def test_argument_bound(self):
  with self.assertRaisesRegex(AssertionError,"ARGV"):self.arm(argv=self.argv+["x"]*127)
 def test_report_contains_no_paths(self):
  row=m.finish(self.arm(),0,self.cwd,self.reader);text=json.dumps(row["report"]);self.assertNotIn(self.root,text);self.assertLess(len(text),1024)
class StaticSource(unittest.TestCase):
 def test_source_is_observer_only(self):
  row=m.inspect_source(SOURCE);self.assertFalse(row["perlSyntaxQualified"]);self.assertFalse(row["writeAuthority"])
 def test_apply_weakening_rejected(self):
  with self.assertRaisesRegex(AssertionError,"SOURCE_MODE"):m.inspect_source(SOURCE.replace('unless $mode eq "observe"','unless 1'))
 def test_exit_restore_removal_rejected(self):
  with self.assertRaisesRegex(AssertionError,"SOURCE_EXIT"):m.inspect_source(SOURCE.replace('$?=$saved;',''))
 def test_unknown_child_execution_rejected(self):
  with self.assertRaisesRegex(AssertionError,"SOURCE_SIDE_EFFECT"):m.inspect_source(SOURCE+"\nsystem 'unqualified';\n")
 def test_no_failed_output_authorization(self):
  self.assertIn("windowsHeldIdentityQualified=>JSON::PP::false",SOURCE);self.assertNotIn("fno-temp-file",SOURCE)

class ProbeProtocol(unittest.TestCase):
 def row(self):return {"state":"OBSERVE_ONLY_NO_WRITE_AUTHORITY","configureSHA256":"a"*64,"makefileSHA256":"b"*64,"makefileBytes":100,"windowsHeldIdentityQualified":False,"productionEnabled":False}
 def text(self,row):return "VIBETRAM_DIRECT_OUTPUT_OBSERVATION "+json.dumps(row)
 def test_observation_schema(self):self.assertEqual(m.parse_observation(self.text(self.row())),self.row())
 def test_observation_authority_denied(self):
  for key in ("windowsHeldIdentityQualified","productionEnabled"):
   row=self.row();row[key]=True
   with self.assertRaisesRegex(AssertionError,"AUTHORITY"):m.parse_observation(self.text(row))
 def test_missing_duplicate_and_oversized_observation_denied(self):
  for text in ("",self.text(self.row())+"\n"+self.text(self.row()),"VIBETRAM_DIRECT_OUTPUT_OBSERVATION "+"x"*1025):
   with self.assertRaises(AssertionError):m.parse_observation(text)
 def test_extra_private_field_denied(self):
  row=self.row();row["path"]="PRIVATE"
  with self.assertRaisesRegex(AssertionError,"SCHEMA"):m.parse_observation(self.text(row))
 def test_wrong_hash_and_size_denied(self):
  for key,value in (("configureSHA256","wrong"),("makefileBytes",True),("makefileBytes",0),("makefileBytes",m.MAX_BYTES+1)):
   row=self.row();row[key]=value
   with self.assertRaisesRegex(AssertionError,"INPUT"):m.parse_observation(self.text(row))
 def test_entry_exact_context(self):
  for event in ("push","pull_request","workflow_dispatch"):
   for repo in ("TroubledPerson/Vibetram","other/Vibetram"):
    for ref in ("refs/heads/main","refs/heads/other"):
     self.assertEqual(m.allowed_entry(event,repo,ref,m.MARKER),event=="push" and repo=="TroubledPerson/Vibetram" and ref=="refs/heads/main")
 def test_metadata_collision_denied(self):
  for marker in ("[metadata-image-only-191]","[tool-metadata-only-191]"):
   self.assertFalse(m.allowed_entry("push","TroubledPerson/Vibetram","refs/heads/main",m.MARKER+" "+marker))
 def test_final_report_unknown_cleanup_is_fatal(self):
  for monitor in (None,{"started":False},{"started":True,"zeroOwnedMembers":None},{"started":True,"zeroOwnedMembers":True,"censusPending":False,"censusCleanupFailures":[],"censusFailure":True}):
   self.assertEqual(m.seal_report({"state":"PASS"},monitor)["state"],"FAILED")
 def test_final_report_verified_cleanup_preserves_result(self):
  monitor={"started":True,"zeroOwnedMembers":True,"censusPending":False,"censusCleanupFailures":[],"censusFailure":False}
  self.assertEqual(m.seal_report({"state":"PASS"},monitor)["state"],"PASS")
  self.assertEqual(m.seal_report({"state":"FAILED","code":"ORIGINAL"},monitor)["code"],"ORIGINAL")
 def test_controller_no_compiler_or_shell(self):
  self.assertIn("system { $^X } $^X",m.CONTROLLER_SOURCE);self.assertNotIn("clang",m.CONTROLLER_SOURCE);self.assertNotIn("make.exe",m.CONTROLLER_SOURCE)
 def test_production_does_not_import_probe(self):
  import inspect,cloud_build,perl_overlay
  self.assertNotIn("configure_hook_probe",inspect.getsource(cloud_build));self.assertNotIn("configure_hook_probe",inspect.getsource(perl_overlay))
if __name__=="__main__":unittest.main()
