"""Exact previously tested NDK linker payload; not an archive-verification claim."""
import pathlib,json
SHA="b64100b407a472f831caf2789f6c09d501e2e4c876ebc772997c294be7f9f8f3"
SIZE=69225112
REVISION="30.0.16248370"
ROOT=pathlib.Path(r"C:\Program Files (x86)\Android\android-sdk")
NDK=ROOT/("ndk/"+REVISION)
EXACT=NDK/"toolchains/llvm/prebuilt/windows-x86_64/bin/ld.lld.exe"
KEY="VIBETRAM_NDK_LLD_BINDING"
PROVENANCE="runner-20261103.298.1-qualified-run-42751233275"
VERSION="LLD 21.0.0 (/mnt/disks/build-disk/src/googleplex-android/llvm-r574158-release/out/llvm-project/llvm 9f872551d3c681d06fd303b36f16ed5c274735eb) (compatible with GNU linkers)"
def schema(pin):
 assert isinstance(pin,dict) and set(pin)=={"path","identity","bytes","modifiedNs","sha256","ndkRevision","provenance"},"NDK_LLD_SCHEMA"
 assert pin["path"]==str(EXACT),"NDK_LLD_EXACT_PATH"
 assert pin["bytes"]==SIZE and type(pin["bytes"]) is int,"NDK_LLD_LENGTH"
 assert pin["sha256"]==SHA,"NDK_LLD_HASH_PIN"
 assert pin["ndkRevision"]==REVISION and pin["provenance"]==PROVENANCE,"NDK_LLD_PROVENANCE"
 assert isinstance(pin["identity"],list) and len(pin["identity"])==2 and all(type(n) is int for n in pin["identity"]),"NDK_LLD_IDENTITY_SCHEMA"
 assert type(pin["modifiedNs"]) is int and pin["modifiedNs"]>=0,"NDK_LLD_MTIME_SCHEMA"
 return pin
def pinned(path,meta,pin):
 schema(pin);assert str(path)==str(EXACT),"NDK_LLD_EXACT_PATH"
 assert [meta.st_dev,meta.st_ino]==pin["identity"] and meta.st_mtime_ns==pin["modifiedNs"],"NDK_LLD_STALE_IDENTITY"
 assert meta.st_size==SIZE,"NDK_LLD_LENGTH"
 return SHA
def revision():
 from openssl_probe import regular_chain
 p=NDK/"source.properties";regular_chain(p);before=p.lstat();assert 0<before.st_size<=4096,"NDK_REVISION_BOUND"
 text=p.read_text(encoding="utf-8");after=p.lstat();key=lambda m:(m.st_dev,m.st_ino,m.st_size,m.st_mtime_ns)
 assert key(before)==key(after),"NDK_REVISION_CHANGED"
 assert [line.strip() for line in text.splitlines() if line.startswith("Pkg.Revision = ")]==["Pkg.Revision = "+REVISION],"NDK_REVISION_REQUIRED"
def environment(env):
 for k in ("ANDROID_HOME","ANDROID_SDK_ROOT"):assert env.get(k)==str(ROOT),"NDK_LLD_SDK_ROUTE"
 for k in ("ANDROID_NDK","ANDROID_NDK_ROOT","ANDROID_NDK_HOME"):assert env.get(k)==str(NDK),"NDK_LLD_NDK_ROUTE"
def select(env,path):
 if KEY not in env:return None
 value=env[KEY];assert isinstance(value,str) and 0<len(value)<=2048,"NDK_LLD_BINDING_BOUND";pin=schema(json.loads(value));environment(env);revision()
 return pin if str(path)==str(EXACT) else None
def qualify(env,sample=None):
 from build_guard import executable_snapshot
 environment(env);revision();m=EXACT.lstat();pin={"path":str(EXACT),"identity":[m.st_dev,m.st_ino],"bytes":SIZE,"modifiedNs":m.st_mtime_ns,"sha256":SHA,"ndkRevision":REVISION,"provenance":PROVENANCE}
 row=executable_snapshot(EXACT,sample,large_ndk_binding=pin);assert row["identity"]==pin["identity"] and row["bytes"]==SIZE and row["sha256"]==SHA,"NDK_LLD_QUALIFICATION_CHANGED"
 return {KEY:json.dumps(pin,separators=(",",":"))}
def version(text):assert text==VERSION,"NDK_LLD_VERSION_CHANGED"
