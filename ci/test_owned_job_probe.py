import unittest,pathlib,ast,inspect
import owned_job_probe as p
class HostedOwnedJobPolicy(unittest.TestCase):
 def test_fixture_compiles_and_cannot_receive_credentials(self):
  compile(p.FIXTURE,'owned_job_fixture.py','exec');self.assertIn('CREATE_NO_WINDOW',p.FIXTURE);self.assertNotIn('socket',p.FIXTURE)
 def test_clean_fixture_environment(self):
  from unittest.mock import patch
  with patch.dict(p.os.environ,{'GITHUB_TOKEN':'synthetic','AWS_SECRET_ACCESS_KEY':'synthetic'}):env=p.test_environment(pathlib.Path('D:/owned'))
  self.assertNotIn('GITHUB_TOKEN',env);self.assertNotIn('AWS_SECRET_ACCESS_KEY',env);self.assertEqual(env['PYTHONNOUSERSITE'],'1')
 def test_real_probe_has_no_compiler_or_taskkill(self):
  text=inspect.getsource(p);self.assertNotIn('taskkill',text);self.assertNotIn('cargo',text);self.assertNotIn('shell=True',text)
 def test_failure_injection_distinct_from_os_denial(self):
  self.assertIn('injectedNotOSDenial',inspect.getsource(p.failure_case));self.assertIn('INJECTED_ASSIGNMENT_FAILURE',inspect.getsource(p.InjectedFailureAPI));self.assertIn('INJECTED_RESUME_FAILURE',inspect.getsource(p.InjectedFailureAPI))
 def test_strict_owned_members_and_no_exclusion(self):
  text=inspect.getsource(p.lifecycle_case);self.assertIn('len(extras)<=2',text);self.assertIn("x['systemConsole']",text);self.assertIn('job.observe()',text);self.assertIn('zeroInnerMembers',text);self.assertIn('zeroOuterMembers',text)
 def test_bounds(self):self.assertEqual(p.MAX_SECONDS,90);self.assertEqual(p.MAX_OUTPUT,16*1024**2);self.assertEqual(p.MIN_FREE,40*1024**3)
 def test_entry_requires_trusted_commit_and_marker(self):
  text=inspect.getsource(p.main)
  for name in ['GITHUB_REPOSITORY','GITHUB_REF','GITHUB_EVENT_NAME','GITHUB_SHA','[owned-job-probe-191]']:self.assertIn(name,text)
 def test_fixed_case_inventory(self):
  text=inspect.getsource(p.qualify);self.assertIn("[('wait',False),('early',True)]",text);self.assertIn("['assign','resume']",text)
class FailureConstruction(unittest.TestCase):
 def test_duplicate_failure_cleans_unreturned_process_handles(self):
  from unittest.mock import Mock,patch
  api=Mock();api.create_suspended.return_value=(10,11);wrapper=p.InjectedFailureAPI(api,'assign')
  with patch.object(p,'duplicate_owned_handle',side_effect=OSError(5,'synthetic')):
   with self.assertRaises(OSError):wrapper.create_suspended([],None,{})
  api.terminate_unassigned.assert_called_once_with(10);self.assertEqual([c.args[0] for c in api.close.call_args_list],[11,10])
 def test_output_scan_denial_never_ignored(self):
  from unittest.mock import Mock,patch
  import types
  base=pathlib.Path('D:/synthetic-owned')
  def walk(*a,**kw):kw['onerror'](PermissionError(5,'synthetic'));return iter(())
  with patch.object(p.shutil,'disk_usage',return_value=types.SimpleNamespace(free=p.MIN_FREE+1)),patch.object(p.os,'walk',side_effect=walk):
   with self.assertRaises(PermissionError):p.resource_check(base,p.time.monotonic())
 def test_fixture_retains_files_without_rename_churn(self):
  self.assertNotIn('.rename(',p.FIXTURE);self.assertIn('.done',p.FIXTURE)

if __name__=='__main__':unittest.main()
