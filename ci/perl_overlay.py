"""Pinned pure-Perl build-tool overlay in a single ephemeral job; never system install."""
import pathlib,hashlib,tarfile,io,re,json,urllib.request,os,sys
from perl_prerequisites import imports,module_set,program,parse
ARCHIVE_SHA="b009ff51f4fb108d19961a523e99b4373ccf958d37ca35bf1583215908dca9a9"
MODULE_SHA="bc8d1474d8c70a284b898c5bfa7ec1b0246427571d9d9404af8908c94ac67b62"
ARCHIVE_BYTES=9223
URL="https://cpan.metacpan.org/authors/id/J/JE/JESSE/Locale-Maketext-Simple-0.21.tar.gz"
PREFIX="Locale-Maketext-Simple-0.21"
GIT_PERL_SHA="c0e2fb0e8be3962cdc7aa1391f104df6502191029ec15977a37623afb32c7b36"
def review(data):
 assert len(data)==ARCHIVE_BYTES and hashlib.sha256(data).hexdigest()==ARCHIVE_SHA,"PINNED_CPAN_ARCHIVE_MISMATCH"
 selected={};seen=set();total=0
 with tarfile.open(fileobj=io.BytesIO(data),mode="r:gz") as tar:
  members=tar.getmembers();assert 0<len(members)<=128,"CPAN_MEMBER_COUNT"
  for m in members:
   p=pathlib.PurePosixPath(m.name)
   assert not p.is_absolute() and ".." not in p.parts and "\\" not in m.name and ":" not in m.name,"CPAN_PATH"
   assert p.parts and p.parts[0]==PREFIX and re.fullmatch(r"[A-Za-z0-9_./-]+",m.name),"CPAN_PREFIX"
   key=m.name.rstrip("/").casefold();assert key not in seen,"CPAN_DUPLICATE";seen.add(key)
   assert m.isdir() or m.isfile(),"CPAN_LINK_OR_SPECIAL"
   assert 0<=m.size<=128*1024,"CPAN_FILE_SIZE";total+=m.size;assert total<=1024**2,"CPAN_TOTAL_SIZE"
   assert not m.name.lower().endswith((".xs",".c",".so",".dll",".exe")),"NOT_PURE_PERL"
   if m.name in [PREFIX+"/"+x for x in ("lib/Locale/Maketext/Simple.pm","README","META.yml","Makefile.PL")]:
    assert m.isfile(),"CPAN_EXPECTED_REGULAR_FILE";selected[m.name[len(PREFIX)+1:]]=tar.extractfile(m).read()
 assert set(selected)=={"lib/Locale/Maketext/Simple.pm","README","META.yml","Makefile.PL"},"CPAN_REQUIRED_FILES"
 assert hashlib.sha256(selected["lib/Locale/Maketext/Simple.pm"]).hexdigest()==MODULE_SHA,"PINNED_MODULE_MISMATCH"
 meta=selected["META.yml"].decode("utf-8");body=selected["lib/Locale/Maketext/Simple.pm"].decode("utf-8")
 assert re.search(r"^\s*name:\s+Locale-Maketext-Simple\s*$",meta,re.M) and re.search(r"^\s*version:\s+0[.]21\s*$",meta,re.M),"CPAN_PACKAGE_IDENTITY"
 assert re.search(r"^\s*requires:\s*\{\s*\}",meta,re.M),"NEW_RUNTIME_DEPENDENCIES"
 assert re.search(r"^\s*license:\s*perl\s*$",meta,re.M),"CPAN_LICENCE_METADATA"
 assert imports(body)=={"base","strict"} and "use base 'Locale::Maketext';" in body and re.search(r"eval\s*\{\s*require\s+Locale::Maketext::Lexicon;\s*1\s*}\s*or\s*return;",body),"UNREVIEWED_MODULE_IMPORT"
 assert "COPYRIGHT" in body and "MIT" in body,"MODULE_NOTICE_ABSENT"
 return selected,{"archiveSHA256":ARCHIVE_SHA,"archiveBytes":len(data),"moduleSHA256":MODULE_SHA,"declaredRuntimeDependencies":{},"observedCoreImports":["strict"],"optionalBranchImports":["Locale::Maketext::Lexicon","File::Spec","base/Locale::Maketext"],"optionalLexicon":"Documented fallback when Locale::Maketext::Lexicon is absent; focused runtime test required","metadataLicense":"perl; complete original module/README/META/Makefile notices retained","memberCount":len(members),"uncompressedBytes":total,"sourceReviewedBeforeCopy":True}
def prepare(work,out):
 root=pathlib.Path(__file__).resolve().parents[1]
 assert work==root/"openssl-probe-work" and out==root/"openssl-probe-output" and work.is_dir() and out.is_dir(),"OWNED_OVERLAY_SCOPE"
 target=work/"perl-overlay";assert not target.exists(),"PRESERVE_EXISTING_OVERLAY"
 class NoRedirect(urllib.request.HTTPRedirectHandler):
  def redirect_request(self,*args,**kwargs):raise AssertionError("CPAN_REDIRECT_STOP")
 with urllib.request.build_opener(NoRedirect()).open(URL,timeout=25) as r:
  assert r.status==200 and r.url==URL,"CPAN_SOURCE_CHANGED"
  data=r.read(32769);assert len(data)<=32768,"CPAN_DOWNLOAD_BOUND"
 files,report=review(data)
 target.mkdir();(target/"lib/Locale/Maketext").mkdir(parents=True);(target/"notices").mkdir()
 for name,body in files.items():
  destination=target/name if name.startswith("lib/") else target/"notices"/name
  with destination.open("xb") as f:f.write(body)
 with (target/"source.tar.gz").open("xb") as f:f.write(data)
 with (target/"lib/.vibetram-module-pin").open("x",encoding="ascii") as f:f.write(MODULE_SHA)
 report.update(state="PREPARED_JOB_ONLY_PERL_OVERLAY",systemInstallationChanged=False,installerExecuted=False,packageCodeExecuted=False,overlayRelative="openssl-probe-work/perl-overlay")
 (out/"perl-overlay-review.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8");print(json.dumps(report,indent=2),flush=True)
def resolver_program():
 return r'''use strict;
use Cwd qw(abs_path);
my $p=abs_path("perl-overlay/lib");die "overlay path unavailable" unless defined($p);
open my $f,"<","$p/.vibetram-module-pin" or die "overlay pin unavailable";
local $/;my $pin=<$f>;close($f) or die "pin close failed";
print join(chr(9),"OVERLAY",$p,$pin),chr(10);
'''
def parse_overlay_path(text):
 rows=text.splitlines();assert len(rows)==1,"OVERLAY_PROTOCOL"
 fields=rows[0].split("\t");assert len(fields)==3 and fields[0]=="OVERLAY" and fields[2]==MODULE_SHA,"OVERLAY_PIN_PROTOCOL"
 value=fields[1];p=pathlib.PurePosixPath(value)
 assert p.is_absolute() and not value.startswith("//") and ".." not in p.parts and re.fullmatch(r"/[A-Za-z0-9_./+-]+",value),"OVERLAY_POSIX_SCOPE"
 assert value.endswith("/openssl-probe-work/perl-overlay/lib"),"OVERLAY_PATH_SUFFIX"
 return value
def focused_program():
 return r'''use strict;
use warnings;
use Locale::Maketext::Simple Style=>"gettext";
use Params::Check ();
use IPC::Cmd ();
die "module version" unless Locale::Maketext::Simple->VERSION eq "0.21";
die "localization" unless loc("synthetic %1","fixture") eq "synthetic fixture";
my %template=(name=>{required=>1,defined=>1,allow=>["fixture"]});
my %valid=(name=>"fixture");my $accepted=Params::Check::check(\%template,\%valid,0);
die "valid parameter" unless defined($accepted) && $accepted->{name} eq "fixture";
my %invalid=(name=>"blocked");
die "invalid parameter" if defined Params::Check::check(\%template,\%invalid,0);
die "IPC functions" unless IPC::Cmd->can("run") && IPC::Cmd->can("can_run");
print '{"state":"PASS_FOCUSED_PERL_TOOL_CHECKS","checks":5,"externalCommandsExecuted":false}',chr(10);
'''
def repair_git_perl(guard,env,work,out,src,original):
 from ndk_input_metadata import capture_one
 row=next((x for x in original["candidates"] if x["installation"]=="Git for Windows"),None)
 assert row and row["status"]=="INVENTORIED" and row["sha256"]==GIT_PERL_SHA and row["metadata"]["version"]=="5.42.3" and row["metadata"]["unixPaths"],"CHANGED_GIT_PERL_INPUT"
 missing={m for v in row["modules"].values() for m in v["missing"]}
 assert missing=={"Locale::Maketext::Simple"},"UNEXPECTED_MISSING_DEPENDENCY"
 assert all(row["modules"].get(m,{}).get("loaded") for m in ("base","Exporter","strict")),"CORE_OVERLAY_DEPENDENCY_MISSING"
 guard.run([sys.executable,"-B",__file__,"--prepare",str(work),str(out)],env=env,timeout=60)
 perl=pathlib.Path(row["path"]);resolver=work/"perl-overlay-path.pl";resolver.write_text(resolver_program(),encoding="ascii")
 modules,_=module_set(src);results={};next_env=env.copy()
 def callback():
  assert hashlib.sha256(perl.read_bytes()).hexdigest()==GIT_PERL_SHA,"PERL_BINARY_CHANGED"
  posix=parse_overlay_path(guard.run([perl,resolver],cwd=work,env=env,capture=True,timeout=15).stdout)
  next_env["PERL5LIB"]=posix
  script=work/"perl-overlay-required.pl";script.write_text(program(modules),encoding="ascii")
  loaded=parse(guard.run([perl,script],cwd=src,env=next_env,capture=True,timeout=25).stdout,modules)
  assert loaded["complete"] and loaded["modules"]["Locale::Maketext::Simple"]["version"]=="0.21","OVERLAY_MODULE_SMOKE_FAILED"
  smoke=work/"perl-overlay-focused.pl";smoke.write_text(focused_program(),encoding="ascii")
  focused=json.loads(guard.run([perl,smoke],cwd=src,env=next_env,capture=True,timeout=25).stdout)
  assert focused=={"state":"PASS_FOCUSED_PERL_TOOL_CHECKS","checks":5,"externalCommandsExecuted":False},"OVERLAY_FOCUSED_TESTS_FAILED"
  results.update(loaded);results["focused"]=focused
 module=work/"perl-overlay/lib/Locale/Maketext/Simple.pm"
 def module_callback():
  assert hashlib.sha256(module.read_bytes()).hexdigest()==MODULE_SHA,"OVERLAY_MODULE_CHANGED"
  callback()
 def interpreter_callback():
  results["moduleInputLease"]=capture_one(work/"perl-overlay",module,callback=module_callback)
  assert results["moduleInputLease"]["qualified"] and results["moduleInputLease"].get("callbackSucceeded"),"OVERLAY_MODULE_INPUT_FAILED"
 lease=capture_one(perl.parent,perl,callback=interpreter_callback)
 assert lease["qualified"] and lease.get("callbackSucceeded"),"OVERLAY_INTERPRETER_OR_SMOKE_FAILED"
 selected={**row,**results,"complete":True,"overlayUsed":True}
 report={"state":"PASS_JOB_ONLY_PERL_OVERLAY_SMOKE","archiveSHA256":ARCHIVE_SHA,"moduleSHA256":MODULE_SHA,"interpreterSHA256":GIT_PERL_SHA,"requiredModuleCount":len(modules),"modules":results["modules"],"focused":results["focused"],"moduleInputLease":results["moduleInputLease"],"moduleCodeExecutedForSmoke":True,"moduleCodeUnmodified":True,"systemInstallationChanged":False,"childOnlyPERL5LIB":True,"inputLease":lease}
 (out/"perl-overlay-module-smoke.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8");print(json.dumps(report,indent=2),flush=True)
 return selected,next_env,report

# Versions are the releases shipped by upstream Perl 5.42.3 (Porting/Maintainers.pl).
# Archive hashes verified against each official CPAN author's CHECKSUMS, without eval.
RUNTIME_PACKAGES=(
 ("B/BI/BINGOS","ExtUtils-MakeMaker-7.76","30bcfd75fec4d512e9081c792f7cb590009d9de2fe285ffa8eec1be35a5ae7ca","ExtUtils-MakeMaker","7.76"),
 ("R/RR/RRA","podlators-v6.0.2","2992125eab7d2b1c5a2b15a26ad7955f7d989eba6c831abdcaf2000e86a91337","podlators","v6.0.2"),
 ("K/KH/KHW","Pod-Simple-3.45","8483bb95cd3e4307d66def092a3779f843af772482bfdc024e3e00d0c4db0cfa","Pod-Simple","3.45"),
 ("N/NE/NEILB","Pod-Escapes-1.07","dbf7c827984951fb248907f940fd8f19f2696bc5545c0a15287e0fbe56a52308","Pod-Escapes","1.07"))
ACTIVE_MM={"ExtUtils::MakeMaker","ExtUtils::MM","ExtUtils::MM_Cygwin","ExtUtils::MM_Unix","ExtUtils::MM_Any","ExtUtils::MM_Win32","ExtUtils::MY","ExtUtils::Liblist","ExtUtils::Liblist::Kid","ExtUtils::MakeMaker::Config","ExtUtils::MakeMaker::version"}

def runtime_review(data,pin):
 author,prefix,digest,name,version=pin
 assert len(data)<=2*1024**2 and hashlib.sha256(data).hexdigest()==digest,"RUNTIME_ARCHIVE_CHECKSUM"
 files={};seen=set();total=0
 with tarfile.open(fileobj=io.BytesIO(data),mode="r:gz") as tar:
  members=tar.getmembers();assert 0<len(members)<=1024,"RUNTIME_MEMBER_COUNT"
  for m in members:
   path=pathlib.PurePosixPath(m.name)
   assert path.parts and path.parts[0]==prefix and not path.is_absolute() and ".." not in path.parts and "\\" not in m.name and ":" not in m.name,"RUNTIME_MEMBER_PATH"
   assert re.fullmatch(r"[A-Za-z0-9_./+ -]+",m.name),"RUNTIME_MEMBER_CHARACTERS"
   key=m.name.rstrip("/").casefold();assert key not in seen,"RUNTIME_DUPLICATE";seen.add(key)
   assert m.isfile() or m.isdir(),"RUNTIME_LINK_OR_SPECIAL"
   total+=m.size;assert 0<=m.size<=2*1024**2 and total<=8*1024**2,"RUNTIME_EXTRACT_BOUND"
   if m.isfile():
    rel=m.name[len(prefix)+1:]
    if rel.startswith("lib/"):
     assert rel.endswith((".pm",".pod")),"RUNTIME_NON_PURE_LIBRARY"
     if rel.endswith(".pod"):continue # Documentation remains preserved in the raw archive; never executable overlay input.
     module=rel[4:-3].replace("/","::");assert re.fullmatch(r"[A-Za-z_]\w*(?:::\w+)*",module),"RUNTIME_MODULE_NAME"
     files[rel]=tar.extractfile(m).read()
    elif rel in ("META.json","META.yml","README","README.md","LICENSE","COPYING","COPYRIGHT"):
     files[rel]=tar.extractfile(m).read()
 assert "META.json" in files and any(x.startswith("lib/") for x in files),"RUNTIME_METADATA_MISSING"
 meta=json.loads(files["META.json"])
 assert meta["name"]==name and str(meta["version"])==version and meta["license"]==["perl_5"],"RUNTIME_METADATA_IDENTITY"
 requires=meta["prereqs"]["runtime"].get("requires",{})
 assert type(requires) is dict and len(requires)<=32,"RUNTIME_REQUIRES_SCHEMA"
 for module,minimum in requires.items():
  assert re.fullmatch(r"[A-Za-z_]\w*(?:::\w+)*",module) and type(minimum) is str and re.fullmatch(r"[0-9.v_]+",minimum),"RUNTIME_REQUIREMENT_FIELD"
 return files,{"distribution":name,"version":version,"archiveSHA256":digest,"archiveBytes":len(data),"memberCount":len(members),"unpackedBytes":total,"runtimeRequires":requires,"license":meta["license"]}

def runtime_prepare(work,out):
 root=pathlib.Path(__file__).resolve().parents[1]
 assert work==root/"openssl-probe-work" and out==root/"openssl-probe-output" and work.is_dir() and out.is_dir(),"RUNTIME_OWNED_SCOPE"
 target=work/"runtime-packages";target.mkdir() # exclusive; preserve any previous result
 class NoRedirect(urllib.request.HTTPRedirectHandler):
  def redirect_request(self,*args,**kwargs):raise AssertionError("RUNTIME_CPAN_REDIRECT")
 opener=urllib.request.build_opener(NoRedirect());packages=[];providers={}
 for pin in RUNTIME_PACKAGES:
  author,prefix,digest,name,version=pin;url="https://cpan.metacpan.org/authors/id/"+author+"/"+prefix+".tar.gz"
  with opener.open(url,timeout=25) as response:
   assert response.status==200 and response.url==url,"RUNTIME_REGISTRY_ROUTE"
   data=response.read(2*1024**2+1)
  files,report=runtime_review(data,pin);destination=target/prefix;destination.mkdir()
  with (destination/"source.tar.gz").open("xb") as f:f.write(data)
  for rel,body in files.items():
   p=destination/rel;p.parent.mkdir(parents=True,exist_ok=True)
   with p.open("xb") as f:f.write(body)
   if rel.startswith("lib/"):
    module=rel[4:-3].replace("/","::");assert module not in providers,"RUNTIME_PROVIDER_COLLISION"
    providers[module]={"relative":prefix+"/"+rel,"sha256":hashlib.sha256(body).hexdigest()}
  packages.append(report)
 plan={"packages":packages,"providers":providers,"installed":False,"installerExecuted":False,"nativeCodeCopied":False}
 (out/"runtime-package-plan.json").write_text(json.dumps(plan,indent=2)+"\n",encoding="utf-8")
 print(json.dumps({"state":"REVIEWED_RUNTIME_PACKAGE_BATCH","packages":packages,"providerCount":len(providers)}),flush=True)

def presence_program(modules):
 assert modules and len(modules)<=128 and all(re.fullmatch(r"[A-Za-z_]\w*(?:::\w+)*",m) for m in modules)
 return r'''use strict;
use warnings;
use JSON::PP;
use Digest::SHA ();
use Errno qw(ENOENT ENOTDIR);
my %result;
for my $m (qw(__MODULES__)) {
 my $relative=$m;$relative=~s{::}{/}g;$relative.=".pm";
 my @found;
 for my $dir (@INC) {
  die "unqualified INC hook" if ref($dir);
  my $p="$dir/$relative";
  my @s=lstat($p);
  if (!@s) {die "module metadata inaccessible" unless $! == ENOENT || $! == ENOTDIR;next;}
  die "module link or special" unless -f _ && !-l _;
  open my $f,"<",$p or die "module read denied";binmode($f);
  my $h=Digest::SHA->new(256)->addfile($f)->hexdigest;close($f) or die "module close failed";
  push @found,$h;
 }
 $result{$m}=\@found;
}
print JSON::PP::encode_json(\%result),chr(10);
'''.replace("__MODULES__"," ".join(modules))

def runtime_helper_program():
 return r'''use strict;
use warnings;
use JSON::PP;
use IPC::Cmd ();
use Cwd qw(abs_path);
my @checks;
# Do not preload MakeMaker: the first real can_run must exercise IPC's delayed require.
for my $windows (@ARGV) {
 my $p=Cygwin::win_to_posix_path($windows,1);
 die "invalid tool path" unless defined($p) && $p=~m{^/} && -f $p && -x $p;
 my $found=IPC::Cmd::can_run($p);
 die "can_run identity" unless defined($found) && abs_path($found) eq abs_path($p);
 push @checks,"can_run";
 my $mm=MM->maybe_command($p);
 die "maybe_command identity" unless defined($mm) && abs_path($mm) eq abs_path($p);
 push @checks,"maybe_command";
}
die "missing path accepted" if IPC::Cmd::can_run(abs_path(".")."/vibetram-nonexistent-runtime-tool");
push @checks,"missing_rejected";
die "directory accepted" if MM->maybe_command(abs_path("."));
push @checks,"directory_rejected";
my %loaded=map {$_=>JSON::PP::true} keys %INC;
print JSON::PP::encode_json({state=>"PASS_ACTUAL_COMPILER_DISCOVERY_HELPERS",checks=>scalar(@checks),canRunCalls=>scalar(@ARGV)+1,maybeCommandCalls=>scalar(@ARGV)+1,externalCommandsExecuted=>JSON::PP::false,makeMakerVersion=>$ExtUtils::MakeMaker::VERSION,loaded=>\%loaded}),chr(10);
'''

def select_missing(providers,presence):
 assert set(providers)==set(presence),"RUNTIME_PRESENCE_SCHEMA"
 missing=[]
 for module,pin in providers.items():
  hashes=presence[module];assert type(hashes) is list and len(hashes)<=16,"RUNTIME_PRESENCE_RECORD"
  assert all(type(h) is str and re.fullmatch(r"[a-f0-9]{64}",h) for h in hashes),"RUNTIME_PRESENCE_HASH"
  if hashes:
   assert all(h==pin["sha256"] for h in hashes),"EXISTING_RUNTIME_MODULE_DIFFERS_NO_SHADOW"
  else:missing.append(module)
 return sorted(missing)


def runtime_version_program(requirements):
 body="use strict;\n"
 for module,minimums in sorted(requirements.items()):
  assert re.fullmatch(r"[A-Za-z_]\w*(?:::\w+)*",module),"RUNTIME_VERSION_MODULE"
  for minimum in minimums:
   assert re.fullmatch(r"[0-9.v_]+",minimum),"RUNTIME_VERSION_REQUIREMENT"
   body+='{my $m="'+module+'";my $f=$m;$f=~s{::}{/}g;require "$f.pm";$m->VERSION("'+minimum+'");}\n'
 return body+'print "PASS_RUNTIME_MINIMUM_VERSIONS\\n";\n'

def runtime_diagnosis():
 from openssl_probe import ROOT,PREFIX,probe_layout,probe_environment,with_physical_ndk_inputs
 from build_guard import Guard,MIN_FREE,MAX_OUTPUT
 from check_source import source_check
 from perl_prerequisites import inventory
 from ndk_input_metadata import capture_one
 import shutil
 assert os.name=="nt" and os.environ.get("GITHUB_REPOSITORY")=="TroubledPerson/Vibetram" and os.environ.get("GITHUB_REF")=="refs/heads/main"
 event=json.loads(pathlib.Path(os.environ["GITHUB_EVENT_PATH"]).read_text());assert os.environ["GITHUB_EVENT_NAME"]=="push" and "[perl-runtime-191]" in event["head_commit"]["message"]
 source_check(ROOT);work,out,cargo,rustup=probe_layout(ROOT)
 assert not any(p.exists() for p in (work,out,cargo,rustup)),"PRESERVE_RUNTIME_OUTPUTS"
 assert shutil.disk_usage(ROOT).free>=MIN_FREE+MAX_OUTPUT
 for p in (work,out,cargo,rustup):p.mkdir()
 for p in ("tmp","home","profile","profile/AppData/Local","profile/AppData/Roaming"):(work/p).mkdir(parents=True,exist_ok=True)
 env=probe_environment(work,cargo,rustup);guard=Guard(ROOT,work,out,env)
 guard.run([sys.executable,"-B",ROOT/"ci/openssl_probe.py","--materialize",work],env=env,timeout=180)
 src=work/"crate"/PREFIX/"openssl";_,original=inventory(guard,env,work,out,src)
 selected,env,_=repair_git_perl(guard,env,work,out,src,original);guard.env=env;perl=pathlib.Path(selected["path"])
 guard.run([sys.executable,"-B",__file__,"--runtime-prepare",work,out],env=env,timeout=180)
 plan=json.loads((out/"runtime-package-plan.json").read_text());providers=plan["providers"]
 script=work/"runtime-presence.pl";script.write_text(presence_program(sorted(providers)),encoding="ascii")
 presence=json.loads(guard.run([perl,script],cwd=src,env=env,capture=True,timeout=30).stdout)
 print("RUNTIME_EXISTING_PROVIDER_REVIEW "+json.dumps({"absent":[m for m in providers if not presence.get(m)],"different":[m for m in providers if any(h!=providers[m]["sha256"] for h in presence.get(m,[]))]}),flush=True)
 missing=select_missing(providers,presence)
 target=work/"runtime-overlay/lib";target.mkdir(parents=True)
 for module in missing:
  pin=providers[module];source=work/"runtime-packages"/pin["relative"];body=source.read_bytes();assert hashlib.sha256(body).hexdigest()==pin["sha256"],"RUNTIME_REVIEWED_BYTES_CHANGED"
  dest=target/(module.replace("::","/")+".pm");dest.parent.mkdir(parents=True,exist_ok=True)
  with dest.open("xb") as f:f.write(body)
 resolver=work/"runtime-path.pl";resolver.write_text('use Cwd qw(abs_path); print abs_path("runtime-overlay/lib"),chr(10);',encoding="ascii")
 posix=guard.run([perl,resolver],cwd=work,env=env,capture=True,timeout=15).stdout.strip()
 assert re.fullmatch(r"/[A-Za-z0-9_./+-]+/openssl-probe-work/runtime-overlay/lib",posix) and ".." not in pathlib.PurePosixPath(posix).parts,"RUNTIME_PATH_SCOPE"
 env=env.copy();env["PERL5LIB"]=posix+":"+env["PERL5LIB"];guard.env=env
 required=set(module_set(src)[0])|ACTIVE_MM
 requirements={}
 for package in plan["packages"]:
  for module,minimum in package["runtimeRequires"].items():
   if module!="perl":required.add(module);requirements.setdefault(module,[]).append(minimum)
 script=work/"runtime-closure.pl";script.write_text(program(sorted(required)),encoding="ascii")
 closure=parse(guard.run([perl,script],cwd=src,env=env,capture=True,timeout=30).stdout,sorted(required))
 print("RUNTIME_COMPLETE_MODULE_BATCH "+json.dumps(closure),flush=True)
 assert closure["complete"],"RUNTIME_COMPLETE_MODULE_BATCH_FAILED"
 # Perl VERSION checks retain dotted-version semantics rather than Python float comparisons.
 checks=work/"runtime-versions.pl"
 body=runtime_version_program(requirements)
 checks.write_text(body,encoding="ascii");assert guard.run([perl,checks],cwd=src,env=env,capture=True,timeout=30).stdout.strip()=="PASS_RUNTIME_MINIMUM_VERSIONS"
 helper=work/"runtime-helpers.pl";helper.write_text(runtime_helper_program(),encoding="ascii");results={}
 def actual(ndk,tools):
  def run_helpers():
   assert hashlib.sha256(perl.read_bytes()).hexdigest()==GIT_PERL_SHA,"RUNTIME_PERL_IDENTITY"
   results.update(json.loads(guard.run([perl,helper,perl,tools/"clang.exe",tools/"llvm-ar.exe",tools/"llvm-ranlib.exe"],cwd=work,env=env,capture=True,timeout=30).stdout))
   assert results["state"]=="PASS_ACTUAL_COMPILER_DISCOVERY_HELPERS" and results["checks"]==10 and results["makeMakerVersion"]=="7.76","RUNTIME_ACTUAL_HELPERS_FAILED"
  lease=capture_one(perl.parent,perl,callback=run_helpers)
  assert lease["qualified"] and lease.get("callbackSucceeded"),"RUNTIME_INTERPRETER_LEASE"
 with_physical_ndk_inputs(guard,env,out,actual)
 report={"state":"PASS_RUNTIME_DEPENDENCY_AND_HELPER_QUALIFICATION","packages":plan["packages"],"missingProviderCount":len(missing),"preservedInstalledProviderCount":len(providers)-len(missing),"requiredModuleCount":len(required),"moduleClosure":closure["modules"],"helperTests":results,"configureExecuted":False,"compilerExecuted":False,"globalInstallationChanged":False,"limits":"Active Cygwin compiler-discovery helpers and declared runtime prerequisites; not every MakeMaker API or future configure/make/build path","monitor":guard.report()}
 text=json.dumps(report,indent=2)+"\n";assert len(text.encode())<65536
 (out/"runtime-qualification.json").write_text(text,encoding="utf-8");source_check(ROOT);print(text,flush=True)

if __name__=="__main__":
 if len(sys.argv)==2 and sys.argv[1]=="--runtime-diagnosis":runtime_diagnosis()
 elif len(sys.argv)==4 and sys.argv[1]=="--runtime-prepare":runtime_prepare(pathlib.Path(sys.argv[2]),pathlib.Path(sys.argv[3]))
 else:
  assert len(sys.argv)==4 and sys.argv[1]=="--prepare"
  prepare(pathlib.Path(sys.argv[2]),pathlib.Path(sys.argv[3]))
