import unittest
from runner_preflight import evaluate,REQUIRED,MIN_FREE
class PreflightPolicy(unittest.TestCase):
 def test_exact_threshold(self):self.assertTrue(evaluate(MIN_FREE,{k:True for k in REQUIRED})['qualified'])
 def test_low_disk(self):self.assertFalse(evaluate(MIN_FREE-1,{k:True for k in REQUIRED})['qualified'])
 def test_each_missing_tool(self):
  for key in REQUIRED:
   with self.subTest(key=key):
    tools={k:True for k in REQUIRED};tools[key]=False;self.assertFalse(evaluate(MIN_FREE,tools)['qualified'])
 def test_missing_field(self):self.assertFalse(evaluate(MIN_FREE,{})['qualified'])
 def test_nonboolean_tool(self):self.assertFalse(evaluate(MIN_FREE,{k:'true' for k in REQUIRED})['qualified'])
 def test_invalid_disk(self):
  for value in (None,True,-1,'large'):self.assertFalse(evaluate(value,{k:True for k in REQUIRED})['qualified'])
if __name__=='__main__':unittest.main()
