"""Synthetic tests for the actual fresh-entry walker; no external links or compiler."""
import unittest,pathlib,types,stat,time
from unittest.mock import patch
from build_guard import Guard,fresh_entry,MIN_FREE
from test_alias_accounting import guard,ROOT
def meta(size=3,mode=stat.S_IFREG,attrs=0,tag=0):
 return types.SimpleNamespace(st_size=size,st_mode=mode,st_file_attributes=attrs,st_reparse_tag=tag)
class FreshMetadata(unittest.TestCase):
 def test_exactly_one_fresh_nofollow_call(self):
  with patch('build_guard.os.lstat',return_value=meta()) as call:self.assertEqual(fresh_entry(ROOT/'a').st_size,3);call.assert_called_once_with(ROOT/'a')
 def test_permission_fatal(self):
  with patch('build_guard.os.lstat',side_effect=PermissionError(5,'synthetic')):
   with self.assertRaises(PermissionError):fresh_entry(ROOT/'a')
 def test_missing_fatal(self):
  with patch('build_guard.os.lstat',side_effect=FileNotFoundError()):
   with self.assertRaises(FileNotFoundError):fresh_entry(ROOT/'a')
 def test_negative_size_fatal(self):
  with patch('build_guard.os.lstat',return_value=meta(-1)):
   with self.assertRaises(AssertionError):fresh_entry(ROOT/'a')
 def test_missing_attribute_fatal(self):
  with patch('build_guard.os.lstat',return_value=types.SimpleNamespace(st_size=1)):
   with self.assertRaises(AttributeError):fresh_entry(ROOT/'a')
class ActualWalker(unittest.TestCase):
 def walk(self,g,n=300,metadata=None):
  def walk(root,followlinks,onerror):
   self.assertFalse(followlinks);yield str(root),[],['f%d'%i for i in range(n)]
  with patch('build_guard.os.walk',walk),patch('build_guard.os.lstat',side_effect=metadata or (lambda p:meta())),patch.object(pathlib.Path,'exists',return_value=True),patch.object(pathlib.Path,'is_symlink',return_value=False),patch.object(pathlib.Path,'is_junction',return_value=False):
   return g._walk(None)
 def test_exact_counts_telemetry_and_one_call_each(self):
  g=guard();calls=[]
  self.assertEqual(self.walk(g,metadata=lambda p:(calls.append(p) or meta())),900)
  self.assertEqual(len(calls),300);self.assertEqual(g.root_scans[0]['ordinaryFileEntries'],300);self.assertTrue(g.root_scans[0]['complete']);self.assertEqual(g.root_scans[0]['completedRootBytes'],900);self.assertGreaterEqual(g.root_scans[0]['seconds'],0)
 def test_unknown_reparse_fatal(self):
  with self.assertRaises(AssertionError):self.walk(guard(),1,lambda p:meta(attrs=0x400,tag=0x123))
 def test_unexpected_regular_tag_fatal(self):
  with self.assertRaises(AssertionError):self.walk(guard(),1,lambda p:meta(tag=0x123))
 def test_unknown_file_type_fatal(self):
  with self.assertRaises(AssertionError):self.walk(guard(),1,lambda p:meta(mode=stat.S_IFIFO))
 def test_changed_file_to_directory_fatal(self):
  with self.assertRaises(AssertionError):self.walk(guard(),1,lambda p:meta(mode=stat.S_IFDIR,attrs=16))
 def test_unqualified_symlink_fatal(self):
  g=guard();g.env['CARGO_HOME']=ROOT/'cargo'
  with self.assertRaisesRegex(AssertionError,'OUTPUT_LINK_OUTSIDE_PINNED_CACHE'):self.walk(g,1,lambda p:meta(mode=stat.S_IFLNK,attrs=0x400,tag=0xa000000c))
 def test_missing_is_not_zero(self):
  g=guard()
  with self.assertRaisesRegex(AssertionError,'UNVERIFIED_FILE_DISAPPEARANCE'):self.walk(g,1,lambda p:(_ for _ in ()).throw(FileNotFoundError()))
  self.assertFalse(g.root_scans[0]['complete']);self.assertIsNone(g.root_scans[0]['completedRootBytes'])
 def test_denial_retains_partial_no_completed_total(self):
  g=guard();counter=[0]
  def m(p):
   counter[0]+=1
   if counter[0]==2:raise PermissionError(5,'synthetic')
   return meta()
  with self.assertRaises(PermissionError):self.walk(g,3,m)
  self.assertFalse(g.root_scans[0]['complete']);self.assertEqual(g.root_scans[0]['confirmedPartialRootBytes'],3);self.assertIsNone(g.root_scans[0]['completedRootBytes'])
 def test_free_floor_enforced_during_enumeration(self):
  g=guard();del g._enumeration_resources
  with patch('build_guard.shutil.disk_usage',side_effect=[types.SimpleNamespace(free=MIN_FREE+1),types.SimpleNamespace(free=MIN_FREE-1)]):
   with self.assertRaisesRegex(AssertionError,'FREE_SPACE_GUARD'):self.walk(g)
  self.assertEqual(g.root_scans[0]['ordinaryFileEntries'],256);self.assertFalse(g.root_scans[0]['complete']);self.assertEqual(g.peak,768)
 def test_time_interval_enforces_check_below_entry_bound(self):
  g=guard();checks=[];g._enumeration_resources=lambda n:checks.append(n)
  with patch('build_guard.time.monotonic',side_effect=lambda:time.perf_counter()*100000):
   self.assertEqual(self.walk(g,3),9)
  self.assertGreater(len(checks),2)
 def test_global_time_guard_still_fatal(self):
  g=guard();del g._enumeration_resources;g.start=-100000
  with patch('build_guard.shutil.disk_usage',return_value=types.SimpleNamespace(free=MIN_FREE+1)):
   with self.assertRaisesRegex(AssertionError,'TRIAL_DEADLINE'):self.walk(g,1)
if __name__=='__main__':unittest.main()
