import unittest
from lock_diagnostic import lock_delta,resolve_link,allowed_cargo
class DiagnosticPolicy(unittest.TestCase):
 def test_native_commands_denied(self):
  for verb in ('build','test','check','run','install'):self.assertFalse(allowed_cargo([verb]))
 def test_metadata_locked_only(self):
  self.assertTrue(allowed_cargo(['metadata','--locked','--format-version','1']));self.assertFalse(allowed_cargo(['metadata']))
 def test_proposal_offline_workspace_only(self):
  self.assertTrue(allowed_cargo(['update','--workspace','--offline']));self.assertFalse(allowed_cargo(['update']))
 def test_equal_pins(self):
  d={'package':[{'name':'a','version':'1','source':'registry+https://example.invalid','checksum':'a','dependencies':['b']}]};self.assertTrue(lock_delta(d,d)['externalIdentitiesAndChecksumsUnchanged'])
 def test_local_edge_delta_no_external_upgrade(self):
  a={'package':[{'name':'local','version':'0','dependencies':['a']}]};b={'package':[{'name':'local','version':'0','dependencies':['a','b']}]};r=lock_delta(a,b);self.assertTrue(r['externalIdentitiesAndChecksumsUnchanged']);self.assertEqual(len(r['changedEntries']),1)
 def test_version_change_detected(self):
  a={'package':[{'name':'a','version':'1','source':'registry+https://example.invalid','checksum':'a'}]};b={'package':[{'name':'a','version':'2','source':'registry+https://example.invalid','checksum':'b'}]};self.assertFalse(lock_delta(a,b)['externalIdentitiesAndChecksumsUnchanged'])
 def test_checksum_change_detected(self):
  a={'package':[{'name':'a','version':'1','source':'registry+https://example.invalid','checksum':'a'}]};b={'package':[{'name':'a','version':'1','source':'registry+https://example.invalid','checksum':'b'}]};self.assertFalse(lock_delta(a,b)['externalIdentitiesAndChecksumsUnchanged'])
 def test_internal_license_target(self):
  e={'sub/LICENSE':{'mode':'120000','target':'../LICENSE'},'LICENSE':{'mode':'100644','sha':'a'}};self.assertEqual(resolve_link(e,'sub/LICENSE')[0],'LICENSE')
 def test_link_escape(self):
  with self.assertRaises(AssertionError):resolve_link({'LICENSE':{'mode':'120000','target':'../outside'}},'LICENSE')
 def test_link_absolute(self):
  with self.assertRaises(AssertionError):resolve_link({'LICENSE':{'mode':'120000','target':'C:/private'}},'LICENSE')
 def test_link_cycle(self):
  with self.assertRaises(AssertionError):resolve_link({'LICENSE':{'mode':'120000','target':'LICENSE'}},'LICENSE')
if __name__=='__main__':unittest.main()

