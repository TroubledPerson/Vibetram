import unittest,types,ast,pathlib,stat,io,json
from unittest.mock import patch
import ndk_linker as n
class NdkBinding(unittest.TestCase):
 def pin(self):return {"path":str(n.EXACT),"identity":[1,2],"bytes":n.SIZE,"modifiedNs":7,"sha256":n.SHA,"ndkRevision":n.REVISION,"provenance":n.PROVENANCE}
 def meta(self):return types.SimpleNamespace(st_dev=1,st_ino=2,st_mtime_ns=7,st_size=n.SIZE)
 def env(self):return {**{k:str(n.ROOT) for k in ("ANDROID_HOME","ANDROID_SDK_ROOT")},**{k:str(n.NDK) for k in ("ANDROID_NDK","ANDROID_NDK_ROOT","ANDROID_NDK_HOME")},n.KEY:json.dumps(self.pin())}
 def test_exact_pin(self):self.assertEqual(n.pinned(n.EXACT,self.meta(),self.pin()),n.SHA)
 def test_wrong_pin_fields(self):
  for k,v in (("sha256","0"*64),("bytes",n.SIZE+1),("path",str(n.EXACT.with_name("other.exe"))),("ndkRevision","other"),("provenance","unqualified"),("identity",[1,3]),("modifiedNs",8)):
   pin=self.pin();pin[k]=v
   with self.subTest(field=k),self.assertRaises(AssertionError):n.pinned(n.EXACT,self.meta(),pin)
 def test_missing_provenance_and_extra_fields(self):
  for k in self.pin():
   pin=self.pin();del pin[k]
   with self.subTest(field=k),self.assertRaises(AssertionError):n.schema(pin)
  with self.assertRaises(AssertionError):n.schema({**self.pin(),"extra":True})
 def test_path_name_only_rejected(self):
  with self.assertRaises(AssertionError):n.pinned(n.EXACT.with_name("other.exe"),self.meta(),self.pin())
 def test_wrong_actual_size_rejected(self):
  m=self.meta();m.st_size+=1
  with self.assertRaises(AssertionError):n.pinned(n.EXACT,m,self.pin())
 def test_binding_bound_and_routes(self):
  for env in ({n.KEY:"{}"}, {n.KEY:"x"*2049}, {**self.env(),"ANDROID_HOME":"C:/different"}):
   with self.assertRaises((AssertionError,ValueError)):n.select(env,n.EXACT)
 def test_missing_binding_does_not_allow_image(self):self.assertIsNone(n.select({},n.EXACT))
 def test_exact_selection_only_and_version(self):
  with patch.object(n,"revision"):self.assertEqual(n.select(self.env(),n.EXACT),self.pin());self.assertIsNone(n.select(self.env(),n.EXACT.with_name("other.exe")))
  n.version(n.VERSION)
  for text in ("LLD 21.0.0","LLD 22.0.0",n.VERSION+" changed"):
   with self.assertRaises(AssertionError):n.version(text)
 def snapshot(self,size=None,digest=None,change=None):
  import build_guard
  expected=str(n.EXACT);calls={}
  class Path:
   def __init__(self,p):self.p=pathlib.PureWindowsPath(str(p))
   def __str__(self):return str(self.p)
   def is_absolute(self):return self.p.is_absolute()
   @property
   def parts(self):return self.p.parts
   @property
   def parents(self):return [Path(p) for p in self.p.parents]
   def lstat(self):
    text=str(self);calls[text]=calls.get(text,0)+1;file=text==expected;ino=2 if file else 1
    if calls[text]>1 and change=="file" and file:ino=3
    if calls[text]>1 and change=="ancestor" and text==str(n.ROOT):ino=3
    return types.SimpleNamespace(st_dev=1,st_ino=ino,st_mtime_ns=7,st_size=(n.SIZE if size is None else size) if file else 0,st_mode=stat.S_IFREG if file else stat.S_IFDIR,st_reparse_tag=1 if change=="link" and file else 0,st_file_attributes=0)
   def open(self,mode):
    if change=="denial":raise PermissionError(5,"synthetic")
    return io.BytesIO(b"MZ"+bytes(62))
  class Digest:
   def update(self,b):pass
   def hexdigest(self):return n.SHA if digest is None else digest
  tree=ast.parse(GUARD_SOURCE);nodes=[x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name=="executable_snapshot"];scope={"pathlib":types.SimpleNamespace(Path=Path),"stat":stat,"hashlib":types.SimpleNamespace(sha256=Digest),"time":types.SimpleNamespace(monotonic=lambda:0),"os":types.SimpleNamespace(environ={})};exec(compile(ast.Module(body=nodes,type_ignores=[]),"<ndk-snapshot>","exec"),scope);return scope["executable_snapshot"]
 def test_snapshot_hash_and_fresh_metadata(self):self.assertEqual(self.snapshot()(n.EXACT,large_ndk_binding=self.pin())["sha256"],n.SHA)
 def test_general_limit_unchanged(self):
  with self.assertRaisesRegex(AssertionError,"EXECUTABLE_SIZE_BOUND"):self.snapshot()(n.EXACT)
  self.assertEqual(self.snapshot(size=64)(n.EXACT)["bytes"],64)
 def test_snapshot_wrong_digest_and_size(self):
  with self.assertRaisesRegex(AssertionError,"HASH_MISMATCH"):self.snapshot(digest="0"*64)(n.EXACT,large_ndk_binding=self.pin())
  with self.assertRaisesRegex(AssertionError,"LENGTH"):self.snapshot(size=n.SIZE+1)(n.EXACT,large_ndk_binding=self.pin())
 def test_snapshot_replacement_link_and_denial_fatal(self):
  for change in ("file","ancestor","link","denial"):
   with self.subTest(change=change),self.assertRaises((AssertionError,PermissionError)):self.snapshot(change=change)(n.EXACT,large_ndk_binding=self.pin())
 def test_conflicting_large_pins_fatal(self):
  with self.assertRaisesRegex(AssertionError,"AMBIGUOUS"):self.snapshot()(n.EXACT,large_ndk_binding=self.pin(),large_lld_binding={})
 def test_qualify_reads_revision_and_fresh_snapshot(self):
  import build_guard
  with patch.object(n,"revision") as rev,patch.object(pathlib.Path,"lstat",return_value=self.meta()),patch.object(build_guard,"executable_snapshot",return_value={"identity":[1,2],"bytes":n.SIZE,"sha256":n.SHA}) as snap:
   env=self.env();env.pop(n.KEY);out=n.qualify(env);self.assertEqual(json.loads(out[n.KEY]),self.pin());rev.assert_called_once();self.assertEqual(snap.call_args.kwargs["large_ndk_binding"],self.pin())
 def test_integration_both_capture_and_cargo_routes(self):
  self.assertEqual(PROCESS_SOURCE.count("ndk_pin=select("),2);self.assertIn("large_ndk_binding",PROCESS_SOURCE);self.assertLess(PERL_SOURCE.index("cross.update(qualify_ndk("),PERL_SOURCE.index('versions={name:guard.run'));self.assertIn('check_ndk_version(versions["lld"])',PERL_SOURCE);self.assertIn("cross.update(qualify_ndk(cross,GUARD._resource_sample))",CLOUD_SOURCE)
 def test_actual_image_cache_carries_ndk_pin_before_and_after_exit(self):
  import process_image as image,test_process_image,sys
  p,row,file,oldquery,stub=test_process_image.CacheTests().setup();calls=[];querycalls=[]
  class Query:
   def __call__(self,h,flags,buf,count):querycalls.append(h);buf.value=str(n.EXACT);return True
  p.api.k.QueryFullProcessImageNameW=Query();file.update(bytes=n.SIZE,modifiedNs=7,sha256=n.SHA)
  def snapshot(path,*args,**kwargs):
   pin=kwargs.get("large_ndk_binding");self.assertIsNotNone(pin);self.assertEqual(pin,self.pin());n.pinned(path,self.meta(),pin);calls.append(pin);return dict(file)
  stub.executable_snapshot=snapshot
  with patch.dict(sys.modules,{"build_guard":stub}),patch.object(n,"revision"):
   image.remember(p,1,dict(row),self.env(),expected=n.EXACT);row["exited"]=True;result=image.retained(p,1,dict(row),self.env())
  self.assertEqual(len(querycalls),1);self.assertEqual(len(calls),2);self.assertTrue(result["heldIdentityVerified"]);self.assertTrue(result["imageObservedWhileAlive"]);self.assertNotIn("path",result)

 def test_revision_wrong_metadata_replacement_and_denial(self):
  import openssl_probe
  good="Pkg.Revision = "+n.REVISION+"\n"
  def meta(ino=2):return types.SimpleNamespace(st_dev=1,st_ino=ino,st_size=100,st_mtime_ns=7)
  with patch.object(openssl_probe,"regular_chain"),patch.object(pathlib.Path,"lstat",return_value=meta()),patch.object(pathlib.Path,"read_text",return_value=good):n.revision()
  for text in ("Pkg.Revision = wrong\n","",good+good):
   with patch.object(openssl_probe,"regular_chain"),patch.object(pathlib.Path,"lstat",return_value=meta()),patch.object(pathlib.Path,"read_text",return_value=text),self.subTest(text=text),self.assertRaises(AssertionError):n.revision()
  with patch.object(openssl_probe,"regular_chain"),patch.object(pathlib.Path,"lstat",side_effect=[meta(),meta(3)]),patch.object(pathlib.Path,"read_text",return_value=good),self.assertRaisesRegex(AssertionError,"CHANGED"):n.revision()
  with patch.object(openssl_probe,"regular_chain",side_effect=PermissionError(5,"synthetic")),self.assertRaises(PermissionError):n.revision()
 def test_qualification_mismatch_produces_no_binding(self):
  import build_guard
  for row in ({"identity":[1,99],"bytes":n.SIZE,"sha256":n.SHA},{"identity":[1,2],"bytes":n.SIZE,"sha256":"0"*64}):
   with patch.object(n,"revision"),patch.object(pathlib.Path,"lstat",return_value=self.meta()),patch.object(build_guard,"executable_snapshot",return_value=row),self.subTest(row=row),self.assertRaisesRegex(AssertionError,"CHANGED"):n.qualify(self.env())
if __name__=="__main__":
 root=pathlib.Path(__file__).parent;GUARD_SOURCE=(root/"build_guard.py").read_text();PROCESS_SOURCE=(root/"process_image.py").read_text();PERL_SOURCE=(root/"perl_overlay.py").read_text();CLOUD_SOURCE=(root/"cloud_build.py").read_text();unittest.main()
