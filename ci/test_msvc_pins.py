import unittest,copy
from msvc_pins import read_pins,tool_pins,rust_pin
class QualifiedPins(unittest.TestCase):
 def setUp(self):
  self.p=read_pins();self.a={k:self.p[k] for k in ('toolset','sdkVersion','setupSHA256','libraryInputs')};self.a['vswhereIdentity']=self.p['tools'][:1];self.a['toolIdentities']=self.p['tools'][1:]
 def test_exact_qualified_tools(self):tool_pins(self.p,self.a)
 def test_changed_executable_rejected(self):
  a=copy.deepcopy(self.a);a['toolIdentities'][0]['sha256']='0'*64
  with self.assertRaises(AssertionError):tool_pins(self.p,a)
 def test_changed_sdk_rejected(self):
  a=copy.deepcopy(self.a);a['sdkVersion']='10.0.99999.0'
  with self.assertRaises(AssertionError):tool_pins(self.p,a)
 def test_changed_setup_rejected(self):
  a=copy.deepcopy(self.a);a['setupSHA256']='0'*64
  with self.assertRaises(AssertionError):tool_pins(self.p,a)
 def test_changed_library_rejected(self):
  a=copy.deepcopy(self.a);a['libraryInputs'][0]['sha256']='0'*64
  with self.assertRaises(AssertionError):tool_pins(self.p,a)
 def test_duplicate_tool_rejected(self):
  a=copy.deepcopy(self.a);a['toolIdentities'].append(a['toolIdentities'][0])
  with self.assertRaises(AssertionError):tool_pins(self.p,a)
 def test_exact_rust(self):rust_pin(self.p,self.p['rustVersion'])
 def test_other_rust_rejected(self):
  with self.assertRaises(AssertionError):rust_pin(self.p,'rustc 1.95.0 (other)')
if __name__=='__main__':unittest.main()
