"""Synthetic report/evidence tests; no compiler or account access."""
import copy,contextlib,io,json,os,pathlib,tempfile,types,unittest,uuid
from unittest.mock import patch
import runtime_report as rr

def fixture(count=1,padding=0):
 commands=[]
 for i in range(1,count+1):
  commands.append({'stage':i,'tool':'synthetic.exe','exit':0,'ownedJobTeardown':{'treeState':'VERIFIED_OWNED_JOB_ZERO_MEMBERS','processTreeExitIndependentlyVerified':True,'completeActiveMemberAccounting':True,'activeMembers':0,'knownHandlesExited':True,'heldIdentityCount':1,'heldIdentities':[{'pid':i,'creationFiletime':i+100,'exited':True,'exitCode':0}],'supervisionFailures':[]},'diagnostic':{'keep':'X'*padding}})
 monitor={'minimumFreeBytes':40*1024**3,'monitoredOutputThresholdBytes':64*1024**3,'maximumSeconds':5400,'censusPending':False,'lastSnapshotComplete':True,'censusCleanupFailures':[],'commands':commands,'retainedPeakBytes':1000,'lastCompletedRootScans':[{'rootIndex':0,'complete':True,'completedRootBytes':1000}],'maximumObservedSupervisionGap':.25,'completeAdditionalDiagnostic':{'mustRemain':[1,2,'synthetic']}}
 return {'state':'PASS_RUNTIME_CONFIGURE_ONLY','packages':[{'distribution':'synthetic','version':'0'}],'requiredModuleCount':1,'configuration':{'allFields':'preserved'},'monitor':monitor}

class RuntimeReportTests(unittest.TestCase):
 def out(self):
  root=pathlib.Path(os.environ.get('RUNNER_TEMP',tempfile.gettempdir()));out=root/('report-'+uuid.uuid4().hex);out.mkdir();return out
 def write(self,report=None):
  out=self.out();report=report or fixture();summary=rr.write_runtime_report(report,out,lambda:None);return out,report,summary
 def test_normal_lossless_roundtrip(self):
  out,report,summary=self.write();actual,m=rr.read_runtime_report(out)
  self.assertEqual(actual,summary);self.assertEqual(m,report['monitor']);self.assertEqual(actual['configuration'],report['configuration'])
  self.assertTrue(all(p.stat().st_size<rr.LIMIT for p in out.rglob('*.json')))
 def test_oversized_original_is_losslessly_planned(self):
  report=fixture(80,1000);self.assertGreater(len(rr.encode(report)),rr.LIMIT)
  summary,parts,final=rr.plan_runtime_report(report);self.assertLess(len(final),rr.LIMIT)
  self.assertTrue(all(len(v)<rr.LIMIT for v in parts.values()))
  index=rr.parse(parts['runtime-evidence/index.json']);m=rr.parse(parts[index['metadata']['path']]);m['commands']=[rr.parse(parts[r['path']]) for r in index['commands']]
  self.assertEqual(m,report['monitor']);self.assertEqual(rr.digest(m),summary['monitor']['originalSHA256'])
 def test_oversized_individual_part_fails(self):
  with self.assertRaises(AssertionError):rr.plan_runtime_report(fixture(1,70000))
 def test_oversized_summary_fails(self):
  r=fixture();r['configuration']['large']='X'*70000
  with self.assertRaises(AssertionError):rr.plan_runtime_report(r)
 def test_total_bundle_bound_fails(self):
  with self.assertRaises(AssertionError):rr.plan_runtime_report(fixture(32,40000))
 def test_oversized_index_fails(self):
  with self.assertRaises(AssertionError):rr.plan_runtime_report(fixture(512))
 def test_empty_commands_fails(self):
  with self.assertRaises(AssertionError):rr.plan_runtime_report(fixture(0))
 def test_unknown_active_member_fails(self):
  r=fixture();r['monitor']['commands'][0]['ownedJobTeardown']['activeMembers']=1
  with self.assertRaises(AssertionError):rr.plan_runtime_report(r)
 def test_incomplete_held_proof_fails(self):
  r=fixture();r['monitor']['commands'][0]['ownedJobTeardown']['heldIdentityCount']=2
  with self.assertRaises(AssertionError):rr.plan_runtime_report(r)
 def test_duplicate_held_identity_fails(self):
  r=fixture();t=r['monitor']['commands'][0]['ownedJobTeardown'];t['heldIdentities']*=2;t['heldIdentityCount']=2
  with self.assertRaises(AssertionError):rr.plan_runtime_report(r)
 def test_failed_command_fails(self):
  r=fixture();r['monitor']['commands'][0]['exit']=1
  with self.assertRaises(AssertionError):rr.plan_runtime_report(r)
 def test_incomplete_census_fails(self):
  r=fixture();r['monitor']['lastCompletedRootScans'][0]['complete']=False
  with self.assertRaises(AssertionError):rr.plan_runtime_report(r)
 def test_pending_census_fails(self):
  r=fixture();r['monitor']['censusPending']=True
  with self.assertRaises(AssertionError):rr.plan_runtime_report(r)
 def test_resource_limit_change_fails(self):
  r=fixture();r['monitor']['minimumFreeBytes']=1
  with self.assertRaises(AssertionError):rr.plan_runtime_report(r)
 def test_known_output_margin_fails(self):
  r=fixture();r['monitor']['retainedPeakBytes']=64*1024**3-1
  with self.assertRaises(AssertionError):rr.plan_runtime_report(r)
 def test_missing_part_fails_closed(self):
  out,_,_=self.write();original=rr.load_bytes
  def missing(path):
   if path.name=='command-0001.json':raise FileNotFoundError('synthetic missing part')
   return original(path)
  with patch.object(rr,'load_bytes',side_effect=missing):
   with self.assertRaises(FileNotFoundError):rr.read_runtime_report(out)
 def test_mutated_part_digest_fails(self):
  out,_,_=self.write();part=out/'runtime-evidence/command-0001.json';data=rr.parse(part.read_bytes());data['tool']='changed.exe';part.write_bytes(rr.encode(data))
  with self.assertRaises(AssertionError):rr.read_runtime_report(out)
 def test_missing_diagnostic_field_cannot_be_hidden(self):
  out,_,summary=self.write();summary['monitor']['originalSHA256']='0'*64
  with self.assertRaises(AssertionError):rr.verify_bundle(out,summary)
 def test_unsafe_reference_rejected_without_read(self):
  with self.assertRaises(AssertionError):rr.read_reference(self.out(),{'path':'../private.json','bytes':1,'sha256':'0'*64})
 def test_unknown_link_tag_fails(self):
  fake=types.SimpleNamespace(lstat=lambda:types.SimpleNamespace(st_mode=0o100644,st_file_attributes=0x400,st_reparse_tag=1))
  with self.assertRaises(AssertionError):rr.metadata(fake)
 def test_root_replacement_fails_before_write(self):
  out=self.out()
  with patch.object(rr,'directory_identity',side_effect=[(1,1,1),(1,2,1)]):
   with self.assertRaises(AssertionError):rr.write_runtime_report(fixture(),out,lambda:None)
  self.assertFalse((out/'runtime-qualification.json').exists())
 def test_denied_read_preserves_partial_without_success(self):
  out=self.out()
  with patch.object(rr,'load_bytes',side_effect=PermissionError('synthetic denial')):
   with self.assertRaises(PermissionError):rr.write_runtime_report(fixture(),out,lambda:None)
  self.assertTrue((out/'runtime-evidence/metadata.json').exists());self.assertFalse((out/'runtime-qualification.json').exists())
 def test_safety_callback_failure_is_fatal(self):
  out=self.out()
  def fail():raise AssertionError('SYNTHETIC_RESOURCE_STOP')
  with self.assertRaises(AssertionError):rr.write_runtime_report(fixture(),out,fail)
  self.assertFalse((out/'runtime-qualification.json').exists())
 def test_duplicate_json_keys_fail(self):
  with self.assertRaises(AssertionError):rr.parse(b'{"a":1,"a":2}')
 def test_nonfinite_values_fail(self):
  r=fixture();r['monitor']['bad']=float('nan')
  with self.assertRaises(ValueError):rr.plan_runtime_report(r)
 def test_failure_diagnostic_bounded_without_payload(self):
  r=fixture();r['configuration']['large']='PRIVATE_SENTINEL'*6000;log=io.StringIO()
  with contextlib.redirect_stdout(log):
   with self.assertRaises(AssertionError):rr.write_runtime_report(r,self.out(),lambda:None)
  self.assertIn('FAILED_RUNTIME_REPORT_EVIDENCE',log.getvalue());self.assertNotIn('PRIVATE_SENTINEL',log.getvalue());self.assertLess(len(log.getvalue()),4096)

if __name__=='__main__':unittest.main()
