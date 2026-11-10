import unittest
from lock_diagnostic import lock_delta,resolve_link,allowed_cargo
class DiagnosticPolicy(unittest.TestCase):
 def test_native_commands_denied(self):
  for verb in ('build','test','check','run','install'):self.assertFalse(allowed_cargo([verb]))
 def test_metadata_locked_only(self):
  self.assertTrue(allowed_cargo(['metadata','--locked','--format-version','1']));self.assertFalse(allowed_cargo(['metadata']))
 def test_proposal_offline_workspace_only(self):
  self.assertTrue(allowed_cargo(['update','--workspace','--offline']));self.assertFalse(allowed_cargo(['update']))
 def test_equal_pins(self):
  d={'package':[{'name':'a','version':'1','source':'registry+https://example.invalid','checksum':'a','dependencies':['b']}]};self.assertTrue(lock_delta(d,d)['externalIdentitiesAndChecksumsUnchanged'])
 def test_local_edge_delta_no_external_upgrade(self):
  a={'package':[{'name':'local','version':'0','dependencies':['a']}]};b={'package':[{'name':'local','version':'0','dependencies':['a','b']}]};r=lock_delta(a,b);self.assertTrue(r['externalIdentitiesAndChecksumsUnchanged']);self.assertEqual(len(r['changedEntries']),1)
 def test_version_change_detected(self):
  a={'package':[{'name':'a','version':'1','source':'registry+https://example.invalid','checksum':'a'}]};b={'package':[{'name':'a','version':'2','source':'registry+https://example.invalid','checksum':'b'}]};self.assertFalse(lock_delta(a,b)['externalIdentitiesAndChecksumsUnchanged'])
 def test_checksum_change_detected(self):
  a={'package':[{'name':'a','version':'1','source':'registry+https://example.invalid','checksum':'a'}]};b={'package':[{'name':'a','version':'1','source':'registry+https://example.invalid','checksum':'b'}]};self.assertFalse(lock_delta(a,b)['externalIdentitiesAndChecksumsUnchanged'])
 def test_internal_license_target(self):
  e={'sub/LICENSE':{'mode':'120000','target':'../LICENSE'},'LICENSE':{'mode':'100644','sha':'a'}};self.assertEqual(resolve_link(e,'sub/LICENSE')[0],'LICENSE')
 def test_link_escape(self):
  with self.assertRaises(AssertionError):resolve_link({'LICENSE':{'mode':'120000','target':'../outside'}},'LICENSE')
 def test_link_absolute(self):
  with self.assertRaises(AssertionError):resolve_link({'LICENSE':{'mode':'120000','target':'C:/private'}},'LICENSE')
 def test_link_cycle(self):
  with self.assertRaises(AssertionError):resolve_link({'LICENSE':{'mode':'120000','target':'LICENSE'}},'LICENSE')


class EntryGateConsistency(unittest.TestCase):
 def workflow_condition(self,expression,event,repo,ref,message):
  # Interpret only this small Boolean GitHub-expression subset. Never eval source.
  import ast
  values={"github.event_name":event,"github.repository":repo,"github.ref":ref,"github.event.head_commit.message":message}
  tree=ast.parse(expression.replace("&&"," and ").replace("||"," or "),mode="eval");self.assertLess(len(list(ast.walk(tree))),128)
  def value(n):
   if isinstance(n,ast.Expression):return value(n.body)
   if isinstance(n,ast.Constant):self.assertIsInstance(n.value,str);return n.value
   if isinstance(n,ast.Attribute):key=ast.unparse(n);self.assertIn(key,values);return values[key]
   if isinstance(n,ast.BoolOp):
    items=[value(x) for x in n.values]
    if isinstance(n.op,ast.And):return all(items)
    self.assertIsInstance(n.op,ast.Or);return any(items)
   if isinstance(n,ast.Compare):self.assertEqual(len(n.ops),1);self.assertIsInstance(n.ops[0],ast.Eq);return value(n.left)==value(n.comparators[0])
   if isinstance(n,ast.Call):
    self.assertIsInstance(n.func,ast.Name);self.assertEqual(n.func.id,"contains");self.assertEqual(len(n.args),2);self.assertFalse(n.keywords)
    hay,needle=[value(x) for x in n.args];return isinstance(hay,str) and needle in hay
   raise AssertionError("Unreviewed workflow expression node: "+type(n).__name__)
  return value(tree)
 def workflow(self):
  import json,pathlib
  return json.loads((pathlib.Path(__file__).resolve().parents[1]/".github/workflows/offline-android.yml").read_text())
 def test_workflow_and_script_gate_match_full_matrix(self):
  from lock_diagnostic import allowed_entry
  condition=self.workflow()["jobs"]["lock-diagnostic"]["if"]
  for event in ("push","pull_request","workflow_dispatch"):
   for repo in ("TroubledPerson/Vibetram","untrusted/Vibetram","TroubledPerson/Other"):
    for ref in ("refs/heads/main","refs/heads/other","refs/pull/1/merge"):
     for message in ("ordinary","[unsigned-trial-191]","[lock-diagnostic-191]","[unsigned-trial-191] [lock-diagnostic-191]","[openssl-probe-191]",None):
      with self.subTest(event=event,repo=repo,ref=ref,message=message):self.assertEqual(self.workflow_condition(condition,event,repo,ref,message),allowed_entry(event,repo,ref,message))
 def test_exact_marker_set_not_assertion_removed(self):
  from lock_diagnostic import ENTRY_MARKERS,allowed_entry
  self.assertEqual(set(ENTRY_MARKERS),{"[unsigned-trial-191]","[lock-diagnostic-191]"})
  self.assertFalse(allowed_entry("push","TroubledPerson/Vibetram","refs/heads/main",None));self.assertFalse(allowed_entry("push","TroubledPerson/Vibetram","refs/heads/main","ordinary"))
 def test_main_assert_calls_predicate(self):
  import ast,inspect,lock_diagnostic
  tree=ast.parse(inspect.getsource(lock_diagnostic.main))
  calls=[n.test for n in ast.walk(tree) if isinstance(n,ast.Assert) and isinstance(n.test,ast.Call) and isinstance(n.test.func,ast.Name) and n.test.func.id=="allowed_entry"]
  self.assertEqual(len(calls),1);self.assertEqual(len(calls[0].args),4)
 def test_unsigned_gate_matches_actual_build_entry(self):
  import inspect,cloud_build
  condition=self.workflow()["jobs"]["unsigned-qualification"]["if"]
  for event,repo,ref,message,expected in [("push","TroubledPerson/Vibetram","refs/heads/main","[unsigned-trial-191]",True),("push","TroubledPerson/Vibetram","refs/heads/main","[lock-diagnostic-191]",False),("pull_request","TroubledPerson/Vibetram","refs/heads/main","[unsigned-trial-191]",False),("push","other/Vibetram","refs/heads/main","[unsigned-trial-191]",False),("push","TroubledPerson/Vibetram","refs/heads/other","[unsigned-trial-191]",False)]:
   self.assertEqual(self.workflow_condition(condition,event,repo,ref,message),expected)
  source=inspect.getsource(cloud_build.main);self.assertIn("assert '[unsigned-trial-191]' in event['head_commit']['message']",source)
 def test_build_roots_equal_bootstrap_owned_pair(self):
  import cloud_build,perl_overlay
  self.assertTrue(perl_overlay.owned_pair(cloud_build.ROOT,cloud_build.WORK,cloud_build.OUT));self.assertEqual(cloud_build.WORK,cloud_build.ROOT/"ci-work");self.assertEqual(cloud_build.OUT,cloud_build.ROOT/"dist")
 def test_qualification_and_host_restore_precede_any_cargo(self):
  import ast,inspect,cloud_build
  tree=ast.parse(inspect.getsource(cloud_build.main));calls=[n for n in ast.walk(tree) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)]
  bootstrap=[n.lineno for n in calls if n.func.id=="bootstrap_for_cargo"];smoke=[n.lineno for n in calls if n.func.id=="qualify_make_link"]
  cargo=[n.lineno for n in calls if n.func.id=="run" and n.args and isinstance(n.args[0],ast.List) and n.args[0].elts and isinstance(n.args[0].elts[0],ast.Constant) and n.args[0].elts[0].value=="cargo"]
  restore=[n.lineno for n in ast.walk(tree) if isinstance(n,ast.Assign) and isinstance(n.value,ast.Name) and n.value.id=="ENV" and any(isinstance(t,ast.Attribute) and isinstance(t.value,ast.Name) and t.value.id=="GUARD" and t.attr=="env" for t in n.targets)]
  self.assertEqual(len(bootstrap),1);self.assertEqual(len(smoke),1);self.assertEqual(len(restore),2);late=[n for n in restore if n>smoke[0]];self.assertEqual(len(late),1);self.assertLess(bootstrap[0],smoke[0]);self.assertLess(late[0],min(cargo))
 def test_shared_entry_imports_exist(self):
  import ast,inspect,importlib,perl_overlay
  for fn in (perl_overlay.qualify_prepared_runtime,perl_overlay.bootstrap_for_cargo,perl_overlay.qualify_make_link):
   for node in ast.walk(ast.parse(inspect.getsource(fn))):
    if isinstance(node,ast.ImportFrom):
     module=importlib.import_module(node.module)
     for alias in node.names:self.assertTrue(hasattr(module,alias.name))
 def test_prerequisites_and_release_stay_fail_closed(self):
  w=self.workflow();build=w["jobs"]["unsigned-qualification"];self.assertIn("lock-diagnostic",build["needs"]);self.assertEqual(build["permissions"],{"contents":"read"});self.assertEqual(w["jobs"]["release"]["if"],chr(36)+"{{ false }}")

if __name__=='__main__':unittest.main()

