"""Batch installed Perl prerequisite inventory; no installation or native compilation."""
import pathlib,re,json,hashlib,os,urllib.request,tarfile,io
SEEDS={"base","Carp","Config","Cwd","Data::Dumper","Digest::SHA","Exporter","File::Basename","File::Compare","File::Copy","File::Glob","File::Path","File::Spec","File::Spec::Functions","File::Temp","FindBin","Getopt::Std","Getopt::Long","IO::Handle","IO::Select","IPC::Cmd","IPC::Open3","JSON::PP","Locale::Maketext::Simple","Module::Load::Conditional","Params::Check","POSIX","Scalar::Util","Symbol","Text::ParseWords","Text::Template","Time::Piece"}
CANDIDATES=(("Git for Windows",pathlib.Path("C:/Program Files/Git/usr/bin/perl.exe")),("MSYS2",pathlib.Path("C:/msys64/usr/bin/perl.exe")),("Strawberry",pathlib.Path("C:/Strawberry/perl/bin/perl.exe")))
MODULE=re.compile(r"[A-Za-z_]\w*(?:::\w+)*",re.ASCII)
def imports(text):
 result=set();pod=False
 for line in text.splitlines():
  if line.startswith("=cut"):pod=False;continue
  if line.startswith("="):pod=True;continue
  if pod:continue
  if line.startswith(("__END__","__DATA__")):break
  m=re.match(r"^\s*(?:use|require)\s+([A-Za-z_]\w*(?:::\w+)*)\b",line,re.ASCII)
  if m:result.add(m[1])
 return result
def module_set(src):
 roots=[src/"Configure",src/"Configurations/unix-Makefile.tmpl",src/"Configurations/unix-checker.pm",*sorted((src/"Configurations").glob("*.conf"))]
 assert len(roots)<=128
 pending=list(roots);seen=set();mods=set(SEEDS)
 while pending:
  p=pending.pop()
  if p in seen:continue
  assert len(seen)<128 and p.is_relative_to(src) and p.stat().st_size<1024**2,"SOURCE_MODULE_SCAN_BOUND"
  seen.add(p);found=imports(p.read_text(encoding="utf-8"));mods.update(found)
  for m in found:
   assert MODULE.fullmatch(m),"SOURCE_MODULE_NAME"
   local=src/"util/perl"/(m.replace("::","/")+".pm")
   if local.is_file() and local not in seen:pending.append(local)
 assert len(mods)<=128,"MODULE_COUNT"
 return sorted(mods),sorted(p.relative_to(src).as_posix() for p in seen)
def program(modules):
 assert modules and len(modules)<=128 and len(set(modules))==len(modules) and all(MODULE.fullmatch(m) for m in modules)
 return r'''use strict;
use warnings;
unshift @INC, 'util/perl', 'external/perl/Text-Template-1.56/lib';
my @required = qw(__MODULES__);
my @rows;
for my $m (@required) {
 my $file=$m; $file =~ s{::}{/}g; $file.=".pm";
 my $ok=eval { require $file; if ($m eq "Text::Template") { Text::Template->VERSION(1.46); } 1; };
 my $error=$@;
 my @missing=($error =~ m{Can't locate ([A-Za-z0-9_/]+)[.]pm}g);
 for (@missing) { s{/}{::}g; }
 my $version=eval { $m->VERSION };
 $version=defined($version) ? "$version" : "-";
 $version =~ s/[^A-Za-z0-9_.+-]//g;
 $version=substr($version,0,80); $version="-" unless length($version);
 push @rows,join(chr(9),"MODULE",$m,$ok ? "1":"0",$version,@missing ? join(";",@missing):"-");
}
my $path=eval { File::Spec::Functions::rel2abs(".") };
my $unix=defined($path) && index($path,"/")>=0 && index($path,chr(92))<0;
my $version="$^V"; $version =~ s/^v//;
my $arch=$Config::Config{archname} // "-";
print join(chr(9),"META",$version,$arch,$^O,$unix ? "1":"0"),chr(10);
for (@rows) { print $_,chr(10); }
print join(chr(9),"END",scalar(@required)),chr(10);
'''.replace("__MODULES__"," ".join(modules))
def parse(text,modules):
 assert len(text.encode())<=65536,"MODULE_REPORT_BOUND"
 lines=text.splitlines();assert len(lines)==len(modules)+2,"MODULE_REPORT_LENGTH"
 meta=lines[0].split("\t");assert len(meta)==5 and meta[0]=="META" and meta[4] in ("0","1"),"MODULE_META"
 assert all(re.fullmatch(r"[A-Za-z0-9_.+-]{1,160}",v) for v in meta[1:4]),"MODULE_META_FIELDS"
 end=lines[-1].split("\t");assert end==["END",str(len(modules))],"MODULE_REPORT_END"
 rows={}
 for line in lines[1:-1]:
  fields=line.split("\t");assert len(fields)==5 and fields[0]=="MODULE","MODULE_RECORD"
  _,name,loaded,version,missing=fields
  assert name in modules and name not in rows and loaded in ("0","1") and re.fullmatch(r"[A-Za-z0-9_.+-]{1,80}",version),"MODULE_RECORD_FIELDS"
  missing=[] if missing=="-" else missing.split(";")
  assert len(missing)<=8 and all(MODULE.fullmatch(m) for m in missing),"TRANSITIVE_MODULE_NAME"
  rows[name]={"loaded":loaded=="1","version":None if version=="-" else version,"missing":missing}
 assert set(rows)==set(modules),"INCOMPLETE_MODULE_SET"
 version=tuple(int(x) for x in meta[1].split(".")) if re.fullmatch(r"\d+[.]\d+[.]\d+",meta[1]) else ()
 unix=meta[4]=="1";all_loaded=all(x["loaded"] for x in rows.values())
 return {"metadata":{"version":meta[1],"arch":meta[2],"os":meta[3],"unixPaths":unix},"modules":rows,"complete":all_loaded and unix and version>=(5,10,0),"allModulesLoaded":all_loaded}
def inventory(guard,env,work,out,src):
 from ndk_input_metadata import capture_one
 modules,files=module_set(src);script=work/"perl-required-modules.pl";script.write_text(program(modules),encoding="ascii")
 rows=[]
 for label,path in CANDIDATES:
  row={"installation":label,"path":str(path),"provenance":"Documented installation on official hosted Windows image","status":"PENDING"}
  def check():
   row["sha256"]=hashlib.sha256(path.read_bytes()).hexdigest()
   result=guard.run([path,script],cwd=src,env=env,capture=True,timeout=25)
   row.update(parse(result.stdout,modules));row["status"]="INVENTORIED"
  metadata=capture_one(path.parent,path,callback=check);row["inputMetadata"]=metadata
  if metadata.get("osError") in (2,3) and not metadata.get("callbackInvoked"):
   row["status"]="NOT_INSTALLED";rows.append(row);continue
  rows.append(row)
  if not metadata["qualified"] or not metadata.get("callbackSucceeded"):
   row["status"]="METADATA_OR_EXECUTION_STOP";break
 report={"state":"INSTALLED_PERL_MODULE_INVENTORY","requiredModules":modules,"sourceFiles":files,"candidates":rows,"sourceBasis":"Checksum-pinned OpenSSL Configure/local module closure plus direct configuration imports and explicit IPC/core dependencies","limits":"Observed module-load closure and selected Configure syntax check; not a guarantee for all future make/test paths","modulesInstalled":False}
 text=json.dumps(report,indent=2)+"\n";assert len(text.encode())<65536
 (out/"perl-module-inventory.json").write_text(text,encoding="utf-8");print(text,flush=True)
 assert all(r["status"] in ("INVENTORIED","NOT_INSTALLED") for r in rows) and len(rows)==len(CANDIDATES),"PERL_INPUT_QUALIFICATION_STOP"
 selected=next((r for r in rows if r.get("complete")),None)
 return selected,report
def cpan_proposal(out):
 base="https://cpan.metacpan.org/authors/id/J/JE/JESSE/"
 def get(name,limit):
  with urllib.request.urlopen(base+name,timeout=25) as r:
   assert r.status==200 and r.url.startswith(base),"CPAN_ROUTE_CHANGED"
   data=r.read(limit+1);assert len(data)<=limit,"CPAN_SIZE_BOUND";return data
 report={"state":"CPAN_PROPOSAL_ONLY","distribution":"Locale-Maketext-Simple","version":"0.21","author":"JESSE","archiveURL":base+"Locale-Maketext-Simple-0.21.tar.gz","installed":False,"executedPackageCode":False}
 try:
  checks=get("CHECKSUMS",1024**2).decode("utf-8");name="Locale-Maketext-Simple-0.21.tar.gz"
  entry=re.search(r"'"+re.escape(name)+r"'\s*=>\s*\{(.*?)\n\s*\}",checks,re.S);assert entry,"CPAN_CHECKSUM_ENTRY"
  digest=re.search(r"'sha256'\s*=>\s*'([a-f0-9]{64})'",entry[1]);assert digest,"CPAN_SHA256_ABSENT"
  data=get(name,128*1024);assert hashlib.sha256(data).hexdigest()==digest[1],"CPAN_CHECKSUM_MISMATCH"
  prefix="Locale-Maketext-Simple-0.21/"
  with tarfile.open(fileobj=io.BytesIO(data),mode="r:gz") as tar:
   members=tar.getmembers();assert len(members)<=128
   for m in members:
    p=pathlib.PurePosixPath(m.name);assert not p.is_absolute() and ".." not in p.parts and "\\" not in m.name and (m.isdir() or m.isfile()) and m.size<=128*1024,"CPAN_MEMBER"
   meta=tar.extractfile(prefix+"META.yml").read().decode("utf-8");body=tar.extractfile(prefix+"lib/Locale/Maketext/Simple.pm").read().decode("utf-8")
   readme=tar.extractfile(prefix+"README").read().decode("utf-8")
   report.update(sha256=digest[1],archiveBytes=len(data),declaredRuntimeRequiresEmpty=bool(re.search(r"^\s*requires:\s*\{\s*\}",meta,re.M)),sourceImports=sorted(imports(body)),purePerl=not any(m.name.endswith((".xs",".c",".so",".dll")) for m in members),licenceMetadata="perl" if re.search(r"license:\s*perl",meta) else "UNRESOLVED",README_SHA256=hashlib.sha256(readme.encode()).hexdigest(),moduleSHA256=hashlib.sha256(body.encode()).hexdigest(),proposal="Future ephemeral job-owned pure-Perl overlay only after reviewing required/optional imports and preserving package notices; no system install or version changes")
 except Exception as e:report.update(state="CPAN_PROPOSAL_INCOMPLETE_STOP",reason=str(e)[:120],checksumQualified=False)
 (out/"cpan-proposal.json").write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8");print(json.dumps(report,indent=2),flush=True)
if __name__=="__main__":
 import sys
 assert len(sys.argv)==3 and sys.argv[1]=="--cpan-proposal"
 cpan_proposal(pathlib.Path(sys.argv[2]))
