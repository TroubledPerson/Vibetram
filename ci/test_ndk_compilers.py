import unittest,types,pathlib,ast,inspect,json,os
from unittest.mock import patch
import ndk_compilers as c
class Compilers(unittest.TestCase):
 def pin(self,role="clang.exe",identity=None):
  return {"role":role,"path":str(c.PATHS[role]),"identity":identity or [1,2],"bytes":c.SIZE,"modifiedNs":7,"sha256":c.HASHES[role],"ndkRevision":c.ndk.REVISION,"compilerVersion":c.VERSION,"provenance":c.PROVENANCE}
 def meta(self,identity=None):return types.SimpleNamespace(st_dev=(identity or [1,2])[0],st_ino=(identity or [1,2])[1],st_mtime_ns=7,st_size=c.SIZE)
 def env(self,bound=True):
  env={**{k:str(c.ndk.ROOT) for k in ("ANDROID_HOME","ANDROID_SDK_ROOT")},**{k:str(c.ndk.NDK) for k in ("ANDROID_NDK","ANDROID_NDK_ROOT","ANDROID_NDK_HOME")},**{k:str(c.PATHS[v]) for k,v in (("CARGO_TARGET_AARCH64_LINUX_ANDROID_LINKER","clang.exe"),("CC_aarch64_linux_android","clang.exe"),("CXX_aarch64_linux_android","clang++.exe"))},**{k:"--target=aarch64-linux-android29" for k in ("CFLAGS_aarch64_linux_android","CXXFLAGS_aarch64_linux_android")}}
  if bound:env[c.KEY]=json.dumps({r:self.pin(r) for r in c.HASHES})
  return env
 def test_distinct_exact_pins_accept_fresh_not_historical_identities(self):
  for role in c.HASHES:
   pin=self.pin(role,[77,88]);self.assertEqual(c.pinned(c.PATHS[role],self.meta([77,88]),pin),c.HASHES[role])
  self.assertNotEqual(c.HASHES["clang.exe"],c.HASHES["clang++.exe"]);self.assertNotIn("1422631540",inspect.getsource(c))
 def test_wrong_hash_size_version_role_provenance_fields(self):
  for key,value in (("sha256","0"*64),("bytes",c.SIZE+1),("compilerVersion","22.0.0"),("ndkRevision","other"),("provenance","missing"),("role","clang-cl.exe"),("identity",[1,3]),("modifiedNs",8)):
   pin=self.pin();pin[key]=value
   with self.subTest(key=key),self.assertRaises(AssertionError):c.pinned(c.PATHS["clang.exe"],self.meta(),pin)
 def test_missing_fields_and_unknown_fields_fail(self):
  for key in self.pin():
   pin=self.pin();del pin[key]
   with self.subTest(key=key),self.assertRaises(AssertionError):c.schema(pin)
  with self.assertRaises(AssertionError):c.schema({**self.pin(),"extra":True})
 def test_wrong_quoted_alternate_and_unselected_paths_fail(self):
  for path in (str(c.PATHS["clang.exe"]).lower(),'"'+str(c.PATHS["clang.exe"])+'"',str(c.PATHS["clang.exe"]).replace("Program Files (x86)","Android"),str(c.PATHS["clang.exe"].with_name("clang-cl.exe")),str(c.PATHS["clang++.exe"])):
   with self.subTest(path=path),self.assertRaises(AssertionError):c.pinned(path,self.meta(),self.pin())
 def test_swapped_role_maps_and_hashes_rejected(self):
  records={r:self.pin(r) for r in c.HASHES};records["clang.exe"],records["clang++.exe"]=records["clang++.exe"],records["clang.exe"];env=self.env();env[c.KEY]=json.dumps(records)
  with self.assertRaises(AssertionError):c.bindings(env)
  pin=self.pin();pin["sha256"]=c.HASHES["clang++.exe"]
  with self.assertRaises(AssertionError):c.schema(pin)
 def test_missing_environment_roles_and_target_flags_fail(self):
  for key in self.env(False):
   env=self.env();del env[key]
   with self.subTest(key=key),patch.object(c.ndk,"revision"),self.assertRaises(AssertionError):c.bindings(env)
 def test_json_bound_duplicates_and_missing_pairs_fail(self):
  for text in ("", "x"*4097, "{}",'{"clang.exe":{},"clang.exe":{}}'):
   env=self.env();env[c.KEY]=text
   with self.subTest(text=text[:30]),self.assertRaises((AssertionError,ValueError)):c.bindings(env)
 def test_selection_only_registered_images_and_missing_binding_none(self):
  self.assertIsNone(c.select({},c.PATHS["clang.exe"]))
  with patch.object(c.ndk,"revision"):
   for role in c.HASHES:self.assertEqual(c.select(self.env(),c.PATHS[role]),self.pin(role))
   self.assertIsNone(c.select(self.env(),pathlib.Path("C:/host/cl.exe")));self.assertIsNone(c.select(self.env(),c.ndk.EXACT))
 def test_qualification_uses_fresh_snapshots_and_refuses_reused_environment(self):
  import build_guard
  calls=[]
  def snap(path,sample=None,**kw):
   pin=kw["large_ndk_compiler_binding"];c.pinned(path,self.meta([77,88]),pin);calls.append(pin);return {"identity":[77,88],"modifiedNs":7,"bytes":c.SIZE,"sha256":c.HASHES[pin["role"]]}
  with patch.object(c.ndk,"revision"),patch.object(pathlib.Path,"lstat",return_value=self.meta([77,88])),patch.object(build_guard,"executable_snapshot",side_effect=snap):
   result=c.qualify(self.env(False));self.assertEqual(len(calls),2);self.assertTrue(all(x["identity"]==[77,88] for x in json.loads(result[c.KEY]).values()))
   with self.assertRaisesRegex(AssertionError,"FRESH_ENV"):c.qualify(self.env())
 def test_wrong_qualification_result_and_revision_denial_fail(self):
  import build_guard
  with patch.object(c.ndk,"revision"),patch.object(pathlib.Path,"lstat",return_value=self.meta()),patch.object(build_guard,"executable_snapshot",return_value={"identity":[1,99],"modifiedNs":7,"bytes":c.SIZE,"sha256":c.HASHES["clang.exe"]}),self.assertRaisesRegex(AssertionError,"CHANGED"):c.qualify(self.env(False))
  with patch.object(c.ndk,"revision",side_effect=PermissionError(5,"synthetic")),self.assertRaises(PermissionError):c.qualify(self.env(False))
 def test_host_and_android_probe_environments_stay_separate(self):
  host={"HOST_CC":"C:/host/cl.exe"};android=self.env()
  with patch.object(c.ndk,"revision"):
   for name in ("rustc","javac"):self.assertIs(c.version_environment(name,host,android),host)
   for name in ("ndkClang","ndkClangXX","ndkArchiver"):self.assertIs(c.version_environment(name,host,android),android)
   for key in (c.KEY,c.ndk.KEY):
    with self.assertRaises(AssertionError):c.version_environment("rustc",{**host,key:"unexpected"},android)
   with self.assertRaises(AssertionError):c.version_environment("unknown",host,android)
   with self.assertRaises(AssertionError):c.version_environment("ndkClang",host,host)
 def test_runtime_version_bounded_and_exact(self):
  c.check_version("Android vendor clang version 21.0.0 (qualified payload)")
  for text in ("clang version 21.0.01","clang version 22.0.0","clang version 21.1.0","x"*4097,None):
   with self.subTest(text=str(text)[:30]),self.assertRaises(AssertionError):c.check_version(text)
 def snapshot(self,role="clang.exe",**options):
  import test_ndk_linker
  with patch.object(test_ndk_linker,"GUARD_SOURCE",GUARD_SOURCE,create=True),patch.object(c.ndk,"EXACT",c.PATHS[role]):return test_ndk_linker.NdkBinding().snapshot(size=options.get("size",c.SIZE),digest=options.get("digest",c.HASHES[role]),change=options.get("change"))
 def test_actual_snapshot_both_pins_and_general_limit_unchanged(self):
  for role in c.HASHES:
   self.assertEqual(self.snapshot(role)(c.PATHS[role],large_ndk_compiler_binding=self.pin(role))["sha256"],c.HASHES[role])
   with self.assertRaisesRegex(AssertionError,"EXECUTABLE_SIZE_BOUND"):self.snapshot(role)(c.PATHS[role])
 def test_snapshot_wrong_digest_size_replacement_link_and_denial(self):
  for options in ({"digest":"0"*64},{"size":c.SIZE+1},{"change":"file"},{"change":"ancestor"},{"change":"link"},{"change":"denial"}):
   with self.subTest(options=options),self.assertRaises((AssertionError,PermissionError)):self.snapshot(**options)(c.PATHS["clang.exe"],large_ndk_compiler_binding=self.pin())
 def test_conflicting_image_exceptions_fail(self):
  for kw in ({"large_ndk_binding":{}},{"large_lld_binding":{}}):
   with self.assertRaisesRegex(AssertionError,"AMBIGUOUS"):self.snapshot()(c.PATHS["clang.exe"],large_ndk_compiler_binding=self.pin(),**kw)
 def cache(self,deny=False):
  import test_process_image,process_image,sys
  p,row,file,q,stub=test_process_image.CacheTests().setup();calls=[];queries=[]
  class Query:
   def __call__(self,h,flags,buf,count):queries.append(h);buf.value=str(c.PATHS["clang.exe"]);return True
  p.api.k.QueryFullProcessImageNameW=Query();file.update(bytes=c.SIZE,modifiedNs=7,sha256=c.HASHES["clang.exe"])
  def snap(path,*a,**kw):
   calls.append(kw)
   if deny:raise PermissionError(5,"synthetic")
   pin=kw["large_ndk_compiler_binding"];c.pinned(path,self.meta(),pin);return dict(file)
  stub.executable_snapshot=snap
  return p,row,file,stub,calls,queries
 def test_actual_cache_forwards_compiler_pin_and_binds_process_identity(self):
  import process_image,sys
  p,row,file,stub,calls,queries=self.cache()
  with patch.dict(sys.modules,{"build_guard":stub}),patch.object(c.ndk,"revision"):
   process_image.remember(p,1,dict(row),self.env(),expected=c.PATHS["clang.exe"]);row["exited"]=True;result=process_image.retained(p,1,dict(row),self.env());self.assertTrue(result["heldIdentityVerified"]);self.assertEqual(len(queries),1);self.assertEqual(len(calls),2);row["creationFiletime"]+=1
   with self.assertRaises(AssertionError):process_image.retained(p,1,dict(row),self.env())
 def test_image_capture_denial_latched_without_retry(self):
  import process_image,sys
  p,row,file,stub,calls,queries=self.cache(True)
  with patch.dict(sys.modules,{"build_guard":stub}),patch.object(c.ndk,"revision"):
   with self.assertRaises(PermissionError):process_image.remember(p,1,row,self.env())
   with self.assertRaises(RuntimeError):process_image.remember(p,1,row,self.env())
  self.assertEqual(len(calls),1);self.assertEqual(len(queries),1)
 def test_production_start_denial_never_resumes_and_owned_cleanup_verified(self):
  from census_supervisor import OwnedProcess
  from test_census_supervision import FakeOwnedJobAPI
  class API(FakeOwnedJobAPI):
   def duplicate(self,*a):return 100+len(self.closed)
   def snapshot(self,h):return {**super().snapshot(h),"exitCode":0 if self.dead else None}
   def create_in_job(self,*a):self.active=True;self.assigned=True;return 10,11
  api=API();p=OwnedProcess(api)
  def denied(*a):raise AssertionError("NDK_COMPILER_HASH_PIN")
  with open(os.devnull,"wb") as a,open(os.devnull,"wb") as b:
   with self.assertRaisesRegex(AssertionError,"HASH_PIN"):p.start([str(c.PATHS["clang.exe"])],str(c.ndk.NDK),{"PATH":"C:/fixture-only"},stdout=a,stderr=b,image_capture=denied)
  self.assertNotIn("resume",api.calls);self.assertFalse(api.active);self.assertTrue(p.closed);self.assertTrue(p.teardown["processTreeExitIndependentlyVerified"])
 def test_final_source_routes_both_compilers_before_make_and_fresh_android_cargo(self):
  self.assertEqual(PROCESS_SOURCE.count("compiler_pin=select_compiler("),2);self.assertIn("large_ndk_compiler_binding",PROCESS_SOURCE);self.assertLess(PERL_SOURCE.index("cross.update(qualify_compilers("),PERL_SOURCE.index('versions={name:guard.run'))
  self.assertIn("probe_env=version_environment(name,ENV,cross)",CLOUD_SOURCE);self.assertIn("env=probe_env",CLOUD_SOURCE);self.assertIn("ndkClangXX",CLOUD_SOURCE);self.assertIn("cross.update(qualify_compilers(cross,GUARD._resource_sample))",CLOUD_SOURCE)
 def test_fresh_android_pin_qualification_precedes_cargo_and_host_isolated(self):
  tail=CLOUD_SOURCE.split("cross=cargo_environment(build_android_environment",1)[1];self.assertLess(tail.index("cross.update(qualify_compilers("),tail.index("built=run(['cargo','test'"));host=CLOUD_SOURCE.split("host=run(",1)[1].split("\n",1)[0];self.assertIn("env=ENV",host)
 def test_compiler_cache_rejects_changed_job_closed_owner_or_file(self):
  import process_image,sys
  for change in ("job","closed","file"):
   p,row,file,stub,calls,queries=self.cache()
   with patch.dict(sys.modules,{"build_guard":stub}),patch.object(c.ndk,"revision"):
    process_image.remember(p,1,dict(row),self.env());row["exited"]=True
    if change=="job":p.job+=1
    elif change=="closed":p.closed=True
    else:file["modifiedNs"]+=1
    with self.subTest(change=change),self.assertRaises(AssertionError):process_image.retained(p,1,dict(row),self.env())

 def make_env(self):
  from perl_overlay import build_android_environment
  parent={"PATH":"C:/synthetic-host-tools","HOST_CC":"C:/synthetic-msvc/cl.exe"}
  cross=build_android_environment(parent,c.ndk.NDK,c.PATHS["clang.exe"].parent,pathlib.Path("C:/Program Files/Git/usr/bin/perl.exe"))
  return parent,cross
 def test_actual_make_builder_satisfies_strict_target_roles(self):
  parent,cross=self.make_env();c.environment(cross)
  self.assertEqual(cross["CC"],"clang.exe");self.assertEqual(cross["AR"],"llvm-ar.exe")
  self.assertEqual(cross["CXX_aarch64_linux_android"],str(c.PATHS["clang++.exe"]))
  self.assertEqual(cross["CC_aarch64_linux_android"],str(c.PATHS["clang.exe"]))
  self.assertEqual(cross["CARGO_TARGET_AARCH64_LINUX_ANDROID_LINKER"],str(c.PATHS["clang.exe"]))
  self.assertNotIn(c.KEY,cross);self.assertEqual(parent,{"PATH":"C:/synthetic-host-tools","HOST_CC":"C:/synthetic-msvc/cl.exe"})
  self.assertEqual(cross["HOST_CC"],parent["HOST_CC"])
 def test_actual_cargo_builder_remains_separate_and_absolute(self):
  from build_guard import android_env
  parent={"ANDROID_HOME":str(c.ndk.ROOT),"ANDROID_SDK_ROOT":str(c.ndk.ROOT),"PATH":"C:/host"}
  cross=android_env(parent,c.ndk.NDK);c.environment(cross)
  self.assertNotIn(c.KEY,parent);self.assertNotIn("CC",cross)
  self.assertEqual(cross["CARGO_TARGET_AARCH64_LINUX_ANDROID_LINKER"],str(c.PATHS["clang.exe"]))
 def test_make_target_basename_quote_alias_or_swapped_role_still_denied(self):
  _,cross=self.make_env()
  for key in ("CC_aarch64_linux_android","CXX_aarch64_linux_android","CARGO_TARGET_AARCH64_LINUX_ANDROID_LINKER"):
   role="clang++.exe" if key.startswith("CXX") else "clang.exe"
   for wrong in (role,'"'+str(c.PATHS[role])+'"',str(c.PATHS[role].with_name("clang-cl.exe")),str(c.PATHS["clang.exe" if role=="clang++.exe" else "clang++.exe"])):
    with self.subTest(key=key,wrong=wrong),self.assertRaises(AssertionError):c.environment({**cross,key:wrong})
 def test_actual_make_environment_qualifies_fresh_pins_then_stale_rejected(self):
  import build_guard
  _,cross=self.make_env();calls=[]
  def snapshot(path,sample=None,large_ndk_compiler_binding=None):
   pin=large_ndk_compiler_binding;c.schema(pin);calls.append(pin["role"])
   return {"identity":[1,2],"bytes":c.SIZE,"modifiedNs":7,"sha256":c.HASHES[pin["role"]]}
  with patch.object(pathlib.Path,"lstat",return_value=self.meta()),patch.object(c.ndk,"revision"),patch.object(build_guard,"executable_snapshot",side_effect=snapshot):
   qualified={**cross,**c.qualify(cross)};self.assertEqual(calls,["clang.exe","clang++.exe"])
   self.assertEqual(c.select(qualified,c.PATHS["clang.exe"])["sha256"],c.HASHES["clang.exe"])
   with self.assertRaisesRegex(AssertionError,"REQUIRE_FRESH_ENV"):c.qualify(qualified)
  with self.assertRaisesRegex(AssertionError,"STALE_IDENTITY"):c.pinned(c.PATHS["clang.exe"],self.meta([1,3]),self.pin())
 def test_make_qualified_environment_never_enters_host_version_probe(self):
  _,cross=self.make_env();cross[c.KEY]=json.dumps({r:self.pin(r) for r in c.HASHES})
  with self.assertRaisesRegex(AssertionError,"ALLOWANCE_IN_HOST_ENV"):c.version_environment("rustc",cross,cross)
  host={"PATH":"C:/host"}
  with patch.object(c.ndk,"revision"):
   self.assertIs(c.version_environment("ndkClang",host,cross),cross)
   self.assertIs(c.version_environment("javac",host,cross),host)
if __name__=="__main__":
 root=pathlib.Path(__file__).parent;GUARD_SOURCE=(root/"build_guard.py").read_text();PROCESS_SOURCE=(root/"process_image.py").read_text();PERL_SOURCE=(root/"perl_overlay.py").read_text();CLOUD_SOURCE=(root/"cloud_build.py").read_text();unittest.main()
