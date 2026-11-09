"""Configure-only qualification of installed Git/MSYS Perl; no Cargo or OpenSSL compilation."""
import pathlib,os,json,hashlib,urllib.request,tarfile,stat,sys,shutil
from check_source import source_check
from build_guard import Guard,clean_env,android_env,MIN_FREE,MAX_OUTPUT
ROOT=pathlib.Path(__file__).resolve().parents[1]
VERSION="300.6.1+3.6.3"
CHECKSUM="46eb8fb9fb3b61ce1c0f8a026c4c1a0714d3a9e138e7fbde78753ce2babc3846"
ARCHIVE_LIMIT=32*1024**2
EXTRACT_LIMIT=256*1024**2
MEMBER_LIMIT=50000
PREFIX="openssl-src-"+VERSION+"/"
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def safe_member(name):
 p=pathlib.PurePosixPath(name)
 assert not p.is_absolute() and ".." not in p.parts and "\\" not in name and ":" not in name,"ARCHIVE_PATH"
 assert name.startswith(PREFIX),"ARCHIVE_PREFIX"
 return p
def validate_members(members):
 assert len(members)<=MEMBER_LIMIT,"ARCHIVE_MEMBER_COUNT"
 seen=set();total=0
 for m in members:
  safe_member(m.name)
  assert m.name not in seen,"ARCHIVE_DUPLICATE"
  seen.add(m.name)
  assert m.isdir() or m.isfile(),"ARCHIVE_LINK_OR_SPECIAL"
  assert 0<=m.size<=16*1024**2,"ARCHIVE_FILE_SIZE"
  total+=m.size
  assert total<=EXTRACT_LIMIT,"ARCHIVE_EXTRACT_SIZE"
 return total
def materialize(work):
 archive=work/"openssl-src.crate"
 request=urllib.request.Request("https://static.crates.io/crates/openssl-src/openssl-src-"+VERSION+".crate",headers={"User-Agent":"Vibetram-configure-qualification"})
 with urllib.request.urlopen(request,timeout=45) as response,archive.open("xb") as target:
  assert response.status==200 and response.url.startswith("https://static.crates.io/"),"OFFICIAL_ARCHIVE_ROUTE"
  total=0
  while True:
   block=response.read(65536)
   if not block: break
   total+=len(block);assert total<=ARCHIVE_LIMIT,"ARCHIVE_DOWNLOAD_SIZE";target.write(block)
 assert sha(archive)==CHECKSUM,"LOCKED_ARCHIVE_CHECKSUM"
 with tarfile.open(archive,"r:gz") as tar:
  members=tar.getmembers();total=validate_members(members)
  for m in members:
   p=work/"crate"/m.name
   if m.isdir():p.mkdir(parents=True,exist_ok=True)
   else:
    p.parent.mkdir(parents=True,exist_ok=True)
    with tar.extractfile(m) as src,p.open("xb") as dst:shutil.copyfileobj(src,dst,65536)
 lib=(work/"crate"/PREFIX/"src/lib.rs").read_text(encoding="utf-8")
 assert 'env::var("OPENSSL_SRC_PERL")' in lib and 'env::var("PERL")' in lib,"PINNED_PERL_OVERRIDE_ABSENT"
 assert '"aarch64-linux-android" => "linux-aarch64"' in lib,"PINNED_TARGET_CHANGED"
 print(json.dumps({"archiveSHA256":sha(archive),"archiveBytes":archive.stat().st_size,"extractedBytes":total,"memberCount":len(members),"pinnedPerlOverride":True}))
def regular_chain(path):
 for p in [path,*path.parents]:
  m=os.lstat(p)
  assert not m.st_file_attributes&0x400 and not m.st_reparse_tag,"TOOL_REPARSE"
 assert path.is_file(),"TOOL_NOT_FILE"
def configure_args(prefix):
 return ["./Configure","--prefix="+prefix,"--openssldir=/usr/local/ssl","no-shared","no-module","no-tests","no-comp","no-zlib","no-zlib-dynamic","--libdir=lib","no-ssl3","no-md2","no-rc5","no-weak-ssl-ciphers","no-camellia","no-idea","no-seed","no-stdio","linux-aarch64","-O2","-DANDROID","-ffunction-sections","-fdata-sections","-fPIC","--target=aarch64-linux-android","-w","--target=aarch64-linux-android29"]
def perl_metadata_program():
 return """use Config;
use File::Spec::Functions qw(rel2abs);
use JSON::PP;
my $p = rel2abs(".");
print encode_json({version=>$Config{version},arch=>$Config{archname},os=>$^O,unixPaths=>((index($p,"/")>=0 && index($p,chr(92))<0) ? JSON::PP::true : JSON::PP::false)});
"""
def validate_perl_metadata(data):
 assert type(data) is dict and set(data)=={"version","arch","os","unixPaths"},"PERL_METADATA_SCHEMA"
 for key in ("version","arch","os"):
  assert type(data[key]) is str and 0<len(data[key])<=160 and all(c.isalnum() or c in ".-_+" for c in data[key]),"PERL_METADATA_FIELD"
 assert type(data["unixPaths"]) is bool,"PERL_METADATA_BOOLEAN"
 assert data["unixPaths"],"UNQUALIFIED_PERL_UNIX_PATHS"
 return data
def probe_environment(work,cargo,rustup):
 env=clean_env(os.environ,work)
 env.update(CARGO_HOME=str(cargo),RUSTUP_HOME=str(rustup))
 assert env.get("SystemRoot") and env.get("WINDIR"),"WINDOWS_SYSTEM_ENVIRONMENT_MISSING"
 return env
def probe_layout(root):
 roots=[root/name for name in ("openssl-probe-work","openssl-probe-output","openssl-probe-cargo","openssl-probe-rustup")]
 assert all(not a.is_relative_to(b) and not b.is_relative_to(a) for i,a in enumerate(roots) for b in roots[i+1:]),"OVERLAPPING_PROBE_ROOTS"
 return roots
PHYSICAL_SDK=pathlib.Path(r"C:\Program Files (x86)\Android\android-sdk")
def with_physical_ndk_inputs(guard,env,out,callback):
 from ndk_input_metadata import capture_one
 ndk=PHYSICAL_SDK/"ndk/30.0.16248370";tools=ndk/"toolchains/llvm/prebuilt/windows-x86_64/bin"
 paths=[ndk/"source.properties",tools/"clang.exe",tools/"llvm-ar.exe",tools/"llvm-ranlib.exe"]
 rows={}
 def step(index):
  if index==len(paths):
   assert "Pkg.Revision = 30.0.16248370" in paths[0].read_text(encoding="utf-8"),"PINNED_NDK_REVISION"
   callback(ndk,tools);return
  p=paths[index];row=capture_one(ndk,p,callback=lambda:step(index+1));rows[p.name]=row
  assert row["qualified"] and row.get("callbackSucceeded"),"PHYSICAL_NDK_INPUT_OR_CALLBACK_FAILED"
 try:
  alias=capture_one(PHYSICAL_SDK,pathlib.Path(r"C:\Android\android-sdk"),directory=True,expected_target=PHYSICAL_SDK,callback=lambda:step(0))
  rows["sdkAlias"]=alias
  assert alias["qualified"] and alias.get("callbackSucceeded"),"SDK_MAPPING_OR_CALLBACK_FAILED"
 finally:
  report={"state":"PHYSICAL_NDK_LEASE_REPORT","physicalSDK":str(PHYSICAL_SDK),"physicalNDK":str(ndk),"inputs":rows,"aliasTraversed":False,"permissionsChanged":False,"compilerBuildRequested":False}
  text=json.dumps(report,indent=2)+"\n";assert len(text.encode())<32768;(out/"physical-ndk-qualification.json").write_text(text,encoding="utf-8");print(text,flush=True)
 return rows
def main():
 assert os.name=="nt" and os.environ.get("GITHUB_REPOSITORY")=="TroubledPerson/Vibetram" and os.environ.get("GITHUB_REF")=="refs/heads/main"
 event=json.loads(pathlib.Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
 assert os.environ["GITHUB_EVENT_NAME"]=="push" and "[openssl-probe-191]" in event["head_commit"]["message"]
 source_check(ROOT)
 work,out,cargo,rustup=probe_layout(ROOT)
 assert not any(p.exists() for p in (work,out,cargo,rustup)),"PRESERVE_EXISTING_PROBE"
 assert shutil.disk_usage(ROOT).free>=MIN_FREE+MAX_OUTPUT
 work.mkdir();out.mkdir();cargo.mkdir();rustup.mkdir()
 for p in ("tmp","home","profile","profile/AppData/Local","profile/AppData/Roaming"):(work/p).mkdir(parents=True,exist_ok=True)
 env=probe_environment(work,cargo,rustup);guard=Guard(ROOT,work,out,env)
 guard.run([sys.executable,"-B",__file__,"--materialize",str(work)],env=env,timeout=180)
 git=pathlib.Path(r"C:\Program Files\Git\cmd\git.exe");perl=git.parents[1]/"usr/bin/perl.exe"
 regular_chain(git);regular_chain(perl)
 git_version=guard.run([git,"--version"],env=env,capture=True,timeout=15).stdout.strip()
 metadata_program=work/"perl-metadata.pl";metadata_program.write_text(perl_metadata_program(),encoding="ascii")
 details=json.loads(guard.run([perl,metadata_program],env=env,capture=True,timeout=15).stdout)
 preliminary={"gitVersion":git_version,"gitSHA256":sha(git),"perlPath":str(perl),"perlSHA256":sha(perl),"metadata":details}
 (out/"installed-perl-metadata.json").write_text(json.dumps(preliminary,indent=2)+"\n",encoding="utf-8")
 validate_perl_metadata(details)
 print("INSTALLED_PERL_METADATA "+json.dumps(preliminary),flush=True)
 src=work/"crate"/PREFIX/"openssl"
 def configure_physical(ndk,tools):
  cross=android_env(env,ndk);cross["OPENSSL_SRC_PERL"]=str(perl);cross["PERL"]=str(perl)
  cross.update(CC=str(tools/"clang.exe"),CFLAGS="--target=aarch64-linux-android29",AR=str(tools/"llvm-ar.exe"),ARFLAGS="crs",RANLIB=str(tools/"llvm-ranlib.exe"))
  guard.run([perl,"-e","require q(./Configurations/unix-checker.pm);"],cwd=src,env=cross,capture=True,timeout=15)
  guard.run([perl,*configure_args((work/"install").as_posix())],cwd=src,env=cross,capture=True,timeout=120)
 physical_inputs=with_physical_ndk_inputs(guard,env,out,configure_physical)
 makefile=src/"Makefile";assert makefile.is_file() and makefile.stat().st_size<16*1024**2,"CONFIGURE_MAKEFILE_MISSING"
 text=makefile.read_text(encoding="utf-8")
 assert "PLATFORM=linux-aarch64" in text and "--target=aarch64-linux-android29" in text,"CONFIGURE_TARGET_NOT_PRESERVED"
 make_candidates=[]
 for p in [git.parents[1]/"usr/bin/make.exe",pathlib.Path(r"C:\msys64\usr\bin\make.exe")]:
  if p.exists():
   regular_chain(p);v=guard.run([p,"--version"],env=env,capture=True,timeout=15).stdout.splitlines()[0]
   make_candidates.append({"path":str(p),"sha256":sha(p),"version":v})
 report={"state":"PASS_CONFIGURE_ONLY_NOT_COMPILED","physicalInputMetadata":physical_inputs,"gitVersion":git_version,"gitSHA256":sha(git),"perlPath":str(perl),"perlSHA256":sha(perl),"perlVersion":details["version"],"perlArch":details["arch"],"perlOS":details["os"],"OpenSSLUnixCheckerPassed":True,"unixPathSemantics":True,"opensslVersion":"3.6.3","crateVersion":VERSION,"archiveSHA256":CHECKSUM,"makefileSHA256":sha(makefile),"makeCandidates":make_candidates,"dependencyVersionsChanged":False,"compiled":False,"signed":False,"releasable":False,"provenance":"Installed Git for Windows on official GitHub hosted Windows image; binary hashes observed, not independent publisher attestation","monitor":guard.report()}
 source_check(ROOT);(out/"qualification.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8");print(json.dumps(report,indent=2))
if __name__=="__main__":
 if len(sys.argv)==3 and sys.argv[1]=="--materialize":materialize(pathlib.Path(sys.argv[2]))
 else:main()
