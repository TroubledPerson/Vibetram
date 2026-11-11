import unittest,json,pathlib
MARKER="contains(github.event.head_commit.message, '[metadata-image-only-191]')"
TRIGGER="github.event_name == 'push' && "+MARKER+" && github.ref == 'refs/heads/main' && github.repository == 'TroubledPerson/Vibetram'"
TOOL_MARKER="contains(github.event.head_commit.message, '[tool-metadata-only-191]')"
TOOL_TRIGGER="github.event_name == 'push' && contains(github.event.head_commit.message, '[tool-metadata-only-191]') && github.ref == 'refs/heads/main' && github.repository == 'TroubledPerson/Vibetram'"
class MetadataWorkflow(unittest.TestCase):
 def test_single_bounded_readonly_job(self):
  j=WORKFLOW['jobs']['metadata-image-qualification'];self.assertEqual(j['runs-on'],'windows-latest');self.assertEqual(j['timeout-minutes'],10);self.assertEqual(j['permissions'],{'contents':'read'});self.assertNotIn('needs',j)
 def test_owner_main_push_marker_required(self):self.assertEqual(WORKFLOW['jobs']['metadata-image-qualification']['if'],'('+TRIGGER+') && !'+TOOL_MARKER)
 def test_all_other_jobs_explicitly_excluded(self):
  for n,j in WORKFLOW['jobs'].items():
   with self.subTest(job=n):
    if n=='release':self.assertEqual(j['if'],'$'+'{{ false }}')
    elif n not in ('metadata-image-qualification','tool-metadata-qualification'):self.assertIn(' && !('+TRIGGER+')',j['if'])
 def test_exact_entrypoints_only(self):
  self.assertEqual([s['run'] for s in WORKFLOW['jobs']['metadata-image-qualification']['steps'] if 'run' in s],['python -B ci/'+p for p in ('check_source.py','test_metadata_workflow.py','test_process_image.py','test_host_linker.py','test_census_supervision.py')])
 def test_pinned_checkout_no_saved_credentials(self):
  self.assertEqual([s for s in WORKFLOW['jobs']['metadata-image-qualification']['steps'] if 'uses' in s],[{'uses':'actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd','with':{'persist-credentials':False}}])
 def test_no_compile_provision_upload_release(self):
  text=json.dumps(WORKFLOW['jobs']['metadata-image-qualification']);self.assertFalse(any(x in text for x in ('upload-artifact','provision_rust','cloud_build','cargo ','rustc ','contents": "write','release.py')))
 def test_global_readonly_and_cancellation_preserved(self):self.assertEqual(WORKFLOW['permissions'],{'contents':'read'});self.assertTrue(WORKFLOW['concurrency']['cancel-in-progress'])
class ToolMetadataWorkflow(unittest.TestCase):
 def test_exact_bounded_isolated_job(self):
  j=WORKFLOW["jobs"]["tool-metadata-qualification"];self.assertEqual(j["if"],TOOL_TRIGGER);self.assertEqual(j["runs-on"],"windows-latest");self.assertEqual(j["timeout-minutes"],10);self.assertEqual(j["permissions"],{"contents":"read"});self.assertNotIn("needs",j)
 def test_exact_steps_no_provision_build_upload_release(self):
  j=WORKFLOW["jobs"]["tool-metadata-qualification"];self.assertEqual(j["steps"][0],{"uses":"actions/checkout@de0fac2e4500dabe0009e67214ff5f5447ce83dd","with":{"persist-credentials":False}});self.assertEqual([x["run"] for x in j["steps"] if "run" in x],["python -B ci/"+p for p in ("check_source.py","test_tool_metadata_probe.py","test_metadata_workflow.py","test_lock_diagnostic.py","tool_metadata_probe.py")]);self.assertEqual(len(j["steps"]),6)
 def test_all_marker_combinations_leave_only_metadata_job(self):
  from test_lock_diagnostic import EntryGateConsistency
  evaluator=EntryGateConsistency()
  for message in ("[tool-metadata-only-191]","[tool-metadata-only-191] [unsigned-trial-191]","[tool-metadata-only-191] [metadata-image-only-191]","[tool-metadata-only-191] [unsigned-trial-191] [metadata-image-only-191] [overlay-probe-191]"):
   for name,j in WORKFLOW["jobs"].items():
    expression=j["if"] if name!="release" else "false"
    with self.subTest(message=message,job=name):self.assertEqual(evaluator.workflow_condition(expression,"push","TroubledPerson/Vibetram","refs/heads/main",message),name=="tool-metadata-qualification")
 def test_source_checks_include_probe_regressions_once(self):
  self.assertEqual(sum(s.get("run")=="python -B ci/test_tool_metadata_probe.py" for s in WORKFLOW["jobs"]["source-checks"]["steps"]),1)

if __name__=='__main__':
 WORKFLOW=json.loads((pathlib.Path(__file__).resolve().parents[1]/'.github/workflows/offline-android.yml').read_text());unittest.main()
