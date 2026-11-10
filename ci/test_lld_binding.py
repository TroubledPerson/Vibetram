import unittest,ast,pathlib,types,stat,io,tomllib
from unittest.mock import patch
PIN='3cf499fc8a03853722d19e3ae1c5cdd143ac7426f1405b9e6efacd7a94b7328a'
class BindingTests(unittest.TestCase):
 def setup_scope(self,change=None,size=113349120,digest=PIN):
  file='/verified/toolchains/1.95.0-x86_64-pc-windows-msvc/lib/rustlib/x86_64-pc-windows-msvc/bin/rust-lld.exe';calls={};Pure=pathlib.PurePosixPath
  class Path:
   def __init__(self,p):self.p=Pure(str(p))
   def __str__(self):return str(self.p)
   def __eq__(self,o):return str(self)==str(o)
   def __truediv__(self,x):return Path(self.p/x)
   def is_absolute(self):return self.p.is_absolute()
   @property
   def parts(self):return self.p.parts
   @property
   def parents(self):return [Path(p) for p in self.p.parents]
   def lstat(self):
    name=str(self);calls[name]=calls.get(name,0)+1;regular=name==file;ino=2 if regular else 1
    if calls[name]>1 and change=='file' and regular:ino=3
    if calls[name]>1 and change=='ancestor' and name=='/verified':ino=3
    return types.SimpleNamespace(st_dev=1,st_ino=ino,st_mode=stat.S_IFREG if regular else stat.S_IFDIR,st_size=size if regular else 0,st_mtime_ns=1,st_file_attributes=0,st_reparse_tag=0)
   def open(self,mode):return io.BytesIO(b'MZ'+bytes(62))
  class Digest:
   def update(self,b):pass
   def hexdigest(self):return digest
  tree=ast.parse(GUARD_SOURCE);nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('pinned_large_lld','executable_snapshot')];scope={'pathlib':types.SimpleNamespace(Path=Path),'os':types.SimpleNamespace(environ={'RUSTUP_HOME':'/verified','VIBETRAM_PROVISIONED_RUST':'1'}),'stat':stat,'hashlib':types.SimpleNamespace(sha256=Digest),'time':types.SimpleNamespace(monotonic=lambda:0)};exec(compile(ast.Module(body=nodes,type_ignores=[]),'<binding-under-test>','exec'),scope)
  pin={'path':file,'identity':[1,2],'bytes':113349120,'sha256':PIN};return scope,file,pin
 def test_valid_pinned_linker(self):
  s,f,p=self.setup_scope();self.assertEqual(s['executable_snapshot'](f,large_lld_binding=p)['sha256'],PIN)
 def test_wrong_identity(self):
  s,f,p=self.setup_scope();p['identity']=[1,99]
  with self.assertRaisesRegex(AssertionError,'IDENTITY'):s['executable_snapshot'](f,large_lld_binding=p)
 def test_wrong_expected_hash(self):
  s,f,p=self.setup_scope();p['sha256']='0'*64
  with self.assertRaisesRegex(AssertionError,'HASH_PIN'):s['executable_snapshot'](f,large_lld_binding=p)
 def test_wrong_actual_hash(self):
  s,f,p=self.setup_scope(digest='0'*64)
  with self.assertRaisesRegex(AssertionError,'HASH_MISMATCH'):s['executable_snapshot'](f,large_lld_binding=p)
 def test_wrong_length(self):
  s,f,p=self.setup_scope(size=113349121)
  with self.assertRaisesRegex(AssertionError,'LENGTH'):s['executable_snapshot'](f,large_lld_binding=p)
 def test_wrong_bound_length(self):
  s,f,p=self.setup_scope();p['bytes']=113349119
  with self.assertRaisesRegex(AssertionError,'LENGTH'):s['executable_snapshot'](f,large_lld_binding=p)
 def test_unexpected_executable_path(self):
  s,f,p=self.setup_scope();p['path']='/other/rust-lld.exe'
  with self.assertRaisesRegex(AssertionError,'EXACT_PATH'):s['executable_snapshot'](f,large_lld_binding=p)
 def test_unprovisioned_root(self):
  s,f,p=self.setup_scope();s['os'].environ['VIBETRAM_PROVISIONED_RUST']='0'
  with self.assertRaisesRegex(AssertionError,'PROVISIONED'):s['executable_snapshot'](f,large_lld_binding=p)
 def test_general_oversized_still_rejected(self):
  s,f,p=self.setup_scope()
  with self.assertRaisesRegex(AssertionError,'EXECUTABLE_SIZE_BOUND'):s['executable_snapshot'](f)
 def test_file_replacement_rejected(self):
  s,f,p=self.setup_scope(change='file')
  with self.assertRaisesRegex(AssertionError,'IDENTITY_CHANGED'):s['executable_snapshot'](f,large_lld_binding=p)
 def test_ancestor_replacement_rejected(self):
  s,f,p=self.setup_scope(change='ancestor')
  with self.assertRaisesRegex(AssertionError,'ANCESTOR_CHANGED'):s['executable_snapshot'](f,large_lld_binding=p)
 def test_fixture_metadata_and_target_separation(self):
  tree=ast.parse(LLD_SOURCE);literals=[n.value for n in ast.walk(tree) if isinstance(n,ast.Constant) and isinstance(n.value,str)];manifest=next(x for x in literals if x.startswith('[package]') and 'lld-routing-fixture' in x);data=tomllib.loads(manifest);self.assertEqual(data['lib']['crate-type'],['cdylib','rlib']);self.assertEqual(data['profile']['dev']['debug'],'limited');self.assertIn('CARGO_TARGET_X86_64_PC_WINDOWS_MSVC_LINKER',LLD_SOURCE);self.assertIn("cross['CARGO_TARGET_AARCH64_LINUX_ANDROID_LINKER']",LLD_SOURCE);self.assertIn('loadAlignment16384',LLD_SOURCE);self.assertIn('large_lld_binding=large_pin',LLD_SOURCE)
if __name__=='__main__':
 root=pathlib.Path(__file__).parent;GUARD_SOURCE=(root/'build_guard.py').read_text();LLD_SOURCE=(root/'lld_probe.py').read_text();unittest.main()
