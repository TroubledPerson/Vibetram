import unittest,pathlib,struct,ast
from lld_probe import rust_args,pe_debug,LLD_SHA,LLD_SIZE
class File:
 def __init__(self,b,p):self.b=b;self.p=p
 def read_bytes(self):return self.b
 def with_name(self,n):return File(self.p,b'')
def fixture():
 b=bytearray(2048);b[:2]=b'MZ';struct.pack_into('<I',b,60,128);b[128:132]=b'PE\0\0';struct.pack_into('<HH',b,132,0x8664,1);struct.pack_into('<H',b,148,240);o=152;struct.pack_into('<H',b,o,0x20b);struct.pack_into('<H',b,o+70,0x140);struct.pack_into('<Q',b,o+72,8388608);struct.pack_into('<II',b,o+160,0x1000,28);struct.pack_into('<IIII',b,o+240+8,1024,0x1000,1024,512);struct.pack_into('<IIII',b,524,2,35,0x1040,576);guid=bytes(range(16));cv=b'RSDS'+guid+struct.pack('<I',1)+b'tiny.pdb\0';b[576:576+len(cv)]=cv
 p=bytearray(2048);p[:32]=b'Microsoft C/C++ MSF 7.00\r\n\x1aDS\0\0\0';struct.pack_into('<IIIIII',p,32,512,0,4,16,0,1);struct.pack_into('<I',p,512,2);struct.pack_into('<IIII',p,1024,2,0,28,3);struct.pack_into('<III',p,1536,20000404,0,1);p[1548:1564]=guid
 return bytes(b),bytes(p)
class Tests(unittest.TestCase):
 def test_identity_constants(self):self.assertEqual(len(LLD_SHA),64);self.assertEqual(LLD_SIZE,113349120)
 def test_exact_routing_preserves_flags(self):
  w=pathlib.Path('/fixture');a=['rustc','--edition','2024','--target','x86_64-pc-windows-msvc','-C','linker=/msvc/link.exe',str(w/'tiny-msvc.rs'),'-o',str(w/'tiny-msvc.exe')];r=rust_args(a,w,pathlib.Path('/verified/rust-lld.exe'));self.assertIn('target-feature=+crt-static',r);self.assertIn('link-arg=/STACK:8388608',r);self.assertIn('debuginfo=1',r);self.assertEqual(a[6],'linker=/msvc/link.exe')
 def test_wrong_scope_rejected(self):
  w=pathlib.Path('/fixture');a=['rustc','--edition','2024','--target','x86_64-pc-windows-msvc','-C','linker=/msvc/link.exe',str(w/'tiny-msvc.rs'),'-o',str(w/'tiny-msvc.exe')]
  for i,value in [(0,'cargo'),(4,'aarch64-linux-android'),(6,'linker=/other/ld'),(7,'unrelated.rs')]:
   with self.subTest(i=i):
    q=a.copy();q[i]=value
    with self.assertRaises(AssertionError):rust_args(q,w,pathlib.Path('/verified/rust-lld.exe'))
 def test_pdb_binding_stack_crt(self):
  b,p=fixture();r=pe_debug(File(b,p));self.assertTrue(r['pdbGuidAgeBinding']);self.assertTrue(r['staticCRTImportsVerified'])
 def test_wrong_stack(self):
  b,p=fixture();b=bytearray(b);struct.pack_into('<Q',b,224,1048576)
  with self.assertRaisesRegex(AssertionError,'STACK'):pe_debug(File(bytes(b),p))
 def test_missing_debug(self):
  b,p=fixture();b=bytearray(b);struct.pack_into('<II',b,312,0,0)
  with self.assertRaisesRegex(AssertionError,'DEBUG'):pe_debug(File(bytes(b),p))
 def test_bad_guid(self):
  b,p=fixture();p=bytearray(p);p[1548]^=1
  with self.assertRaisesRegex(AssertionError,'PDB_GUID'):pe_debug(File(b,bytes(p)))
 def test_private_pdb_path(self):
  b,p=fixture();b=bytearray(b);b[600:609]=b'C:/x.pdb\0'
  with self.assertRaisesRegex(AssertionError,'PDB_BASENAME'):pe_debug(File(bytes(b),p))
 def test_metadata_failure_still_allows_owned_failure_cleanup(self):
  tree=ast.parse(pathlib.Path(__file__).with_name('lld_probe.py').read_text());node=next(x for x in ast.walk(tree) if isinstance(x,ast.ClassDef) and x.name=='Observed');observations=[{'metadataFailure':'Denied'}]
  class Base:
   teardown=None
   def observe(self):return []
   def finish(self,terminate=False,sampler=None,seconds=3):return {'terminated':terminate,'zeroMembers':True}
  scope={'OwnedProcess':Base,'observations':observations};exec(compile(ast.Module(body=[node],type_ignores=[]),'<owned-metadata-test>','exec'),scope);proc=scope['Observed']()
  with self.assertRaisesRegex(AssertionError,'METADATA'):proc.finish()
  self.assertEqual(proc.finish(terminate=True),{'terminated':True,'zeroMembers':True})
if __name__=='__main__':unittest.main()
