"""Pinned pure-Perl build-tool overlay in a single ephemeral job; never system install."""
import pathlib,hashlib,tarfile,io,re,json,urllib.request,os,sys,time
from perl_prerequisites import imports,module_set,program,parse
ARCHIVE_SHA="b009ff51f4fb108d19961a523e99b4373ccf958d37ca35bf1583215908dca9a9"
MODULE_SHA="bc8d1474d8c70a284b898c5bfa7ec1b0246427571d9d9404af8908c94ac67b62"
ARCHIVE_BYTES=9223
URL="https://cpan.metacpan.org/authors/id/J/JE/JESSE/Locale-Maketext-Simple-0.21.tar.gz"
PREFIX="Locale-Maketext-Simple-0.21"
GIT_PERL_SHA="c0e2fb0e8be3962cdc7aa1391f104df6502191029ec15977a37623afb32c7b36"
def owned_pair(root,work,out):
 return (work,out) in ((root/"openssl-probe-work",root/"openssl-probe-output"),(root/"ci-work",root/"dist"))

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
 assert owned_pair(root,work,out) and work.is_dir() and out.is_dir(),"OWNED_OVERLAY_SCOPE"
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
 assert value.endswith(("/openssl-probe-work/perl-overlay/lib","/ci-work/perl-overlay/lib")),"OVERLAY_PATH_SUFFIX"
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

def sanitized_lease(lease):
 if type(lease) is not dict:return {"state":"UNAVAILABLE_LEASE_REPORT"}
 result={}
 for key in ("qualified","callbackInvoked","callbackSucceeded","metadataQualifiedBeforeCallback","expectedDirectory"):
  if type(lease.get(key)) is bool:result[key]=lease[key]
 for key in ("osError","closeFailures","bytes","elapsedMilliseconds","metadataDifferenceCount"):
  if type(lease.get(key)) in (int,float) and 0<=lease[key]<=2**64:result[key]=lease[key]
 for key in ("state","reason","metadataPhase"):
  if key in lease:
   value=str(lease[key])
   if re.fullmatch(r"[A-Z][A-Z0-9_]{0,119}",value):result[key]=value
   else:result[key]="WITHHELD_NONCODE_VALUE";result[key+"SHA256"]=hashlib.sha256(value.encode()).hexdigest()
 if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,79}",str(lease.get("errorClass",""))):result["errorClass"]=lease["errorClass"]
 for key in ("fileIdentity","metadataChainLengths"):
  value=lease.get(key)
  if type(value) is list and len(value)<=3 and all(type(x) is int and 0<=x<=2**64 for x in value):result[key]=value
 changes=[]
 raw_changes=lease.get("metadataDifferences",[])
 if type(raw_changes) is not list:raw_changes=[];result["metadataDiagnosticsInvalid"]=True
 for row in raw_changes[:8]:
  if type(row) is not dict:continue
  i=row.get("componentIndex");fields=row.get("changedFields")
  if type(i) is not int or not 0<=i<24 or type(fields) is not list or not 1<=len(fields)<=4 or any(k not in ("identity","attributes","tag","bytes") for k in fields):continue
  clean={"componentIndex":i,"directory":row.get("directory") is True,"changedFields":fields,"before":{},"after":{}}
  for side in ("before","after"):
   for field in fields:
    value=row.get(side,{}).get(field)
    if type(value) is int and 0<=value<=2**64:clean[side][field]=value
    elif field=="identity" and type(value) is list and len(value)==3 and all(type(n) is int and 0<=n<=2**64 for n in value):clean[side][field]=value
  changes.append(clean)
 if changes:result["metadataDifferences"]=changes
 return result

def require_lease(lease,code,out,label,nested=None,progress=None):
 if type(lease) is dict and lease.get("qualified") and lease.get("callbackSucceeded"):return
 root=pathlib.Path(__file__).resolve().parents[1]
 assert out in (root/"dist",root/"openssl-probe-output") and re.fullmatch(r"[A-Za-z0-9_.-]{1,64}",label),"LEASE_DIAGNOSTIC_SCOPE"
 assert re.fullmatch(r"[A-Z][A-Z0-9_]{0,79}",code),"LEASE_DIAGNOSTIC_CODE"
 report={"state":"FAILED_LEASE_VALIDATION_UNCHANGED","wrapper":code,"lease":sanitized_lease(lease),"nested":{name:sanitized_lease(value) for name,value in (nested or {}).items() if re.fullmatch(r"[A-Za-z0-9_-]{1,40}",name)},"smokeProgress":{name:value for name,value in (progress or {}).items() if re.fullmatch(r"[A-Za-z0-9_-]{1,40}",name) and type(value) is bool}}
 text=json.dumps(report,indent=2)+"\n";assert len(text.encode())<=16384,"LEASE_DIAGNOSTIC_BOUND"
 print("LEASE_FAILURE_DIAGNOSTIC "+json.dumps(report),flush=True) # Keep cause in job logs even if saving the report fails.
 with (out/("lease-"+label+".json")).open("x",encoding="utf-8") as f:f.write(text)
 raise AssertionError(code)

def repair_git_perl(guard,env,work,out,src,original):
 from ndk_input_metadata import capture_one
 row=next((x for x in original["candidates"] if x["installation"]=="Git for Windows"),None)
 assert row and row["status"]=="INVENTORIED" and row["sha256"]==GIT_PERL_SHA and row["metadata"]["version"]=="5.42.3" and row["metadata"]["unixPaths"],"CHANGED_GIT_PERL_INPUT"
 missing={m for v in row["modules"].values() for m in v["missing"]}
 assert missing=={"Locale::Maketext::Simple"},"UNEXPECTED_MISSING_DEPENDENCY"
 assert all(row["modules"].get(m,{}).get("loaded") for m in ("base","Exporter","strict")),"CORE_OVERLAY_DEPENDENCY_MISSING"
 guard.run([sys.executable,"-B",__file__,"--prepare",str(work),str(out)],env=env,timeout=60)
 perl=pathlib.Path(row["path"]);resolver=work/"perl-overlay-path.pl";resolver.write_text(resolver_program(),encoding="ascii")
 modules,_=module_set(src);results={};next_env=env.copy();progress={}
 def callback():
  assert hashlib.sha256(perl.read_bytes()).hexdigest()==GIT_PERL_SHA,"PERL_BINARY_CHANGED"
  progress["interpreterHashVerified"]=True
  posix=parse_overlay_path(guard.run([perl,resolver],cwd=work,env=env,capture=True,timeout=15).stdout)
  next_env["PERL5LIB"]=posix;progress["resolverPassed"]=True
  script=work/"perl-overlay-required.pl";script.write_text(program(modules),encoding="ascii")
  loaded=parse(guard.run([perl,script],cwd=src,env=next_env,capture=True,timeout=25).stdout,modules)
  assert loaded["complete"] and loaded["modules"]["Locale::Maketext::Simple"]["version"]=="0.21","OVERLAY_MODULE_SMOKE_FAILED"
  progress["moduleBatchPassed"]=True
  smoke=work/"perl-overlay-focused.pl";smoke.write_text(focused_program(),encoding="ascii")
  focused=json.loads(guard.run([perl,smoke],cwd=src,env=next_env,capture=True,timeout=25).stdout)
  assert focused=={"state":"PASS_FOCUSED_PERL_TOOL_CHECKS","checks":5,"externalCommandsExecuted":False},"OVERLAY_FOCUSED_TESTS_FAILED"
  progress["focusedOutputMatched"]=True
  results.update(loaded);results["focused"]=focused
 module=work/"perl-overlay/lib/Locale/Maketext/Simple.pm"
 def module_callback():
  assert hashlib.sha256(module.read_bytes()).hexdigest()==MODULE_SHA,"OVERLAY_MODULE_CHANGED"
  callback()
 def interpreter_callback():
  results["moduleInputLease"]=capture_one(work/"perl-overlay",module,callback=module_callback,mutable_ci_work=work==pathlib.Path(__file__).resolve().parents[1]/"ci-work")
  require_lease(results["moduleInputLease"],"OVERLAY_MODULE_INPUT_FAILED",out,"overlay-module",progress=progress)
 lease=capture_one(perl.parent,perl,callback=interpreter_callback)
 require_lease(lease,"OVERLAY_INTERPRETER_OR_SMOKE_FAILED",out,"overlay-interpreter",nested={"moduleInput":results.get("moduleInputLease",{})},progress=progress)
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
 ("N/NE/NEILB","Pod-Escapes-1.07","dbf7c827984951fb248907f940fd8f19f2696bc5545c0a15287e0fbe56a52308","Pod-Escapes","1.07"),
 ("M/MA/MAREKR","Pod-Usage-2.05","100c27908757c56ebfeca8b7bf15a9867e449df663ff013de3855d183dfbea30","Pod-Usage","2.05"),
 ("M/MA/MALLEN","Pod-Perldoc-3.28","cc41e605b8e13c40a8ee6504ff46347b5ba7fbd92203b3bb055422051befc64d","Pod-Perldoc","3.28"),
 ("E/EX/EXODIST","Test-Simple-1.302210","acb9ca8d582b8c0bbe53c6d9b3264f1cf66eaa7135f41f979747104183aea509","Test-Simple","1.302210"),
 ("E/EX/EXODIST","Term-Table-0.024","52288538c3b0514bcd2b61f645686c256619e56a421ae992e2b76d31927c4ece","Term-Table","0.024"))
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
 assert owned_pair(root,work,out) and work.is_dir() and out.is_dir(),"RUNTIME_OWNED_SCOPE"
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
 assert modules and len(modules)<=512 and all(re.fullmatch(r"[A-Za-z_]\w*(?:::\w+)*",m) for m in modules)
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



CONFIGURATION_ROOTS=("Configure","configdata.pm.in","Configurations/common0.tmpl","Configurations/unix-Makefile.tmpl","Configurations/gentemplate.pm","Configurations/platform.pm","Configurations/platform/Unix.pm","Configurations/platform/BASE.pm","include/openssl/configuration.h.in")

def configuration_source_closure(src):
 # The target is exactly linux-aarch64: platform.pm's dynamic selection is Unix.
 # Catalogue source, but do not pretend this substitutes for generated-script execution.
 pending=[src/p for p in CONFIGURATION_ROOTS];seen=set();external=set();local={}
 while pending:
  p=pending.pop()
  if p in seen:continue
  assert p.is_relative_to(src) and len(seen)<128 and p.stat().st_size<1024**2,"CONFIGURATION_SOURCE_BOUND"
  text=p.read_text(encoding="utf-8");seen.add(p)
  for module in imports(text):
   assert re.fullmatch(r"[A-Za-z_]\w*(?:::\w+)*",module),"CONFIGURATION_MODULE_NAME"
   if module=="configdata":continue # generated by the single real Configure below
   relative=module.replace("::","/")+".pm"
   candidates=[base/relative for base in (src/"util/perl",src/"Configurations")]
   matches=[q for q in candidates if q.is_file()]
   assert len(matches)<=1,"AMBIGUOUS_LOCAL_PERL_MODULE"
   if matches:
    local[module]=matches[0].relative_to(src).as_posix();pending.extend(matches)
   else:external.add(module)
 modules,base_files=module_set(src);external.update(m for m in modules if m not in local and m!="configdata")
 seen.update(src/name for name in base_files);assert len(seen)<=128,"CONFIGURATION_CATALOG_SOURCE_BOUND"
 # Perldoc contains a lazy HTTP::Tiny import; qualify its installed module but never
 # exercise URL retrieval, external pagers/renderers or any network in this probe.
 external.add("HTTP::Tiny")
 assert len(external)<=128,"CONFIGURATION_EXTERNAL_MODULE_BOUND"
 return {"state":"STATIC_CONFIGURATION_CATALOG_REQUIRES_DYNAMIC_EXECUTION","externalModules":sorted(external),"localModules":local,"sourceFiles":[{"path":q.relative_to(src).as_posix(),"sha256":hashlib.sha256(q.read_bytes()).hexdigest()} for q in sorted(seen)],"dynamicPlatform":"platform::Unix","generatedModule":"configdata.pm","limits":"Selected configuration/generation/help paths only, not make targets or every optional Perl API"}

def pod_runtime_program():
 return r'''use strict;
use warnings;
use Pod::Usage ();
use Pod::Perldoc ();
use JSON::PP;
my $input=Cygwin::win_to_posix_path($ARGV[0],1);
my $output="";open my $fh,">",\$output or die "synthetic output handle";
Pod::Usage::pod2usage(-input=>$input,-output=>$fh,-verbose=>1,-exitval=>"NOEXIT",-noperldoc=>1);
close($fh) or die "synthetic output close";
die "POD rendering failed" unless index($output,"OFFLINE_POD_USAGE_FIXTURE")>=0;
print JSON::PP::encode_json({state=>"PASS_ACTUAL_LOCAL_POD_RENDERING",checks=>1,networkRequested=>JSON::PP::false,externalPerldocRequested=>JSON::PP::false}),chr(10);
'''

def generated_helper_program():
 return r'''use strict;
use warnings;
use lib '.', 'Configurations', 'util/perl', 'external/perl/Text-Template-1.56/lib';
use JSON::PP;
require configdata;
require platform;
require gentemplate;
require OpenSSL::Template;
die "unexpected platform" unless @platform::ISA==1 && $platform::ISA[0] eq "platform::Unix";
die "bin helper" unless platform->bin("offline_fixture") eq "offline_fixture";
die "object helper" unless platform->objext() eq ".o";
die "library helper" unless platform->libext() eq ".a";
my $t=OpenSSL::Template->new(TYPE=>"STRING",SOURCE=>"before {- 2+3 -} after");
my $rendered=$t->fill_in(HASH=>{});die "actual template helper" unless defined($rendered) && $rendered eq "before 5 after";
my @templates=@{$configdata::config{build_file_templates}};
for (@templates) {s{\\}{/}g;}
die "unexpected selected templates" unless @templates==2 && $templates[0] eq "Configurations/common0.tmpl" && $templates[1] eq "Configurations/unix-Makefile.tmpl";
print JSON::PP::encode_json({state=>"PASS_ACTUAL_GENERATED_CONFIGURATION_HELPERS",checks=>5,target=>$configdata::config{target},buildFile=>$configdata::config{build_file},templates=>\@templates,platform=>$platform::ISA[0]}),chr(10);
'''


def openssl_shell_tool(role,value):
 """Encode only selected canonical tools for Configure's shell-command fields.
 Canonical Cargo target variables and executable identity pins stay unquoted.
 This encoding grants no execution allowance; normal fresh image guards apply.
 """
 from ndk_compilers import PATHS
 from ndk_linker import NDK
 roles={"CC":PATHS["clang.exe"],"CXX":PATHS["clang++.exe"],"AR":NDK/"toolchains/llvm/prebuilt/windows-x86_64/bin/llvm-ar.exe","RANLIB":NDK/"toolchains/llvm/prebuilt/windows-x86_64/bin/llvm-ranlib.exe"}
 assert role in roles and type(value) is str,"OPENSSL_COMMAND_ROLE_OR_TYPE"
 path=roles[role]
 if value==path.name:return value
 assert value==str(path),"OPENSSL_COMMAND_EXACT_CANONICAL_PATH"
 return "'"+path.as_posix()+"'"

def openssl_shell_tools_program():
 from ndk_compilers import PATHS
 from ndk_linker import NDK
 roles={"CC":PATHS["clang.exe"],"CXX":PATHS["clang++.exe"],"AR":NDK/"toolchains/llvm/prebuilt/windows-x86_64/bin/llvm-ar.exe","RANLIB":NDK/"toolchains/llvm/prebuilt/windows-x86_64/bin/llvm-ranlib.exe"}
 def literal(s):return "'"+s.replace("\\","\\\\").replace("'","\\'")+"'"
 entries=[]
 for role,path in roles.items():
  target={"CC":"CC_aarch64_linux_android","CXX":"CXX_aarch64_linux_android","AR":"AR_aarch64_linux_android","RANLIB":"RANLIB_aarch64_linux_android"}[role]
  entries.append(literal(role)+"=>["+ ",".join(literal(v) for v in (str(path),path.name,openssl_shell_tool(role,str(path)),target))+"]")
 return (" my %shell_tools=("+",".join(entries)+");\n"+r''' die "unqualified Configure command scope" unless ($ENV{VIBETRAM_OPENSSL_CARGO_BRIDGE}//"") eq "1";
 for my $role (sort keys %shell_tools) {
  next unless defined $ENV{$role};
  my ($canonical,$basename,$encoded,$target)=@{$shell_tools{$role}};
  my $value=$ENV{$role};
  die "unexpected Configure tool command" unless $value eq $canonical || $value eq $basename;
  if ($value eq $canonical) {
   my $selected=$ENV{$target};
   die "Configure target tool mismatch" unless defined($selected) && ($selected eq $canonical || ($role ne "CC" && $role ne "CXX" && $selected eq $basename));
   $ENV{$role}=$encoded;
  }
 }
''')

def cargo_prefix_bridge_program():
 return r'''package Vibetram::ConfigurePaths;
use strict;
use warnings;
use Cwd ();
use Digest::SHA ();
sub import {
 return unless $0 =~ m{(?:^|[/\\])Configure$};
 my $root=$ENV{VIBETRAM_OPENSSL_WORK};my $pin=$ENV{VIBETRAM_OPENSSL_CONFIGURE_SHA};
 die "missing qualified build root" unless defined($root) && defined($pin) && $pin =~ /^[a-f0-9]{64}$/;
 $root=Cygwin::win_to_posix_path($root,1);$root=~s{/$}{};
 my $cwd=Cwd::getcwd();die "Configure outside owned work" unless index(lc($cwd),lc($root)."/")==0;
 open my $f,"<","./Configure" or die "pinned Configure unavailable";binmode($f);
 my $hash=Digest::SHA->new(256)->addfile($f)->hexdigest;close($f) or die "Configure close";
 die "Configure identity changed" unless $hash eq $pin;
 return unless grep {$_ eq "linux-aarch64"} @ARGV;
 my @prefix=grep {$ARGV[$_] =~ /^--prefix=/} 0..$#ARGV;die "Configure prefix count" unless @prefix==1;
 my $value=substr($ARGV[$prefix[0]],9);die "unsafe prefix characters" unless $value =~ m{^(?:[A-Za-z]:)?/[A-Za-z0-9_./+-]+$};
 die "prefix traversal" if grep {$_ eq "." || $_ eq ".."} split m{/},$value;
 my $posix=Cygwin::win_to_posix_path($value,1);
 die "prefix outside owned work" unless index(lc($posix),lc($root)."/")==0;
 my $relative=substr($posix,length($root)+1);
 die "unexpected OpenSSL install scope" unless $relative eq "install" || $relative =~ m{^target/aarch64-linux-android/ci-test/build/openssl-sys-[a-f0-9]{1,64}/out/openssl-build/install$};
 if (defined $ENV{VIBETRAM_OPENSSL_ARFLAGS}) {
  die "unqualified OpenSSL archive operation" unless $ENV{VIBETRAM_OPENSSL_ARFLAGS} eq "crs";
  die "unexpected OpenSSL inherited operation" if defined($ENV{ARFLAGS}) && $ENV{ARFLAGS} ne "crs";
  $ENV{ARFLAGS}="crs"; # pinned Configure writes its own Makefile operation
 }
__VIBETRAM_OPENSSL_COMMANDS__
 $ARGV[$prefix[0]]="--prefix=".$posix;
 print STDERR "VIBETRAM_PINNED_OPENSSL_PREFIX_QUALIFIED\n";
}
1;
'''.replace('__VIBETRAM_OPENSSL_COMMANDS__',openssl_shell_tools_program())

def preserve_cargo_perl_paths(env):
 assert env.get("VIBETRAM_OPENSSL_CARGO_BRIDGE")=="1","PERL_PATH_BRIDGE_SCOPE"
 value=env.get("PERL5LIB");assert isinstance(value,str) and len(value)<=4096,"PERL_INCLUDE_LIST_BOUND"
 entries=value.split(":");assert len(entries)==2,"PERL_INCLUDE_ENTRY_COUNT"
 suffixes=("/runtime-overlay/lib","/perl-overlay/lib");roots=[]
 for entry,suffix in zip(entries,suffixes):
  assert re.fullmatch(r"/[A-Za-z0-9_ ./+-]+",entry) and entry.endswith(suffix),"PERL_INCLUDE_POSIX_SCOPE"
  assert all(part not in ("",".","..") for part in entry.split("/")[1:]),"PERL_INCLUDE_TRAVERSAL"
  roots.append(entry[:-len(suffix)])
 assert roots[0] and roots[0]==roots[1],"PERL_INCLUDE_ROOT_MISMATCH"
 assert env.get("MSYS2_ENV_CONV_EXCL","") in ("","PERL5LIB="),"UNREVIEWED_ENV_CONVERSION_EXCLUSION"
 result=env.copy();result["MSYS2_ENV_CONV_EXCL"]="PERL5LIB="
 return result

def install_cargo_prefix_bridge(env,work,src):
 assert env.get("VIBETRAM_OPENSSL_CARGO_BRIDGE")=="1","BUILD_BRIDGE_MODE"
 env=preserve_cargo_perl_paths(env)
 target=work/"runtime-overlay/lib/Vibetram/ConfigurePaths.pm";target.parent.mkdir()
 with target.open("x",encoding="ascii") as f:f.write(cargo_prefix_bridge_program())
 result=env.copy();result.update(PERL5OPT="-MVibetram::ConfigurePaths",VIBETRAM_OPENSSL_WORK=str(work),VIBETRAM_OPENSSL_CONFIGURE_SHA=hashlib.sha256((src/"Configure").read_bytes()).hexdigest())
 return result

def build_android_environment(env,ndk,tools,perl):
 cross=configure_environment(env,ndk,tools,perl)
 make_dir=ndk/"prebuilt/windows-x86_64/bin"
 cross["PATH"]=str(make_dir)+os.pathsep+cross["PATH"]
 cross.update(CC_aarch64_linux_android=str(tools/"clang.exe"),CXX_aarch64_linux_android=str(tools/"clang++.exe"),AR_aarch64_linux_android="llvm-ar.exe",RANLIB_aarch64_linux_android="llvm-ranlib.exe",SHELL=(perl.parent/"sh.exe").as_posix(),MAKEFLAGS="-j1")
 return cross

def tiny_makefile(native):
 # Windows-native consumers receive mixed D:/ paths, never Cygwin /d paths.
 # See https://cygwin.com/cygwin-ug-net/cygpath.html (-m for shell-safe slashes).
 assert re.fullmatch(r"[A-Za-z]:/[A-Za-z0-9_./+ -]+/ci-work/tool-smoke space",native) and not any(x in (".","..") for x in native.split("/")),"SMOKE_OUTPUT_SCOPE"
 return "VIBETRAM_SMOKE_DIR="+native+r'''
.PHONY: VIBETRAM_TOOLCHAIN_SMOKE
VIBETRAM_TOOLCHAIN_SMOKE:
	@$(PERL) -e 'print "PASS_GENERATED_MAKE_PERL\n"'
	$(CC) --target=aarch64-linux-android29 -fPIC -c "$(VIBETRAM_SMOKE_DIR)/probe source.c" -o "$(VIBETRAM_SMOKE_DIR)/probe object.o"
	$(AR) crs "$(VIBETRAM_SMOKE_DIR)/probe archive.a" "$(VIBETRAM_SMOKE_DIR)/probe object.o"
	$(RANLIB) "$(VIBETRAM_SMOKE_DIR)/probe archive.a"
	$(CC) --target=aarch64-linux-android29 -shared -fPIC -Wl,-z,max-page-size=16384 "$(VIBETRAM_SMOKE_DIR)/probe object.o" -o "$(VIBETRAM_SMOKE_DIR)/probe native.so"
'''

def native_path_conversion_program():
 return r'''use strict;use warnings;use JSON::PP;
die "one path required" unless @ARGV==1;
my $posix=Cygwin::win_to_posix_path($ARGV[0],1);
my $native=Cygwin::posix_to_win_path($posix,1);$native=~s{\\}{/}g;
my @a=stat($ARGV[0]);my @b=stat($posix);my @c=stat($native);
die "conversion identity changed" unless @a && @b && @c && $a[0]==$b[0] && $a[1]==$b[1] && $a[0]==$c[0] && $a[1]==$c[1];
print JSON::PP::encode_json({posix=>$posix,native=>$native,identityChecks=>2}),chr(10);
'''

def validate_native_conversion(row,smoke):
 assert type(row) is dict and set(row)=={"posix","native","identityChecks"} and row["identityChecks"]==2,"SMOKE_CONVERSION_SCHEMA"
 native=smoke.as_posix();tiny_makefile(native)
 assert row["native"]==native and isinstance(row["posix"],str) and re.fullmatch(r"/[A-Za-z0-9_./+ -]+/ci-work/tool-smoke space",row["posix"]) and not any(x in (".","..") for x in row["posix"].split("/")),"SMOKE_CONVERSION_SCOPE"
 return native

def validate_openssl_recipe(output):
 import shlex
 # Review the actual generated recipe before executing only this object target.
 lines=[line.strip() for line in output.splitlines() if re.match(r"^clang\.exe\s",line.strip())]
 assert len(lines)==1,"REPRESENTATIVE_COMPILER_COUNT"
 args=shlex.split(lines[0],posix=True)
 assert args[0]=="clang.exe" and args.count("-c")==1 and args.count("-o")==1 and args[args.index("-o")+1]=="crypto/libcrypto-lib-ctype.o" and args[-1]=="crypto/ctype.c","REPRESENTATIVE_RECIPE_IDENTITY"
 assert "--target=aarch64-linux-android29" in args and not any(x.startswith("/") or x.startswith("-I/") for x in args),"REPRESENTATIVE_NATIVE_PATH_OR_TARGET"
 # These three -D values are embedded Android installation-directory strings,
 # not native compiler file operands; preserve their upstream POSIX spelling.
 assert all(re.fullmatch(r"[A-Za-z0-9_./=,+:-]+",x) or re.fullmatch(r'-D(?:OPENSSLDIR|ENGINESDIR|MODULESDIR)="/[A-Za-z0-9_./+-]+"',x) for x in args),"REPRESENTATIVE_UNEXPECTED_SHELL_SYNTAX"
 return args

def smoke_artifact_identity(path):
 import stat
 before=path.lstat()
 assert stat.S_ISREG(before.st_mode) and not getattr(before,"st_file_attributes",0)&0x400,"SMOKE_ARTIFACT_NOT_REGULAR"
 data=path.read_bytes();after=path.lstat()
 fields=("st_dev","st_ino","st_mode","st_size","st_mtime_ns","st_ctime_ns","st_file_attributes")
 assert all(getattr(before,k,None)==getattr(after,k,None) for k in fields) and len(data)==before.st_size,"SMOKE_ARTIFACT_CHANGED"
 return {"identity":[before.st_dev,before.st_ino],"bytes":len(data),"sha256":hashlib.sha256(data).hexdigest(),"regularNoFollowMetadata":True}

def representative_openssl_recipe(guard,cross,src,make):
 target="crypto/libcrypto-lib-ctype.o";source=src/"crypto/ctype.c";native=src/target
 assert source.is_file() and not native.exists(),"REPRESENTATIVE_SOURCE_OR_EXISTING_OUTPUT"
 source_hash=hashlib.sha256(source.read_bytes()).hexdigest();make_hash=hashlib.sha256((src/"Makefile").read_bytes()).hexdigest()
 # Header generation is a real generated Perl recipe, not a replacement header.
 guard.run([make,"-f","Makefile","-j1","include/openssl/opensslv.h"],cwd=src,env=cross,capture=True,timeout=60)
 dry=guard.run([make,"-f","Makefile","--dry-run","-j1",target],cwd=src,env=cross,capture=True,timeout=30)
 args=validate_openssl_recipe(dry.stdout)
 completed=guard.run([make,"-f","Makefile","-j1",target],cwd=src,env=cross,capture=True,timeout=90)
 assert args==validate_openssl_recipe(completed.stdout),"REPRESENTATIVE_RECIPE_CHANGED"
 data=native.read_bytes();assert len(data)>=64 and data[:6]==b"\x7fELF\x02\x01" and int.from_bytes(data[16:18],"little")==1 and int.from_bytes(data[18:20],"little")==183,"REPRESENTATIVE_EXPECTED_ARM64_OBJECT"
 assert hashlib.sha256(source.read_bytes()).hexdigest()==source_hash and hashlib.sha256((src/"Makefile").read_bytes()).hexdigest()==make_hash,"REPRESENTATIVE_INPUT_CHANGED"
 return {"state":"PASS_ACTUAL_GENERATED_OPENSSL_OBJECT_RECIPE","target":target,"sourceSHA256":source_hash,"generatedMakefileSHA256":make_hash,"compilerArgv":args,"objectBytes":len(data),"objectSHA256":hashlib.sha256(data).hexdigest(),"ELF64":True,"machine":"AArch64","type":"REL","sourceAndRecipeUnchanged":True,"fixtureExecuted":False,"otherOpenSSLObjectsRequested":False,"sourceIdentity":smoke_artifact_identity(source),"objectIdentity":smoke_artifact_identity(native)}

def qualify_make_link(guard,env,work,out,src,perl,elf_validator):
 from openssl_probe import PHYSICAL_SDK
 from ndk_input_metadata import capture_one
 import shutil
 ndk=PHYSICAL_SDK/"ndk/30.0.16248370";tools=ndk/"toolchains/llvm/prebuilt/windows-x86_64/bin"
 make=ndk/"prebuilt/windows-x86_64/bin/make.exe";shell=perl.parent/"sh.exe";lld=tools/"ld.lld.exe";readelf=tools/"llvm-readelf.exe"
 cross=build_android_environment(env,ndk,tools,perl);results={};leases={}
 def execute():
  assert pathlib.Path(shutil.which("make.exe",path=cross["PATH"]) or "")==make,"WRONG_SELECTED_MAKE"
  from host_linker import direct_msvc_linker
  linker=direct_msvc_linker(env);assert linker and pathlib.Path(shutil.which("link.exe",path=cross["PATH"]) or "")==pathlib.Path(linker),"HOST_LINKER_PATH_COLLISION"
  from ndk_linker import qualify as qualify_ndk,version as check_ndk_version
  cross.update(qualify_ndk(cross,guard._resource_sample))
  from ndk_compilers import qualify as qualify_compilers
  cross.update(qualify_compilers(cross,guard._resource_sample))
  from perl_path_probe import qualify as qualify_paths
  results["nestedPerlPaths"]=qualify_paths(guard,env,work,out,perl,ndk)
  versions={name:guard.run([tool,"--version"],env=cross,capture=True,timeout=30).stdout.strip()[:2048] for name,tool in (("make",make),("shell",shell),("lld",lld))}
  check_ndk_version(versions["lld"])
  assert versions["make"].startswith("GNU Make ") and "GNU bash" in versions["shell"] and "LLD" in versions["lld"],"UNEXPECTED_BUILD_TOOL_VERSION"
  smoke=work/"tool-smoke space";smoke.mkdir();(smoke/"probe source.c").write_text("int vibetram_offline_link_probe(void) { return 7; }\n",encoding="ascii")
  source_hash=hashlib.sha256((smoke/"probe source.c").read_bytes()).hexdigest()
  converter=work/"smoke-paths.pl";converter.write_text(native_path_conversion_program(),encoding="ascii")
  conversion=json.loads(guard.run([perl,converter,smoke],env=cross,capture=True,timeout=15).stdout)
  native_dir=validate_native_conversion(conversion,smoke);recipe=smoke/"smoke.mk";recipe.write_text(tiny_makefile(native_dir),encoding="ascii")
  result=guard.run([make,"-f","Makefile","-f",recipe,"-j1","VIBETRAM_TOOLCHAIN_SMOKE"],cwd=src,env=cross,capture=True,timeout=90)
  assert "PASS_GENERATED_MAKE_PERL" in result.stdout,"GENERATED_MAKE_PERL_PATH_FAILED"
  native=smoke/"probe native.so";assert native.is_file(),"TINY_ANDROID_LINK_MISSING";elf_validator(native.read_bytes())
  dynamic=guard.run([readelf,"-d",native],env=cross,capture=True,timeout=20).stdout
  needed=re.findall(r"\(NEEDED\).*\[([^\]]+)\]",dynamic);assert all(x in ("libc.so","libdl.so","libm.so","liblog.so","libandroid.so") for x in needed),"SMOKE_RUNTIME_DEPENDENCY"
  assert hashlib.sha256((smoke/"probe source.c").read_bytes()).hexdigest()==source_hash,"SMOKE_SOURCE_CHANGED"
  obj=(smoke/"probe object.o").read_bytes();assert obj[:6]==b"\x7fELF\x02\x01" and int.from_bytes(obj[16:18],"little")==1 and int.from_bytes(obj[18:20],"little")==183,"SMOKE_OBJECT_TARGET"
  archive=smoke/"probe archive.a";assert archive.read_bytes().startswith(b"!<arch>\n"),"SMOKE_ARCHIVE_FORMAT"
  members=guard.run([tools/"llvm-ar.exe","t",archive],env=cross,capture=True,timeout=20).stdout.splitlines();assert members==["probe object.o"],"SMOKE_ARCHIVE_MEMBER"
  from archive_policy import qualify as qualify_cc_archive
  results["cargoArchiver"]=qualify_cc_archive(guard,cross,tools,smoke)
  representative=representative_openssl_recipe(guard,cross,src,make)
  results.update(state="PASS_INSTALLED_MAKE_SHELL_ANDROID_ARCHIVE_LINK",tools={name:{"path":str(tool),"sha256":hashlib.sha256(tool.read_bytes()).hexdigest()} for name,tool in (("make",make),("shell",shell),("lld",lld))},versions=versions,nativeSHA256=hashlib.sha256(native.read_bytes()).hexdigest(),needed=needed,elf16KiBAligned=True,fixtureExecuted=False,makeWorkers=1,hostLinkerPreserved=True,sourceSHA256=source_hash,pathConversion=conversion,quotedNativePathsWithSpaces=True,objectSHA256=hashlib.sha256(obj).hexdigest(),archiveSHA256=hashlib.sha256(archive.read_bytes()).hexdigest(),representativeOpenSSL=representative,artifacts={name:smoke_artifact_identity(smoke/name) for name in ("probe source.c","probe object.o","probe archive.a","probe native.so")})
 def step(i):
  paths=((ndk,make),(shell.parent,shell),(ndk,lld),(ndk,readelf))
  if i==len(paths):execute();return
  root,tool=paths[i];lease=capture_one(root,tool,callback=lambda:step(i+1));leases[tool.name]=lease
  require_lease(lease,"INSTALLED_MAKE_LINK_INPUT_OR_PROBE_FAILED",out,"make-link-"+tool.name)
 try:step(0)
 finally:
  text=json.dumps({"result":results,"inputLeases":leases},indent=2)+"\n";(out/"make-link-qualification.json").write_text(text,encoding="utf-8");print(text,flush=True)
 return cross,results

def configure_environment(env,ndk,tools,perl):
 from build_guard import android_env
 from openssl_probe import PHYSICAL_SDK
 cross=android_env(env,ndk)
 cross.update(ANDROID_HOME=str(PHYSICAL_SDK),ANDROID_SDK_ROOT=str(PHYSICAL_SDK),OPENSSL_SRC_PERL=str(perl),PERL=str(perl),CC="clang.exe",CFLAGS="--target=aarch64-linux-android29",AR="llvm-ar.exe",ARFLAGS="crs",RANLIB="llvm-ranlib.exe",VIBETRAM_OPENSSL_ARFLAGS="crs")
 # Basenames avoid shell parsing of spaces; actual PATH lookup is identity-checked
 # against the leased physical NDK files immediately before Configure.
 from host_linker import direct_msvc_linker
 host=direct_msvc_linker(env)
 prefixes=[str(tools)]+([str(pathlib.Path(host).parent)] if host else [])+[str(perl.parent)]
 cross["PATH"]=os.pathsep.join(prefixes+[env["PATH"]])
 if env.get("VIBETRAM_OPENSSL_CARGO_BRIDGE")=="1":cross["PERL"]="perl.exe"
 return cross

def configure_lookup_program():
 return r'''use strict;
use warnings;
use IPC::Cmd ();
use JSON::PP;
my @tools=qw(clang.exe llvm-ar.exe llvm-ranlib.exe);die "tool count" unless @ARGV==@tools+1;
for my $i (0..$#tools) {
 my $expected=Cygwin::win_to_posix_path($ARGV[$i],1);
 my $found=IPC::Cmd::can_run($tools[$i]);die "PATH tool unavailable" unless defined($found);
 my @a=stat($found);my @b=stat($expected);
 die "PATH tool identity mismatch" unless @a && @b && $a[0]==$b[0] && $a[1]==$b[1] && $a[7]==$b[7];
}
print JSON::PP::encode_json({state=>"PASS_EXACT_PHYSICAL_NDK_PATH_LOOKUP",checks=>3,compilerExecuted=>JSON::PP::false,prefix=>Cygwin::win_to_posix_path($ARGV[3],1)}),chr(10);
'''

def configure_with_runtime(guard,env,work,out,src,perl,ndk,tools,cargo_commands=False):
 from openssl_probe import configure_args,PHYSICAL_SDK
 cross=cargo_command_environment(guard,env,ndk,tools,perl) if cargo_commands else configure_environment(env,ndk,tools,perl)
 lookup=work/"configure-tool-lookup.pl";lookup.write_text(configure_lookup_program(),encoding="ascii")
 found=json.loads(guard.run([perl,lookup,tools/"clang.exe",tools/"llvm-ar.exe",tools/"llvm-ranlib.exe",work/"install"],cwd=src,env=cross,capture=True,timeout=20).stdout)
 assert set(found)=={"state","checks","compilerExecuted","prefix"} and found["state"]=="PASS_EXACT_PHYSICAL_NDK_PATH_LOOKUP" and found["checks"]==3 and found["compilerExecuted"] is False,"CONFIGURE_LOOKUP_CHECKS"
 prefix=found["prefix"]
 assert type(prefix) is str and re.fullmatch(r"/[A-Za-z0-9_./+-]+/(?:openssl-probe-work|ci-work)/install",prefix) and ".." not in pathlib.PurePosixPath(prefix).parts,"CONFIGURE_PREFIX_SCOPE"
 guard.run([perl,"-c","./Configure"],cwd=src,env=cross,capture=True,timeout=25)
 guard.run([perl,"-e","require q(./Configurations/unix-checker.pm);"],cwd=src,env=cross,capture=True,timeout=15)
 command=[str(perl),*configure_args((work/"install").as_posix() if cross.get("VIBETRAM_OPENSSL_CARGO_BRIDGE")=="1" else prefix)]
 evidence={"argv":command,"environment":{"ANDROID_HOME":cross["ANDROID_HOME"],"ANDROID_SDK_ROOT":cross["ANDROID_SDK_ROOT"],"ANDROID_NDK_HOME":cross["ANDROID_NDK_HOME"],"CC":cross["CC"],"CFLAGS":cross["CFLAGS"],"AR":cross["AR"],"RANLIB":cross["RANLIB"],"PATHPrefix":[str(tools),str(perl.parent)]},"lookup":found,"configureAttempts":1,"makeRequested":False}
 print("ACTUAL_CONFIGURE_COMMAND "+json.dumps(evidence),flush=True)
 completed=guard.run(command,cwd=src,env=cross,capture=True,timeout=120)
 assert completed.returncode==0,"CONFIGURE_EXIT"
 if cross.get("VIBETRAM_OPENSSL_CARGO_BRIDGE")=="1":assert "VIBETRAM_PINNED_OPENSSL_PREFIX_QUALIFIED" in completed.stderr,"CARGO_PREFIX_BRIDGE_NOT_EXECUTED"
 files={}
 for name in ("Makefile","configdata.pm"):
  p=src/name;assert p.is_file() and p.stat().st_size<16*1024**2,"CONFIGURE_OUTPUT_MISSING"
  files[name]={"bytes":p.stat().st_size,"sha256":hashlib.sha256(p.read_bytes()).hexdigest()}
 text=(src/"Makefile").read_text(encoding="utf-8")
 assert "PLATFORM=linux-aarch64" in text and "--target=aarch64-linux-android29" in text,"CONFIGURE_TARGET_CHANGED"
 fields={}
 for line in text.splitlines():
  if re.match(r"^(?:PLATFORM|CROSS_COMPILE|CC|CXX|AR|ARFLAGS|RANLIB|PERL|CFLAGS|CPPFLAGS|CNF_CFLAGS|CNF_CPPFLAGS|OPTIONS)=",line):
   key,value=line.split("=",1);assert key not in fields and len(value)<=8192,"CONFIGURE_FIELD_BOUND";fields[key]=value
 configured_tool_fields(fields,cargo_commands)
 # Configure's real no-argument configdata.pm invocation generated these files.
 # Exercise that generated program's parse/help/report paths as well, without
 # reconfigure, make, external perldoc, URL retrieval or environment dumping.
 script=work/"generated-helper-checks.pl";script.write_text(generated_helper_program(),encoding="ascii")
 generated=json.loads(guard.run([perl,script],cwd=src,env=cross,capture=True,timeout=30).stdout)
 assert generated.get("state")=="PASS_ACTUAL_GENERATED_CONFIGURATION_HELPERS" and generated.get("checks")==5 and generated.get("target")=="linux-aarch64","GENERATED_HELPERS_FAILED"
 guard.run([perl,"-c","./configdata.pm"],cwd=src,env=cross,capture=True,timeout=30)
 help_result=guard.run([perl,"./configdata.pm","--help"],cwd=src,env=cross,capture=True,timeout=30)
 assert "configdata" in help_result.stdout and len(help_result.stdout)>50,"GENERATED_HELP_OUTPUT"
 build_result=guard.run([perl,"./configdata.pm","--build-parameters"],cwd=src,env=cross,capture=True,timeout=30)
 assert "common0.tmpl" in build_result.stdout and "unix-Makefile.tmpl" in build_result.stdout,"GENERATED_TEMPLATE_REPORT"
 options_result=guard.run([perl,"./configdata.pm","--options"],cwd=src,env=cross,capture=True,timeout=30)
 assert "Disabled features:" in options_result.stdout,"GENERATED_OPTIONS_REPORT"
 header=src/"include/openssl/configuration.h";assert header.is_file(),"GENERATED_CONFIGURATION_HEADER_MISSING"
 files["include/openssl/configuration.h"]={"bytes":header.stat().st_size,"sha256":hashlib.sha256(header.read_bytes()).hexdigest()}
 if cross.get("VIBETRAM_OPENSSL_CARGO_BRIDGE")=="1":assert fields.get("PERL")=="perl.exe","GENERATED_MAKE_PERL_NOT_BASENAME"
 evidence["generatedExecution"]={"helpers":generated,"syntaxChecked":True,"helpBytes":len(help_result.stdout.encode()),"buildParametersBytes":len(build_result.stdout.encode()),"optionsBytes":len(options_result.stdout.encode()),"regenerationDuringConfigure":True,"networkRequested":False,"externalPerldocRequested":False}
 evidence.update(state="PASS_ACTUAL_CONFIGURE_ONLY_NOT_COMPILED",exitCode=completed.returncode,files=files,makefileFields=fields,stdout=completed.stdout[-8192:],stderr=completed.stderr[-4096:],compilationRequested=False,compilerVersionQueriesAllowed=True)
 (out/"actual-configure.json").write_text(json.dumps(evidence,indent=2)+"\n",encoding="utf-8");print("ACTUAL_CONFIGURE_RESULT "+json.dumps(evidence),flush=True)
 return evidence

def qualify_prepared_runtime(guard,env,work,out,src,configure=True,cargo_commands=False):
 from openssl_probe import ROOT,with_physical_ndk_inputs
 from perl_prerequisites import inventory
 from ndk_input_metadata import capture_one
 from check_source import source_check
 assert owned_pair(ROOT,work,out),"SHARED_RUNTIME_OWNED_SCOPE"
 _,original=inventory(guard,env,work,out,src)
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
 assert re.fullmatch(r"/[A-Za-z0-9_./+-]+/(?:openssl-probe-work|ci-work)/runtime-overlay/lib",posix) and ".." not in pathlib.PurePosixPath(posix).parts,"RUNTIME_PATH_SCOPE"
 env=env.copy();env["PERL5LIB"]=posix+":"+env["PERL5LIB"]
 if env.get("VIBETRAM_OPENSSL_CARGO_BRIDGE")=="1":env=install_cargo_prefix_bridge(env,work,src)
 guard.env=env
 catalogue=configuration_source_closure(src) if configure else None
 if catalogue is not None:
  (out/"configuration-source-catalog.json").write_text(json.dumps(catalogue,indent=2)+"\n",encoding="utf-8")
  print("CONFIGURATION_SOURCE_CATALOG "+json.dumps(catalogue),flush=True)
 required=set(catalogue["externalModules"] if catalogue else module_set(src)[0])|ACTIVE_MM
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
 pod_result={}
 if configure:
  pod=work/"synthetic-runtime.pod";pod.write_text("=head1 NAME\n\noffline_fixture - synthetic documentation\n\n=head1 SYNOPSIS\n\nOFFLINE_POD_USAGE_FIXTURE\n\n=cut\n",encoding="ascii")
  pod_script=work/"pod-runtime.pl";pod_script.write_text(pod_runtime_program(),encoding="ascii")
  pod_result=json.loads(guard.run([perl,pod_script,pod],cwd=work,env=env,capture=True,timeout=30).stdout)
  assert pod_result.get("state")=="PASS_ACTUAL_LOCAL_POD_RENDERING" and pod_result.get("checks")==1,"POD_RUNTIME_EXECUTION_FAILED"
  print("ACTUAL_POD_RUNTIME_RESULT "+json.dumps(pod_result),flush=True)
 helper=work/"runtime-helpers.pl";helper.write_text(runtime_helper_program(),encoding="ascii");results={};configuration={}
 def actual(ndk,tools):
  def run_helpers():
   assert hashlib.sha256(perl.read_bytes()).hexdigest()==GIT_PERL_SHA,"RUNTIME_PERL_IDENTITY"
   results.update(json.loads(guard.run([perl,helper,perl,tools/"clang.exe",tools/"llvm-ar.exe",tools/"llvm-ranlib.exe"],cwd=work,env=env,capture=True,timeout=30).stdout))
   assert results["state"]=="PASS_ACTUAL_COMPILER_DISCOVERY_HELPERS" and results["checks"]==10 and results["makeMakerVersion"]=="7.76","RUNTIME_ACTUAL_HELPERS_FAILED"
   if configure:
    if cargo_commands:configuration.update(configure_with_runtime(guard,env,work,out,src,perl,ndk,tools,cargo_commands=True))
    else:configuration.update(configure_with_runtime(guard,env,work,out,src,perl,ndk,tools))
  lease=capture_one(perl.parent,perl,callback=run_helpers)
  require_lease(lease,"RUNTIME_INTERPRETER_LEASE",out,"runtime-interpreter")
 with_physical_ndk_inputs(guard,env,out,actual)
 report={"state":"PASS_RUNTIME_CONFIGURE_ONLY" if configure else "PASS_RUNTIME_DEPENDENCY_AND_HELPER_QUALIFICATION","packages":plan["packages"],"missingProviderCount":len(missing),"preservedInstalledProviderCount":len(providers)-len(missing),"requiredModuleCount":len(required),"moduleClosure":closure["modules"],"helperTests":results,"podRuntime":pod_result,"sourceCatalogue":catalogue,"configureExecuted":configure,"compilationRequested":False,"compilerVersionQueriesAllowed":configure,"configuration":configuration,"globalInstallationChanged":False,"limits":"Active Cygwin compiler-discovery helpers and declared runtime prerequisites; not every MakeMaker API or future configure/make/build path","monitor":guard.report()}
 from runtime_report import write_runtime_report
 report=write_runtime_report(report,out,guard._resource_sample)
 source_check(ROOT);print(json.dumps(report,indent=2),flush=True)

 return selected,env,report

def prepare_cargo_runtime_source(guard,env,work,out):
 from openssl_probe import ROOT,PREFIX
 assert owned_pair(ROOT,work,out) and work==ROOT/"ci-work","CARGO_RUNTIME_OWNED_SCOPE"
 from host_linker import direct_msvc_linker
 assert direct_msvc_linker(env),"QUALIFIED_HOST_LINKER_REQUIRED"
 prepared=env.copy();prepared["VIBETRAM_OPENSSL_CARGO_BRIDGE"]="1"
 guard.run([sys.executable,"-B",ROOT/"ci/openssl_probe.py","--materialize",work],env=prepared,timeout=180)
 return prepared,work/"crate"/PREFIX/"openssl"

def overlay_only_probe(guard,env,work,out):
 from perl_prerequisites import inventory
 prepared,src=prepare_cargo_runtime_source(guard,env,work,out)
 _,original=inventory(guard,prepared,work,out,src)
 selected,_,smoke=repair_git_perl(guard,prepared,work,out,src,original)
 report={"state":"PASS_OVERLAY_ONLY_ACTUAL_BUILD_ENVIRONMENT","PerlVersion":selected["metadata"]["version"],"interpreterSHA256":selected["sha256"],"moduleSHA256":MODULE_SHA,"requiredModuleCount":smoke["requiredModuleCount"],"focused":smoke["focused"],"validationRelaxed":False,"ConfigureExecuted":False,"makeExecuted":False,"projectCompiled":False,"monitor":guard.report()}
 text=json.dumps(report,indent=2)+"\n";assert len(text.encode())<32768
 (out/"overlay-only-result.json").write_text(text,encoding="utf-8");print(text,flush=True)
 return report

def bootstrap_for_cargo(guard,env,work,out):
 prepared,src=prepare_cargo_runtime_source(guard,env,work,out)
 selected,prepared,report=qualify_prepared_runtime(guard,prepared,work,out,src,configure=True)
 assert report["state"]=="PASS_RUNTIME_CONFIGURE_ONLY","CARGO_RUNTIME_PREFLIGHT_FAILED"
 return prepared,pathlib.Path(selected["path"]),src,report

def cargo_command_environment(guard,env,ndk,tools,perl):
 assert env.get("VIBETRAM_OPENSSL_CARGO_BRIDGE")=="1","CARGO_COMMAND_PROBE_BRIDGE_REQUIRED"
 cross=build_android_environment(env,ndk,tools,perl)
 cross.update(CC=str(tools/"clang.exe"),CXX=str(tools/"clang++.exe"),AR=str(tools/"llvm-ar.exe"),RANLIB=str(tools/"llvm-ranlib.exe"),RANLIB_aarch64_linux_android=str(tools/"llvm-ranlib.exe"))
 from ndk_linker import qualify as qualify_ndk
 from ndk_compilers import qualify as qualify_compilers
 cross.update(qualify_ndk(cross,guard._resource_sample));cross.update(qualify_compilers(cross,guard._resource_sample))
 return cross

def configured_tool_fields(fields,cargo_commands=False):
 assert fields.get("CROSS_COMPILE")=="","CONFIGURE_TOOL_SELECTION_CHANGED"
 roles={"CC":"clang.exe","AR":"llvm-ar.exe","RANLIB":"llvm-ranlib.exe"}
 if cargo_commands:roles["CXX"]="clang++.exe"
 from ndk_linker import NDK
 tools=NDK/"toolchains/llvm/prebuilt/windows-x86_64/bin"
 for role,name in roles.items():
  expected=openssl_shell_tool(role,str(tools/name)) if cargo_commands else name
  assert fields.get(role)=="$(CROSS_COMPILE)"+expected,"CONFIGURE_TOOL_SELECTION_CHANGED"

def _recipe_word(value):
 return bool(re.fullmatch(r"[A-Za-z0-9_./=,+:-]+",value) or re.fullmatch(r'-D(?:OPENSSLDIR|ENGINESDIR|MODULESDIR)=\"/[A-Za-z0-9_./+-]+\"',value))

def targeted_dependency_sequence(output,target,stage):
 assert stage in ("dryrun","executed"),"TARGETED_RECIPE_STAGE"
 assert isinstance(output,str) and len(output.encode())<=32768 and len(output.splitlines())<=128,"TARGETED_RECIPE_BOUND"
 if target!="crypto/libcrypto-lib-ctype.o":return output
 dep="crypto/libcrypto-lib-ctype.d";lines=[x.strip() for x in output.splitlines() if x.strip()]
 tail=["touch "+dep+".tmp","if cmp "+dep+".tmp "+dep+" > /dev/null 2> /dev/null; then "+chr(92),"rm -f "+dep+".tmp; "+chr(92),"else "+chr(92),"mv "+dep+".tmp "+dep+"; "+chr(92),"fi"]
 if stage=="dryrun":assert len(lines)==7 and lines[1:]==tail,"TARGETED_DEPENDENCY_SEQUENCE"
 else:assert len(lines)==1,"TARGETED_SILENT_DEPENDENCY_OUTPUT"
 return lines[0]

def cargo_recipe_arguments(output,target,source,generator_required=None,recipe_stage=None):
 import shlex
 from ndk_compilers import PATHS
 allowed={"crypto/libcrypto-lib-ctype.o":"crypto/ctype.c","crypto/aes/libcrypto-lib-aes-sha1-armv8.o":"crypto/aes/aes-sha1-armv8.S"}
 assert allowed.get(target)==source,"TARGETED_OBJECT_SCOPE"
 if recipe_stage is not None:output=targeted_dependency_sequence(output,target,recipe_stage)
 assert isinstance(output,str) and len(output.encode())<=32768,"TARGETED_RECIPE_BOUND"
 lines=[line.strip() for line in output.splitlines() if line.strip()];assert len(lines)<=128,"TARGETED_RECIPE_LINES"
 encoded=openssl_shell_tool("CC",str(PATHS["clang.exe"]));compiler=[];generators=[]
 for line in lines:
  try:args=shlex.split(line,posix=True)
  except ValueError:raise AssertionError("TARGETED_RECIPE_QUOTING") from None
  assert args and len(args)<=128 and all(len(x)<=2048 for x in args),"TARGETED_ARGV_BOUND"
  if args[0]==PATHS["clang.exe"].as_posix():
   assert line.startswith(encoded+" "),"TARGETED_COMPILER_ENCODING"
   assert args.count("-c")==1 and args.count("-o")==1 and args[args.index("-o")+1]==target and args[-1]==source,"TARGETED_RECIPE_IDENTITY"
   assert "--target=aarch64-linux-android29" in args and all(_recipe_word(x) for x in args[1:]),"TARGETED_UNEXPECTED_SHELL_SYNTAX"
   assert not any(x.startswith("/") or x.startswith("-I/") for x in args[1:]),"TARGETED_NATIVE_INPUT_PATH"
   if recipe_stage is not None and target=="crypto/libcrypto-lib-ctype.o":
    dep="crypto/libcrypto-lib-ctype.d.tmp"
    assert args.count("-MMD")==1 and args.count("-MF")==1 and args[args.index("-MF")+1]==dep and not any(x.startswith("-MF") and x!="-MF" for x in args),"TARGETED_DEPENDENCY_COMPILER_OUTPUT"
   compiler.append(args)
  elif args[0]=="CC="+encoded:
   assert len(args)>=5 and target=="crypto/aes/libcrypto-lib-aes-sha1-armv8.o" and args[1]=="perl.exe","TARGETED_GENERATOR_ROLE"
   script="crypto/aes/asm/aes-sha1-armv8.pl";assert args.count(script)==1,"TARGETED_GENERATOR_SCRIPT"
   index=args.index(script);assert index+2<len(args),"TARGETED_GENERATOR_ARGUMENT_COUNT"
   assert all(x in ("-I.","-Iutil/perl") for x in args[2:index]) and len(set(args[2:index]))==len(args[2:index]),"TARGETED_GENERATOR_PREFIX"
   assert args[index+1]=="linux64" and args[-1]==source,"TARGETED_GENERATOR_TARGET"
   assert all(_recipe_word(x) and not x.startswith("/") and not x.startswith("-I/") for x in args[index+2:-1]),"TARGETED_GENERATOR_ARGUMENT"
   generators.append(args)
  else:raise AssertionError("TARGETED_UNKNOWN_COMMAND")
 assert len(compiler)==1 and len(generators)<=1,"TARGETED_COMMAND_COUNT"
 if generator_required is not None:assert type(generator_required) is bool and len(generators)==int(generator_required),"TARGETED_GENERATOR_COUNT"
 return compiler[0]

def command_evidence(output,target,work,recipe_stage=None):
 import shlex
 allowed={"crypto/libcrypto-lib-ctype.o","crypto/aes/libcrypto-lib-aes-sha1-armv8.o"}
 assert target in allowed and isinstance(output,str),"COMMAND_EVIDENCE_SCOPE"
 try:raw=output.encode("utf-8")
 except UnicodeEncodeError:raw=output.encode("utf-8","surrogatepass");invalid=True
 else:invalid=False
 row={"target":target,"inputBytes":len(raw),"inputSHA256":hashlib.sha256(raw).hexdigest(),"completeForQualification":False}
 if invalid or any(ord(c)>126 or ord(c)<32 and c not in "\n\r\t" for c in output):return {**row,"state":"COMMAND_TEXT_ENCODING_FATAL"}
 if len(raw)>32768 or len(output.splitlines())>128:return {**row,"state":"COMMAND_TEXT_SIZE_FATAL"}
 if any(x in output for x in ("<ndk>","<work>","<redacted>")):return {**row,"state":"COMMAND_TEXT_MARKER_FATAL"}
 from ndk_linker import NDK
 tools=NDK/"toolchains/llvm/prebuilt/windows-x86_64/bin"
 normalized=output
 roots=[(str(tools),"<ndk>"),(tools.as_posix(),"<ndk>"),(str(work),"<work>"),(work.as_posix(),"<work>")]
 if re.fullmatch(r"[A-Za-z]:/.*",work.as_posix()):roots.append(("/"+work.as_posix()[0].lower()+"/"+work.as_posix()[3:],"<work>"))
 for prefix,marker in sorted(set(roots),key=lambda x:len(x[0]),reverse=True):
  normalized=re.sub(re.escape(prefix)+r"(?=$|[\\/\"'])",lambda _:marker,normalized)
 if re.search(r"(?i)(?:[A-Z0-9_]*(?:TOKEN|SECRET|PASSWORD|AUTHORIZATION|API_KEY)[A-Z0-9_]*)\s*=",normalized) or re.search(r"(?i)[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}",normalized):return {**row,"state":"COMMAND_PRIVATE_FIELD_FATAL"}
 if re.search(r"[A-Za-z]:|\\\\|://",normalized) or any(x in normalized for x in ("$",chr(96),"\x00")):return {**row,"state":"COMMAND_UNAPPROVED_PATH_FATAL"}
 if recipe_stage is not None:
  try:normalized=targeted_dependency_sequence(normalized,target,recipe_stage)
  except (AssertionError,IndexError):return {**row,"state":"COMMAND_DEPENDENCY_SEQUENCE_FATAL"}
 for line_index,line in enumerate(normalized.splitlines(),1):
  if not line.strip():continue
  try:tokens=shlex.split(line,posix=True)
  except ValueError:return {**row,"state":"COMMAND_QUOTING_FATAL"}
  if not tokens or not (tokens[0]=="<ndk>/clang.exe" or tokens[0].startswith("CC=") and len(tokens)>1 and tokens[1]=="perl.exe"):
   # Diagnostic categories are fixed labels, never unknown token contents.
   known={"perl.exe":"perl","make.exe":"make","echo":"echo"}
   shape={"head":known.get(tokens[0],"other") if tokens else "empty","arguments":["option" if token.startswith("-") else "assignment" if "=" in token else "value" for token in tokens[1:17]],"omittedArguments":max(0,len(tokens)-17)}
   return {**row,"state":"COMMAND_UNCLASSIFIED_FATAL","rejectedLineIndex":line_index,"tokenCount":len(tokens),"lineSHA256":hashlib.sha256(line.encode("utf-8")).hexdigest(),"commandShape":shape}
  for token in tokens:
   if token in ("-DOPENSSLDIR=\"/usr/local/ssl\"","-DOPENSSLDIR='/usr/local/ssl'"):continue
   value=token.split("=",1)[-1].strip("'\"")
   if value.startswith(("/","~")) or token.startswith(("-I/","-L/")) or "\\" in token or re.search(r"(?:^|[/\\])\.\.(?=[/\\]|$)",value) or token in ("|","||","&&",";","<",">",">>"):return {**row,"state":"COMMAND_UNAPPROVED_PATH_FATAL"}
 return {**row,"state":"BOUNDED_NORMALIZED_COMMAND_TEXT","completeForQualification":True,"normalizedCommandText":normalized}

def put_command_evidence(out,stage,target,row):
 names={"crypto/libcrypto-lib-ctype.o":"ctype","crypto/aes/libcrypto-lib-aes-sha1-armv8.o":"aes-sha1"}
 assert target in names and stage in ("dryrun","executed","dryrun-failure","executed-failure","object"),"COMMAND_RECEIPT_SCOPE"
 data=(json.dumps(row,indent=2)+"\n").encode();assert len(data)<=49152,"COMMAND_RECEIPT_BOUND"
 with (out/("command-"+names[target]+"-"+stage+".json")).open("xb") as f:f.write(data)

def validated_command_evidence(out,stage,output,target,source,work,generator_required):
 assert stage in ("dryrun","executed"),"COMMAND_STAGE"
 evidence=command_evidence(output,target,work,stage);put_command_evidence(out,stage,target,evidence)
 try:
  assert evidence["completeForQualification"],"COMMAND_EVIDENCE_INCOMPLETE"
  return cargo_recipe_arguments(output,target,source,generator_required,stage)
 except BaseException as error:
  code=error.args[0] if error.args and isinstance(error.args[0],str) and re.fullmatch(r"[A-Z_0-9]{1,80}",error.args[0]) else "COMMAND_VALIDATION_FAILED"
  failure={"state":"COMMAND_VALIDATION_FAILED_FATAL","target":target,"inputSHA256":evidence["inputSHA256"],"errorClass":type(error).__name__[:64],"code":code,"errno":getattr(error,"errno",None) if type(getattr(error,"errno",None)) is int else None,"winerror":getattr(error,"winerror",None) if type(getattr(error,"winerror",None)) is int else None,"partialBuildAccepted":False}
  try:put_command_evidence(out,stage+"-failure",target,failure)
  except BaseException as report_error:error.add_note("COMMAND_FAILURE_RECEIPT_FAILED:"+type(report_error).__name__)
  raise


OPENSSL_TEMPLATE_SHA256="cc02bca6ac2c5a32c89661d391bc1c610116fa2c98f7a202a41056c05a25f8b8"
OPENSSL_TEMPLATE_BYTES=85121

class TemplateInputAPI:
 def __init__(self):
  import ctypes
  from ndk_input_metadata import API
  self.ctypes=ctypes;self.meta=API();self.k=self.meta.k;w=self.meta.w
  self.k.ReadFile.argtypes=[w.HANDLE,ctypes.c_void_p,w.DWORD,ctypes.POINTER(w.DWORD),ctypes.c_void_p];self.k.ReadFile.restype=w.BOOL
 def open(self,path,read=False):
  h=self.k.CreateFileW(str(path),0x80000000 if read else 0,1,None,3,0x02200000,None)
  if h==self.ctypes.c_void_p(-1).value:raise self.ctypes.WinError(self.ctypes.get_last_error())
  return h
 def info(self,h):return self.meta.info(h)
 def read(self,h,limit):
  parts=[];total=0
  while total<limit:
   b=self.ctypes.create_string_buffer(min(65536,limit-total));n=self.meta.w.DWORD()
   if not self.k.ReadFile(h,b,len(b),self.ctypes.byref(n),None):raise self.ctypes.WinError(self.ctypes.get_last_error())
   if not n.value:break
   total+=n.value;parts.append(b.raw[:n.value])
  return b"".join(parts)
 def close(self,h):return bool(self.k.CloseHandle(h))

def qualify_openssl_template(src,resource_check=lambda:None,api=None,clock=time.monotonic):
 src=pathlib.Path(src);assert src.is_absolute() and ".." not in src.parts,"TEMPLATE_SOURCE_SCOPE"
 path=src/"Configurations/unix-Makefile.tmpl";assert len(path.parts)<=24,"TEMPLATE_PATH_DEPTH"
 assert 0<OPENSSL_TEMPLATE_BYTES<=262144,"TEMPLATE_SIZE_BOUND"
 api=api or TemplateInputAPI();held=[];primary=None;started=clock()
 def tick():
  resource_check();assert clock()-started<5,"TEMPLATE_METADATA_DEADLINE"
 def opened(p,read=False):
  tick();h=api.open(p,read=read);held.append(h);return h
 def checked(h,directory):
  tick();r=api.info(h)
  assert r["tag"]==0 and not r["attributes"]&0x400,"TEMPLATE_REPARSE"
  assert bool(r["attributes"]&0x10)==directory,"TEMPLATE_COMPONENT_TYPE"
  return r
 def stable(a,b,directory):
  assert all(a[k]==b[k] for k in ("identity","attributes","tag")),"TEMPLATE_IDENTITY_CHANGED"
  if not directory:assert a["bytes"]==b["bytes"]==OPENSSL_TEMPLATE_BYTES,"TEMPLATE_SIZE_CHANGED"
 try:
  chain=[];part=pathlib.Path(path.anchor)
  for i,name in enumerate(path.parts):
   if i:part=part/name
   h=opened(part);directory=i<len(path.parts)-1;r=checked(h,directory)
   chain.append((part,h,r,directory))
  leaf=chain[-1][2];assert leaf["bytes"]==OPENSSL_TEMPLATE_BYTES,"TEMPLATE_SIZE_MISMATCH"
  reader=opened(path,True);stable(leaf,checked(reader,False),False)
  data=api.read(reader,OPENSSL_TEMPLATE_BYTES+1);tick()
  assert len(data)==OPENSSL_TEMPLATE_BYTES and hashlib.sha256(data).hexdigest()==OPENSSL_TEMPLATE_SHA256,"TEMPLATE_HASH_MISMATCH"
  stable(leaf,checked(reader,False),False)
  for part,h,before,directory in chain:
   stable(before,checked(h,directory),directory)
   fresh=opened(part);stable(before,checked(fresh,directory),directory)
  return {"sha256":OPENSSL_TEMPLATE_SHA256,"bytes":OPENSSL_TEMPLATE_BYTES,"fileIdentity":leaf["identity"],"ancestorIdentities":[x[2]["identity"] for x in chain[:-1]],"noFollowRegularChain":True}
 except BaseException as e:primary=e;raise
 finally:
  failed=False
  for h in reversed(held):
   try:failed=not api.close(h) or failed
   except BaseException:failed=True
  if failed:
   if primary is not None:primary.add_note("TEMPLATE_HANDLE_CLOSE_FAILED")
   else:raise AssertionError("TEMPLATE_HANDLE_CLOSE_FAILED")

def qualify_cargo_objects(guard,env,work,out,src,perl,configuration):
 from openssl_probe import PHYSICAL_SDK,CHECKSUM,PREFIX
 from perl_path_probe import MAKE_SHA,MAKE_BYTES
 from build_guard import executable_snapshot
 ndk=PHYSICAL_SDK/"ndk/30.0.16248370";tools=ndk/"toolchains/llvm/prebuilt/windows-x86_64/bin"
 cross=cargo_command_environment(guard,env,ndk,tools,perl)
 configured_tool_fields(configuration["makefileFields"],True)
 make=ndk/"prebuilt/windows-x86_64/bin/make.exe";shell=perl.parent/"sh.exe"
 for path,digest,size in ((make,MAKE_SHA,MAKE_BYTES),(shell,"5490d0da5e7cf9d92068cc48fcc590f2bcf8564add8ff91c3b5fe541eb2d72e3",None),(perl,GIT_PERL_SHA,None)):
  row=executable_snapshot(path,guard._resource_sample)
  assert row["sha256"]==digest and (size is None or row["bytes"]==size),"TARGETED_TOOL_PIN"
 makefile=src/"Makefile";before=hashlib.sha256(makefile.read_bytes()).hexdigest()
 assert before==configuration["files"]["Makefile"]["sha256"],"TARGETED_MAKEFILE_CHANGED"
 assert src==work/"crate"/PREFIX/"openssl","TARGETED_TEMPLATE_SOURCE_SCOPE"
 template_binding=qualify_openssl_template(src,guard._resource_sample)
 def verify_template():assert qualify_openssl_template(src,guard._resource_sample)==template_binding,"TARGETED_TEMPLATE_CHANGED"
 guard.run([make,"-f","Makefile","-j1","include/openssl/opensslv.h"],cwd=src,env=cross,capture=True,timeout=60)
 verify_template()
 rows=[]
 for target,source in (("crypto/libcrypto-lib-ctype.o","crypto/ctype.c"),("crypto/aes/libcrypto-lib-aes-sha1-armv8.o","crypto/aes/aes-sha1-armv8.S")):
  obj=src/target;assert not obj.exists(),"TARGETED_EXISTING_OBJECT"
  initial=smoke_artifact_identity(src/source) if (src/source).is_file() else None
  verify_template()
  dry=guard.run([make,"-f","Makefile","--dry-run","-j1",target],cwd=src,env=cross,capture=True,timeout=30)
  verify_template()
  generator_required=target=="crypto/aes/libcrypto-lib-aes-sha1-armv8.o" and initial is None
  generator=src/"crypto/aes/asm/aes-sha1-armv8.pl"
  generator_identity=smoke_artifact_identity(generator) if target=="crypto/aes/libcrypto-lib-aes-sha1-armv8.o" else None
  args=validated_command_evidence(out,"dryrun",dry.stdout,target,source,work,generator_required)
  verify_template()
  done=guard.run([make,"-f","Makefile","-j1",target],cwd=src,env=cross,capture=True,timeout=90)
  verify_template()
  assert validated_command_evidence(out,"executed",done.stdout,target,source,work,generator_required)==args,"TARGETED_EXECUTED_RECIPE_CHANGED"
  if generator_identity is not None:assert smoke_artifact_identity(generator)==generator_identity,"TARGETED_GENERATOR_CHANGED"
  meta=smoke_artifact_identity(obj);assert 64<=meta["bytes"]<=2*1024**2,"TARGETED_OBJECT_SIZE"
  data=obj.read_bytes();assert data[:6]==b"\x7fELF\x02\x01" and int.from_bytes(data[16:18],"little")==1 and int.from_bytes(data[18:20],"little")==183,"TARGETED_OBJECT_NOT_ARM64_REL"
  source_meta=smoke_artifact_identity(src/source)
  if initial is not None:assert initial==source_meta,"TARGETED_SOURCE_CHANGED"
  assert hashlib.sha256(makefile.read_bytes()).hexdigest()==before,"TARGETED_MAKEFILE_CHANGED"
  row={"target":target,"source":source,"compilerArgv":args,"object":meta,"sourceIdentity":source_meta,"generatedSource":initial is None,"ELF64":True,"machine":"AArch64","type":"REL","executed":False}
  put_command_evidence(out,"object",target,{"state":"ONE_OBJECT_VALIDATED_NOT_OVERALL_PASS",**row});rows.append(row)
 report={"state":"PASS_CARGO_EQUIVALENT_OPENSSL_TWO_OBJECTS","templateInputBinding":template_binding,"objects":rows,"configureCompilerFields":configuration["makefileFields"],"sourceArchiveSHA256":CHECKSUM,"makefileSHA256":before,"makeSHA256":MAKE_SHA,"shellSHA256":"5490d0da5e7cf9d92068cc48fcc590f2bcf8564add8ff91c3b5fe541eb2d72e3","perlSHA256":GIT_PERL_SHA,"maximumObjects":2,"makeWorkers":1,"fullAndroidBuild":False,"rustProvisioning":False,"signed":False,"releasable":False,"monitor":guard.report()}
 (out/"cargo-command-qualification.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8");print(json.dumps(report,indent=2),flush=True)
 return report

def runtime_diagnosis(configure=False,cargo_commands=False):
 from openssl_probe import ROOT,PREFIX,probe_layout,probe_environment,with_physical_ndk_inputs
 from build_guard import Guard,MIN_FREE,MAX_OUTPUT
 from check_source import source_check
 from perl_prerequisites import inventory
 from ndk_input_metadata import capture_one
 import shutil
 assert os.name=="nt" and os.environ.get("GITHUB_REPOSITORY")=="TroubledPerson/Vibetram" and os.environ.get("GITHUB_REF")=="refs/heads/main"
 event=json.loads(pathlib.Path(os.environ["GITHUB_EVENT_PATH"]).read_text());assert os.environ["GITHUB_EVENT_NAME"]=="push" and ("[openssl-probe-191]" if configure else "[perl-runtime-191]") in event["head_commit"]["message"]
 source_check(ROOT);work,out,cargo,rustup=probe_layout(ROOT)
 assert not any(p.exists() for p in (work,out,cargo,rustup)),"PRESERVE_RUNTIME_OUTPUTS"
 assert shutil.disk_usage(ROOT).free>=MIN_FREE+MAX_OUTPUT
 for p in (work,out,cargo,rustup):p.mkdir()
 for p in ("tmp","home","profile","profile/AppData/Local","profile/AppData/Roaming"):(work/p).mkdir(parents=True,exist_ok=True)
 env=probe_environment(work,cargo,rustup)
 if cargo_commands:
  assert configure,"CARGO_COMMAND_CONFIGURE_REQUIRED"
  env["VIBETRAM_OPENSSL_CARGO_BRIDGE"]="1"
 guard=Guard(ROOT,work,out,env)
 if cargo_commands:
  import time
  deadline=time.monotonic()+540;original_sample=guard._resource_sample
  def bounded_sample():
   assert time.monotonic()<=deadline,"TARGETED_PROBE_DEADLINE"
   original_sample()
  guard._resource_sample=bounded_sample
 guard.run([sys.executable,"-B",ROOT/"ci/openssl_probe.py","--materialize",work],env=env,timeout=180)
 src=work/"crate"/PREFIX/"openssl"
 if cargo_commands:selected,qualified_env,report=qualify_prepared_runtime(guard,env,work,out,src,configure=configure,cargo_commands=True)
 else:selected,qualified_env,report=qualify_prepared_runtime(guard,env,work,out,src,configure=configure)
 if cargo_commands:qualify_cargo_objects(guard,qualified_env,work,out,src,pathlib.Path(selected["path"]),report["configuration"])
 if not configure:
  from perl_path_probe import qualify as qualify_paths
  from openssl_probe import PHYSICAL_SDK
  qualify_paths(guard,qualified_env,work,out,pathlib.Path(selected["path"]),PHYSICAL_SDK/"ndk/30.0.16248370")

if __name__=="__main__":
 if len(sys.argv)==2 and sys.argv[1]=="--runtime-cargo-command":runtime_diagnosis(configure=True,cargo_commands=True)
 elif len(sys.argv)==2 and sys.argv[1]=="--runtime-configure":runtime_diagnosis(configure=True)
 elif len(sys.argv)==2 and sys.argv[1]=="--runtime-diagnosis":runtime_diagnosis()
 elif len(sys.argv)==4 and sys.argv[1]=="--runtime-prepare":runtime_prepare(pathlib.Path(sys.argv[2]),pathlib.Path(sys.argv[3]))
 else:
  assert len(sys.argv)==4 and sys.argv[1]=="--prepare"
  prepare(pathlib.Path(sys.argv[2]),pathlib.Path(sys.argv[3]))
