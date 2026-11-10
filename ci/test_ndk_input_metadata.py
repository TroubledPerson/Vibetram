import unittest,pathlib,types,os
from unittest.mock import patch
from ndk_input_metadata import target_for,stable_rows,regular_target,safe_target,capture_one,expected_mapping
class Metadata(unittest.TestCase):
 def record(self,name,relative=True):return {"substituteName":name,"relative":relative}
 def test_relative(self):self.assertEqual(target_for(r"C:/ndk",r"C:/ndk/bin/clang.exe",self.record("clang-real.exe")),pathlib.PureWindowsPath(r"C:/ndk/bin/clang-real.exe"))
 def test_absolute(self):self.assertEqual(target_for("C:/ndk","C:/ndk/clang.exe",self.record(chr(92)+"??"+chr(92)+"C:/ndk/real.exe",False)),pathlib.PureWindowsPath("C:/ndk/real.exe"))
 def test_escape(self):
  with self.assertRaises(AssertionError):target_for(r"C:/ndk",r"C:/ndk/clang.exe",self.record(r"../outside.exe"))
 def test_drive_relative(self):
  with self.assertRaises(AssertionError):target_for(r"C:/ndk",r"C:/ndk/clang.exe",self.record("C:relative"))
 def test_unc(self):
  with self.assertRaises(AssertionError):target_for(r"C:/ndk",r"C:/ndk/clang.exe",self.record(r"//host/share/x",False))
 def test_self(self):
  with self.assertRaises(AssertionError):target_for(r"C:/ndk",r"C:/ndk/clang.exe",self.record("clang.exe"))
 def test_ancestor(self):
  with self.assertRaises(AssertionError):target_for(r"C:/ndk",r"C:/ndk/bin/clang.exe",self.record(".."))
 def test_scope_relative(self):
  with self.assertRaises(AssertionError):target_for("ndk",r"C:/ndk/clang.exe",self.record("real.exe"))
 def row(self,id=2,attrs=0x20,tag=0):return {"identity":[7,0,id],"attributes":attrs,"tag":tag,"bytes":1}
 def test_regular(self):regular_target([self.row(1,0x10),self.row()],7,[7,0,9])
 def test_volume(self):
  with self.assertRaises(AssertionError):regular_target([self.row()],8,[7,0,9])
 def test_reparse(self):
  with self.assertRaises(AssertionError):regular_target([self.row(attrs=0x420,tag=0xA000000C)],7,[7,0,9])
 def test_target_directory(self):
  with self.assertRaises(AssertionError):regular_target([self.row(attrs=0x10)],7,[7,0,9])
 def test_target_alias_identity(self):
  with self.assertRaises(AssertionError):regular_target([self.row()],7,[7,0,2])
 def test_stable(self):stable_rows([self.row()],[self.row()])
 def test_changed(self):
  with self.assertRaises(AssertionError):stable_rows([self.row()],[self.row(3)])
 def test_empty(self):
  with self.assertRaises(AssertionError):stable_rows([],[])
 def test_unknown_target_sanitized(self):self.assertTrue(safe_target(self.record(r"D:/unapproved/target",False)).startswith("WITHHELD_UNKNOWN_TARGET_SHA256:"))
 @unittest.skipUnless(os.name=="nt","Windows path layout")
 def test_close_failure(self):
  class Fake:
   def __init__(self):self.paths={};self.k=types.SimpleNamespace(CloseHandle=lambda h:False)
   def open(self,p):h=len(self.paths)+1;self.paths[h]=p;return h
   def info(self,h):return {"identity":[7,0,h],"attributes":0x20 if self.paths[h].name=="tool.exe" else 0x10,"tag":0,"bytes":0}
  with patch("ndk_input_metadata.API",Fake):
   d=capture_one(pathlib.Path(r"C:/ndk"),pathlib.Path(r"C:/ndk/tool.exe"))
  self.assertEqual(d["state"],"HANDLE_CLOSE_FAILURE_STOP");self.assertFalse(d["qualified"]);self.assertGreater(d["closeFailures"],0)
 @unittest.skipUnless(os.name=="nt","Windows path layout")
 def test_access_denied(self):
  class Fake:
   def __init__(self):self.k=types.SimpleNamespace(CloseHandle=lambda h:True)
   def open(self,p):raise OSError(5,"synthetic")
  with patch("ndk_input_metadata.API",Fake):d=capture_one(pathlib.Path(r"C:/ndk"),pathlib.Path(r"C:/ndk/tool.exe"))
  self.assertEqual(d["state"],"OS_ACCESS_DENIED_STOP");self.assertFalse(d["qualified"])

 def test_directory_target(self):regular_target([self.row(attrs=0x10)],7,[7,0,9],directory=True)
 def test_directory_expected_file_rejected(self):
  with self.assertRaises(AssertionError):regular_target([self.row()],7,[7,0,9],directory=True)
 def test_expected_sdk_mapping(self):expected_mapping("C:/physical",{"tag":0xA000000C,"relative":False},"C:/physical")
 def test_changed_sdk_mapping(self):
  with self.assertRaises(AssertionError):expected_mapping("C:/other",{"tag":0xA000000C,"relative":False},"C:/physical")
 def test_relative_sdk_mapping_rejected(self):
  with self.assertRaises(AssertionError):expected_mapping("C:/physical",{"tag":0xA000000C,"relative":True},"C:/physical")
 @unittest.skipUnless(os.name=="nt","Windows handle metadata model")
 def test_callback_held_then_revalidated(self):
  closed=[]
  class Fake:
   def __init__(self):self.paths={};self.k=types.SimpleNamespace(CloseHandle=lambda h:(closed.append(h) or True))
   def open(self,p):h=len(self.paths)+1;self.paths[h]=p;return h
   def info(self,h):return {"identity":[7,0,h],"attributes":0x20 if self.paths[h].name=="tool.exe" else 0x10,"tag":0,"bytes":0}
  def callback():self.assertEqual(closed,[])
  with patch("ndk_input_metadata.API",Fake):d=capture_one(pathlib.Path("C:/ndk"),pathlib.Path("C:/ndk/tool.exe"),callback=callback)
  self.assertTrue(d["qualified"]);self.assertTrue(d["callbackSucceeded"]);self.assertTrue(closed)
 @unittest.skipUnless(os.name=="nt","Windows handle metadata model")
 def test_post_callback_identity_change(self):
  changed=[False]
  class Fake:
   def __init__(self):self.paths={};self.k=types.SimpleNamespace(CloseHandle=lambda h:True)
   def open(self,p):h=len(self.paths)+1;self.paths[h]=p;return h
   def info(self,h):return {"identity":[7,0,h+(100 if changed[0] else 0)],"attributes":0x20 if self.paths[h].name=="tool.exe" else 0x10,"tag":0,"bytes":0}
  with patch("ndk_input_metadata.API",Fake):d=capture_one(pathlib.Path("C:/ndk"),pathlib.Path("C:/ndk/tool.exe"),callback=lambda:changed.__setitem__(0,True))
  self.assertFalse(d["qualified"]);self.assertEqual(d["reason"],"METADATA_CHANGED")


class MetadataReportingOnly(unittest.TestCase):
 @unittest.skipUnless(os.name=="nt","Windows handle metadata model")
 def test_directory_byte_change_diagnostic_remains_fatal(self):
  changed=[False]
  class Fake:
   def __init__(self):self.paths={};self.k=types.SimpleNamespace(CloseHandle=lambda h:True)
   def open(self,p):h=len(self.paths)+1;self.paths[h]=p;return h
   def info(self,h):
    leaf=self.paths[h].name=="tool.exe";size=1 if leaf else (8192 if changed[0] and self.paths[h].name=="ndk" else 4096)
    return {"identity":[7,0,h],"attributes":0x20 if leaf else 0x10,"tag":0,"bytes":size}
  with patch("ndk_input_metadata.API",Fake):d=capture_one(pathlib.Path("C:/ndk"),pathlib.Path("C:/ndk/tool.exe"),callback=lambda:changed.__setitem__(0,True))
  self.assertFalse(d["qualified"]);self.assertEqual(d["reason"],"METADATA_CHANGED");self.assertEqual(d["metadataPhase"],"POST_CALLBACK_INPUT");self.assertTrue(d["callbackSucceeded"]);diff=d["metadataDifferences"];self.assertEqual(len(diff),1);self.assertTrue(diff[0]["directory"]);self.assertEqual(diff[0]["changedFields"],["bytes"]);self.assertEqual(diff[0]["before"]["bytes"],4096);self.assertEqual(diff[0]["after"]["bytes"],8192)
 @unittest.skipUnless(os.name=="nt","Windows handle metadata model")
 def test_callback_error_class_and_phase(self):
  class Fake:
   def __init__(self):self.paths={};self.k=types.SimpleNamespace(CloseHandle=lambda h:True)
   def open(self,p):h=len(self.paths)+1;self.paths[h]=p;return h
   def info(self,h):return {"identity":[7,0,h],"attributes":0x20 if self.paths[h].name=="tool.exe" else 0x10,"tag":0,"bytes":0}
  def callback():raise AssertionError("SYNTHETIC_CALLBACK_FAILURE")
  with patch("ndk_input_metadata.API",Fake):d=capture_one(pathlib.Path("C:/ndk"),pathlib.Path("C:/ndk/tool.exe"),callback=callback)
  self.assertFalse(d["qualified"]);self.assertEqual(d["errorClass"],"AssertionError");self.assertEqual(d["metadataPhase"],"CALLBACK");self.assertEqual(d["reason"],"SYNTHETIC_CALLBACK_FAILURE");self.assertFalse(d["callbackSucceeded"])

class MutableCiWorkAncestor(unittest.TestCase):
 def run_case(self,change=None,denied=False,scope=True):
  import ndk_input_metadata
  work=pathlib.Path(ndk_input_metadata.__file__).resolve().parents[1]/"ci-work";root=work/"perl-overlay";tool=root/"lib/Locale/Maketext/Simple.pm";changed=[False]
  class Fake:
   def __init__(self):self.paths={};self.k=types.SimpleNamespace(CloseHandle=lambda h:True)
   def open(self,p):h=len(self.paths)+1;self.paths[h]=p;return h
   def info(self,h):
    path=self.paths[h];leaf=path==tool
    if changed[0] and denied and path==work:raise OSError(5,"synthetic")
    row={"identity":[7,0,h],"attributes":0x20 if leaf else 0x10,"tag":0,"bytes":9707 if leaf else 8192}
    if changed[0] and change:change(path,row,work,tool)
    return row
  with patch("ndk_input_metadata.API",Fake):return capture_one(root,tool,callback=lambda:changed.__setitem__(0,True),mutable_ci_work=scope)
 def test_exact_job_ancestor_growth_allowed(self):
  row=self.run_case(lambda p,r,w,t:r.update(bytes=12288) if p==w else None)
  self.assertTrue(row["qualified"]);self.assertEqual(row["qualifiedMutableAncestorGrowthBytes"],4096);self.assertTrue(row["callbackSucceeded"])
 def test_growth_is_opt_in(self):
  self.assertFalse(self.run_case(lambda p,r,w,t:r.update(bytes=12288) if p==w else None,scope=False)["qualified"])
 def test_ancestor_identity_type_tag_and_shrink_fatal(self):
  for key,value in [("identity",[8,0,99]),("attributes",0x410),("attributes",0x20),("tag",0xA000000C),("bytes",4096)]:
   with self.subTest(key=key,value=value):
    row=self.run_case(lambda p,r,w,t:r.update({key:value}) if p==w else None);self.assertFalse(row["qualified"]);self.assertEqual(row["reason"],"METADATA_CHANGED")
 def test_growth_plus_identity_mutation_fatal(self):
  self.assertFalse(self.run_case(lambda p,r,w,t:r.update(bytes=12288,identity=[7,0,999]) if p==w else None)["qualified"])
 def test_module_mutation_fatal(self):
  for key,value in [("bytes",9800),("identity",[7,0,999]),("tag",0xA000000C)]:
   with self.subTest(key=key):self.assertFalse(self.run_case(lambda p,r,w,t:r.update({key:value}) if p==t else None)["qualified"])
 def test_other_ancestor_growth_fatal(self):
  self.assertFalse(self.run_case(lambda p,r,w,t:r.update(bytes=12288) if p==w/"perl-overlay" else None)["qualified"])
 def test_denial_fatal(self):
  row=self.run_case(denied=True);self.assertFalse(row["qualified"]);self.assertEqual(row["state"],"OS_ACCESS_DENIED_STOP")
 def test_arbitrary_mutable_scope_rejected(self):
  row=capture_one(pathlib.Path("D:/not-job/perl-overlay"),pathlib.Path("D:/not-job/perl-overlay/lib/Locale/Maketext/Simple.pm"),callback=lambda:None,mutable_ci_work=True)
  self.assertFalse(row["qualified"]);self.assertEqual(row["reason"],"MUTABLE_CI_WORK_SCOPE")

if __name__=="__main__":unittest.main()
