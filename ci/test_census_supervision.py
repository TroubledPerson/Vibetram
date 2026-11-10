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
class FailureContext(unittest.TestCase):
 def diagnostic(self,error,location=None):
  from census_supervisor import census_diagnostic
  p=pathlib.Path("D:/synthetic-owned");return census_diagnostic(error,[p/"work",p/"out",p/"cargo",p/"rustup"],location or {"phase":"FILE_ENTRY_METADATA","rootIndex":0,"relative":"target/ci-test/deps/temporary.o"})
 def test_not_found_has_exact_os_numbers_and_owned_relative(self):
  e=FileNotFoundError(2,"sensitive text",str(pathlib.Path("D:/synthetic-owned/work/target/ci-test/deps/temporary.o")));e.winerror=3;r=self.diagnostic(e)
  self.assertEqual(r["failureCode"],"CENSUS_FILENOTFOUNDERROR");self.assertEqual(r["errno"],2);self.assertEqual(r["winerror"],3);self.assertEqual(r["relative"],"target/ci-test/deps/temporary.o");self.assertEqual(r["entrySource"],"OS_FILENAME");self.assertFalse(r["partialTotalAccepted"]);self.assertNotIn("sensitive",json.dumps(r))
 def test_denial_link_and_identity_stay_distinct(self):
  errors=[PermissionError(5,"sensitive"),AssertionError("UNQUALIFIED_OUTPUT_DIRECTORY_LINK:private"),AssertionError("SCRATCH_PARENT_IDENTITY_CHANGED:private")]
  expected=["CENSUS_PERMISSION_DENIED","UNQUALIFIED_OUTPUT_DIRECTORY_LINK","SCRATCH_PARENT_IDENTITY_CHANGED"]
  for e,code in zip(errors,expected):
   with self.subTest(code=code):self.assertEqual(self.diagnostic(e)["failureCode"],code);self.assertFalse(self.diagnostic(e)["partialTotalAccepted"])
 def test_private_absolute_outside_or_unsafe_paths_withheld(self):
  for name in ("C:/Users/private-owner/private@example.invalid", "D:/synthetic-owned/work/target/private@example.invalid", "D:/synthetic-owned/work/../elsewhere"):
   with self.subTest(name=name):
    r=self.diagnostic(FileNotFoundError(2,"private-value",name));self.assertIsNone(r["relative"]);self.assertNotIn("private",json.dumps(r));self.assertNotIn("Users",json.dumps(r))
 def test_fallback_is_labeled_last_operation_not_exact_os_path(self):
  r=self.diagnostic(FileNotFoundError(2,"private-value"));self.assertEqual(r["entrySource"],"LAST_OPERATION_CONTEXT");self.assertEqual(r["phase"],"FILE_ENTRY_METADATA")
 def test_invalid_diagnostic_fields_fail_closed(self):
  from census_supervisor import validate_census_diagnostic
  row=self.diagnostic(FileNotFoundError(2,"private"));self.assertEqual(validate_census_diagnostic(row),row)
  for patcher in ({"relative":"../outside"},{"phase":"private@example.invalid"},{"rootIndex":8},{"winerror":"private"},{"partialTotalAccepted":True},{"extra":"value"}):
   with self.subTest(patcher=patcher),self.assertRaises(AssertionError):validate_census_diagnostic({**row,**patcher})
 def test_parent_retains_worker_diagnostic_without_accepting_partial_total(self):
  from census_supervisor import census_diagnostic
  g=ParentResourceLimits().g();g.count=46
  e=FileNotFoundError(2,"private",str(g.work/"target/ci-test/temporary.o"));e.winerror=2
  diagnostic=census_diagnostic(e,g.roots,{"phase":"DIRECTORY_ENTRY_METADATA"});state=export_state(g)
  with patch('build_guard.run_census',side_effect=CensusFailure('CENSUS_FILENOTFOUNDERROR',{'state':state,'diagnostic':diagnostic})):
   with self.assertRaises(CensusFailure):g.check()
  r=g.report();self.assertEqual(r['censusFailureDiagnostic']['commandStage'],46);self.assertEqual(r['censusFailureDiagnostic']['relative'],'target/ci-test/temporary.o');self.assertFalse(r['lastSnapshotComplete']);self.assertIsNone(r['lastCompletedSnapshotBytes'])
 def test_actual_worker_error_frame_contains_sanitized_context(self):
  import io,types,census_worker
  p=root();req=request(p);req['deadline']=time.monotonic()+30;output=io.StringIO()
  def fail(g,deadline):
   entry=g.work/'target/ci-test/temporary.o';g._census_at('FILE_ENTRY_METADATA',g.work,entry);error=FileNotFoundError(2,'private-value',str(entry));error.winerror=2;raise error
  stdin=types.SimpleNamespace(buffer=io.BytesIO((json.dumps(req)+'\n').encode()))
  with patch('census_worker.sys.stdin',stdin),patch('census_worker.sys.stdout',output),patch.object(Guard,'scan_epoch',fail):
   with self.assertRaises(SystemExit):census_worker.main()
  row=json.loads(output.getvalue());self.assertEqual(row['kind'],'error');self.assertEqual(row['payload']['diagnostic']['relative'],'target/ci-test/temporary.o');self.assertEqual(row['payload']['diagnostic']['winerror'],2);self.assertNotIn('private-value',output.getvalue());self.assertNotIn(str(p),json.dumps(row['payload']['diagnostic']))

class TeardownEvidence(unittest.TestCase):
 def test_parent_exit_and_taskkill_codes_never_prove_tree_exit(self):
  from census_supervisor import classify_teardown
  for code in (0,128,None):
   r=classify_teardown(0,code);self.assertEqual(r['treeState'],'UNKNOWN_DESCENDANT_STATE');self.assertFalse(r['processTreeExitIndependentlyVerified'])
 def test_surviving_bound_child_distinct_from_unknown(self):
  from census_supervisor import classify_teardown
  r=classify_teardown(0,0,[{'identityBound':True,'exited':False}],True);self.assertEqual(r['treeState'],'SURVIVING_KNOWN_CHILD');self.assertFalse(r['processTreeExitIndependentlyVerified'])
 def test_only_complete_identity_bound_exit_evidence_verifies(self):
  from census_supervisor import classify_teardown
  self.assertTrue(classify_teardown(0,0,[{'identityBound':True,'exited':True}],True)['processTreeExitIndependentlyVerified'])
  for complete,bound in ((False,True),(True,False)):
   self.assertFalse(classify_teardown(0,0,[{'identityBound':bound,'exited':True}],complete)['processTreeExitIndependentlyVerified'])
 def test_already_exited_parent_skips_taskkill_but_tree_stays_unknown(self):
  from census_supervisor import stop_compiler_tree
  from unittest.mock import Mock
  p=Mock();p.pid=123;p.poll.return_value=0
  with patch('census_supervisor.subprocess.Popen') as popen:self.assertEqual(stop_compiler_tree(p,Mock(),'C:/Windows'),[])
  popen.assert_not_called();self.assertTrue(p._vibetram_teardown_diagnostic['parentAlreadyExitedBeforeStop']);self.assertFalse(p._vibetram_teardown_diagnostic['processTreeExitIndependentlyVerified'])
 def test_stop_launch_denial_retains_unknown_outcome(self):
  from census_supervisor import stop_compiler_tree
  from unittest.mock import Mock
  p=Mock();p.pid=123;p.poll.return_value=None
  with patch('census_supervisor.subprocess.Popen',side_effect=PermissionError(5,'private-value')):failures=stop_compiler_tree(p,Mock(),'C:/Windows')
  self.assertEqual(failures,['COMPILER_STOP_PermissionError']);self.assertEqual(p._vibetram_teardown_diagnostic['treeState'],'UNKNOWN_DESCENDANT_STATE');self.assertNotIn('private-value',json.dumps(p._vibetram_teardown_diagnostic))

class FakeOwnedJobAPI:
 def __init__(self,fail=None,hang=False):self.fail=fail;self.hang=hang;self.calls=[];self.assigned=False;self.active=False;self.dead=False;self.child=False;self.closed=[]
 def event(self,name):
  self.calls.append(name)
  if self.fail==name:raise PermissionError(5,'synthetic owned-job denial')
 def create_job(self):self.event('create_job');return 1
 def create_suspended(self,*a):self.event('create_suspended');self.active=True;return 10,11
 def assign(self,*a):self.event('assign');self.assigned=True
 def in_job(self,p,j=None):return self.assigned if j else False
 def resume(self,*a):self.event('resume');self.child=True
 def members(self,j):
  self.event('members');return ([1001,1002] if self.child else [1001]) if self.active else []
 def active_count(self,j):return (2 if self.child else 1) if self.active else 0
 def snapshot(self,h):return {'pid':1002 if h==20 else 1001,'creationFiletime':2 if h==20 else 1,'exited':self.dead}
 def open_member(self,j,pid):self.event('open_member');return 20
 def terminate(self,j):
  self.event('terminate')
  if not self.hang:self.active=False;self.dead=True
 def terminate_unassigned(self,p):self.event('terminate_unassigned');self.active=False;self.dead=True
 def close(self,h):
  self.event('close');self.closed.append(h)
  if h==1:self.active=False;self.dead=True

class IsolatedOwnedJobs(unittest.TestCase):
 def argv(self):
  p=pathlib.Path('D:/synthetic-owned-job');return [sys.executable,'-B',str(p/'owned_job_fixture.py'),'wait','a'*32,str(p)],p
 def start(self,api):
  from census_supervisor import OwnedJobPrototype
  j=OwnedJobPrototype(api);argv,p=self.argv();j.start_test(argv,p,{});return j
 def test_assignment_precedes_execution(self):
  a=FakeOwnedJobAPI();j=self.start(a);self.assertLess(a.calls.index('assign'),a.calls.index('resume'));self.assertEqual(j.events,['CREATED_SUSPENDED','ASSIGNED_OWNED_INNER','RESUMED_AFTER_ASSIGNMENT']);j.close();self.assertEqual(sorted(a.closed),[1,10,11,20])
 def test_job_creation_denial_never_starts_any_process(self):
  from census_supervisor import OwnedJobPrototype
  a=FakeOwnedJobAPI('create_job')
  with self.assertRaises(PermissionError):OwnedJobPrototype(a)
  self.assertEqual(a.calls,['create_job']);self.assertEqual(a.closed,[])
 def test_creation_failure_never_resumes(self):
  a=FakeOwnedJobAPI('create_suspended')
  with self.assertRaises(PermissionError):self.start(a)
  self.assertNotIn('resume',a.calls);self.assertEqual(a.closed,[1])
 def test_assignment_denial_terminates_only_unassigned_owned_handle(self):
  a=FakeOwnedJobAPI('assign')
  with self.assertRaises(PermissionError):self.start(a)
  self.assertNotIn('resume',a.calls);self.assertIn('terminate_unassigned',a.calls);self.assertEqual(sorted(a.closed),[1,10,11])
 def test_resume_failure_stops_assigned_job(self):
  a=FakeOwnedJobAPI('resume')
  with self.assertRaises(PermissionError):self.start(a)
  self.assertIn('terminate',a.calls);self.assertFalse(a.active);self.assertEqual(sorted(a.closed),[1,10,11])
 def test_zero_members_and_all_held_identities_exit_required(self):
  a=FakeOwnedJobAPI();j=self.start(a);r=j.stop();self.assertEqual(r['activeMembers'],0);self.assertTrue(r['knownHandlesExited']);j.close()
 def test_bounded_timeout_never_qualifies(self):
  a=FakeOwnedJobAPI(hang=True);j=self.start(a);clock=[0]
  def sleep(n):clock[0]+=n
  with patch('census_supervisor.time.monotonic',side_effect=lambda:clock[0]),patch('census_supervisor.time.sleep',side_effect=sleep):
   with self.assertRaisesRegex(TimeoutError,'DEADLINE'):j.stop(.03)
  a.hang=False;j.close()
 def test_empty_pid_buffer_without_zero_active_count_not_success(self):
  a=FakeOwnedJobAPI(hang=True);j=self.start(a);clock=[0]
  def sleep(n):clock[0]+=n
  with patch.object(a,'members',return_value=[]),patch.object(a,'snapshot',return_value={'pid':1001,'creationFiletime':1,'exited':True}),patch('census_supervisor.time.monotonic',side_effect=lambda:clock[0]),patch('census_supervisor.time.sleep',side_effect=sleep):
   with self.assertRaises(TimeoutError):j.stop(.03)
  a.hang=False;j.close()
 def test_all_job_members_including_console_helper_are_retained(self):
  class Three(FakeOwnedJobAPI):
   def members(self,j):return [1001,1002,1003] if self.active else []
   def active_count(self,j):return 3 if self.active else 0
   def open_member(self,j,pid):return {1002:20,1003:30}[pid]
   def snapshot(self,h):return {'pid':{10:1001,20:1002,30:1003}[h],'creationFiletime':h,'exited':self.dead}
  a=Three();j=self.start(a);r=j.stop();self.assertEqual(len(r['before']),3);self.assertEqual(len(r['after']),3);j.close();self.assertEqual(sorted(a.closed),[1,10,11,20,30])
 def test_parent_exits_before_child_without_losing_job_members(self):
  class Early(FakeOwnedJobAPI):
   def members(self,j):return [1002] if self.active else []
   def active_count(self,j):return 1 if self.active else 0
   def snapshot(self,h):return {'pid':1002 if h==20 else 1001,'creationFiletime':2 if h==20 else 1,'exited':True if h==10 else self.dead}
  a=Early();j=self.start(a);r=j.stop();self.assertEqual(len(r['before']),1);self.assertEqual(r['activeMembers'],0);self.assertTrue(r['knownHandlesExited']);j.close()
 def test_failed_stop_is_not_retried_during_handle_cleanup(self):
  a=FakeOwnedJobAPI();j=self.start(a);a.fail='terminate'
  with self.assertRaises(PermissionError):j.stop()
  j.close();self.assertEqual(a.calls.count('terminate'),1);self.assertTrue(j.closed)
 def test_handle_close_failure_is_explicit(self):
  a=FakeOwnedJobAPI();j=self.start(a);j.stop();a.fail='close'
  with self.assertRaisesRegex(RuntimeError,'CLEANUP_UNCERTAIN'):j.close()
 def test_changed_creation_identity_is_fatal(self):
  a=FakeOwnedJobAPI();j=self.start(a);original=a.snapshot
  def changed(h):return {**original(h),'creationFiletime':999}
  with patch.object(a,'snapshot',side_effect=changed):
   with self.assertRaisesRegex(AssertionError,'IDENTITY_CHANGED'):j.observe()
  j.close()
 def test_no_production_runner_replacement(self):
  import inspect,ast
  tree=ast.parse(__import__("textwrap").dedent(inspect.getsource(Guard.run)));self.assertNotIn('OwnedJobPrototype',ast.unparse(tree));self.assertNotIn('WindowsOwnedJobAPI',ast.unparse(tree))
 def test_environment_double_nul_and_no_credential_keys(self):
  from census_supervisor import owned_job_test_environment
  env={'SystemRoot':'C:/Windows','PYTHONNOUSERSITE':'1','PYTHONDONTWRITEBYTECODE':'1'};block=owned_job_test_environment(env);self.assertTrue(block.endswith(chr(0)*2));self.assertNotIn('\\0',block)
  for change in ({'TOKEN':'synthetic'},{'PATH':'x'+chr(0)+'y'}):
   with self.assertRaises(AssertionError):owned_job_test_environment({**env,**change})




class ProductionOwnedJobs(unittest.TestCase):
 def fake(self,**options):
  from census_supervisor import OwnedProcess
  class API(FakeOwnedJobAPI):
   def snapshot(self,h):return {**super().snapshot(h),'exitCode':0 if self.dead else None}
  a=API(**options);j=OwnedProcess(a);j.process=10;j.thread=11;j.assigned=True;j.initial=a.snapshot(10);j.pid=1001;a.active=True;a.assigned=True;a.child=True;return a,j
 def test_poll_after_verified_close_uses_observed_exit_without_reopening(self):
  a,j=self.fake();j.finish(True);j.close();calls=len(a.calls);self.assertEqual(j.poll(),0);self.assertEqual(len(a.calls),calls)
 def test_production_direct_stop_accounts_every_member(self):
  a,j=self.fake();r=j.finish(True);self.assertTrue(r['processTreeExitIndependentlyVerified']);self.assertEqual(r['activeMembers'],0);self.assertEqual(r['heldIdentityCount'],2);self.assertEqual(a.calls.count('terminate'),1);j.close()
 def test_parent_exit_does_not_skip_child_teardown(self):
  a,j=self.fake();old=a.snapshot
  a.snapshot=lambda h:{**old(h),'exited':True,'exitCode':0} if h==10 else old(h)
  with self.assertRaisesRegex(RuntimeError,'DESCENDANTS_AFTER_PARENT'):j.finish()
  self.assertEqual(a.calls.count('terminate'),1);self.assertTrue(j.teardown['processTreeExitIndependentlyVerified']);j.close()
 def test_access_denial_never_falls_back_or_retries(self):
  a,j=self.fake();a.fail='members'
  with self.assertRaises(PermissionError):j.finish(True)
  calls=len(a.calls);j.close();self.assertNotIn('terminate_unassigned',a.calls);self.assertEqual(a.calls[calls:],['close','close','close'])
 def test_termination_denial_not_retried(self):
  a,j=self.fake();a.fail='terminate'
  with self.assertRaises(PermissionError):j.finish(True)
  j.close();self.assertEqual(a.calls.count('terminate'),1);self.assertIsNone(j.teardown)
 def test_changed_held_identity_rejected(self):
  a,j=self.fake();old=a.snapshot;a.snapshot=lambda h:{**old(h),'creationFiletime':900}
  with self.assertRaisesRegex(AssertionError,'IDENTITY_CHANGED'):j.finish(True)
  j.close();self.assertIsNone(j.teardown)
 def test_zero_pid_list_without_zero_active_count_cannot_pass(self):
  a,j=self.fake(hang=True);a.members=lambda job:[];a.snapshot=lambda h:{'pid':1001,'creationFiletime':1,'exited':True,'exitCode':0};clock=[0]
  with patch('census_supervisor.time.monotonic',side_effect=lambda:clock[0]),patch('census_supervisor.time.sleep',side_effect=lambda n:clock.__setitem__(0,clock[0]+n)):
   with self.assertRaises(TimeoutError):j.finish(True,seconds=.03)
  j.close();self.assertIsNone(j.teardown)
 def test_supervision_failure_does_not_prevent_owned_stop(self):
  a,j=self.fake()
  def failure():raise AssertionError('SYNTHETIC_FLOOR')
  r=j.finish(True,Sampler(failure));self.assertTrue(r['processTreeExitIndependentlyVerified']);self.assertIn('AssertionError',r['supervisionFailures']);j.close()
 def test_failed_handle_close_is_not_successful_cleanup(self):
  a,j=self.fake();j.finish(True);a.fail='close'
  with self.assertRaisesRegex(RuntimeError,'CLOSE_UNCERTAIN'):j.close()
 def test_production_and_census_use_owned_process_without_legacy_stop(self):
  import inspect
  self.assertIn('OwnedProcess()',inspect.getsource(Guard.run));self.assertIn('OwnedProcess()',inspect.getsource(run_census));self.assertNotIn('stop_compiler_tree(',inspect.getsource(Guard.run));self.assertNotIn('subprocess.Popen(',inspect.getsource(run_census));self.assertNotIn('proc.terminate(',inspect.getsource(run_census))
 def test_environment_rejects_secrets_case_duplicates_and_nul(self):
  from census_supervisor import production_environment
  for env in [{'GITHUB_TOKEN':'synthetic'},{'PATH':'a','Path':'b'},{'PATH':'a'+chr(0)}]:
   with self.assertRaises(AssertionError):production_environment(env)
  self.assertTrue(production_environment({'PATH':'tools','LIB':'libs','PERL5LIB':'overlay'}).endswith(chr(0)*2))
 def test_job_and_handle_list_at_creation_before_resume(self):
  import inspect
  from census_supervisor import WindowsProductionJobAPI,OwnedProcess
  text=inspect.getsource(WindowsProductionJobAPI.create_in_job);self.assertIn('0x20002',text);self.assertIn('0x2000d',text);self.assertIn('0x4|0x400|0x08000000|0x80000',text)
  text=inspect.getsource(OwnedProcess.start);self.assertLess(text.index('self.api.in_job'),text.index('self.api.resume'));self.assertNotIn('shell=True',text)
 def test_member_overflow_and_duplicates_fail_closed(self):
  import inspect
  from census_supervisor import WindowsProductionJobAPI
  text=inspect.getsource(WindowsProductionJobAPI.members);self.assertIn('row.assigned==row.listed',text);self.assertIn('len(set(pids))',text);self.assertIn('<=256',text)

if __name__=='__main__':unittest.main()
