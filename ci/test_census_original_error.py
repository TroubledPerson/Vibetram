import unittest,pathlib,types,json,io,time
from unittest.mock import patch
from census_supervisor import census_diagnostic,validate_census_diagnostic,CensusFailure
from build_guard import Guard,qualified_ordinary_churn,MIN_FREE
from test_alias_accounting import guard
from test_scratch_snapshot import FakeAPI,ROOT,P
TEMP=P.parent/'serde_with_macros-0200f88160ed189c.dll.tmpa87e45f'
LOC={'phase':'FILE_ENTRY_METADATA','rootIndex':0,'relative':TEMP.relative_to(ROOT).as_posix()}
def missing(filename=TEMP,code=2):
 e=FileNotFoundError(2,'PRIVATE_TEXT',None if filename is None else str(filename));e.winerror=code;return e
def wrapped(cause):
 try:raise cause
 except BaseException as e:
  try:raise AssertionError('UNVERIFIED_FILE_DISAPPEARANCE') from e
  except AssertionError as out:return out
def diagnostic(e):return census_diagnostic(e,[ROOT],LOC)
class NestedMetadata(unittest.TestCase):
 def test_actual_nested_not_found(self):
  r=diagnostic(wrapped(missing()));self.assertEqual(r['failureCode'],'UNVERIFIED_FILE_DISAPPEARANCE');self.assertEqual(r['errorClass'],'FileNotFoundError');self.assertEqual((r['errno'],r['winerror']),(2,2));self.assertEqual(r['relative'],LOC['relative']);self.assertEqual(r['entrySource'],'OS_FILENAME');self.assertFalse(r['partialTotalAccepted']);self.assertEqual(validate_census_diagnostic(r),r);self.assertNotIn('PRIVATE_TEXT',json.dumps(r))
 def test_path_not_found_retained_but_not_accepted(self):
  r=diagnostic(wrapped(missing(code=3)));self.assertEqual(r['winerror'],3);self.assertEqual(r['failureCode'],'UNVERIFIED_FILE_DISAPPEARANCE');self.assertFalse(r['partialTotalAccepted'])
 def test_missing_codes_retained_as_unknown(self):
  e=FileNotFoundError();r=diagnostic(wrapped(e));self.assertIsNone(r['errno']);self.assertIsNone(r['winerror'])
 def test_outside_root_withheld(self):
  r=diagnostic(wrapped(missing('C:/Users/private-owner/private-file')));self.assertIsNone(r['relative']);self.assertIsNone(r['rootIndex']);self.assertNotIn('private',json.dumps(r))
 def test_oversized_filename_rejected_before_path_parse(self):
  e=wrapped(missing('D:/'+('x'*5000)))
  with patch('census_supervisor.pathlib.Path',side_effect=AssertionError('MUST_NOT_PARSE_OVERSIZE')):r=diagnostic(e)
  self.assertIsNone(r['relative']);self.assertEqual(r['entrySource'],'INVALID_OS_FILENAME');self.assertLess(len(json.dumps(r)),600)
 def test_unsafe_and_oversized_relative_withheld(self):
  for name in (ROOT/'target/private@example.invalid',ROOT/('x'*241),ROOT/'target/../outside'):
   r=diagnostic(wrapped(missing(name)));self.assertIsNone(r['relative']);self.assertNotIn('private',json.dumps(r))
 def test_missing_filename_uses_labeled_operation_context(self):
  r=diagnostic(wrapped(missing(None)));self.assertEqual(r['entrySource'],'LAST_OPERATION_CONTEXT');self.assertEqual(r['relative'],LOC['relative'])
 def test_no_explicit_cause_does_not_infer(self):
  try:raise missing()
  except FileNotFoundError:
   try:raise AssertionError('UNVERIFIED_FILE_DISAPPEARANCE')
   except AssertionError as out:e=out
  r=diagnostic(e);self.assertEqual(r['errorClass'],'AssertionError');self.assertIsNone(r['errno'])
 def test_unknown_cause_not_walked(self):
  inner=wrapped(missing());r=diagnostic(wrapped(inner));self.assertEqual(r['errorClass'],'AssertionError');self.assertIsNone(r['winerror'])
 def test_cyclic_chain_not_walked(self):
  e=AssertionError('UNVERIFIED_FILE_DISAPPEARANCE');e.__cause__=e;r=diagnostic(e);self.assertEqual(r['errorClass'],'AssertionError')
 def test_different_wrapper_unchanged(self):
  e=AssertionError('DIFFERENT_FATAL');e.__cause__=missing();r=diagnostic(e);self.assertEqual(r['failureCode'],'DIFFERENT_FATAL');self.assertEqual(r['errorClass'],'AssertionError')
 def test_custom_subclass_not_trusted(self):
  class Custom(FileNotFoundError):pass
  r=diagnostic(wrapped(Custom(2,'PRIVATE_TEXT')));self.assertEqual(r['errorClass'],'AssertionError')
 def test_denial_not_reclassified(self):
  r=diagnostic(PermissionError(13,'PRIVATE_TEXT'));self.assertEqual(r['failureCode'],'CENSUS_PERMISSION_DENIED');self.assertEqual(r['errno'],13);self.assertFalse(r['partialTotalAccepted'])
 def test_reparse_and_replacement_fatal_unchanged(self):
  for code in ('UNQUALIFIED_OUTPUT_DIRECTORY_LINK','SCRATCH_PARENT_REPLACED'):
   e=AssertionError(code);e.__cause__=missing();r=diagnostic(e);self.assertEqual(r['failureCode'],code);self.assertEqual(r['errorClass'],'AssertionError')
 def test_numeric_bounds_and_bool_rejected(self):
  for value in (True,2**40,'PRIVATE_TEXT'):
   e=missing();e.winerror=value;r=diagnostic(wrapped(e));self.assertIsNone(r['winerror']);validate_census_diagnostic(r)
 def test_no_dll_churn_authorization(self):
  for code in (2,3):self.assertFalse(qualified_ordinary_churn(ROOT,TEMP,missing(code=code)))
class ActualWalker(unittest.TestCase):
 def failure(self,error):
  g=guard();api=FakeAPI()
  def walk(root,followlinks,onerror):yield str(TEMP.parent),[],[TEMP.name]
  with patch('scratch_snapshot.MetadataAPI',return_value=api),patch('build_guard.os.walk',walk),patch('build_guard.os.lstat',side_effect=error),patch.object(pathlib.Path,'exists',return_value=True),patch.object(pathlib.Path,'is_symlink',return_value=False),patch.object(pathlib.Path,'is_junction',return_value=False):
   try:g._walk(None)
   except BaseException as e:return g,e,api
  self.fail('MISSING_FATAL_ERROR')
 def test_actual_walker_preserves_explicit_cause(self):
  g,e,api=self.failure(missing());self.assertIs(type(e),AssertionError);self.assertIs(type(e.__cause__),FileNotFoundError);r=census_diagnostic(e,g.roots,g.census_location);self.assertEqual(r['failureCode'],'UNVERIFIED_FILE_DISAPPEARANCE');self.assertEqual(r['winerror'],2);self.assertFalse(r['partialTotalAccepted']);self.assertEqual(len(api.opened),len(api.closed))
 def test_actual_walker_permission_not_absence(self):
  g,e,api=self.failure(PermissionError(13,'PRIVATE_TEXT'));self.assertIs(type(e),PermissionError);self.assertEqual(diagnostic(e)['failureCode'],'CENSUS_PERMISSION_DENIED')
 def test_worker_transports_original_without_partial_acceptance(self):
  import census_worker
  spec={'root':str(ROOT),'work':str(ROOT),'out':str(ROOT.parent/'out'),'cargo':str(ROOT.parent/'cargo'),'rustup':str(ROOT.parent/'rustup'),'globalStart':time.monotonic()}
  req={'nonce':'a'*32,'generation':1,'specHash':census_worker.spec_hash(spec),'spec':spec,'state':{},'deadline':time.monotonic()+30}
  output=io.StringIO();stdin=types.SimpleNamespace(buffer=io.BytesIO((json.dumps(req)+'\n').encode()))
  def fail(g,deadline):
   g._census_at('FILE_ENTRY_METADATA',g.work,TEMP);raise wrapped(missing())
  with patch('census_worker.sys.stdin',stdin),patch('census_worker.sys.stdout',output),patch.object(Guard,'scan_epoch',fail):
   with self.assertRaises(SystemExit):census_worker.main()
  row=json.loads(output.getvalue());r=validate_census_diagnostic(row['payload']['diagnostic']);self.assertEqual(row['kind'],'error');self.assertEqual(row['code'],'UNVERIFIED_FILE_DISAPPEARANCE');self.assertEqual(r['winerror'],2);self.assertFalse(r['partialTotalAccepted']);self.assertIsNone(row['payload']['state']['last_completed_bytes']);self.assertNotIn('PRIVATE_TEXT',output.getvalue())
 def test_fatal_wrapper_does_not_rescan_or_accept_total(self):
  g=guard();g.start=time.monotonic();g.last_completed_bytes=None;g.snapshot_incomplete=0
  with patch.object(g,'_size_once',side_effect=wrapped(missing())) as attempt,patch.object(g,'_enumeration_resources',return_value=None):
   with self.assertRaisesRegex(AssertionError,'UNVERIFIED_FILE_DISAPPEARANCE'):g.scan_epoch(time.monotonic()+30)
  self.assertEqual(attempt.call_count,1);self.assertIsNone(g.last_completed_bytes);self.assertEqual(g.snapshot_incomplete,0)
