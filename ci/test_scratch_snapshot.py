import pathlib,unittest,copy,types,struct
from unittest.mock import patch
from scratch_snapshot import eligible,ScratchTracker,IncompleteScratchSnapshot,directory_records
from build_guard import Guard,MIN_FREE
ROOT=pathlib.Path('D:/job/work');P=ROOT/'target/ci-test/deps/rmetaABC123'
class FakeAPI:
 def __init__(self):self.rows={};self.opened=[];self.closed=[];self.pending=False;self.allocation=4096;self.entry_hook=None;self.rename=False
 def open(self,p,share,list_directory=False):
  key=str(p);self.opened.append((key,share,list_directory))
  if key not in self.rows:self.rows[key]={'identity':[1,0,len(self.rows)+1],'created':1,'tag':0,'attributes':16}
  return key
 def info(self,h):return copy.deepcopy(self.rows[h])
 def standard(self,h):return {'deletePending':self.pending,'directory':True,'allocationBytes':self.allocation}
 def entries(self,h):
  if self.entry_hook:return self.entry_hook(h)
  return [{'name':'lib.rmeta','attributes':0,'size':100,'fileId':1}]
 def final_name(self,h):return pathlib.PureWindowsPath(P.with_name('renamed') if self.rename else h)
 def close(self,h):self.closed.append(h)
def gone(path=P):
 e=FileNotFoundError(2,'synthetic vanished',str(path));e.winerror=3;return e
class ScratchProof(unittest.TestCase):
 def test_exact_scope(self):self.assertTrue(eligible(ROOT,P));self.assertTrue(eligible(ROOT,ROOT/'target/aarch64-linux-android/ci-test/deps/rmetaABC123'))
 def test_other_scope_rejected(self):
  for p in (ROOT/'profile/rmetaABC123',ROOT/'target/ci-test/deps/otherABC123',ROOT/'target/ci-test/deps/rmetaX',pathlib.Path('C:/outside/rmetaABC123')):self.assertFalse(eligible(ROOT,p))
 def test_counts_handle_metadata_and_all_files(self):
  api=FakeAPI()
  with ScratchTracker(ROOT,{}, {},api) as t:self.assertEqual(t.scan(P,0),4196)
  self.assertEqual(len(api.closed),len(api.opened));self.assertEqual(api.opened[-1][1:],(7,True));self.assertTrue(all(s==1 and not listing for _,s,listing in api.opened[:-1]))
 def test_confirmed_delete_is_incomplete_not_zero(self):
  api=FakeAPI();api.pending=True
  with ScratchTracker(ROOT,{}, {},api) as t:
   with self.assertRaises(IncompleteScratchSnapshot) as c:t.scan(P,123)
   self.assertEqual(c.exception.partial_bytes,123);self.assertEqual(c.exception.allocation_bytes,4096)
 def test_missing_before_verification_is_fatal(self):
  api=FakeAPI();api.open=lambda *args:(_ for _ in ()).throw(gone())
  with ScratchTracker(ROOT,{}, {},api) as t:
   with self.assertRaises(FileNotFoundError):t.scan(P,0)
 def test_permission_is_not_retried(self):
  api=FakeAPI();api.entry_hook=lambda h:(_ for _ in ()).throw(PermissionError(5,'synthetic denied'))
  with ScratchTracker(ROOT,{}, {},api) as t:
   with self.assertRaises(PermissionError):t.scan(P,0)
 def test_missing_but_not_pending_is_fatal(self):
  api=FakeAPI();api.entry_hook=lambda h:(_ for _ in ()).throw(gone())
  with ScratchTracker(ROOT,{}, {},api) as t:
   with self.assertRaisesRegex(AssertionError,'NOT_CONFIRMED_DELETE'):t.scan(P,0)
 def test_missing_with_verified_delete_is_incomplete(self):
  api=FakeAPI()
  def entry(h):api.pending=True;raise gone()
  api.entry_hook=entry
  with ScratchTracker(ROOT,{}, {},api) as t:
   with self.assertRaises(IncompleteScratchSnapshot):t.scan(P,100)
 def test_changed_entry_identity_fatal(self):
  api=FakeAPI()
  def entry(h):api.rows[h]['identity'][-1]+=1;return []
  api.entry_hook=entry
  with ScratchTracker(ROOT,{}, {},api) as t:
   with self.assertRaisesRegex(AssertionError,'IDENTITY_RACE'):t.scan(P,0)
 def test_parent_identity_race_fatal(self):
  api=FakeAPI()
  def entry(h):api.rows[str(P.parent)]['identity'][-1]+=1;return []
  api.entry_hook=entry
  with ScratchTracker(ROOT,{}, {},api) as t:
   with self.assertRaisesRegex(AssertionError,'PARENT_IDENTITY_RACE'):t.scan(P,0)
 def test_reparse_entry_fatal(self):
  api=FakeAPI()
  def entry(h):api.rows[h]['tag']=0xa0000003;return []
  api.entry_hook=entry
  with ScratchTracker(ROOT,{}, {},api) as t:
   with self.assertRaises(AssertionError):t.scan(P,0)
 def test_unknown_child_reparse_fatal(self):
  api=FakeAPI();api.entry_hook=lambda h:[{'name':'unknown','attributes':0x400,'size':0,'fileId':1}]
  with ScratchTracker(ROOT,{}, {},api) as t:
   with self.assertRaises(AssertionError):t.scan(P,0)
 def test_unknown_child_directory_fatal(self):
  api=FakeAPI();api.entry_hook=lambda h:[{'name':'child','attributes':16,'size':0,'fileId':1}]
  with ScratchTracker(ROOT,{}, {},api) as t:
   with self.assertRaises(AssertionError):t.scan(P,0)
 def test_rename_fatal(self):
  api=FakeAPI();api.rename=True
  with ScratchTracker(ROOT,{}, {},api) as t:
   with self.assertRaisesRegex(AssertionError,'RENAMED'):t.scan(P,0)
 def test_replacement_next_scan_fatal(self):
  api=FakeAPI();baseline={};parents={}
  with ScratchTracker(ROOT,baseline,parents,api) as t:t.scan(P,0)
  api.rows[str(P)]['identity'][-1]+=1
  with ScratchTracker(ROOT,baseline,parents,api) as t:
   with self.assertRaisesRegex(AssertionError,'REPLACED'):t.scan(P,0)
class BinaryMetadata(unittest.TestCase):
 def raw(self,name='lib.rmeta',size=100,attrs=0):
  encoded=name.encode('utf-16-le');b=bytearray(104+len(encoded));struct.pack_into('<qII',b,40,size,0,0);struct.pack_into('<II',b,56,attrs,len(encoded));struct.pack_into('<Q',b,96,7);b[104:]=encoded;return b
 def test_record_fields(self):self.assertEqual(directory_records(self.raw())[0],{'name':'lib.rmeta','size':100,'attributes':0,'fileId':7})
 def test_bad_length(self):
  with self.assertRaises(AssertionError):directory_records(self.raw()[:-1])
 def test_unsafe_name(self):
  with self.assertRaises(AssertionError):directory_records(self.raw('../outside'))
 def test_negative_size(self):
  with self.assertRaises(AssertionError):directory_records(self.raw(size=-1))
 def test_next_offset_loop(self):
  b=self.raw();struct.pack_into('<I',b,0,8)
  with self.assertRaises(AssertionError):directory_records(b)
class SnapshotRetry(unittest.TestCase):
 def guard(self):
  g=object.__new__(Guard);g.root=ROOT;g.start=0;g.peak=100;g.snapshot_incomplete=0;g.last_completed_bytes=None;g.last_snapshot_complete=False;g.alias_failure=None;return g
 def test_incomplete_then_complete_preserves_peak(self):
  g=self.guard()
  with patch.object(g,'size',side_effect=[IncompleteScratchSnapshot('target/ci-test/deps/rmetaABC123',[1,2,3],200,4096),50]),patch('build_guard.time.monotonic',return_value=1),patch('build_guard.shutil.disk_usage',return_value=types.SimpleNamespace(free=MIN_FREE+1)):
   elapsed,used=g.check()
  self.assertEqual(used,50);self.assertEqual(g.peak,4296);self.assertEqual(g.snapshot_incomplete,1);self.assertTrue(g.last_snapshot_complete)
 def test_three_incomplete_scans_fail_without_total(self):
  g=self.guard()
  with patch.object(g,'size',side_effect=lambda:(_ for _ in ()).throw(IncompleteScratchSnapshot('target/ci-test/deps/rmetaABC123',[1,2,3],1,4096))),patch('build_guard.time.monotonic',return_value=1),patch('build_guard.shutil.disk_usage',return_value=types.SimpleNamespace(free=MIN_FREE+1)):
   with self.assertRaisesRegex(AssertionError,'INCOMPLETE_SNAPSHOT_RETRY_BOUND'):g.check()
  self.assertIsNone(g.last_completed_bytes);self.assertFalse(g.last_snapshot_complete);self.assertIsNotNone(g.alias_failure)
 def test_free_guard_applies_between_attempts(self):
  g=self.guard()
  with patch.object(g,'size',side_effect=IncompleteScratchSnapshot('x',[1,2,3],1,1)),patch('build_guard.time.monotonic',return_value=1),patch('build_guard.shutil.disk_usage',side_effect=[types.SimpleNamespace(free=MIN_FREE+1),types.SimpleNamespace(free=MIN_FREE-1)]):
   with self.assertRaisesRegex(AssertionError,'FREE_SPACE_GUARD'):g.check()
 def test_permission_not_retried(self):
  g=self.guard()
  with patch.object(g,'size',side_effect=PermissionError(5,'synthetic denied')) as size,patch('build_guard.time.monotonic',return_value=1),patch('build_guard.shutil.disk_usage',return_value=types.SimpleNamespace(free=MIN_FREE+1)):
   with self.assertRaises(PermissionError):g.check()
   self.assertEqual(size.call_count,1)
class ProductionWalker(unittest.TestCase):
 def test_scratch_counted_via_handle_and_pruned_from_walk(self):
  from test_alias_accounting import guard
  g=guard();api=FakeAPI()
  def walk(root,followlinks,onerror):
   dirs=[P.name];yield str(P.parent),dirs,[];self.assertNotIn(P.name,dirs,'SCRATCH_PATH_WAS_TRAVERSED')
  with patch('scratch_snapshot.MetadataAPI',return_value=api),patch('build_guard.os.walk',walk),patch.object(pathlib.Path,'exists',lambda p:True),patch.object(pathlib.Path,'is_symlink',lambda p:False),patch.object(pathlib.Path,'is_junction',lambda p:False):
   self.assertEqual(g._walk(None),4196)
  self.assertEqual(len(api.closed),len(api.opened))
if __name__=='__main__':unittest.main()
