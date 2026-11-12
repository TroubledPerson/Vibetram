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
  g=object.__new__(Guard);g.root=ROOT;g.start=0;g.peak=100;g.snapshot_incomplete=0;g.last_completed_bytes=None;g.last_snapshot_complete=False;g.alias_failure=None;g.recent_churn=[];return g
 def test_incomplete_then_complete_preserves_peak(self):
  g=self.guard()
  with patch.object(g,'_size_once',side_effect=[IncompleteScratchSnapshot('target/ci-test/deps/rmetaABC123',[1,2,3],200,4096),50]),patch('build_guard.time.monotonic',return_value=1),patch('build_guard.shutil.disk_usage',return_value=types.SimpleNamespace(free=MIN_FREE+1)):
   used=g.scan_epoch(31)
  self.assertEqual(used,50);self.assertEqual(g.peak,4296);self.assertEqual(g.snapshot_incomplete,1);self.assertFalse(g.last_snapshot_complete)
 def test_two_incomplete_scans_fail_without_total(self):
  g=self.guard()
  with patch.object(g,'_size_once',side_effect=lambda:(_ for _ in ()).throw(IncompleteScratchSnapshot('target/ci-test/deps/rmetaABC123',[1,2,3],1,4096))),patch('build_guard.time.monotonic',return_value=1),patch('build_guard.shutil.disk_usage',return_value=types.SimpleNamespace(free=MIN_FREE+1)):
   with self.assertRaisesRegex(AssertionError,'CENSUS_TWO_ATTEMPTS_EXHAUSTED'):g.scan_epoch(31)
  self.assertIsNone(g.last_completed_bytes);self.assertFalse(g.last_snapshot_complete);self.assertEqual(g.snapshot_incomplete,2)
 def test_free_guard_applies_between_attempts(self):
  g=self.guard()
  with patch.object(g,'_size_once',side_effect=IncompleteScratchSnapshot('x',[1,2,3],1,1)),patch('build_guard.time.monotonic',return_value=1),patch('build_guard.shutil.disk_usage',side_effect=[types.SimpleNamespace(free=MIN_FREE+1),types.SimpleNamespace(free=MIN_FREE-1)]):
   with self.assertRaisesRegex(AssertionError,'FREE_SPACE_GUARD'):g.scan_epoch(31)
 def test_permission_not_retried(self):
  g=self.guard()
  with patch.object(g,'_size_once',side_effect=PermissionError(5,'synthetic denied')) as size,patch('build_guard.time.monotonic',return_value=1),patch('build_guard.shutil.disk_usage',return_value=types.SimpleNamespace(free=MIN_FREE+1)):
   with self.assertRaises(PermissionError):g.scan_epoch(31)
   self.assertEqual(size.call_count,1)
class ProductionWalker(unittest.TestCase):
 def test_scratch_counted_via_handle_and_pruned_from_walk(self):
  from test_alias_accounting import guard,fake_metadata
  g=guard();api=FakeAPI()
  def walk(root,followlinks,onerror):
   dirs=[P.name];yield str(P.parent),dirs,[];self.assertNotIn(P.name,dirs,'SCRATCH_PATH_WAS_TRAVERSED')
  with patch('scratch_snapshot.MetadataAPI',return_value=api),patch('build_guard.os.lstat',fake_metadata),patch('build_guard.os.walk',walk),patch.object(pathlib.Path,'exists',lambda p:True),patch.object(pathlib.Path,'is_symlink',lambda p:False),patch.object(pathlib.Path,'is_junction',lambda p:False):
   self.assertEqual(g._walk(None),4196)
  self.assertEqual(len(api.closed),len(api.opened))

class LifecycleAPI(FakeAPI):
 def __init__(self,mode='count'):
  super().__init__();self.mode=mode;self.leaf_info=0;self.close_attempts=[]
 def open(self,path,share,list_directory=False):
  if pathlib.Path(path)==P and self.mode=='open-missing':
   e=FileNotFoundError(2,'synthetic');e.winerror=2;raise e
  if pathlib.Path(path)==P.parent and self.mode=='parent-denied':raise PermissionError(13,'synthetic')
  return super().open(path,share,list_directory)
 def info(self,h):
  if h==str(P):
   self.leaf_info+=1
   if self.mode=='prior-info-missing' and self.leaf_info==1 or self.mode=='confirm-info-missing' and self.pending:
    e=FileNotFoundError(2,'synthetic');e.winerror=2;raise e
   if self.mode=='confirm-denied' and self.pending:raise PermissionError(13,'synthetic')
   if self.mode=='leaf-reparse':self.rows[h]['tag']=0xa0000003;self.rows[h]['attributes']=0x410
  return super().info(h)
 def entries(self,h):
  if self.mode in ('delete','repeated','confirm-info-missing','confirm-denied','not-pending','identity-changed','parent-changed','parent-reparse','cleanup-delete'):
   self.pending=self.mode!='not-pending'
   if self.mode=='identity-changed':self.rows[str(P)]['identity'][-1]+=1
   if self.mode=='parent-changed':self.rows[str(P.parent)]['identity'][-1]+=1
   if self.mode=='parent-reparse':self.rows[str(P.parent)]['tag']=0xa0000003
   e=FileNotFoundError(2,'synthetic');e.winerror=2;raise e
  return super().entries(h)
 def final_name(self,h):
  if h==str(P) and self.mode=='final-name-delete':
   self.pending=True;e=FileNotFoundError(2,'synthetic');e.winerror=2;raise e
  if h==str(P) and self.mode=='rename':return pathlib.PureWindowsPath(P.with_name('renamed'))
  return super().final_name(h)
 def close(self,h):
  self.close_attempts.append(h)
  if self.mode in ('cleanup','cleanup-delete'):raise PermissionError(13,'synthetic')
  super().close(h)
class IntegratedDirectoryLifecycle(unittest.TestCase):
 def run_scan(self,mode='count',mutate=None):
  from test_alias_accounting import guard,fake_metadata
  g=guard();g.last_completed_bytes=None;g.last_snapshot_complete=False;g.snapshot_incomplete=0;g.ordinary_churn_count=0;g.recent_churn=[];g.peak=1;apis=[];walks=[0]
  def factory():a=LifecycleAPI(mode);apis.append(a);return a
  def walk(root,followlinks,onerror):
   walks[0]+=1;dirs=[] if mode in ('delete','final-name-delete') and walks[0]>1 else [P.name]
   yield str(P.parent),dirs,['one.bin']
   if dirs:self.assertNotIn(P.name,dirs,'QUALIFIED_LEAF_MUST_NOT_BE_PATH_TRAVERSED')
  def metadata(p):
   self.assertNotEqual(p,P,'REDUNDANT_LEAF_PATH_LOOKUP_REINTRODUCED')
   return fake_metadata(p)
  try:
   with patch('scratch_snapshot.MetadataAPI',side_effect=factory),patch('build_guard.os.walk',walk),patch('build_guard.os.lstat',metadata),patch.object(pathlib.Path,'exists',return_value=True),patch.object(pathlib.Path,'is_symlink',return_value=False),patch.object(pathlib.Path,'is_junction',return_value=False),patch.object(g,'_leased_pass',return_value=None):
    if mutate:mutate(g)
    value=g.scan_epoch(__import__('time').monotonic()+30)
   return g,value,apis,walks[0],None
  except BaseException as error:return g,None,apis,walks[0],error
 def fail(self,mode,kind,code=None):
  g,value,apis,n,e=self.run_scan(mode);self.assertIsNone(value);self.assertIsInstance(e,kind)
  if code:self.assertIn(code,str(e))
  self.assertIsNone(g.last_completed_bytes);return g,apis,n,e
 def test_handle_first_regular_leaf_has_no_separate_path_stat(self):
  g,value,apis,n,e=self.run_scan();self.assertIsNone(e);self.assertEqual(value,4207);self.assertEqual(n,1);self.assertTrue(all(len(a.opened)==len(a.closed) for a in apis))
 def test_verified_delete_invalidates_entire_census(self):
  g,value,apis,n,e=self.run_scan('delete');self.assertIsNone(e);self.assertEqual((value,n),(11,2));self.assertEqual(g.snapshot_incomplete,1);self.assertFalse(g.recent_churn[0]['completedTotalReported']);self.assertGreaterEqual(g.peak,4096);self.assertTrue(all(len(a.opened)==len(a.closed) for a in apis))
 def test_final_name_delete_uses_prior_held_identity(self):
  g,value,a,n,e=self.run_scan('final-name-delete');self.assertIsNone(e);self.assertEqual((value,n),(11,2));self.assertEqual(g.snapshot_incomplete,1);self.assertGreaterEqual(g.peak,4196)
 def test_initial_open_missing_stays_fatal_with_precise_stage(self):
  from census_supervisor import census_diagnostic
  g,a,n,e=self.fail('open-missing',FileNotFoundError);r=census_diagnostic(e,g.roots,g.census_location);self.assertEqual(r['phase'],'SCRATCH_LEAF_OPEN');self.assertEqual(r['winerror'],2);self.assertEqual(r['relative'],P.relative_to(ROOT).as_posix());self.assertFalse(r['partialTotalAccepted']);self.assertEqual(n,1);self.assertNotIn(str(P),g.scratch_baselines)
 def test_initial_metadata_missing_stays_fatal(self):
  from census_supervisor import census_diagnostic
  g,a,n,e=self.fail('prior-info-missing',FileNotFoundError);self.assertEqual(census_diagnostic(e,g.roots,g.census_location)['phase'],'SCRATCH_PRIOR_IDENTITY');self.assertEqual(n,1);self.assertTrue(all(len(x.opened)==len(x.closed) for x in a))
 def test_confirmation_metadata_missing_stays_fatal(self):
  from census_supervisor import census_diagnostic
  g,a,n,e=self.fail('confirm-info-missing',FileNotFoundError);self.assertEqual(census_diagnostic(e,g.roots,g.census_location)['phase'],'SCRATCH_DELETE_IDENTITY');self.assertEqual(n,1);self.assertEqual(g.snapshot_incomplete,0)
 def test_confirmation_permission_is_fatal(self):self.fail('confirm-denied',PermissionError)
 def test_parent_permission_is_fatal(self):self.fail('parent-denied',PermissionError)
 def test_unconfirmed_absence_not_accepted(self):self.fail('not-pending',AssertionError,'NOT_CONFIRMED_DELETE')
 def test_held_leaf_identity_change_is_fatal(self):self.fail('identity-changed',AssertionError,'ENTRY_IDENTITY_RACE')
 def test_parent_identity_change_is_fatal(self):self.fail('parent-changed',AssertionError,'PARENT_IDENTITY_RACE')
 def test_parent_alias_transition_is_fatal(self):self.fail('parent-reparse',AssertionError,'REPARSE_OR_NON_DIRECTORY')
 def test_leaf_reparse_is_not_followed(self):self.fail('leaf-reparse',AssertionError,'REPARSE_OR_NON_DIRECTORY')
 def test_rename_is_not_delete(self):self.fail('rename',AssertionError,'RENAMED')
 def test_prior_baseline_replacement_is_fatal(self):
  def mutate(g):g.scratch_baselines[str(P)]=((1,9,9),1)
  g,value,a,n,e=self.run_scan(mutate=mutate);self.assertIsNone(value);self.assertIsInstance(e,AssertionError);self.assertIn('ENTRY_REPLACED',str(e))
 def test_repeated_churn_still_exhausts_two_attempts(self):
  g,a,n,e=self.fail('repeated',AssertionError,'TWO_ATTEMPTS_EXHAUSTED');self.assertEqual(n,2);self.assertEqual(g.snapshot_incomplete,2)
 def test_close_failure_prevents_success(self):
  g,a,n,e=self.fail('cleanup',RuntimeError,'CLEANUP_UNVERIFIED');self.assertEqual(n,1);self.assertTrue(all(len(x.close_attempts)==len(x.opened) for x in a))
 def test_close_failure_prevents_churn_restart(self):
  g,a,n,e=self.fail('cleanup-delete',RuntimeError,'CLEANUP_UNVERIFIED');self.assertEqual(n,1);self.assertEqual(g.snapshot_incomplete,0);self.assertTrue(all(len(x.close_attempts)==len(x.opened) for x in a))
 def test_operation_callback_never_changes_acceptance(self):
  api=LifecycleAPI();events=[]
  with ScratchTracker(ROOT,{}, {},api,on_operation=lambda phase,path:events.append((phase,path))) as t:self.assertEqual(t.scan(P,0),4196)
  self.assertTrue(any(p=='SCRATCH_LEAF_OPEN' for p,_ in events));self.assertTrue(any(p=='SCRATCH_LEAF_ENUMERATION' for p,_ in events));self.assertTrue(all(phase.isupper() and len(phase)<=64 for phase,_ in events))
 def test_cancellation_remains_fatal(self):
  def mutate(g):g._enumeration_resources=lambda n:(_ for _ in ()).throw(RuntimeError('CANCELLED'))
  g,value,a,n,e=self.run_scan(mutate=mutate);self.assertIsNone(value);self.assertIsInstance(e,RuntimeError);self.assertEqual(n,0)

class NativeMetadataDiagnostics(unittest.TestCase):
 def test_exact_identity_vs_tag_query_is_retained(self):
  import ctypes
  from scratch_snapshot import MetadataAPI
  class Row(ctypes.Structure):_fields_=[('placeholder',ctypes.c_uint)]
  for identity_ok,expected in ((False,'GET_IDENTITY'),(True,'GET_TAG')):
   api=object.__new__(MetadataAPI);api.INFO=Row;api.TAG=Row
   api.k=types.SimpleNamespace(GetFileInformationByHandle=lambda *args:identity_ok,GetFileInformationByHandleEx=lambda *args:False)
   with patch('scratch_snapshot.ctypes.get_last_error',return_value=2):
    with self.assertRaises(FileNotFoundError) as caught:api.info(123)
   self.assertEqual(caught.exception.scratch_query,expected);self.assertEqual(caught.exception.winerror,2)
 def test_query_annotation_is_bounded_and_does_not_accept_error(self):
  api=FakeAPI();events=[]
  with ScratchTracker(ROOT,{}, {},api,on_operation=lambda phase,path:events.append((phase,path))) as t:
   h,before=t.observe(P)
   e=FileNotFoundError(2,'synthetic');e.winerror=2;e.scratch_query='GET_TAG'
   with patch.object(api,'info',side_effect=e):
    with self.assertRaises(FileNotFoundError):t.info(h,'SCRATCH_PRIOR_IDENTITY')
  self.assertEqual(events[-1][0],'SCRATCH_PRIOR_IDENTITY_GET_TAG')

if __name__=='__main__':unittest.main()
