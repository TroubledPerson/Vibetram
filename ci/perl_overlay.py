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
 assert imports(body)=={"base","strict"} and re.search(r"use\s+base\s+[^;\n]*\bExporter\b",body),"UNREVIEWED_MODULE_IMPORT"
 assert "COPYRIGHT" in body and "MIT" in body,"MODULE_NOTICE_ABSENT"
 return selected,{"archiveSHA256":ARCHIVE_SHA,"archiveBytes":len(data),"moduleSHA256":MODULE_SHA,"declaredRuntimeDependencies":{},"observedCoreImports":["base","Exporter","strict"],"optionalLexicon":"Documented fallback when Locale::Maketext::Lexicon is absent; focused runtime test required","metadataLicense":"perl; complete original module/README/META/Makefile notices retained","memberCount":len(members),"uncompressedBytes":total,"sourceReviewedBeforeCopy":True}
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
if __name__=="__main__":
 assert len(sys.argv)==4 and sys.argv[1]=="--prepare"
 prepare(pathlib.Path(sys.argv[2]),pathlib.Path(sys.argv[3]))
