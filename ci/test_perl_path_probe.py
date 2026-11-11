import unittest,pathlib,ast
from unittest.mock import patch
import perl_path_probe as p
class ProbePolicy(unittest.TestCase):
 def test_native_recipe_is_recursive_no_compiler(self):
  mk,py=p.scripts(pathlib.Path('C:/Program Files/Python/python.exe'),pathlib.Path('D:/job space/native-hop.py'),'probe.mk')
  self.assertGreater(mk.count('\n'),4);self.assertNotIn(r'\n',mk);self.assertIn('true && "$(MAKE)"',mk);self.assertIn('inner:',mk);self.assertIn('subprocess.run',py);self.assertIn('hexdigest()',py);self.assertNotIn('EXPECTED_LIB',py)
  for text in ('cargo ','rustc ','clang','cl.exe','Configure\"'):self.assertNotIn(text,mk+py)
 def test_native_path_scope_and_spaces(self):self.assertEqual(p.safe_native(pathlib.Path('D:/job space/file.py')),'D:/job space/file.py')
 def test_unsafe_native_paths_rejected(self):
  for text in ('relative/file.py','D:/job/../file.py','D:/job/x;bad','D:/job/$bad','D:/job/"bad'):
   with self.subTest(text=text),self.assertRaises(AssertionError):p.safe_native(pathlib.Path(text))
 def test_exact_make_and_perl_pins(self):
  self.assertEqual(p.MAKE_BYTES,300184);self.assertEqual(p.MAKE_SHA,'246668acaeb0308cdf80215e21ad2bb2600df6f01363ecb3bc10b042b3c16662');self.assertEqual(p.PERL_SHA,'c0e2fb0e8be3962cdc7aa1391f104df6502191029ec15977a37623afb32c7b36')
 def test_qualification_requires_fixed_and_negative_evidence(self):
  import inspect
  text=inspect.getsource(p.qualify);self.assertIn('BASELINE_CONVERSION_NOT_REPRODUCED',text);self.assertIn('FIXED_NESTED_MODULE_RESOLUTION_FAILED',text);self.assertIn('capture_one(ndk,make,callback=execute)',text);self.assertIn('PROBE_MAKE_PIN',text);self.assertIn('PROBE_PERL_PIN',text)
 def test_module_has_no_download_or_install(self):
  import inspect
  text=inspect.getsource(p);tree=ast.parse(text);names={a.name for n in ast.walk(tree) if isinstance(n,ast.Import) for a in n.names};self.assertFalse(names&{'urllib','requests','ssl'});self.assertNotIn('pip install',text)
 def test_bad_make_pin_stops_before_any_command(self):
  import types,build_guard
  guard=types.SimpleNamespace(_resource_sample=lambda:None,run=lambda *a,**k:self.fail('UNEXPECTED_COMMAND'))
  with patch.object(pathlib.Path,'read_text',return_value='Pkg.Revision = 30.0.16248370'),patch.object(build_guard,'executable_snapshot',return_value={'sha256':'0'*64,'bytes':p.MAKE_BYTES}):
   with self.assertRaisesRegex(AssertionError,'PROBE_MAKE_PIN'):p.qualify(guard,{},pathlib.Path('D:/fixture/work'),pathlib.Path('D:/fixture/out'),pathlib.Path('C:/Git/perl.exe'),pathlib.Path('C:/SDK/ndk'))
 def test_bad_perl_pin_stops_before_any_command(self):
  import types,build_guard
  guard=types.SimpleNamespace(_resource_sample=lambda:None,run=lambda *a,**k:self.fail('UNEXPECTED_COMMAND'))
  with patch.object(pathlib.Path,'read_text',return_value='Pkg.Revision = 30.0.16248370'),patch.object(build_guard,'executable_snapshot',side_effect=[{'sha256':p.MAKE_SHA,'bytes':p.MAKE_BYTES},{'sha256':'0'*64}]):
   with self.assertRaisesRegex(AssertionError,'PROBE_PERL_PIN'):p.qualify(guard,{},pathlib.Path('D:/fixture/work'),pathlib.Path('D:/fixture/out'),pathlib.Path('C:/Git/perl.exe'),pathlib.Path('C:/SDK/ndk'))
 def test_wrong_revision_stops_before_any_command(self):
  import types
  guard=types.SimpleNamespace(_resource_sample=lambda:None,run=lambda *a,**k:self.fail('UNEXPECTED_COMMAND'))
  with patch.object(pathlib.Path,'read_text',return_value='Pkg.Revision = other'):
   with self.assertRaisesRegex(AssertionError,'PROBE_NDK_REVISION'):p.qualify(guard,{},pathlib.Path('D:/fixture/work'),pathlib.Path('D:/fixture/out'),pathlib.Path('C:/Git/perl.exe'),pathlib.Path('C:/SDK/ndk'))
if __name__=='__main__':unittest.main()
