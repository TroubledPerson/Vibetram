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
  import re
  self.assertIsInstance(expression,str);self.assertTrue(0<len(expression)<=4096)
  # Tokenize GitHub operators outside single-quoted literals; never eval source.
  tokens=[];i=0;depth=0
  names=set(values)|{"contains","true","false"}
  while i<len(expression):
   c=expression[i]
   if c.isspace():i+=1;continue
   if c=="'":
    i+=1;text=[];closed=False
    while i<len(expression):
     if expression[i]=="'":
      if i+1<len(expression) and expression[i+1]=="'":text.append("'");i+=2;continue
      i+=1;closed=True;break
     text.append(expression[i]);i+=1
    self.assertTrue(closed,"Unclosed workflow string");self.assertLessEqual(len(text),2048);tokens.append(repr("".join(text)))
   elif expression[i:i+2] in ("&&","||","==","!="):
    op=expression[i:i+2];tokens.append({"&&":"and","||":"or","==":"==","!=":"!="}[op]);i+=2
   elif c=="!":tokens.append("not");i+=1
   elif c in "(),":
    if c=="(":depth+=1;self.assertLessEqual(depth,32)
    elif c==")":depth-=1;self.assertGreaterEqual(depth,0)
    tokens.append(c);i+=1
   else:
    token=re.match(r"[A-Za-z_][A-Za-z0-9_.]*",expression[i:]);self.assertIsNotNone(token,"Unreviewed workflow token");word=token.group();self.assertIn(word,names);tokens.append(word);i+=len(word)
   self.assertLessEqual(len(tokens),128)
  self.assertEqual(depth,0)
  # Parse the reviewed subset with ! above comparisons, then &&, then ||.
  position=0
  def take(token):
   nonlocal position
   if position<len(tokens) and tokens[position]==token:position+=1;return True
   return False
  def need(token):self.assertTrue(take(token),"Missing workflow delimiter")
  def primary():
   nonlocal position
   self.assertLess(position,len(tokens),"Missing workflow operand")
   if take("("):node=disjunction();need(")");return node
   token=tokens[position];position+=1
   if token=="contains":
    need("(");left=disjunction();need(",");right=disjunction();need(")");return ast.Call(func=ast.Name(id="contains",ctx=ast.Load()),args=[left,right],keywords=[])
   self.assertNotIn(token,("not","and","or","==","!=",")",","));return ast.parse(token,mode="eval").body
  def unary():
   if take("not"):return ast.UnaryOp(op=ast.Not(),operand=unary())
   return primary()
  def comparison():
   left=unary()
   if position<len(tokens) and tokens[position] in ("==","!="):
    op=tokens[position];need(op);return ast.Compare(left=left,ops=[ast.Eq() if op=="==" else ast.NotEq()],comparators=[unary()])
   return left
  def conjunction():
   values=[comparison()]
   while take("and"):values.append(comparison())
   return values[0] if len(values)==1 else ast.BoolOp(op=ast.And(),values=values)
  def disjunction():
   values=[conjunction()]
   while take("or"):values.append(conjunction())
   return values[0] if len(values)==1 else ast.BoolOp(op=ast.Or(),values=values)
  tree=ast.Expression(body=disjunction());self.assertEqual(position,len(tokens),"Unconsumed workflow syntax");self.assertLess(len(list(ast.walk(tree))),128)
  def value(n):
   if isinstance(n,ast.Expression):return value(n.body)
   if isinstance(n,ast.Constant):self.assertIsInstance(n.value,str);return n.value
   if isinstance(n,ast.Attribute):key=ast.unparse(n);self.assertIn(key,values);return values[key]
   if isinstance(n,ast.Name):
    self.assertIn(n.id,("true","false"));return n.id=="true"
   if isinstance(n,ast.UnaryOp):
    self.assertIsInstance(n.op,ast.Not);item=value(n.operand);self.assertIs(type(item),bool);return not item
   if isinstance(n,ast.BoolOp):
    items=[value(x) for x in n.values]
    for item in items:self.assertIs(type(item),bool)
    if isinstance(n.op,ast.And):return all(items)
    self.assertIsInstance(n.op,ast.Or);return any(items)
   if isinstance(n,ast.Compare):
    self.assertEqual(len(n.ops),1);self.assertIsInstance(n.ops[0],(ast.Eq,ast.NotEq));left=value(n.left);right=value(n.comparators[0]);self.assertIs(type(left),type(right));same=left==right;return same if isinstance(n.ops[0],ast.Eq) else not same
   if isinstance(n,ast.Call):
    self.assertIsInstance(n.func,ast.Name);self.assertEqual(n.func.id,"contains");self.assertEqual(len(n.args),2);self.assertFalse(n.keywords)
    hay,needle=[value(x) for x in n.args];self.assertIsInstance(needle,str);return isinstance(hay,str) and needle in hay
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

class ExpressionRegression(unittest.TestCase):
 workflow_condition=EntryGateConsistency.workflow_condition
 def evaluate(self,s):return self.workflow_condition(s,"push","TroubledPerson/Vibetram","refs/heads/main","literal ! != && || it's")
 def test_unary_binds_before_comparison_and_strict_types(self):
  self.assertTrue(self.evaluate("!false == true"));self.assertFalse(self.evaluate("!true == true"));self.assertTrue(self.evaluate("!(false == true)"))
  for text in ("!'a' == 'b'","'a' != !false","true == 'true'","contains('x','x','x')"):
   with self.subTest(text=text),self.assertRaises((AssertionError,SyntaxError)):self.evaluate(text)
 def test_unary_precedence(self):
  for text,expected in [("!false && false",False),("!false || false",True),("false || !false && false",False),("!(false || true)",False),("!('a' == 'b')",True)]:
   with self.subTest(text=text):self.assertEqual(self.evaluate(text),expected)
 def test_parentheses_and_double_negation(self):
  for text,expected in [("!!true",True),("!!!true",False),("!(!false)",False),("!(false && (true || false))",True)]:
   with self.subTest(text=text):self.assertEqual(self.evaluate(text),expected)
 def test_inequality_and_quoted_operators_untouched(self):
  self.assertTrue(self.evaluate("'a!=! &&||' != 'different'"));self.assertFalse(self.evaluate("'a!=! &&||' != 'a!=! &&||'"));self.assertTrue(self.evaluate("contains(github.event.head_commit.message, 'it''s')"));self.assertTrue(self.evaluate("contains(github.event.head_commit.message, '! != && ||')"));self.assertTrue(self.evaluate("github.event_name != 'pull_request' && !false"))
 def test_unsupported_or_malformed_is_fatal(self):
  for text in (""," "*4097,"'unclosed","true &&","(true","true)","unknown","__import__('os')","true + false","true and false","! 'string'","contains('x', true)","true == false == true","!"*129+"true","("*33+"true"+")"*33):
   with self.subTest(text=text),self.assertRaises((AssertionError,SyntaxError)):self.evaluate(text)
 def test_all_actual_job_gates_full_context_matrix(self):
  w=EntryGateConsistency.workflow(self);probe={"owned-job-probe":"owned-job-probe","overlay-probe":"overlay-probe","perl-runtime":"perl-runtime","ndk-metadata":"ndk-metadata","openssl-probe":"openssl-probe","msvc-probe":"msvc-probe"}
  messages=["[configure-hook-only-191]","[configure-hook-only-191] [unsigned-trial-191]","[configure-hook-only-191] [openssl-probe-191]","[configure-hook-only-191] [metadata-image-only-191]","[configure-hook-only-191] [tool-metadata-only-191]","[tool-metadata-only-191]","[tool-metadata-only-191] [unsigned-trial-191]","[tool-metadata-only-191] [metadata-image-only-191]","[tool-metadata-only-191] [unsigned-trial-191] [metadata-image-only-191] [overlay-probe-191]","ordinary",None,"[unsigned-trial-191]","[lock-diagnostic-191]","[metadata-image-only-191]","[unsigned-trial-191] [metadata-image-only-191]","[lock-diagnostic-191] [metadata-image-only-191]"]+["["+m+"-191]" for m in probe.values()]
  for event in ("push","pull_request","workflow_dispatch"):
   for repo in ("TroubledPerson/Vibetram","other/Vibetram"):
    for ref in ("refs/heads/main","refs/heads/other"):
     for message in messages:
      trusted=repo=="TroubledPerson/Vibetram" and ref=="refs/heads/main";push=trusted and event=="push";has=lambda m:isinstance(message,str) and "["+m+"-191]" in message;metadata=push and has("metadata-image-only")
      expected={"source-checks":not metadata,"metadata-image-qualification":metadata,"unsigned-qualification":push and has("unsigned-trial") and not metadata,"lock-diagnostic":push and (has("unsigned-trial") or has("lock-diagnostic")) and not metadata,"runner-preflight":trusted and event!="pull_request" and not metadata,"release":False}
      expected.update({n:push and has(m) and not metadata for n,m in probe.items()})
      tool_metadata=push and has("tool-metadata-only")
      if tool_metadata:expected={name:False for name in expected}
      expected["tool-metadata-qualification"]=tool_metadata
      if has("configure-hook-only"):
       expected={name:(value if name in ("source-checks","runner-preflight") else False) for name,value in expected.items()}
       expected["openssl-probe"]=push and not metadata and not tool_metadata
      self.assertEqual(set(w["jobs"]),set(expected))
      for name,job in w["jobs"].items():
       expression=job["if"] if name!="release" else "false"
       with self.subTest(job=name,event=event,repo=repo,ref=ref,message=message):self.assertEqual(self.workflow_condition(expression,event,repo,ref,message),expected[name])
 def test_metadata_exclusion_is_restrictive_not_script_bypass(self):
  from lock_diagnostic import allowed_entry
  message="[unsigned-trial-191] [metadata-image-only-191]";w=EntryGateConsistency.workflow(self);self.assertTrue(allowed_entry("push","TroubledPerson/Vibetram","refs/heads/main",message));self.assertFalse(self.workflow_condition(w["jobs"]["unsigned-qualification"]["if"],"push","TroubledPerson/Vibetram","refs/heads/main",message));self.assertFalse(self.workflow_condition(w["jobs"]["lock-diagnostic"]["if"],"push","TroubledPerson/Vibetram","refs/heads/main",message))

if __name__=='__main__':unittest.main()

