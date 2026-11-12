import unittest,pathlib,copy,types,time,math
from unittest.mock import patch
from tmp_file_snapshot import TmpFileProof
from scratch_snapshot import identity
from build_guard import Guard,OrdinaryScratchChurn
from test_alias_accounting import guard
from test_scratch_snapshot import FakeAPI,ROOT
def fixture_deadline(clock=None):
 current=(time.monotonic if clock is None else clock)()
 assert type(current) in (int,float) and math.isfinite(current),"FIXTURE_CLOCK_INVALID"
 deadline=math.nextafter(current+30.0,-math.inf)
 assert current<deadline and 0<deadline-current<=30,"FIXTURE_DEADLINE_UNREPRESENTABLE"
 return deadline

P=ROOT/'tmp/assembly-123abc.s'
def missing(path=P,code=2):
 e=FileNotFoundError(2,'synthetic',str(path));e.winerror=code;return e
class Files(FakeAPI):
 def __init__(self):super().__init__();self.pending=False;self.absence=True;self.fresh_error=None;self.file_opened=False;self.race=None
 def open(self,path,share,list_directory=False):
  p=pathlib.Path(path)
  if p==P:
   if self.file_opened:
    if self.fresh_error:raise self.fresh_error
    if self.absence:raise missing()
    key=str(P)+'#replacement';self.rows[key]={'identity':[1,0,999],'created':9,'tag':0,'attributes':0};self.opened.append((key,share,list_directory));return key
   self.file_opened=True;h=super().open(path,share,list_directory);self.rows[h]['attributes']=0;return h
  return super().open(path,share,list_directory)
 def standard(self,h):
  return {'deletePending':self.pending,'directory':False,'allocationBytes':self.allocation,'length':8}
 def info(self,h):
  if self.race:self.race(h)
  return super().info(h)
class ProofCases(unittest.TestCase):
 def make(self,api=None,cancelled=lambda:False,clock=None):
  a=api or Files();return a,TmpFileProof(ROOT,fixture_deadline(clock or time.monotonic),a,cancelled,clock or time.monotonic)
 def test_verified_deletion_invalidates_never_zeroes(self):
  a,t=self.make()
  with t:
   t.observe(P);a.pending=True
   with self.assertRaises(OrdinaryScratchChurn) as caught:t.confirm(P,missing(),77)
   self.assertEqual(caught.exception.partial,4173);self.assertFalse(t.events[0]['completeTotalAccepted']);self.assertTrue(t.events[0]['freshAbsence'])
  self.assertEqual(len(a.closed),len(a.opened))
 def test_prior_identity_missing_fatal(self):
  a,t=self.make()
  with t:
   with self.assertRaisesRegex(AssertionError,'NO_PRIOR'):t.confirm(P,missing(),0)
 def test_rename_not_mislabeled_deletion(self):
  a,t=self.make()
  with t:
   t.observe(P);a.pending=False
   with self.assertRaisesRegex(AssertionError,'NOT_CONFIRMED_DELETE_PENDING'):t.confirm(P,missing(),0)
 def test_regular_replacement_rejected(self):
  a,t=self.make()
  with t:
   t.observe(P);a.pending=True;a.absence=False
   with self.assertRaisesRegex(AssertionError,'NAME_PRESENT_OR_REPLACED'):t.confirm(P,missing(),0)
 def test_changed_held_identity_rejected(self):
  a,t=self.make()
  with t:
   t.observe(P);a.pending=True;a.rows[str(P)]['identity'][-1]+=1
   with self.assertRaisesRegex(AssertionError,'HELD_IDENTITY_CHANGED'):t.confirm(P,missing(),0)
 def test_changed_creation_identity_rejected(self):
  a,t=self.make()
  with t:
   t.observe(P);a.pending=True;a.rows[str(P)]['created']+=1
   with self.assertRaisesRegex(AssertionError,'HELD_IDENTITY_CHANGED'):t.confirm(P,missing(),0)
 def test_reparse_transition_rejected(self):
  a,t=self.make()
  with t:
   t.observe(P);a.pending=True;a.rows[str(P)]['tag']=0xa000000c;a.rows[str(P)]['attributes']=0x400
   with self.assertRaisesRegex(AssertionError,'REPARSE_OR_TYPE'):t.confirm(P,missing(),0)
 def test_parent_identity_change_fatal(self):
  a,t=self.make()
  with t:
   t.observe(P);a.pending=True;a.rows[str(P.parent)]['identity'][-1]+=1
   with self.assertRaisesRegex(AssertionError,'PARENT_IDENTITY_RACE'):t.confirm(P,missing(),0)
 def test_ancestor_reparse_transition_fatal(self):
  a,t=self.make()
  with t:
   t.observe(P);a.pending=True;a.rows[str(ROOT)]['tag']=0xa0000003
   with self.assertRaises(AssertionError):t.confirm(P,missing(),0)
 def test_parent_access_denial_fatal(self):
  a,t=self.make()
  with t:
   t.observe(P);a.pending=True
   with patch.object(a,'info',side_effect=PermissionError(13,'synthetic')):
    with self.assertRaises(PermissionError):t.confirm(P,missing(),0)
 def test_fresh_absence_permission_denial_fatal(self):
  a,t=self.make()
  with t:
   t.observe(P);a.pending=True;a.fresh_error=PermissionError(13,'synthetic')
   with self.assertRaises(PermissionError):t.confirm(P,missing(),0)
 def test_initial_observation_permission_fatal(self):
  a,t=self.make()
  with t,patch.object(a,'open',side_effect=PermissionError(13,'synthetic')):
   with self.assertRaises(PermissionError):t.observe(P)
 def test_unexpected_error_codes_rejected(self):
  for code in (3,5,None,True):
   a,t=self.make()
   with t:
    t.observe(P);a.pending=True
    with self.assertRaisesRegex(AssertionError,'NOT_EXACT_FILE_NOT_FOUND'):t.confirm(P,missing(code=code),0)
 def test_fresh_probe_path_not_found_fatal(self):
  a,t=self.make()
  with t:
   t.observe(P);a.pending=True;a.fresh_error=missing(code=3)
   with self.assertRaisesRegex(AssertionError,'ABSENCE_UNQUALIFIED'):t.confirm(P,missing(),0)
 def test_error_filename_binding_required(self):
  for path in (ROOT/'other/file.s',ROOT/'tmp/../other.s'):
   a,t=self.make()
   with t:
    t.observe(P);a.pending=True
    with self.assertRaisesRegex(AssertionError,'ERROR_PATH_UNBOUND'):t.confirm(P,missing(path),0)
 def test_no_nested_or_outside_scope(self):
  a,t=self.make()
  with t:
   for p in (ROOT/'tmp/nested/file.s',ROOT/'other/file.s',ROOT/'tmp/../other.s'):
    with self.assertRaisesRegex(AssertionError,'EXACT_SCOPE'):t.observe(p)
 def test_prior_reparse_rejected(self):
  a,t=self.make()
  def changed(h):
   if h==str(P):a.rows[h]['tag']=0xa000000c;a.rows[h]['attributes']=0x400
  a.race=changed
  with t:
   with self.assertRaisesRegex(AssertionError,'REPARSE_OR_TYPE'):t.observe(P)
 def test_prior_directory_rejected(self):
  a,t=self.make()
  def changed(h):
   if h==str(P):a.rows[h]['attributes']=16
  a.race=changed
  with t:
   with self.assertRaisesRegex(AssertionError,'REPARSE_OR_TYPE'):t.observe(P)
 def test_cross_volume_rejected(self):
  a,t=self.make()
  def changed(h):
   if h==str(P):a.rows[h]['identity'][0]=2
  a.race=changed
  with t:
   with self.assertRaisesRegex(AssertionError,'CROSS_VOLUME'):t.observe(P)
 def test_cancelled_before_observation(self):
  a,t=self.make(cancelled=lambda:True)
  with t:
   with self.assertRaisesRegex(RuntimeError,'CANCELLED'):t.observe(P)
  self.assertFalse(a.opened)
 def test_cancellation_during_absence_verification(self):
  state=[False];a,t=self.make(cancelled=lambda:state[0])
  with t:
   t.observe(P);a.pending=True
   original=a.open
   def opening(*args,**kw):state[0]=True;return original(*args,**kw)
   with patch.object(a,'open',side_effect=opening):
    with self.assertRaisesRegex(RuntimeError,'CANCELLED'):t.confirm(P,missing(),0)
 def test_independent_deadline_not_renewed(self):
  now=[1];a,t=self.make(clock=lambda:now[0])
  with t:
   t.observe(P);a.pending=True;now[0]=32
   with self.assertRaisesRegex(AssertionError,'DEADLINE'):t.confirm(P,missing(),0)
 def test_cleanup_failure_is_not_success(self):
  a,t=self.make()
  with self.assertRaisesRegex(RuntimeError,'CLEANUP_UNVERIFIED'):
   with t:
    t.observe(P);a.close=lambda h:(_ for _ in ()).throw(PermissionError(13,'synthetic'))
class EpochCases(unittest.TestCase):
 def g(self):
  g=guard();g.worker_mode=True;g.snapshot_incomplete=0;g.ordinary_churn_count=0;g.recent_churn=[];g.last_completed_bytes=None;g.peak=10000;g._enumeration_resources=lambda n:None;return g
 def test_full_snapshot_restarted_without_partial_total(self):
  g=self.g();failure=OrdinaryScratchChurn('tmp/a.s',4096)
  with patch.object(g,'_size_once',side_effect=[failure,123]) as call:
   self.assertEqual(g.scan_epoch(fixture_deadline()),123)
  self.assertEqual(call.call_count,2);self.assertEqual(g.peak,10000);self.assertIsNone(g.last_completed_bytes);self.assertFalse(g.recent_churn[0]['completedTotalReported'])
 def test_repeated_churn_exhausts_original_two_attempts(self):
  g=self.g()
  with patch.object(g,'_size_once',side_effect=OrdinaryScratchChurn('tmp/a.s',4096)) as call:
   with self.assertRaisesRegex(AssertionError,'TWO_ATTEMPTS_EXHAUSTED'):g.scan_epoch(fixture_deadline())
  self.assertEqual(call.call_count,2);self.assertIsNone(g.last_completed_bytes)
 def test_denial_does_not_retry(self):
  g=self.g()
  with patch.object(g,'_size_once',side_effect=PermissionError(13,'synthetic')) as call:
   with self.assertRaises(PermissionError):g.scan_epoch(fixture_deadline())
  self.assertEqual(call.call_count,1);self.assertIsNone(g.last_completed_bytes)
 def test_cancellation_does_not_retry(self):
  g=self.g()
  with patch.object(g,'_size_once',side_effect=RuntimeError('TMP_PROOF_CANCELLED')) as call:
   with self.assertRaisesRegex(RuntimeError,'CANCELLED'):g.scan_epoch(fixture_deadline())
  self.assertEqual(call.call_count,1);self.assertIsNone(g.last_completed_bytes)

class FinalBoundaryCases(unittest.TestCase):
 def test_growth_charged_before_discard(self):
  a=Files();t=TmpFileProof(ROOT,fixture_deadline(),a)
  with t:
   t.observe(P);a.pending=True;a.allocation=32768
   with self.assertRaises(OrdinaryScratchChurn) as caught:t.confirm(P,missing(),100)
   self.assertEqual(caught.exception.partial,32868)
 def test_identity_replaced_during_fresh_absence_check_fatal(self):
  a=Files();t=TmpFileProof(ROOT,fixture_deadline(),a)
  with t:
   t.observe(P);a.pending=True;old=a.open
   def changing(*args,**kw):
    a.rows[str(P)]['identity'][-1]+=1;return old(*args,**kw)
   with patch.object(a,'open',side_effect=changing):
    with self.assertRaisesRegex(AssertionError,'CONFIRMATION_IDENTITY_RACE'):t.confirm(P,missing(),0)
 def test_parent_replaced_during_fresh_absence_check_fatal(self):
  a=Files();t=TmpFileProof(ROOT,fixture_deadline(),a)
  with t:
   t.observe(P);a.pending=True;old=a.open
   def changing(*args,**kw):
    a.rows[str(P.parent)]['identity'][-1]+=1;return old(*args,**kw)
   with patch.object(a,'open',side_effect=changing):
    with self.assertRaisesRegex(AssertionError,'PARENT_IDENTITY_RACE'):t.confirm(P,missing(),0)
 def test_final_metadata_cancellation_rejected(self):
  state=[False];a=Files();t=TmpFileProof(ROOT,fixture_deadline(),a,cancelled=lambda:state[0])
  with t:
   t.observe(P);a.pending=True;old_open=a.open;old_standard=a.standard;after_absence=[False]
   def opening(*args,**kw):
    after_absence[0]=True;return old_open(*args,**kw)
   def standard(h):
    result=old_standard(h)
    if after_absence[0]:state[0]=True
    return result
   with patch.object(a,'open',side_effect=opening),patch.object(a,'standard',side_effect=standard):
    with self.assertRaisesRegex(RuntimeError,'CANCELLED'):t.confirm(P,missing(),0)
 def test_free_floor_failure_still_prevents_restart(self):
  import build_guard
  g=guard();g.start=time.monotonic();g.peak=0;g.snapshot_incomplete=0;g.recent_churn=[];g.ordinary_churn_count=0
  with patch.object(g,'_size_once',side_effect=OrdinaryScratchChurn('tmp/a.s',4096)) as calls,patch('build_guard.shutil.disk_usage',side_effect=[types.SimpleNamespace(free=build_guard.MIN_FREE+1),types.SimpleNamespace(free=build_guard.MIN_FREE-1)]):
   # Restore the actual periodic guard instead of the synthetic fixture's no-op.
   with patch.object(g,'_enumeration_resources',Guard._enumeration_resources.__get__(g)):
    with self.assertRaisesRegex(AssertionError,'FREE_SPACE_GUARD'):g.scan_epoch(fixture_deadline())
  self.assertEqual(calls.call_count,1)

import unittest,pathlib,types,stat,time,copy,json,io
from unittest.mock import patch
from build_guard import Guard,MIN_FREE,MAX_OUTPUT
from census_supervisor import census_diagnostic
from test_alias_accounting import guard
from test_scratch_snapshot import FakeAPI,ROOT
T=ROOT/'tmp/assembly-123abc.s'
def absent(code=2):
 e=FileNotFoundError(2,'synthetic',str(T));e.winerror=code;return e
class WalkerFiles(FakeAPI):
 def __init__(self,mode='count'):super().__init__();self.mode=mode;self.opens=0;self.pending=False
 def open(self,path,share,list_directory=False):
  p=pathlib.Path(path)
  if p==T:
   self.opens+=1
   if self.mode=='absent' and self.opens==1:raise absent()
   if self.mode=='denied' and self.opens==1:raise PermissionError(13,'synthetic')
   if self.opens==1:
    h=super().open(path,share,list_directory);self.rows[h]['attributes']=0;return h
   if self.mode in ('delete','cleanup','repeated'):self.pending=True;raise absent()
   if self.mode=='code3':raise absent(3)
   if self.mode=='fresh-denied':raise PermissionError(13,'synthetic')
   h=str(T)+'#fresh'+str(self.opens);self.rows[h]=copy.deepcopy(self.rows[str(T)])
   if self.mode=='replacement':self.rows[h]['identity'][-1]+=100
   if self.mode=='reparse':self.rows[h]['tag']=0xa000000c;self.rows[h]['attributes']=0x400
   self.opened.append((h,share,list_directory));return h
  h=super().open(path,share,list_directory)
  if self.mode=='parent-replaced' and p==T.parent:self.rows[h]['identity'][-1]+=100
  return h
 def standard(self,h):return {'directory':False,'deletePending':self.pending,'allocationBytes':4096,'length':8}
 def final_name(self,h):return pathlib.PureWindowsPath(T.with_name('renamed.s') if self.mode=='rename' else str(h).split('#')[0])
 def close(self,h):
  self.closed.append(h)
  if self.mode=='cleanup':raise PermissionError(13,'synthetic close')
class IntegratedWalker(unittest.TestCase):
 def run_epoch(self,mode='count',mutate=None):
  g=guard();g.last_snapshot_complete=False;g.last_completed_bytes=None;g.snapshot_incomplete=0;g.ordinary_churn_count=0;g.recent_churn=[];g.peak=1000;apis=[];walks=[0]
  def factory():
   a=WalkerFiles('parent-replaced' if mode=='between' and apis else ('delete' if mode=='between' else mode));apis.append(a);return a
  def walk(root,followlinks,onerror):
   walks[0]+=1;yield str(ROOT),['tmp'],['kept.bin'];yield str(T.parent),[],[] if mode=='delete' and walks[0]>1 else [T.name]
  def metadata(path):
   directory=path==T.parent
   return types.SimpleNamespace(st_size=0 if directory else 7,st_mode=stat.S_IFDIR if directory else stat.S_IFREG,st_file_attributes=16 if directory else 0,st_reparse_tag=0)
  try:
   with patch('tmp_file_snapshot.API',side_effect=factory),patch('build_guard.os.walk',walk),patch('build_guard.os.lstat',metadata),patch.object(pathlib.Path,'exists',return_value=True),patch.object(pathlib.Path,'is_symlink',return_value=False),patch.object(pathlib.Path,'is_junction',return_value=False),patch.object(g,'_leased_pass',return_value=None):
    if mutate:mutate(g)
    value=g.scan_epoch(fixture_deadline())
   return g,value,apis,walks[0],None
  except BaseException as error:return g,None,apis,walks[0],error
 def failure(self,mode,kind,code=None):
  g,value,apis,n,e=self.run_epoch(mode);self.assertIsNone(value);self.assertIsInstance(e,kind)
  if code:self.assertIn(code,str(e))
  self.assertIsNone(g.last_completed_bytes);return g,apis,n,e
 def test_regular_count_is_fresh_bound_handle(self):
  g,v,a,n,e=self.run_epoch();self.assertIsNone(e);self.assertEqual(v,15);self.assertEqual(n,1);self.assertEqual(len(a[0].opened),len(a[0].closed))
 def test_verified_delete_discards_whole_pass(self):
  g,v,a,n,e=self.run_epoch('delete');self.assertIsNone(e);self.assertEqual((v,n),(7,2));self.assertEqual(g.snapshot_incomplete,1);self.assertEqual(g.ordinary_churn_count,1);self.assertFalse(g.recent_churn[0]['completedTotalReported']);self.assertIsNone(g.recent_churn[0]['unmeasuredResidualBytes']);self.assertGreaterEqual(g.peak,4103);self.assertTrue(all(len(x.opened)==len(x.closed) for x in a))
 def test_missing_prior_identity_stays_fatal(self):
  g,a,n,e=self.failure('absent',AssertionError,'UNVERIFIED_FILE_DISAPPEARANCE');self.assertEqual(n,1);self.assertIs(type(e.__cause__),FileNotFoundError);r=census_diagnostic(e,g.roots,g.census_location);self.assertEqual(r['winerror'],2);self.assertEqual(r['relative'],'tmp/'+T.name);self.assertFalse(r['partialTotalAccepted'])
 def test_rename_stays_fatal(self):self.failure('rename',AssertionError,'RENAMED_OR_PATH_ALIAS')
 def test_regular_replacement_fatal(self):self.failure('replacement',AssertionError,'NAMED_FILE_REPLACED')
 def test_reparse_replacement_fatal(self):self.failure('reparse',AssertionError,'REPARSE_OR_TYPE')
 def test_parent_replacement_between_attempts_fatal(self):
  g,a,n,e=self.failure('between',AssertionError,'PARENT_REPLACED');self.assertEqual(n,2);self.assertEqual(g.snapshot_incomplete,1)
 def test_repeated_churn_only_two_attempts(self):
  g,a,n,e=self.failure('repeated',AssertionError,'TWO_ATTEMPTS_EXHAUSTED');self.assertEqual(n,2);self.assertEqual(g.snapshot_incomplete,2)
 def test_permission_fatal_without_retry(self):
  g,a,n,e=self.failure('denied',PermissionError);self.assertEqual(n,1)
 def test_fresh_binding_denial_fatal(self):self.failure('fresh-denied',PermissionError)
 def test_unexpected_absence_code_fatal(self):self.failure('code3',AssertionError,'NOT_EXACT_FILE_NOT_FOUND')
 def test_cleanup_failure_prevents_restart(self):
  g,a,n,e=self.failure('cleanup',RuntimeError,'CLEANUP_UNVERIFIED');self.assertEqual(n,1);self.assertEqual(g.snapshot_incomplete,0);self.assertTrue(e.tmp_cleanup_failures)
 def test_resource_cancellation_closes_handles(self):
  calls=[0]
  def change(g):
   def resources(n):
    calls[0]+=1
    if calls[0]>=4:raise RuntimeError('SYNTHETIC_CANCELLED')
   g._enumeration_resources=resources
  g,v,a,n,e=self.run_epoch(mutate=change);self.assertIsInstance(e,RuntimeError);self.assertIsNone(v);self.assertTrue(all(len(x.opened)==len(x.closed) for x in a))
class WorkerTransport(unittest.TestCase):
 def test_actual_worker_complete_frame_follows_full_restart(self):
  import census_worker
  spec={'root':str(ROOT),'work':str(ROOT),'out':str(ROOT.parent/'out'),'cargo':str(ROOT.parent/'cargo'),'rustup':str(ROOT.parent/'rustup'),'globalStart':time.monotonic()}
  req={'nonce':'b'*32,'generation':2,'specHash':census_worker.spec_hash(spec),'spec':spec,'state':{},'deadline':fixture_deadline()}
  output=io.StringIO();stdin=types.SimpleNamespace(buffer=io.BytesIO((json.dumps(req)+'\n').encode()));walks=[0];apis=[]
  def factory():a=WalkerFiles('delete');apis.append(a);return a
  def walk(root,followlinks,onerror):
   if root==ROOT:
    walks[0]+=1;yield str(ROOT),['tmp'],['kept.bin'];yield str(T.parent),[],[T.name] if walks[0]==1 else []
   else:yield str(root),[],[]
  def metadata(path):
   directory=path==T.parent
   return types.SimpleNamespace(st_size=0 if directory else 7,st_mode=stat.S_IFDIR if directory else stat.S_IFREG,st_file_attributes=16 if directory else 0,st_reparse_tag=0)
  with patch('tmp_file_snapshot.API',side_effect=factory),patch('census_worker.sys.stdin',stdin),patch('census_worker.sys.stdout',output),patch('build_guard.os.walk',walk),patch('build_guard.os.lstat',metadata),patch.object(pathlib.Path,'exists',return_value=True),patch.object(pathlib.Path,'is_symlink',return_value=False),patch.object(pathlib.Path,'is_junction',return_value=False),patch.object(Guard,'_leased_pass',return_value=None),patch('build_guard.shutil.disk_usage',return_value=types.SimpleNamespace(free=MIN_FREE+MAX_OUTPUT+1)):
   census_worker.main()
  terminal=json.loads(output.getvalue().splitlines()[-1]);self.assertEqual(terminal['kind'],'complete');self.assertTrue(terminal['complete']);self.assertEqual(terminal['payload']['bytes'],7);s=terminal['payload']['state'];self.assertEqual(s['snapshot_incomplete'],1);self.assertEqual(s['ordinary_churn_count'],1);self.assertTrue(all(r['complete'] for r in s['root_scans']));self.assertTrue(all(not r['completedTotalReported'] for r in s['recent_churn']));self.assertTrue(all(len(x.opened)==len(x.closed) for x in apis))


class ConservativeFixtureDeadline(unittest.TestCase):
 def test_fractional_raw_deadline_reproduces_original_rejection(self):
  for now in (30.001,255.999):
   with self.subTest(now=now),self.assertRaisesRegex(AssertionError,"TMP_WINDOW_BOUND"):
    TmpFileProof(ROOT,now+30,api=Files(),clock=lambda value=now:value)
 def test_conservative_deadline_is_within_unchanged_guard(self):
  for now in (0.0,10.0,30.001,255.999,15603.109):
   with self.subTest(now=now):
    clock=lambda value=now:value;deadline=fixture_deadline(clock)
    self.assertGreater(deadline,now);self.assertLessEqual(deadline-now,30)
    with TmpFileProof(ROOT,deadline,api=Files(),clock=clock):pass
 def test_expired_deadlines_remain_rejected(self):
  for now in (10.0,30.001):
   with self.subTest(now=now),self.assertRaisesRegex(AssertionError,"TMP_WINDOW_BOUND"):
    TmpFileProof(ROOT,now,api=Files(),clock=lambda value=now:value)
 def test_one_representable_step_above_ceiling_remains_rejected(self):
  for now in (10.0,30.001,255.999):
   with self.subTest(now=now),self.assertRaisesRegex(AssertionError,"TMP_WINDOW_BOUND"):
    TmpFileProof(ROOT,math.nextafter(now+30,math.inf),api=Files(),clock=lambda value=now:value)
 def test_helper_samples_its_clock_once(self):
  calls=[]
  def clock():calls.append(1);return 30.001
  deadline=fixture_deadline(clock);self.assertEqual(len(calls),1);self.assertLessEqual(deadline-30.001,30)
 def test_invalid_or_unrepresentable_clock_is_rejected(self):
  for value in (math.nan,math.inf,-math.inf,float(2**60)):
   with self.subTest(value=str(value)),self.assertRaises(AssertionError):fixture_deadline(lambda:value)
 def test_explicit_clock_does_not_read_default_clock(self):
  with patch.object(time,"monotonic",side_effect=AssertionError("DEFAULT_CLOCK_USED")):
   self.assertGreater(fixture_deadline(lambda:10.0),10.0)

if __name__=='__main__':unittest.main()
