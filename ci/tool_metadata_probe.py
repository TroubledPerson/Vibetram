"""Read known build inputs only. No tool execution or execution-size exceptions."""
import pathlib,os,json,time,hashlib,shutil,sys,ctypes
MAX_SECONDS=90
MAX_FILE=128*1024**2
MAX_TOTAL=1024**3
MAX_REPORT=65536
MAX_TOOLS=64
CHUNK=1024**2
MIN_FREE=40*1024**3
MARKER="[tool-metadata-only-191]"
class Stop(RuntimeError):
 def __init__(self,code,oscode=None,primary=None):
  super().__init__(code);self.code=code;self.oscode=oscode;self.primary=primary
class Budget:
 def __init__(self,clock=time.monotonic,free=None):
  self.clock=clock;self.free=free or (lambda:shutil.disk_usage(pathlib.Path(__file__).resolve().parents[1]).free);self.start=clock();self.last=self.start;self.bytes=0;self.samples=0
 def pulse(self):
  now=self.clock()
  if now-self.start>MAX_SECONDS:raise Stop("METADATA_DEADLINE")
  if now-self.last>1:raise Stop("MISSED_METADATA_SUPERVISION")
  if self.free()<MIN_FREE:raise Stop("FREE_SPACE_GUARD")
  after=self.clock()
  if after-now>1:raise Stop("BLOCKED_FREE_SPACE_SAMPLE")
  self.last=after;self.samples+=1
 def charge(self,n):
  if type(n) is not int or n<0 or self.bytes+n>MAX_TOTAL:raise Stop("TOTAL_READ_BOUND")
  self.bytes+=n
class WindowsAPI:
 def __init__(self):
  from ndk_input_metadata import API
  self.base=API()
 def open(self,p):return self.base.open(p)
 def info(self,h):
  row=self.base.info(h);r=self.base.INFO();self.base.checked(self.base.k.GetFileInformationByHandle(h,ctypes.byref(r)));row["modified100ns"]=[r.written.high,r.written.low];return row
 def close(self,h):
  if not self.base.k.CloseHandle(h):raise OSError(ctypes.get_last_error(),"METADATA_CLOSE")
 def read(self,p):return pathlib.Path(p).open("rb")
def path_scope(spec):
 p=pathlib.PureWindowsPath(spec["path"]);root=pathlib.PureWindowsPath(spec["root"])
 if not p.is_absolute() or not root.is_absolute() or p.drive.startswith("\\\\") or ".." in p.parts or ".." in root.parts or len(p.parts)>32 or not p.is_relative_to(root):raise Stop("INPUT_PATH_SCOPE")
 return p
def stable(row,directory=False):
 return (row["identity"],row["attributes"],row["tag"]) if directory else (row["identity"],row["attributes"],row["tag"],row["bytes"],row["modified100ns"])
def revision_matches(kind,text,expected):
 if kind=="jdk":
  values=[l.split("=",1)[1].strip().strip('"') for l in text.splitlines() if l.startswith("JAVA_VERSION=")]
  return len(values)==1 and values[0].split(".")[0]==expected
 if kind=="msvc":return text.strip()==expected
 key="AndroidVersion.ApiLevel" if kind=="platform" else "Pkg.Revision"
 values=[l.split("=",1)[1].strip() for l in text.splitlines() if l.split("=",1)[0].strip()==key and "=" in l]
 return values==[expected]
def inspect_input(spec,api,budget):
 p=path_scope(spec);held=[];chain=[];result=None;failure=None;file_opened=False
 try:
  current=pathlib.PureWindowsPath(p.anchor)
  for i,part in enumerate(p.parts):
   budget.pulse()
   if i:current=current/part
   h=api.open(str(current));held.append(h);row=api.info(h)
   if row["tag"] or row["attributes"]&0x400:raise Stop("REPARSE_INPUT_STOP")
   directory=i<len(p.parts)-1
   if bool(row["attributes"]&0x10)!=directory:raise Stop("INPUT_TYPE_CHANGED")
   chain.append((h,row,directory))
  file_opened=True;before=chain[-1][1];limit=16384 if spec.get("revisionKind") else MAX_FILE
  if type(before["bytes"]) is not int or not 0<=before["bytes"]<=limit:raise Stop("FILE_READ_BOUND")
  if budget.bytes+before["bytes"]>MAX_TOTAL:raise Stop("TOTAL_READ_BOUND")
  digest=hashlib.sha256();count=0;prefix=b""
  with api.read(str(p)) as stream:
   while True:
    budget.pulse();chunk=stream.read(CHUNK);budget.pulse()
    if not chunk:break
    if len(chunk)>CHUNK:raise Stop("READ_CHUNK_BOUND")
    budget.charge(len(chunk));count+=len(chunk)
    if count>before["bytes"]:raise Stop("INPUT_GREW_DURING_READ")
    digest.update(chunk)
    if len(prefix)<16384:prefix+=chunk[:16384-len(prefix)]
  if count!=before["bytes"]:raise Stop("INCOMPLETE_FILE_READ")
  if spec["kind"]=="image" and prefix[:2]!=b"MZ":raise Stop("IMAGE_HEADER_MISMATCH")
  for h,row,directory in chain:
   budget.pulse();after=api.info(h)
   if stable(row,directory)!=stable(after,directory):raise Stop("INPUT_IDENTITY_OR_METADATA_CHANGED")
  result={"name":spec["name"],"path":spec.get("display",str(p)),"role":spec["role"],"kind":spec["kind"],"status":"MEASURED_ONLY_NOT_EXECUTION_APPROVAL","bytes":count,"sha256":digest.hexdigest(),"identity":before["identity"],"modified100ns":before["modified100ns"],"regularAncestorCount":len(chain)-1,"overExecutionImageLimit":spec["kind"]=="image" and count>64*1024**2,"linkFollowed":False}
  if spec.get("revisionKind"):
   text=prefix.decode("utf-8",errors="strict");result["expectedRevision"]=spec["expectedRevision"];result["revisionMatches"]=revision_matches(spec["revisionKind"],text,spec["expectedRevision"])
   if not result["revisionMatches"]:raise Stop("PINNED_REVISION_MISMATCH")
 except OSError as e:
  code=getattr(e,"winerror",None) or e.errno
  if code in (2,3) and not file_opened:result={"name":spec["name"],"role":spec["role"],"status":"UNAVAILABLE_UNRESOLVED","oscode":code}
  else:failure=Stop("INPUT_DISAPPEARED_AFTER_OPEN" if code in (2,3) else "OS_ACCESS_DENIED" if code==5 else "OS_METADATA_OR_READ_FAILURE",code)
 except (Stop,ValueError,UnicodeError) as e:failure=e if isinstance(e,Stop) else Stop("MALFORMED_TOOL_METADATA")
 finally:
  closes=0
  for h in reversed(held):
   try:api.close(h)
   except BaseException:closes+=1
  if closes:failure=Stop("HANDLE_CLOSE_UNCONFIRMED",primary=failure.code if failure else None)
 if failure:raise failure
 return result
SDK=pathlib.PureWindowsPath(r"C:\Program Files (x86)\Android\android-sdk")
VS=pathlib.PureWindowsPath(r"C:\Program Files\Microsoft Visual Studio\18\Enterprise")
MSVC=VS/"VC/Tools/MSVC/14.51.36231"
def inventory(env,which=shutil.which):
 specs=[];unresolved=[]
 def add(name,path,root,role,kind="image",**more):
  specs.append(dict(name=name,path=str(path),root=str(root),role=role,kind=kind,**more))
 ndk=SDK/"ndk/30.0.16248370";bin=ndk/"toolchains/llvm/prebuilt/windows-x86_64/bin"
 for name in ("clang.exe","clang++.exe","ld.lld.exe","llvm-ar.exe","llvm-ranlib.exe","llvm-strip.exe","llvm-readelf.exe","llvm-nm.exe"):add("ndk-"+name,bin/name,ndk,"Android compiler/linker/archive/inspection")
 for name in ("aarch64-linux-android29-clang.cmd","aarch64-linux-android29-clang++.cmd"):add("ndk-"+name,bin/name,ndk,"API29 wrapper; current configuration selects direct exe","wrapper")
 add("ndk-make",ndk/"prebuilt/windows-x86_64/bin/make.exe",ndk,"OpenSSL make")
 add("ndk-revision",ndk/"source.properties",ndk,"NDK package metadata","metadata",revisionKind="package",expectedRevision="30.0.16248370")
 bt=SDK/"build-tools/35.0.0"
 for name in ("aapt2.exe","zipalign.exe"):add(name,bt/name,SDK,"Android packaging")
 add("d8.jar",bt/"lib/d8.jar",SDK,"Passive Java D8 classpath","data")
 add("android.jar",SDK/"platforms/android-35/android.jar",SDK,"Passive Android compile API","data")
 add("build-tools-revision",bt/"source.properties",SDK,"SDK metadata","metadata",revisionKind="package",expectedRevision="35.0.0")
 add("platform-revision",SDK/"platforms/android-35/source.properties",SDK,"SDK metadata","metadata",revisionKind="platform",expectedRevision="35")
 for variable,items in (("RUSTUP_HOME",("toolchains/1.95.0-x86_64-pc-windows-msvc/bin/cargo.exe","toolchains/1.95.0-x86_64-pc-windows-msvc/bin/rustc.exe","toolchains/1.95.0-x86_64-pc-windows-msvc/lib/rustlib/x86_64-pc-windows-msvc/bin/rust-lld.exe")),("CARGO_HOME",("bin/cargo.exe","bin/rustc.exe","bin/rustup.exe")),("JAVA_HOME_17_X64",("bin/java.exe","bin/javac.exe","bin/jar.exe","release"))):
  raw=env.get(variable,"");root=pathlib.PureWindowsPath(raw)
  if not raw or not root.is_absolute() or root.drive.startswith("\\\\") or ".." in root.parts:
   unresolved.append({"name":variable,"status":"PINNED_ROOT_UNAVAILABLE_UNRESOLVED"});continue
  for item in items:
   name=variable+"-"+item.split("/")[-1];extra={"display":"%"+variable+"%/"+item}
   if item=="release":extra.update(revisionKind="jdk",expectedRevision="17")
   add(name,root/item,root,"Pinned Rust1.95/proxy input" if "RUST" in variable or variable=="CARGO_HOME" else "JDK17 packaging", "metadata" if item=="release" else "image",**extra)
 for name in ("cl.exe","link.exe","lib.exe","nmake.exe","ml64.exe","vctip.exe"):add("msvc-"+name,MSVC/"bin/Hostx64/x64"/name,MSVC,"Explicit Microsoft host tool/helper")
 add("msvc-default",VS/"VC/Auxiliary/Build/Microsoft.VCToolsVersion.default.txt",VS,"MSVC package metadata","metadata",revisionKind="msvc",expectedRevision="14.51.36231")
 add("vsdevcmd",VS/"Common7/Tools/VsDevCmd.bat",VS,"Setup wrapper; not executed","wrapper")
 add("vswhere",pathlib.PureWindowsPath(r"C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe"),pathlib.PureWindowsPath(r"C:\Program Files (x86)\Microsoft Visual Studio"),"Installed setup discovery")
 kits=pathlib.PureWindowsPath(r"C:\Program Files (x86)\Windows Kits\10")
 for name in ("rc.exe","mt.exe"):add("sdk-"+name,kits/"bin/10.0.26100.0/x64"/name,kits,"Conditional native resource helper")
 git=pathlib.PureWindowsPath(r"C:\Program Files\Git")
 for item in ("cmd/git.exe","usr/bin/perl.exe","usr/bin/sh.exe","usr/bin/bash.exe"):add("git-"+item.split("/")[-1],git/item,git,"Git/qualified Unix-path Perl/OpenSSL helper")
 windows=pathlib.PureWindowsPath(r"C:\Windows")
 for name in ("cmd.exe","conhost.exe"):add(name,windows/"System32"/name,windows,"Command wrapper/observed console helper")
 add("pwsh",pathlib.PureWindowsPath(r"C:\Program Files\PowerShell\7\pwsh.exe"),pathlib.PureWindowsPath(r"C:\Program Files\PowerShell"),"Host qualification scripting")
 allowed=[pathlib.PureWindowsPath(p) for p in (r"C:\Program Files",r"C:\Program Files (x86)",r"C:\ProgramData\chocolatey",r"C:\hostedtoolcache")]
 for name in ("cmake.exe","ninja.exe"):
  found=which(name,path=env.get("PATH",""))
  if found and pathlib.PureWindowsPath(found).is_absolute() and any(pathlib.PureWindowsPath(found).is_relative_to(root) for root in allowed):
   root=next(root for root in allowed if pathlib.PureWindowsPath(found).is_relative_to(root));add(name,pathlib.PureWindowsPath(found),root,"Ambient runner PATH only; final Cargo helper selection unresolved")
  else:unresolved.append({"name":name,"status":"PATH_SELECTION_UNAVAILABLE_OR_OUTSIDE_ALLOWED_ROOTS"})
 if len(specs)>MAX_TOOLS:raise Stop("TOOL_COUNT_BOUND")
 return specs,unresolved
def report(specs,unresolved,api,budget):
 rows=[];failure=None
 if len(specs)>MAX_TOOLS:raise Stop("TOOL_COUNT_BOUND")
 for spec in specs:
  try:rows.append(inspect_input(spec,api,budget))
  except Stop as e:failure={"name":spec["name"],"code":e.code,"oscode":e.oscode,"primary":e.primary};break
 unresolved=list(unresolved)+[{"name":"Cargo-generated-build-scripts-and-test-executables","status":"FUTURE_IDENTITIES_SIZES_AND_DYNAMIC_HELPER_SELECTION_UNRESOLVED"}]
 result={"state":"FAILED_CLOSED_METADATA_PROBE" if failure else "METADATA_COLLECTED_WITH_UNRESOLVED","inputs":rows,"unresolved":unresolved,"fatal":failure,"bytesRead":budget.bytes,"samples":budget.samples,"limits":{"seconds":MAX_SECONDS,"fileBytes":MAX_FILE,"totalReadBytes":MAX_TOTAL,"tools":MAX_TOOLS,"reportBytes":MAX_REPORT,"minimumFreeBytes":MIN_FREE},"toolsExecuted":False,"downloads":False,"executionPolicyChanged":False,"atomicFilesystemSnapshot":False,"hardIODeadlineEnforced":False,"limitsNote":"Sampled checks cannot preempt a blocked OS read; the 10-minute job timeout is the outer bound. Missing inputs are not qualified; no future generated image is approved."}
 text=json.dumps(result,separators=(",",":"))
 if len(text.encode())>MAX_REPORT:raise Stop("REPORT_BOUND")
 return result,text
def main():
 if sys.argv[1:]:raise Stop("UNKNOWN_PROBE_ARGUMENT")
 if os.name!="nt" or os.environ.get("GITHUB_REPOSITORY")!="TroubledPerson/Vibetram" or os.environ.get("GITHUB_REF")!="refs/heads/main" or os.environ.get("GITHUB_EVENT_NAME")!="push":raise Stop("TRUSTED_METADATA_ENTRY_REQUIRED")
 event=pathlib.Path(os.environ["GITHUB_EVENT_PATH"])
 if not event.is_absolute() or not 0<event.stat().st_size<=1024**2:raise Stop("EVENT_METADATA_BOUND")
 if MARKER not in json.loads(event.read_text(encoding="utf-8"))["head_commit"]["message"]:raise Stop("TRUSTED_METADATA_MARKER_REQUIRED")
 from check_source import source_check
 source_check(pathlib.Path(__file__).resolve().parents[1]);specs,unresolved=inventory(os.environ);result,text=report(specs,unresolved,WindowsAPI(),Budget());print(text,flush=True)
 summary=os.environ.get("GITHUB_STEP_SUMMARY")
 if summary:
  with pathlib.Path(summary).open("a",encoding="utf-8") as f:f.write("## Read-only tool metadata; no execution approval\n\n"+chr(96)*3+"json\n"+text+"\n"+chr(96)*3+"\n")
 if result["fatal"]:raise SystemExit(1)
if __name__=="__main__":main()
