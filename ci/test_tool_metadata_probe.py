import unittest,io,types,hashlib,json,pathlib,ast,inspect
import tool_metadata_probe as t
class FakeAPI:
 def __init__(self,data=b"MZabc",change=None,missing=False,denied=False,closefail=False):
  self.data=data;self.change=change;self.missing=missing;self.denied=denied;self.closefail=closefail;self.reads=0;self.handles=[];self.closed=[];self.infos={}
 def open(self,path):
  if path.endswith("tool.exe") and (self.missing or self.denied):
   e=OSError(2 if self.missing else 5,"synthetic");e.winerror=e.errno;raise e
  self.handles.append(path);return path
 def info(self,h):
  self.infos[h]=self.infos.get(h,0)+1;file=h.endswith("tool.exe");identity=[1,0,2 if file else len(h)]
  if self.reads and self.change=="file" and file:identity[-1]+=1
  if self.reads and self.change=="ancestor" and h==r"C:\owned":identity[-1]+=1
  return {"identity":identity,"attributes":0 if file else 0x10,"tag":0xA000000C if self.change=="link" and file else 0,"bytes":len(self.data) if file else 0,"modified100ns":[0,7 if not(self.reads and self.change=="mtime" and file) else 8]}
 def read(self,path):
  self.reads+=1
  if self.change=="read-denial":raise PermissionError(5,"synthetic")
  return io.BytesIO(self.data[:-1] if self.change=="partial" else self.data)
 def close(self,h):
  self.closed.append(h)
  if self.closefail:raise OSError(5,"synthetic")
class Probe(unittest.TestCase):
 def budget(self):return t.Budget(clock=lambda:0,free=lambda:t.MIN_FREE+1)
 def spec(self):return {"name":"fixture","path":r"C:\owned\tool.exe","root":r"C:\owned","role":"fixture-only","kind":"image"}
 def test_stable_metadata_hash_size_and_closed_handles(self):
  a=FakeAPI();r=t.inspect_input(self.spec(),a,self.budget());self.assertEqual(r["sha256"],hashlib.sha256(a.data).hexdigest());self.assertEqual(r["bytes"],5);self.assertFalse(r["overExecutionImageLimit"]);self.assertEqual(len(a.closed),len(a.handles));self.assertFalse(r["linkFollowed"])
 def test_missing_is_unresolved_not_zero_or_qualified(self):
  a=FakeAPI(missing=True);r=t.inspect_input(self.spec(),a,self.budget());self.assertEqual(r["status"],"UNAVAILABLE_UNRESOLVED");self.assertNotIn("bytes",r);self.assertEqual(a.reads,0);self.assertEqual(len(a.closed),len(a.handles))
 def test_denial_fails_and_closes(self):
  for change in ("open","read"):
   a=FakeAPI(denied=change=="open",change="read-denial" if change=="read" else None)
   with self.subTest(change=change),self.assertRaises(t.Stop):t.inspect_input(self.spec(),a,self.budget())
   self.assertEqual(len(a.closed),len(a.handles))
 def test_replacement_ancestor_and_mtime_fail(self):
  for change in ("file","ancestor","mtime"):
   a=FakeAPI(change=change)
   with self.subTest(change=change),self.assertRaisesRegex(t.Stop,"CHANGED"):t.inspect_input(self.spec(),a,self.budget())
   self.assertEqual(len(a.closed),len(a.handles))
 def test_reparse_never_followed_or_read(self):
  a=FakeAPI(change="link")
  with self.assertRaisesRegex(t.Stop,"REPARSE"):t.inspect_input(self.spec(),a,self.budget())
  self.assertEqual(a.reads,0);self.assertEqual(len(a.closed),len(a.handles))
 def test_path_escape_unc_relative_and_depth_fail(self):
  for path in (r"C:\owned\..\other\tool.exe",r"\\server\owned\tool.exe","relative.exe","C:\\"+"a\\"*33+"tool.exe",r"D:\other\tool.exe"):
   a=FakeAPI();s=self.spec();s["path"]=path
   with self.subTest(path=path),self.assertRaises(t.Stop):t.inspect_input(s,a,self.budget())
   self.assertEqual(a.handles,[])
 def test_partial_read_not_accepted(self):
  with self.assertRaisesRegex(t.Stop,"INCOMPLETE"):t.inspect_input(self.spec(),FakeAPI(change="partial"),self.budget())
 def test_close_failure_is_explicit_even_with_primary_error(self):
  for change in (None,"link"):
   a=FakeAPI(change=change,closefail=True)
   with self.assertRaisesRegex(t.Stop,"CLOSE_UNCONFIRMED") as e:t.inspect_input(self.spec(),a,self.budget())
   if change:self.assertEqual(e.exception.primary,"REPARSE_INPUT_STOP")
 def test_invalid_image_header(self):
  with self.assertRaisesRegex(t.Stop,"HEADER"):t.inspect_input(self.spec(),FakeAPI(data=b"invalid"),self.budget())
 def test_file_limit_fails_before_read(self):
  a=FakeAPI();old=a.info
  def big(h):return {**old(h),"bytes":t.MAX_FILE+1} if h.endswith("tool.exe") else old(h)
  a.info=big
  with self.assertRaisesRegex(t.Stop,"FILE_READ_BOUND"):t.inspect_input(self.spec(),a,self.budget())
  self.assertEqual(a.reads,0)
 def test_total_read_and_invalid_charge_bounds(self):
  b=self.budget();b.bytes=t.MAX_TOTAL
  with self.assertRaisesRegex(t.Stop,"TOTAL_READ"):t.inspect_input(self.spec(),FakeAPI(),b)
  for x in (-1,True,t.MAX_TOTAL+1):
   with self.subTest(x=x),self.assertRaises(t.Stop):self.budget().charge(x)
 def test_time_gap_and_free_bounds(self):
  clock=[0];b=t.Budget(clock=lambda:clock[0],free=lambda:t.MIN_FREE+1);clock[0]=t.MAX_SECONDS+1
  with self.assertRaisesRegex(t.Stop,"DEADLINE"):b.pulse()
  clock[0]=0;b=t.Budget(clock=lambda:clock[0],free=lambda:t.MIN_FREE+1);clock[0]=1.01
  with self.assertRaisesRegex(t.Stop,"MISSED"):b.pulse()
  with self.assertRaisesRegex(t.Stop,"FREE_SPACE"):t.Budget(clock=lambda:0,free=lambda:t.MIN_FREE-1).pulse()
 def test_blocked_free_sample_fatal(self):
  clock=[0]
  def slow():clock[0]+=1.01;return t.MIN_FREE+1
  with self.assertRaisesRegex(t.Stop,"BLOCKED"):t.Budget(clock=lambda:clock[0],free=slow).pulse()
 def test_revision_matching_without_raw_disclosure(self):
  self.assertTrue(t.revision_matches("package","Pkg.Revision = 30.0.16248370\n","30.0.16248370"));self.assertFalse(t.revision_matches("package","Pkg.Revision = other","30.0.16248370"));self.assertTrue(t.revision_matches("jdk",'JAVA_VERSION="17.0.21"',"17"));self.assertFalse(t.revision_matches("jdk",'JAVA_VERSION="21.0.1"',"17"))
 def test_inventory_both_clang_and_no_clang_cl(self):
  specs,u=t.inventory({},which=lambda *a,**k:None);names={x["name"] for x in specs};self.assertIn("ndk-clang.exe",names);self.assertIn("ndk-clang++.exe",names);self.assertNotIn("ndk-clang-cl.exe",names);self.assertLessEqual(len(specs),t.MAX_TOOLS);self.assertTrue(u)
 def test_outside_path_selection_withheld(self):
  specs,u=t.inventory({"PATH":"synthetic"},which=lambda *a,**k:r"C:\private\secret.exe");self.assertTrue(any("OUTSIDE" in x["status"] for x in u));self.assertFalse(any("private" in str(x) for x in specs+u))
 def test_pinned_rust_unavailable_not_substituted(self):
  specs,u=t.inventory({"RUSTUP_HOME":r"C:\rustup"},which=lambda *a,**k:None);rust=[x for x in specs if x["name"].startswith("RUSTUP_HOME")];self.assertEqual(len(rust),3);self.assertTrue(all("1.95.0" in x["path"] for x in rust));self.assertTrue(all("C:\\rustup" not in x["display"] for x in rust))
 def test_report_future_unknowns_and_no_execution_claim(self):
  r,text=t.report([self.spec()],[],FakeAPI(),self.budget());self.assertEqual(r["state"],"METADATA_COLLECTED_WITH_UNRESOLVED");self.assertFalse(r["toolsExecuted"]);self.assertFalse(r["executionPolicyChanged"]);self.assertTrue(r["unresolved"]);self.assertLess(len(text),t.MAX_REPORT)
 def test_report_fatal_does_not_accept_partial_or_continue(self):
  a=FakeAPI(change="link");r,text=t.report([self.spec(),self.spec()],[],a,self.budget());self.assertEqual(r["state"],"FAILED_CLOSED_METADATA_PROBE");self.assertEqual(r["inputs"],[]);self.assertEqual(a.reads,0)
 def test_count_and_report_bounds(self):
  with self.assertRaisesRegex(t.Stop,"TOOL_COUNT"):t.report([self.spec()]*(t.MAX_TOOLS+1),[],FakeAPI(),self.budget())
  with self.assertRaisesRegex(t.Stop,"REPORT_BOUND"):t.report([], [{"x":"x"*t.MAX_REPORT}],FakeAPI(),self.budget())
 def test_no_launch_download_or_execution_limit_change(self):
  tree=ast.parse(inspect.getsource(t));imports={a.name for n in ast.walk(tree) if isinstance(n,ast.Import) for a in n.names};self.assertFalse(imports&{"subprocess","urllib","requests"});self.assertNotIn("executable_snapshot(",inspect.getsource(t));self.assertEqual(t.MAX_FILE,128*1024**2)
 def test_disappearance_after_open_is_fatal_not_unavailable(self):
  a=FakeAPI()
  def vanished(path):raise FileNotFoundError(2,"synthetic")
  a.read=vanished
  with self.assertRaisesRegex(t.Stop,"DISAPPEARED_AFTER_OPEN"):t.inspect_input(self.spec(),a,self.budget())
  self.assertEqual(len(a.closed),len(a.handles))
 def test_revision_file_result_and_mismatch_are_bounded(self):
  spec=self.spec();spec.update(kind="metadata",revisionKind="package",expectedRevision="30.0.16248370");data=b"Pkg.Revision = 30.0.16248370\n"
  row=t.inspect_input(spec,FakeAPI(data=data),self.budget());self.assertTrue(row["revisionMatches"]);self.assertNotIn("text",row)
  with self.assertRaisesRegex(t.Stop,"REVISION_MISMATCH"):t.inspect_input(spec,FakeAPI(data=b"Pkg.Revision = other"),self.budget())
 def test_growth_never_accepted_as_complete(self):
  a=FakeAPI();old=a.info
  def smaller(h):
   row=old(h)
   if h.endswith("tool.exe"):row["bytes"]-=1
   return row
  a.info=smaller
  with self.assertRaisesRegex(t.Stop,"GREW_DURING_READ"):t.inspect_input(self.spec(),a,self.budget())
 def test_oversized_read_chunk_fatal(self):
  class Stream:
   def __enter__(self):return self
   def __exit__(self,*a):pass
   def read(self,n):return b"MZ"+bytes(t.CHUNK-1)
  a=FakeAPI(data=b"MZ"+bytes(t.CHUNK-1));a.read=lambda path:Stream()
  with self.assertRaisesRegex(t.Stop,"CHUNK_BOUND"):t.inspect_input(self.spec(),a,self.budget())
if __name__=="__main__":unittest.main()
