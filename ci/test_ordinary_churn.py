"""Whole-snapshot invalidation tests using the actual walker and held-parent implementation."""
import unittest,pathlib,types,stat
from unittest.mock import patch
from build_guard import Guard,OrdinaryScratchChurn,qualified_ordinary_churn,compiler_scratch_root,MIN_FREE
from scratch_snapshot import ScratchTracker
from test_scratch_snapshot import FakeAPI,P,ROOT
from test_alias_accounting import guard
def absent(code=2):
 e=FileNotFoundError(code,'synthetic disappearance');e.winerror=code;return e
def meta(link=False):
 return types.SimpleNamespace(st_size=10,st_mode=stat.S_IFREG,st_file_attributes=0x400 if link else 0,st_reparse_tag=0xa0000003 if link else 0)
O=P.parent/'pem.abcdef-cgu.0.rcgu.o'
class Scope(unittest.TestCase):
 def test_exact_observed_shape(self):self.assertTrue(qualified_ordinary_churn(ROOT,O,absent()))
 def test_path_missing_not_file_missing_fatal(self):self.assertFalse(qualified_ordinary_churn(ROOT,O,absent(3)))
 def test_no_windows_identity_fatal(self):self.assertFalse(qualified_ordinary_churn(ROOT,O,FileNotFoundError(2,'synthetic')))
 def test_permission_not_churn(self):self.assertFalse(qualified_ordinary_churn(ROOT,O,PermissionError(5,'synthetic')))
 def test_unknown_extension_not_churn(self):self.assertFalse(qualified_ordinary_churn(ROOT,O.with_suffix('.bin'),absent()))
 def test_nested_or_outside_not_churn(self):
  self.assertFalse(qualified_ordinary_churn(ROOT,O.parent/'child'/O.name,absent()));self.assertFalse(qualified_ordinary_churn(ROOT,ROOT/'outside'/O.name,absent()))
class ActualCombinedWalker(unittest.TestCase):
 def run_walk(self,mode='delete'):
  g=guard();g.peak=1000;api=FakeAPI();scans=[0]
  def walk(root,followlinks,onerror):
   scans[0]+=1
   yield str(O.parent),[],['kept.bin',O.name] if scans[0]==1 or mode!='delete' else ['kept.bin']
  def metadata(p):
   if p==O:
    if scans[0]==1:raise absent()
    if mode=='link':return meta(True)
   return meta()
  with patch('scratch_snapshot.MetadataAPI',return_value=api),patch('build_guard.os.walk',walk),patch('build_guard.os.lstat',metadata),patch.object(pathlib.Path,'exists',return_value=True),patch.object(pathlib.Path,'is_symlink',return_value=False),patch.object(pathlib.Path,'is_junction',return_value=False),patch.object(g,'_leased_pass',return_value=None):
   result=g.size()
  return g,result,scans[0],api
 def test_delete_discards_full_pass_then_recounts(self):
  g,result,scans,api=self.run_walk()
  self.assertEqual(result,10);self.assertEqual(scans,2);self.assertEqual(g.peak,1000);self.assertEqual(g.ordinary_churn_count,1)
  self.assertIsNone(g.recent_churn[0]['unmeasuredResidualBytes']);self.assertFalse(g.recent_churn[0]['completedTotalReported'])
  self.assertEqual(g.recent_churn[0]['confirmedPartialBytes'],10);self.assertFalse(g.recent_churn[0]['discardedRootScans'][0]['complete'])
  self.assertTrue(all(entry[1]==1 for entry in api.opened));self.assertEqual(len(api.opened),len(api.closed))
 def test_replacement_to_link_is_fatal(self):
  with self.assertRaisesRegex(AssertionError,'UNQUALIFIED_OUTPUT_FILE_JUNCTION'):self.run_walk('link')
 def test_regular_replacement_is_fully_counted_not_excluded(self):
  g,result,scans,api=self.run_walk('regular');self.assertEqual(result,20);self.assertEqual(scans,2)
class ParentIdentity(unittest.TestCase):
 def test_root_replacement_between_passes_fatal(self):
  api=FakeAPI();parents={}
  with ScratchTracker(ROOT,{},parents,api) as t:t.lease_parent(O.parent)
  api.rows[str(O.parent)]['identity'][-1]+=1
  with ScratchTracker(ROOT,{},parents,api) as t:
   with self.assertRaisesRegex(AssertionError,'SCRATCH_PARENT_REPLACED'):t.lease_parent(O.parent)
 def test_ancestor_changed_while_held_fatal(self):
  api=FakeAPI()
  with ScratchTracker(ROOT,{}, {},api) as t:
   t.lease_parent(O.parent);api.rows[str(O.parent.parent)]['tag']=0xa0000003
   with self.assertRaises(AssertionError):t.verify_parents()
 def test_parent_denial_never_churn(self):
  api=FakeAPI()
  def denied(path,share,list_directory=False):raise PermissionError(5,'synthetic denied')
  api.open=denied
  with ScratchTracker(ROOT,{}, {},api) as t:
   with self.assertRaises(PermissionError):t.lease_parent(O.parent)
class BoundedWindow(unittest.TestCase):
 def g(self):
  g=guard();del g._enumeration_resources;g.start=0;g.peak=1000;return g
 def test_repeated_churn_three_attempts_no_total(self):
  g=self.g()
  with patch.object(g,'_size_once',side_effect=OrdinaryScratchChurn('target/ci-test/deps/a.rcgu.o',50)) as call,patch('build_guard.time.monotonic',return_value=1),patch('build_guard.shutil.disk_usage',return_value=types.SimpleNamespace(free=MIN_FREE+1)):
   with self.assertRaisesRegex(AssertionError,'ORDINARY_CHURN_RESCAN_BOUND'):g.size()
  self.assertEqual(call.call_count,3);self.assertFalse(g.last_snapshot_complete);self.assertEqual(g.peak,1000);self.assertIsNone(g.snapshot_deadline)
 def test_same_window_expires_without_renewal(self):
  g=self.g();clock=[10]
  def churn():clock[0]+=6;raise OrdinaryScratchChurn('target/ci-test/deps/a.rcgu.o',50)
  with patch.object(g,'_size_once',side_effect=churn) as call,patch('build_guard.time.monotonic',side_effect=lambda:clock[0]),patch('build_guard.shutil.disk_usage',return_value=types.SimpleNamespace(free=MIN_FREE+1)):
   with self.assertRaisesRegex(AssertionError,'SNAPSHOT_VALIDATION_DEADLINE'):g.size()
  self.assertEqual(call.call_count,1);self.assertIn('SNAPSHOT_VALIDATION_DEADLINE',g.alias_failure)
 def test_final_validation_must_finish_in_original_window(self):
  g=self.g();clock=[10]
  def slow():clock[0]+=6;return 10
  with patch.object(g,'_size_once',side_effect=slow),patch('build_guard.time.monotonic',side_effect=lambda:clock[0]),patch('build_guard.shutil.disk_usage',return_value=types.SimpleNamespace(free=MIN_FREE+1)):
   with self.assertRaisesRegex(AssertionError,'SNAPSHOT_VALIDATION_DEADLINE'):g.size()
  self.assertIsNone(g.snapshot_deadline);self.assertIn('SNAPSHOT_VALIDATION_DEADLINE',g.alias_failure)
 def test_free_floor_between_rejected_and_retry(self):
  g=self.g()
  with patch.object(g,'_size_once',side_effect=OrdinaryScratchChurn('target/ci-test/deps/a.rcgu.o',50)) as call,patch('build_guard.time.monotonic',return_value=1),patch('build_guard.shutil.disk_usage',side_effect=[types.SimpleNamespace(free=MIN_FREE+1),types.SimpleNamespace(free=MIN_FREE-1)]):
   with self.assertRaisesRegex(AssertionError,'FREE_SPACE_GUARD'):g.size()
  self.assertEqual(call.call_count,1)
 def test_denial_not_retried(self):
  g=self.g()
  with patch.object(g,'_size_once',side_effect=PermissionError(5,'synthetic')) as call,patch('build_guard.time.monotonic',return_value=1),patch('build_guard.shutil.disk_usage',return_value=types.SimpleNamespace(free=MIN_FREE+1)):
   with self.assertRaises(PermissionError):g.size()
  self.assertEqual(call.call_count,1);self.assertIsNotNone(g.alias_failure)
if __name__=='__main__':unittest.main()
