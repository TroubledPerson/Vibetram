"""Synthetic supervision plus real empty-root scanner seam; no compiler."""
import unittest,pathlib,sys,json,time,os,hashlib,uuid,shutil
from unittest.mock import patch
from census_supervisor import Sampler,run_census,CensusFailure
from census_worker import spec_hash,export_state
from build_guard import Guard
from scratch_snapshot import IncompleteScratchSnapshot
CI=pathlib.Path(__file__).parent
def root():
 base=pathlib.Path(os.environ.get('VIBETRAM_TEST_TMP',os.environ.get('RUNNER_TEMP',str(CI.parent/'ci-unit-output'))));base.mkdir(exist_ok=True,parents=True)
 p=base/uuid.uuid4().hex;p.mkdir()
 for n in ('work','out','cargo','rustup','work/tmp'):(p/n).mkdir(exist_ok=True)
 return p
def request(p):
 spec={'root':str(p),'work':str(p/'work'),'out':str(p/'out'),'cargo':str(p/'cargo'),'rustup':str(p/'rustup'),'globalStart':time.monotonic()}
 return {'nonce':uuid.uuid4().hex,'generation':1,'specHash':spec_hash(spec),'spec':spec,'state':{}}
class Heartbeat(unittest.TestCase):
 def test_gap_fails(self):
  clock=[0];s=Sampler(lambda:None,lambda:clock[0]);s.tick();clock[0]=1.01
  with self.assertRaisesRegex(CensusFailure,'MISSED'):s.tick()
 def test_blocked_sample_fails(self):
  clock=[0]
  def slow():clock[0]+=1.01
  with self.assertRaisesRegex(CensusFailure,'BLOCKED'):Sampler(slow,lambda:clock[0]).tick()
 def test_active_command_deadline_applies_while_census_is_pending(self):
  p=root();g=object.__new__(Guard);g._setup(p,p/'work',p/'out',{'CARGO_HOME':str(p/'cargo'),'RUSTUP_HOME':str(p/'rustup')});g._command_deadline=time.monotonic()-.01
  with self.assertRaisesRegex(AssertionError,'COMMAND_DEADLINE'):g._resource_sample()
 def test_floor_error_not_swallowed(self):
  def denied():raise PermissionError(5,'synthetic')
  with self.assertRaises(PermissionError):Sampler(denied).tick()
class ParentResourceLimits(unittest.TestCase):
 def g(self):
  from build_guard import MIN_FREE
  p=root();g=object.__new__(Guard);g._setup(p,p/'work',p/'out',{'CARGO_HOME':str(p/'cargo'),'RUSTUP_HOME':str(p/'rustup')});return g
 def test_parent_log_threshold_while_worker_is_pending(self):
  from build_guard import MAX_LOG,MIN_FREE
  import stat,types
  g=self.g();g._log_paths=[g.work/'synthetic.log']
  row=types.SimpleNamespace(st_mode=stat.S_IFREG,st_file_attributes=0,st_reparse_tag=0,st_size=MAX_LOG+1)
  with patch('build_guard.fresh_entry',return_value=row),patch('build_guard.shutil.disk_usage',return_value=types.SimpleNamespace(free=MIN_FREE+1)):
   with self.assertRaisesRegex(AssertionError,'COMMAND_LOG_THRESHOLD'):g._resource_sample()
 def test_parent_free_floor_while_worker_is_pending(self):
  from build_guard import MIN_FREE
  import types
  g=self.g()
  with patch('build_guard.shutil.disk_usage',return_value=types.SimpleNamespace(free=MIN_FREE-1)):
   with self.assertRaisesRegex(AssertionError,'FREE_SPACE_GUARD'):g._resource_sample()
 def test_parent_observed_output_threshold(self):
  from build_guard import MAX_OUTPUT,MIN_FREE
  import types
  g=self.g();g.peak=MAX_OUTPUT+1
  with patch('build_guard.shutil.disk_usage',return_value=types.SimpleNamespace(free=MIN_FREE+1)):
   with self.assertRaisesRegex(AssertionError,'OUTPUT_THRESHOLD'):g._resource_sample()
 def test_parent_total_runtime_threshold(self):
  from build_guard import MAX_SECONDS,MIN_FREE
  import types
  g=self.g();g.start=time.monotonic()-MAX_SECONDS-1
  with patch('build_guard.shutil.disk_usage',return_value=types.SimpleNamespace(free=MIN_FREE+1)):
   with self.assertRaisesRegex(AssertionError,'TRIAL_DEADLINE'):g._resource_sample()
class Protocol(unittest.TestCase):
 def fixture(self,mode,seconds=3,sample=lambda:None):
  p=root();s=Sampler(sample);peaks=[]
  try:result=run_census([sys.executable,'-B',str(CI/'test_census_process_fixture.py'),mode],request(p),s,peaks.append,seconds=seconds)
  except BaseException as error:
   self.assertNotIn('UNCONFIRMED_CENSUS_TEARDOWN',getattr(error,'cleanup_failures',[]));raise
  return result,s,peaks
 def test_independent_samples_while_worker_waits(self):
  r,s,p=self.fixture('concurrent');self.assertTrue(r['synthetic']);self.assertGreaterEqual(s.count,4);self.assertEqual(max(p),12)
 def test_stale_generation_rejected(self):
  with self.assertRaisesRegex(CensusFailure,'STALE_OR_UNBOUND'):self.fixture('stale')
 def test_partial_completion_rejected(self):
  with self.assertRaisesRegex(CensusFailure,'INCOMPLETE'):self.fixture('partial')
 def test_denial_not_retried(self):
  with self.assertRaisesRegex(CensusFailure,'PERMISSION_DENIED'):self.fixture('error')
 def test_total_timeout_and_bounded_worker_teardown(self):
  t=time.monotonic()
  with self.assertRaisesRegex(CensusFailure,'DEADLINE'):self.fixture('hang',seconds=.3)
  self.assertLess(time.monotonic()-t,3.5)
 def test_no_parent_credentials_in_worker_environment(self):
  with patch.dict(os.environ,{'GITHUB_TOKEN':'synthetic','ACTIONS_RUNTIME_TOKEN':'synthetic','AWS_ACCESS_KEY_ID':'synthetic'}):self.fixture('credentials')
 def test_resource_failure_cancels_pending_census(self):
  calls=[0]
  def floor():
   calls[0]+=1
   if calls[0]>2:raise AssertionError('SYNTHETIC_FLOOR')
  with self.assertRaisesRegex(AssertionError,'SYNTHETIC_FLOOR'):self.fixture('concurrent',sample=floor)
class Epoch(unittest.TestCase):
 def g(self):
  p=root();g=object.__new__(Guard);g._setup(p,p/'work',p/'out',{'CARGO_HOME':str(p/'cargo'),'RUSTUP_HOME':str(p/'rustup')});g._enumeration_resources=lambda n:None;return g
 def test_two_attempts_share_deadline_and_reject_partial(self):
  g=self.g();deadline=time.monotonic()+30
  with patch.object(g,'_size_once',side_effect=[IncompleteScratchSnapshot('synthetic',[1,2,3],20,4096),7]) as call:self.assertEqual(g.scan_epoch(deadline),7)
  self.assertEqual(call.call_count,2);self.assertGreater(g.peak,7);self.assertEqual(g.snapshot_incomplete,1)
 def test_repeated_churn_is_bounded(self):
  g=self.g()
  with patch.object(g,'_size_once',side_effect=IncompleteScratchSnapshot('synthetic',[1,2,3],20,4096)) as call:
   with self.assertRaisesRegex(AssertionError,'TWO_ATTEMPTS'):g.scan_epoch(time.monotonic()+30)
  self.assertEqual(call.call_count,2)
 def test_unverified_churn_is_not_reported_as_verified(self):
  from build_guard import OrdinaryScratchChurn
  g=self.g()
  with patch.object(g,'_size_once',side_effect=[OrdinaryScratchChurn('synthetic',10),20]):self.assertEqual(g.scan_epoch(time.monotonic()+30),20)
  report=g.report();self.assertEqual(report['churnInvalidatedCensusSnapshots'],1);self.assertEqual(report['ordinaryChurnInvalidations'],1);self.assertNotIn('verifiedIncompleteSnapshots',report)
 def test_internal_alias_rewalks_share_the_same_two_walk_cap(self):
  g=self.g()
  def extra_walks():
   g._walk(None);g._walk(None);return g._walk(None)
  with patch.object(g,'_size_once',side_effect=extra_walks),patch.object(g,'_walk_tracked',return_value=0) as walk:
   with self.assertRaisesRegex(AssertionError,'CENSUS_TWO_WALKS_EXHAUSTED'):g.scan_epoch(time.monotonic()+30)
  self.assertEqual(walk.call_count,2);self.assertEqual(g.census_walk_count,2)
 def test_real_worker_scans_all_empty_owned_roots(self):
  p=root();g=object.__new__(Guard);g._setup(p,p/'work',p/'out',{'CARGO_HOME':str(p/'cargo'),'RUSTUP_HOME':str(p/'rustup')})
  req=request(p);req['state']=export_state(g);s=Sampler(lambda:None)
  payload=run_census([sys.executable,'-B',str(CI/'census_worker.py')],req,s,lambda n:None)
  self.assertEqual(payload['rootCount'],4);self.assertEqual(len(payload['state']['root_scans']),4);self.assertEqual(payload['bytes'],0)
class ParentRun(unittest.TestCase):
 def g(self):
  p=root();env={k:os.environ[k] for k in ('SystemRoot','WINDIR','PATH','PATHEXT') if k in os.environ};env.update(CARGO_HOME=str(p/'cargo'),RUSTUP_HOME=str(p/'rustup'),PYTHONDONTWRITEBYTECODE='1',PYTHONNOUSERSITE='1')
  g=object.__new__(Guard);g._setup(p,p/'work',p/'out',env);return g
 def test_real_parent_loop_keeps_supervision_independent(self):
  g=self.g();r=g.run([sys.executable,'-B','-c','import time; print("synthetic"); time.sleep(.6)'],capture=True)
  self.assertEqual(r.returncode,0);self.assertIn('synthetic',r.stdout);self.assertGreater(g.supervision_samples,4);self.assertIsNone(g._sampler);self.assertFalse(g.census_pending)
 def test_real_parent_timeout_stops_only_its_synthetic_child(self):
  g=self.g()
  with self.assertRaisesRegex(AssertionError,'COMMAND_DEADLINE'):g.run([sys.executable,'-B','-c','import time; time.sleep(10)'],timeout=.3)
  self.assertIsNone(g._sampler);self.assertFalse(g.census_pending)
  report=json.loads((g.work/'failure-summary.json').read_text(encoding='utf-8'));self.assertTrue(report['knownParentExitObserved']);self.assertEqual(report['teardownFailures'],[])

class CompilerDirectoryChurn(unittest.TestCase):
 def scan(self,mode='lookup',code=2):
  from test_scratch_snapshot import FakeAPI,P,ROOT as W
  from test_alias_accounting import guard,fake_metadata
  g=guard();g.ordinary_churn_count=0;g.recent_churn=[];g.snapshot_incomplete=0;g.last_snapshot_complete=False;api=FakeAPI();target=P.parent/'rustcProbe';phase=[0]
  def missing(path,errcode):
   e=FileNotFoundError(errcode,'synthetic compiler churn',str(path));e.winerror=errcode;return e
  def walk(root,followlinks,onerror):
   phase[0]+=1
   ds=[target.name] if phase[0]==1 or mode=='link' else []
   yield str(target.parent),ds,[]
   if mode in ('descent','unknown') and phase[0]==1:onerror(missing(target if mode=='descent' else target.parent/'not_observed',3))
  def metadata(p):
   if p==target and phase[0]==1:
    if mode=='denied':raise PermissionError(5,'synthetic denied')
    if mode=='parent':
     api.rows[str(target.parent)]['identity'][-1]+=1;raise missing(p,2)
    if mode not in ('descent','unknown'):raise missing(p,code)
   return fake_metadata(p,mode=='link' and phase[0]>1)
  with patch('scratch_snapshot.MetadataAPI',return_value=api),patch('build_guard.os.walk',walk),patch('build_guard.os.lstat',metadata),patch.object(pathlib.Path,'exists',return_value=True),patch.object(pathlib.Path,'is_symlink',return_value=False),patch.object(pathlib.Path,'is_junction',return_value=False),patch.object(g,'_leased_pass',return_value=None):
   value=g.scan_epoch(time.monotonic()+30)
  return g,value,phase[0]
 def test_direct_deps_lookup_disappearance_recounts_whole_tree(self):
  g,value,attempts=self.scan();self.assertEqual(value,0);self.assertEqual(attempts,2);self.assertEqual(g.snapshot_incomplete,1)
 def test_preobserved_directory_descent_disappearance(self):
  g,value,attempts=self.scan('descent');self.assertEqual(value,0);self.assertEqual(attempts,2)
 def test_replacement_link_is_fatal(self):
  with self.assertRaisesRegex(AssertionError,'UNQUALIFIED_OUTPUT_DIRECTORY_LINK'):self.scan('link')
 def test_denial_is_not_churn(self):
  with self.assertRaises(PermissionError):self.scan('denied')
 def test_parent_identity_change_is_not_churn(self):
  with self.assertRaisesRegex(AssertionError,'IDENTITY'):self.scan('parent')
 def test_unobserved_path_error_stays_fatal(self):
  with self.assertRaises(FileNotFoundError):self.scan('unknown')
 def test_lookup_path_not_found_without_prior_metadata_stays_fatal(self):
  with self.assertRaises(FileNotFoundError):self.scan(code=3)
if __name__=='__main__':unittest.main()
