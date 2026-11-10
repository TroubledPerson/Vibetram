"""Read-only, no-follow metadata for two exact installed NDK inputs; never execute tools."""
import pathlib,ntpath,os,ctypes,time,json,hashlib,re,shutil
from reparse_metadata import decode_record,MAX_RECORD
from check_source import source_check
MIN_FREE=40*1024**3
MAX_SECONDS=30
MAX_REPORT=32768
def target_for(root,link,record):
 root=pathlib.PureWindowsPath(root);link=pathlib.PureWindowsPath(link);assert root.is_absolute() and link.is_absolute(),"ABSOLUTE_METADATA_SCOPE_REQUIRED"
 name=record["substituteName"]
 if record["relative"]:
  p=pathlib.PureWindowsPath(name)
  assert not p.is_absolute() and not p.drive,"AMBIGUOUS_RELATIVE_TARGET"
  name=ntpath.normpath(str(link.parent/p))
 else:
  if name.startswith("\\\\?\\"):name=name[4:]
  elif name.startswith("\\??\\"):name=name[4:]
 p=pathlib.PureWindowsPath(ntpath.normpath(name))
 assert p.is_absolute() and not p.drive.startswith("\\\\"),"NON_LOCAL_TARGET"
 assert p!=link and p not in link.parents,"TARGET_CYCLE"
 assert p.is_relative_to(root),"OUTSIDE_EXACT_NDK_SCOPE"
 return p
def stable_rows(before,after):
 assert before and len(before)==len(after) and all(a==b for a,b in zip(before,after)),"METADATA_CHANGED"
def regular_target(rows,volume,link_id,directory=False):
 assert rows,"EMPTY_TARGET_CHAIN"
 for i,row in enumerate(rows):
  assert row["tag"]==0 and not row["attributes"]&0x400,"REPARSE_PHYSICAL_TARGET_CHAIN"
  assert row["identity"][0]==volume,"TARGET_VOLUME_CHANGED"
  if i<len(rows)-1:assert row["attributes"]&0x10,"NON_DIRECTORY_ANCESTOR"
 assert bool(rows[-1]["attributes"]&0x10)==directory and rows[-1]["identity"]!=link_id,"NOT_DISTINCT_EXPECTED_TYPE"
def expected_mapping(target,record,expected):
 assert pathlib.PureWindowsPath(target)==pathlib.PureWindowsPath(expected),"SDK_ALIAS_TARGET_CHANGED"
 assert record["tag"]==0xA000000C and not record["relative"],"EXPECTED_ABSOLUTE_SDK_SYMLINK"
def safe_target(record):
 name=record["substituteName"]
 if record["relative"] and re.fullmatch(r"[A-Za-z0-9_.+\\/-]{1,240}",name):return name
 for prefix in ("\\??\\","\\\\?\\"):
  if name.startswith(prefix):name=name[len(prefix):]
 normalized=ntpath.normpath(name)
 if normalized.lower().startswith(("c:\\android\\","c:\\program files\\android\\")):return normalized
 return "WITHHELD_UNKNOWN_TARGET_SHA256:"+hashlib.sha256(record["substituteName"].encode("utf-16-le")).hexdigest()
class API:
 def __init__(self):
  from ctypes import wintypes as w
  self.w=w;self.k=ctypes.WinDLL("kernel32",use_last_error=True)
  class FT(ctypes.Structure):_fields_=[("low",w.DWORD),("high",w.DWORD)]
  class INFO(ctypes.Structure):_fields_=[("attrs",w.DWORD),("created",FT),("accessed",FT),("written",FT),("volume",w.DWORD),("sizeHigh",w.DWORD),("sizeLow",w.DWORD),("links",w.DWORD),("indexHigh",w.DWORD),("indexLow",w.DWORD)]
  class TAG(ctypes.Structure):_fields_=[("attrs",w.DWORD),("tag",w.DWORD)]
  self.INFO=INFO;self.TAG=TAG
  self.k.CreateFileW.argtypes=[w.LPCWSTR,w.DWORD,w.DWORD,ctypes.c_void_p,w.DWORD,w.DWORD,w.HANDLE];self.k.CreateFileW.restype=w.HANDLE
  self.k.GetFileInformationByHandle.argtypes=[w.HANDLE,ctypes.POINTER(INFO)];self.k.GetFileInformationByHandle.restype=w.BOOL
  self.k.GetFileInformationByHandleEx.argtypes=[w.HANDLE,ctypes.c_int,ctypes.c_void_p,w.DWORD];self.k.GetFileInformationByHandleEx.restype=w.BOOL
  self.k.DeviceIoControl.argtypes=[w.HANDLE,w.DWORD,ctypes.c_void_p,w.DWORD,ctypes.c_void_p,w.DWORD,ctypes.POINTER(w.DWORD),ctypes.c_void_p];self.k.DeviceIoControl.restype=w.BOOL
  self.k.CloseHandle.argtypes=[w.HANDLE];self.k.CloseHandle.restype=w.BOOL
 def checked(self,ok):
  if not ok:raise OSError(ctypes.get_last_error(),"NO_FOLLOW_METADATA_QUERY")
 def open(self,path):
  h=self.k.CreateFileW(str(path),0,1,None,3,0x02200000,None)
  if h==ctypes.c_void_p(-1).value:raise OSError(ctypes.get_last_error(),"NO_FOLLOW_METADATA_OPEN")
  return h
 def info(self,h):
  r=self.INFO();t=self.TAG();self.checked(self.k.GetFileInformationByHandle(h,ctypes.byref(r)));self.checked(self.k.GetFileInformationByHandleEx(h,9,ctypes.byref(t),ctypes.sizeof(t)))
  return {"identity":[r.volume,r.indexHigh,r.indexLow],"attributes":t.attrs,"tag":t.tag,"bytes":(r.sizeHigh<<32)|r.sizeLow}
 def raw(self,h):
  b=ctypes.create_string_buffer(MAX_RECORD);n=self.w.DWORD();self.checked(self.k.DeviceIoControl(h,0x000900A8,None,0,b,MAX_RECORD,ctypes.byref(n),None));assert n.value<=MAX_RECORD
  return b.raw[:n.value]
def capture_one(root,tool,directory=False,expected_target=None,callback=None,mutable_ci_work=False):
 started=time.monotonic();metadata_started=started;api=API();held=[];result={"input":str(tool),"linkFollowed":False,"contentsRead":False,"qualified":False,"closeFailures":0,"expectedDirectory":directory,"callbackInvoked":False,"callbackSucceeded":False}
 def deadline():assert time.monotonic()-metadata_started<5,"METADATA_DEADLINE"
 def checked_rows(before,after,role):
  result["metadataPhase"]=("POST_CALLBACK_" if result.get("callbackSucceeded") else "PRE_CALLBACK_")+role
  if before!=after:
   differences=[]
   for i,(a,b) in enumerate(zip(before,after)):
    keys=[key for key in ("identity","attributes","tag","bytes") if a.get(key)!=b.get(key)]
    if keys:differences.append({"componentIndex":i,"directory":bool(a.get("attributes",0)&0x10),"changedFields":keys,"before":{key:a.get(key) for key in keys},"after":{key:b.get(key) for key in keys}})
   result["metadataDifferences"]=differences[:8];result["metadataDifferenceCount"]=len(differences);result["metadataChainLengths"]=[len(before),len(after)]
  # Only the explicitly qualified job-owned ancestor may grow after the callback.
  # All held identities, type/tag fields, immutable ancestors and module bytes stay exact.
  compared=after
  if mutable_ci_work and result.get("callbackSucceeded") and role=="INPUT":
   index=len(work.parts)-1
   if len(before)==len(after) and index<len(before)-1:
    a,b=before[index],after[index]
    if a!=b and a["attributes"]&0x10 and not a["attributes"]&0x400 and a["tag"]==0 and b["bytes"]>=a["bytes"]:
     candidate=dict(b);candidate["bytes"]=a["bytes"]
     if candidate==a:
      compared=list(after);compared[index]=candidate
      result["qualifiedMutableAncestorGrowthBytes"]=b["bytes"]-a["bytes"]
  stable_rows(before,compared)
 def chain(path):
  rows=[];handles=[];p=pathlib.Path(path.anchor)
  assert len(path.parts)<=24,"PATH_DEPTH"
  for i,part in enumerate(path.parts):
   deadline()
   if i:p=p/part
   h=api.open(p);held.append(h);handles.append(h);row=api.info(h);rows.append(row)
   if row["tag"] or row["attributes"]&0x400:return rows,handles,p
   if i<len(path.parts)-1:assert row["attributes"]&0x10,"NON_DIRECTORY_ANCESTOR"
  return rows,handles,None
 try:
  if mutable_ci_work:
   work=pathlib.Path(__file__).resolve().parents[1]/"ci-work"
   assert mutable_ci_work is True and root==work/"perl-overlay" and tool==root/"lib/Locale/Maketext/Simple.pm" and callback is not None and not directory and expected_target is None,"MUTABLE_CI_WORK_SCOPE"
  before,handles,link=chain(tool)
  if link is None:
   assert expected_target is None,"EXPECTED_SDK_ALIAS_ABSENT"
   assert bool(before[-1]["attributes"]&0x10)==directory,"INPUT_TYPE_MISMATCH"
   checked_rows(before,[api.info(h) for h in handles],"INPUT");result.update(state="REGULAR_INPUT_METADATA",qualified=True,fileIdentity=before[-1]["identity"],bytes=before[-1]["bytes"],tagHex="0x0")
  else:
   row=before[-1];raw=api.raw(handles[-1]);assert raw==api.raw(handles[-1]),"REPARSE_RECORD_CHANGED"
   record=decode_record(raw);assert record["tag"]==row["tag"],"REPARSE_TAG_CHANGED"
   checked_rows(before,[api.info(h) for h in handles],"INPUT")
   result.update(state="CAPTURED_UNQUALIFIED_REPARSE",component=str(link),tagHex=hex(row["tag"]),kind=record["kind"],relative=record["relative"],target=safe_target(record),recordSHA256=hashlib.sha256(raw).hexdigest(),linkIdentity=row["identity"])
   target=pathlib.Path(target_for(root,link,record))
   if expected_target is not None:expected_mapping(target,record,expected_target)
   result["independentTarget"]=str(target)
   physical,phandles,plink=chain(target)
   assert plink is None,"REPARSE_PHYSICAL_TARGET_CHAIN"
   regular_target(physical,row["identity"][0],row["identity"],directory=directory)
   checked_rows(physical,[api.info(h) for h in phandles],"PHYSICAL");checked_rows(before,[api.info(h) for h in handles],"INPUT");assert raw==api.raw(handles[-1]),"REPARSE_RECORD_CHANGED";deadline()
   result.update(state="QUALIFIED_INDEPENDENT_PHYSICAL_METADATA",qualified=True,physicalTargetIdentity=physical[-1]["identity"],physicalTargetTagHex="0x0",physicalTargetBytes=physical[-1]["bytes"],physicalAncestorCount=len(physical),physicalAncestorIdentities=[x["identity"] for x in physical])
  if callback is not None:
   result.update(metadataQualifiedBeforeCallback=True,callbackInvoked=True,metadataPhase="CALLBACK")
   callback();result["callbackSucceeded"]=True;metadata_started=time.monotonic()
   checked_rows(before,[api.info(h) for h in handles],"INPUT")
   if link is not None:
    regular_target([api.info(h) for h in phandles],row["identity"][0],row["identity"],directory=directory)
    checked_rows(physical,[api.info(h) for h in phandles],"PHYSICAL");assert raw==api.raw(handles[-1]),"REPARSE_RECORD_CHANGED"
   deadline()
 except OSError as e:result.update(state="OS_ACCESS_DENIED_STOP" if e.errno==5 else "OS_METADATA_FAILURE_STOP",osError=e.errno,errorClass=type(e).__name__,qualified=False)
 except (AssertionError,ValueError,UnicodeError) as e:result.update(state="INTERNAL_METADATA_QUALIFICATION_STOP",reason=str(e)[:120],errorClass=type(e).__name__,qualified=False)
 finally:
  for h in reversed(held):
   if not api.k.CloseHandle(h):result["closeFailures"]+=1
  if result["closeFailures"]:result.update(state="HANDLE_CLOSE_FAILURE_STOP",qualified=False)
  result["elapsedMilliseconds"]=round((time.monotonic()-started)*1000,3)
 return result
def main():
 assert os.name=="nt" and os.environ.get("GITHUB_REPOSITORY")=="TroubledPerson/Vibetram" and os.environ.get("GITHUB_REF")=="refs/heads/main"
 event=json.loads(pathlib.Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"));assert os.environ["GITHUB_EVENT_NAME"]=="push" and "[ndk-metadata-191]" in event["head_commit"]["message"]
 root=pathlib.Path(__file__).resolve().parents[1];source_check(root);assert shutil.disk_usage(root).free>=MIN_FREE+65536
 sdk=pathlib.Path(os.environ["ANDROID_HOME"]);assert str(sdk).lower()==r"c:\android\android-sdk","UNQUALIFIED_SDK_LOCATION"
 ndk=sdk/"ndk/30.0.16248370";bin=ndk/"toolchains/llvm/prebuilt/windows-x86_64/bin";started=time.monotonic();rows=[]
 for name in ("clang.exe","llvm-ar.exe"):
  assert time.monotonic()-started<MAX_SECONDS and shutil.disk_usage(root).free>=MIN_FREE+65536
  row=capture_one(ndk,bin/name);rows.append(row)
  if not row["qualified"]:break
 report={"state":"METADATA_ONLY_NO_EXECUTION","commit":os.environ["GITHUB_SHA"],"inputs":rows,"allRequestedInputsQualified":len(rows)==2 and all(x["qualified"] for x in rows),"compilerExecuted":False,"OpenSSLExecuted":False,"permissionsChanged":False,"inputPolicyChanged":False,"targetContentsRead":False,"linkedTargetTraversed":False,"atomicSnapshot":False}
 text=json.dumps(report,indent=2)+"\n";assert len(text.encode())<=MAX_REPORT and shutil.disk_usage(root).free>=MIN_FREE+65536 and time.monotonic()-started<MAX_SECONDS
 out=root/"openssl-probe-output";assert not out.exists();out.mkdir();(out/"ndk-metadata.json").write_text(text,encoding="utf-8")
 print(text,flush=True)
 with open(os.environ["GITHUB_STEP_SUMMARY"],"a",encoding="utf-8") as f:f.write("## NDK metadata only\n\n```json\n"+text+"```\n")
if __name__=="__main__":main()
