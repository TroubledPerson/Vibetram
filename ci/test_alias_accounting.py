"""Synthetic production-walker tests; no real links, files or target traversal."""
import unittest,pathlib,copy,types
from unittest.mock import patch
from build_guard import Guard
from alias_accounting import ALIAS_METADATA_BYTES,AliasAppeared,lease_key,compare_baseline,safe_absence,disjoint_roots
from reparse_metadata import EXPECTED_ALIAS,EXPECTED_TARGET
ROOT=pathlib.Path('D:/job/work');CACHE=ROOT/'profile/AppData/Local/Microsoft/Windows/INetCache';ALIAS=CACHE/'Content.IE5';TARGET=CACHE/'IE'
def report():
 return {'state':'CAPTURED_ALIAS_AND_REGULAR_TARGET_METADATA_STOP','relativePath':EXPECTED_ALIAS,'reparseTagHex':'0xa0000003','targetClass':'INTERNAL_LEXICAL_ONLY_NOT_QUALIFIED','physicalTargetMetadataQualified':True,'targetMetadataOpenedIndependently':True,'linkTraversed':False,'physicalTargetRelative':EXPECTED_TARGET,'targetJobRelative':EXPECTED_TARGET,'physicalTargetTagHex':'0x0','fileIdentity':[1,0,4],'physicalTargetIdentity':[1,0,3],'physicalAncestorCount':3,'physicalAncestors':[{'depth':i,'identity':[1,0,i+1],'tagHex':'0x0','attributes':'0x10'} for i in range(3)],'rawRecordSHA256':'a'*64,'rawRecordBytes':392}
def guard():
 g=object.__new__(Guard);g.root=ROOT;g.work=ROOT;g.roots=[ROOT];g.env={};g.races=0;g.pending_reparse=None;g.alias_baseline=None;g.alias_last_result=None;g.alias_failure=None;g.alias_passes=0;g.alias_charged_bytes=0;g.qualified_links=set();return g
class AliasPolicy(unittest.TestCase):
 def test_valid_lease(self):self.assertIsNotNone(lease_key(report()))
 def test_external_class_fatal(self):
  r=report();r['targetClass']='EXTERNAL_TARGET_FATAL'
  with self.assertRaises(AssertionError):lease_key(r)
 def test_changed_tag_fatal(self):
  r=report();r['reparseTagHex']='0xa000000c'
  with self.assertRaises(AssertionError):lease_key(r)
 def test_different_target_fatal(self):
  r=report();r['targetJobRelative']='outside'
  with self.assertRaises(AssertionError):lease_key(r)
 def test_reparse_ancestor_fatal(self):
  r=report();r['physicalAncestors'][0]['tagHex']='0xa0000003'
  with self.assertRaises(AssertionError):lease_key(r)
 def test_external_volume_fatal(self):
  r=report();r['physicalAncestors'][1]['identity'][0]=2
  with self.assertRaises(AssertionError):lease_key(r)
 def test_target_reparse_fatal(self):
  r=report();r['physicalTargetTagHex']='0xa0000003'
  with self.assertRaises(AssertionError):lease_key(r)
 def test_replacement_fatal(self):
  a=lease_key(report());b=report();b['fileIdentity']=[1,0,8]
  with self.assertRaises(AssertionError):compare_baseline(a,lease_key(b))
 def test_regular_target_replacement_fatal(self):
  a=lease_key(report());b=report();b['physicalTargetIdentity']=[1,0,9];b['physicalAncestors'][-1]['identity']=[1,0,9]
  with self.assertRaises(AssertionError):compare_baseline(a,lease_key(b))
 def test_access_denial_is_not_absence(self):self.assertFalse(safe_absence({'state':'OS_ACCESS_DENIED_STOP','osError':5,'missingUnderOwnedRoot':True}))
 def test_owned_descendant_absence(self):self.assertTrue(safe_absence({'state':'OS_METADATA_UNAVAILABLE_STOP','osError':2,'missingUnderOwnedRoot':True,'targetOpened':False}))
 def test_missing_root_not_absence(self):self.assertFalse(safe_absence({'state':'OS_METADATA_UNAVAILABLE_STOP','osError':2,'missingUnderOwnedRoot':False}))
 def test_inaccessible_not_absence(self):self.assertFalse(safe_absence({'state':'OS_METADATA_UNAVAILABLE_STOP','osError':32,'missingUnderOwnedRoot':True}))
 def test_overlapping_roots_fatal(self):
  with self.assertRaises(AssertionError):disjoint_roots([ROOT,ROOT/'child'])
 def test_disjoint_roots(self):disjoint_roots([ROOT,pathlib.Path('D:/job/cargo')])
class ActualWalker(unittest.TestCase):
 def walk(self,g,metadata,unknown=False,reverse=False,omit_target=False):
  def mocked_walk(root,followlinks,onerror=None):
   self.assertFalse(followlinks);dirs=['Content.IE5','IE'];dirs=dirs[::-1] if reverse else dirs
   yield str(CACHE),dirs,[]
   self.assertNotIn('Content.IE5',dirs,'ALIAS_WAS_NOT_PRUNED')
   if not omit_target:
    yield str(TARGET),['unknown'] if unknown else [],['one.bin','two.bin']
  def junction(p):return p==ALIAS or unknown and p==TARGET/'unknown'
  with patch('build_guard.os.walk',mocked_walk),patch.object(pathlib.Path,'exists',lambda p:True),patch.object(pathlib.Path,'is_symlink',lambda p:False),patch.object(pathlib.Path,'is_junction',junction),patch.object(pathlib.Path,'stat',lambda p:types.SimpleNamespace(st_size=11 if p.name=='one.bin' else 17)):
   return Guard._walk(g,metadata)
 def test_counts_alias_and_target_once(self):self.assertEqual(self.walk(guard(),report()),ALIAS_METADATA_BYTES+28)
 def test_enumeration_order_does_not_duplicate_count(self):self.assertEqual(self.walk(guard(),report(),reverse=True),ALIAS_METADATA_BYTES+28)
 def test_nested_unknown_link_still_fatal(self):
  with self.assertRaisesRegex(AssertionError,'UNQUALIFIED_OUTPUT_DIRECTORY_LINK'):self.walk(guard(),report(),unknown=True)
 def test_missing_independent_target_scan_fatal(self):
  with self.assertRaises(AssertionError):self.walk(guard(),report(),omit_target=True)
 def test_new_alias_requires_qualification(self):
  with self.assertRaises(AliasAppeared):self.walk(guard(),None)
 def test_successful_lease_surrounds_actual_walk(self):
  g=guard();active=[]
  def capture(root,relative,callback=None):
   r=report();active.append(True);self.assertEqual(callback(r),ALIAS_METADATA_BYTES+28);active.pop();r.update(state='PASS_EXACT_ALIAS_LEASED_ACCOUNTING_METADATA',leasedScanCompleted=True);return r
  def walk(r):self.assertTrue(active);return self.walk(g,r)
  with patch('build_guard.capture_reparse_metadata',capture),patch.object(g,'_walk',walk):self.assertEqual(g.size(),ALIAS_METADATA_BYTES+28)
  self.assertIsNotNone(g.alias_baseline);self.assertEqual(g.alias_passes,1)
 def test_postscan_race_does_not_return_count(self):
  g=guard()
  def capture(root,relative,callback=None):
   r=report();callback(r);r.update(state='UNQUALIFIED_OR_MALFORMED_METADATA_STOP',reason='METADATA_IDENTITY_OR_TAG_RACE');return r
  with patch('build_guard.capture_reparse_metadata',capture),patch.object(g,'_walk',lambda r:123):
   with self.assertRaises(AssertionError):g.size()
  self.assertIsNotNone(g.alias_failure)
 def test_denial_latches_no_automatic_retry(self):
  g=guard()
  with patch('build_guard.capture_reparse_metadata',return_value={'state':'OS_ACCESS_DENIED_STOP','osError':5}) as mocked:
   with self.assertRaises(AssertionError):g.size()
   with self.assertRaises(AssertionError):g.size()
   self.assertEqual(mocked.call_count,1)
 def test_removed_previously_qualified_alias_fatal(self):
  g=guard();g.alias_baseline=lease_key(report())
  with patch('build_guard.capture_reparse_metadata',return_value={'state':'OS_METADATA_UNAVAILABLE_STOP','osError':2,'missingUnderOwnedRoot':True}):
   with self.assertRaises(AssertionError):g.size()
 def test_missing_registered_root_fatal(self):
  g=guard()
  with patch.object(pathlib.Path,'exists',lambda p:False),patch.object(pathlib.Path,'is_symlink',lambda p:False),patch.object(pathlib.Path,'is_junction',lambda p:False):
   with self.assertRaisesRegex(AssertionError,'ACCOUNTING_ROOT_MISSING'):Guard._walk(g,None)
 def test_inaccessible_walk_fatal(self):
  def walk(root,followlinks,onerror):
   onerror(PermissionError(5,'synthetic denied'));yield '',[],[]
  with patch('build_guard.os.walk',walk),patch.object(pathlib.Path,'exists',lambda p:True),patch.object(pathlib.Path,'is_symlink',lambda p:False),patch.object(pathlib.Path,'is_junction',lambda p:False):
   with self.assertRaises(PermissionError):Guard._walk(guard(),report())
 def test_target_file_disappearance_fatal(self):
  def walk(root,followlinks,onerror):
   dirs=['Content.IE5','IE'];yield str(CACHE),dirs,[];self.assertNotIn('Content.IE5',dirs);yield str(TARGET),[],['gone']
  def stat(p):raise FileNotFoundError('synthetic race')
  with patch('build_guard.os.walk',walk),patch.object(pathlib.Path,'exists',lambda p:True),patch.object(pathlib.Path,'is_symlink',lambda p:False),patch.object(pathlib.Path,'is_junction',lambda p:p==ALIAS),patch.object(pathlib.Path,'stat',stat):
   with self.assertRaisesRegex(AssertionError,'IE_TARGET_FILE_SNAPSHOT_RACE'):Guard._walk(guard(),report())
 def test_unknown_sibling_after_pruned_alias_fatal(self):
  def walk(root,followlinks,onerror):
   dirs=['Content.IE5','unknown','IE'];yield str(CACHE),dirs,[]
  with patch('build_guard.os.walk',walk),patch.object(pathlib.Path,'exists',lambda p:True),patch.object(pathlib.Path,'is_symlink',lambda p:False),patch.object(pathlib.Path,'is_junction',lambda p:p in (ALIAS,CACHE/'unknown')):
   with self.assertRaisesRegex(AssertionError,'UNQUALIFIED_OUTPUT_DIRECTORY_LINK'):Guard._walk(guard(),report())
if __name__=='__main__':unittest.main()
