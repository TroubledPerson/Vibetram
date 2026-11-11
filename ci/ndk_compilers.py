"""Two exact hosted-measured compiler payloads; every runner binds fresh identities."""
import pathlib,json,re
import ndk_linker as ndk
KEY="VIBETRAM_NDK_COMPILER_BINDINGS"
SIZE=99559064
VERSION="21.0.0"
PROVENANCE="hosted-metadata-run-42939911668-commit-d284649617da4fdd3665b7a566b2cb071f4cc24b"
HASHES={"clang.exe":"6b7a698ccd1d5ef7375b7733f0675a166c560112961d3e5df0f275565a9201bc","clang++.exe":"5a7b3226976221f6dc1464d850614403dc18e5fddcb43120640f20472c5c960c"}
PATHS={name:ndk.NDK/"toolchains/llvm/prebuilt/windows-x86_64/bin"/name for name in HASHES}
def schema(pin):
 assert isinstance(pin,dict) and set(pin)=={"role","path","identity","bytes","modifiedNs","sha256","ndkRevision","compilerVersion","provenance"},"NDK_COMPILER_SCHEMA"
 role=pin["role"];assert role in HASHES,"NDK_COMPILER_ROLE"
 assert pin["path"]==str(PATHS[role]),"NDK_COMPILER_EXACT_PATH"
 assert type(pin["bytes"]) is int and pin["bytes"]==SIZE,"NDK_COMPILER_LENGTH"
 assert pin["sha256"]==HASHES[role],"NDK_COMPILER_HASH_PIN"
 assert pin["ndkRevision"]==ndk.REVISION and pin["compilerVersion"]==VERSION and pin["provenance"]==PROVENANCE,"NDK_COMPILER_PROVENANCE_OR_VERSION"
 assert isinstance(pin["identity"],list) and len(pin["identity"])==2 and all(type(n) is int for n in pin["identity"]),"NDK_COMPILER_IDENTITY_SCHEMA"
 assert type(pin["modifiedNs"]) is int and pin["modifiedNs"]>=0,"NDK_COMPILER_MTIME_SCHEMA"
 return pin
def pinned(path,meta,pin):
 schema(pin);role=pin["role"];assert str(path)==str(PATHS[role]),"NDK_COMPILER_EXACT_PATH"
 assert [meta.st_dev,meta.st_ino]==pin["identity"] and meta.st_mtime_ns==pin["modifiedNs"],"NDK_COMPILER_STALE_IDENTITY"
 assert meta.st_size==SIZE,"NDK_COMPILER_LENGTH"
 return HASHES[role]
def environment(env):
 ndk.environment(env)
 for key,role in (("CARGO_TARGET_AARCH64_LINUX_ANDROID_LINKER","clang.exe"),("CC_aarch64_linux_android","clang.exe"),("CXX_aarch64_linux_android","clang++.exe")):assert env.get(key)==str(PATHS[role]),"NDK_COMPILER_TARGET_ROLE"
 for key in ("CFLAGS_aarch64_linux_android","CXXFLAGS_aarch64_linux_android"):assert env.get(key)=="--target=aarch64-linux-android29","NDK_COMPILER_TARGET_FLAGS"
def unique_pairs(items):
 result={}
 for key,value in items:
  assert key not in result,"NDK_COMPILER_DUPLICATE_FIELD";result[key]=value
 return result
def bindings(env):
 value=env.get(KEY);assert isinstance(value,str) and 0<len(value)<=4096,"NDK_COMPILER_BINDING_BOUND"
 records=json.loads(value,object_pairs_hook=unique_pairs);assert isinstance(records,dict) and set(records)==set(HASHES),"NDK_COMPILER_ROLE_SET"
 for role,pin in records.items():schema(pin);assert pin["role"]==role,"NDK_COMPILER_SWAPPED_ROLE"
 environment(env);ndk.revision()
 return records
def select(env,path):
 if KEY not in env:return None
 records=bindings(env)
 for role in HASHES:
  if str(path)==str(PATHS[role]):return records[role]
 return None
def qualify(env,sample=None):
 from build_guard import executable_snapshot
 assert KEY not in env,"NDK_COMPILER_REQUIRE_FRESH_ENV"
 environment(env);ndk.revision();records={}
 for role,path in PATHS.items():
  meta=path.lstat();pin={"role":role,"path":str(path),"identity":[meta.st_dev,meta.st_ino],"bytes":SIZE,"modifiedNs":meta.st_mtime_ns,"sha256":HASHES[role],"ndkRevision":ndk.REVISION,"compilerVersion":VERSION,"provenance":PROVENANCE}
  row=executable_snapshot(path,sample,large_ndk_compiler_binding=pin)
  assert row["identity"]==pin["identity"] and row["bytes"]==SIZE and row["modifiedNs"]==pin["modifiedNs"] and row["sha256"]==HASHES[role],"NDK_COMPILER_QUALIFICATION_CHANGED"
  records[role]=pin
 return {KEY:json.dumps(records,separators=(",",":"))}
def version_environment(name,host,android):
 assert name in ("rustc","javac","ndkClang","ndkClangXX","ndkArchiver"),"UNKNOWN_VERSION_PROBE_ROLE"
 assert KEY not in host and ndk.KEY not in host,"NDK_ALLOWANCE_IN_HOST_ENV"
 if name in ("rustc","javac"):return host
 assert select(android,PATHS["clang.exe"]) is not None,"QUALIFIED_ANDROID_PROBE_ENV_REQUIRED"
 return android
def check_version(text):
 assert isinstance(text,str) and 0<len(text)<=4096 and re.search(r"\bclang version 21\.0\.0(?:\s|$)",text),"NDK_COMPILER_RUNTIME_VERSION"
