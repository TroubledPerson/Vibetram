"""Isolated Configure-only qualification; never imported by the production build."""
import hashlib,io,json,re
FLAG=b"-fno-temp-file"
TEMPLATE_SHA256="cc02bca6ac2c5a32c89661d391bc1c610116fa2c98f7a202a41056c05a25f8b8"
TEMPLATE_BYTES=85121
MAX_BYTES=8*1024**2
MAX_LINES=100000
MAX_TARGETS=8192
REQUIRED=(b"crypto/libcrypto-lib-ctype.o",b"crypto/bn/libcrypto-lib-bn_nist.o")
RULE=re.compile(rb"([A-Za-z0-9_./+-]+\.o):[ \t]*([^;\r\n]*)")
C_LINE=re.compile(rb"\t\$\(CC\)(?P<prefix>.*?) -MMD -MF (?P<dep>[A-Za-z0-9_./+-]+\.d)\.tmp -c -o \$@ (?P<src>[A-Za-z0-9_./+-]+\.c)")
PREFIX=re.compile(rb"(?:[ \tA-Za-z0-9_./+=,:\\'\"-]|\$\((?:LIB|DSO|BIN)_(?:CFLAGS|CPPFLAGS)\))*")
def relative(value):
 return bool(value) and not value.startswith((b"/",b"\\")) and all(x not in (b"",b".",b"..") for x in value.split(b"/"))
def plan(data):
 assert isinstance(data,bytes) and 0<len(data)<=MAX_BYTES,"DIRECT_PLAN_INPUT_BOUND"
 assert b"\0" not in data and FLAG not in data,"DIRECT_PLAN_REPLAY_OR_NUL"
 out=[];changed=[];seen=set();rule=None;assembly=0;lines=0
 for line in io.BytesIO(data):
  lines+=1;assert lines<=MAX_LINES and len(line)<=65536,"DIRECT_PLAN_LINE_BOUND"
  eol=b"\r\n" if line.endswith(b"\r\n") else (b"\n" if line.endswith(b"\n") else b"")
  body=line[:-len(eol)] if eol else line
  assert b"\r" not in body,"DIRECT_PLAN_NEWLINE"
  if body and not body.startswith((b"\t",b"#")):
   m=RULE.fullmatch(body);rule=(m[1],m[2].split()) if m else None
  if body.startswith(b"\t$(CC)") and b" -c -o " in body:
   assert body.startswith(b"\t$(CC) ") and rule is not None,"DIRECT_PLAN_OBJECT_RULE"
   target,deps=rule;assert relative(target),"DIRECT_PLAN_TARGET_PATH"
   source=body.rsplit(b" ",1)[-1]
   assert relative(source) and source in deps,"DIRECT_PLAN_SOURCE_BINDING"
   if source.endswith((b".s",b".S")):
    assembly+=1
   else:
    assert source.endswith(b".c"),"DIRECT_PLAN_COMPILER_ROLE"
    m=C_LINE.fullmatch(body);assert m is not None,"DIRECT_PLAN_C_RECIPE"
    prefix=m["prefix"]
    assert PREFIX.fullmatch(prefix) and any(x in prefix for x in (b"$(LIB_CFLAGS)",b"$(DSO_CFLAGS)",b"$(BIN_CFLAGS)")),"DIRECT_PLAN_PREFIX"
    assert body.count(b" -MMD ")==body.count(b" -MF ")==body.count(b" -c ")==body.count(b" -o ")==1,"DIRECT_PLAN_OPERATION"
    assert m["dep"]==target[:-2]+b".d" and m["src"]==source,"DIRECT_PLAN_DEPENDENCY"
    assert target not in seen and len(changed)<MAX_TARGETS,"DIRECT_PLAN_TARGET_BOUND"
    seen.add(target);changed.append(target)
    body=body.replace(b" -MMD -MF ",b" "+FLAG+b" -MMD -MF ",1)
  out.append(body+eol)
 assert all(x in seen for x in REQUIRED),"DIRECT_PLAN_REQUIRED_TARGETS"
 result=b"".join(out)
 assert result.count(FLAG)==len(changed) and len(result)==len(data)+(len(FLAG)+1)*len(changed),"DIRECT_PLAN_EXACT_DIFF"
 targets=b"\n".join(sorted(changed))+b"\n"
 return result,{"state":"REFERENCE_PLAN_ONLY_DISABLED","sourceSHA256":hashlib.sha256(data).hexdigest(),"proposedSHA256":hashlib.sha256(result).hexdigest(),"templateSHA256":TEMPLATE_SHA256,"templateBytes":TEMPLATE_BYTES,"cTargets":len(changed),"targetSetSHA256":hashlib.sha256(targets).hexdigest(),"assemblyRecipesUnchanged":assembly,"requiredTargets":[x.decode() for x in REQUIRED],"globalCFLAGSChanged":False,"fileWritten":False,"productionEnabled":False}

"""Disabled generated-Makefile writer prototype. Never imported by production."""
import pathlib,hashlib,time,ctypes,re
MAX=MAX_BYTES
class Stop(AssertionError):
 def __init__(self,code,cleanup=()):
  assert re.fullmatch("[A-Z_0-9]{1,80}",code)
  self.code=code;self.cleanup=tuple(cleanup);super().__init__(code)
def need(ok,code):
 if not ok:raise Stop(code)
def sha(b):return hashlib.sha256(b).hexdigest()
def key(row,directory):
 need(row["tag"]==0 and not row["attributes"]&0x400,"WRITER_REPARSE")
 need(bool(row["attributes"]&0x10)==directory,"WRITER_INPUT_TYPE")
 if not directory:need(row["links"]==1,"WRITER_HARDLINK")
 return (tuple(row["identity"]),row["created"],row["attributes"]&~0x20,row["tag"],row["links"] if not directory else None)
class WinAPI:
 def __init__(self):
  from ndk_input_metadata import API
  self.m=API();self.k=self.m.k;self.w=self.m.w
  w=self.w;c=ctypes
  self.k.ReadFile.argtypes=[w.HANDLE,c.c_void_p,w.DWORD,c.POINTER(w.DWORD),c.c_void_p];self.k.ReadFile.restype=w.BOOL
  self.k.WriteFile.argtypes=self.k.ReadFile.argtypes;self.k.WriteFile.restype=w.BOOL
  self.k.SetFilePointerEx.argtypes=[w.HANDLE,c.c_longlong,c.POINTER(c.c_longlong),w.DWORD];self.k.SetFilePointerEx.restype=w.BOOL
  self.k.SetEndOfFile.argtypes=[w.HANDLE];self.k.SetEndOfFile.restype=w.BOOL
  self.k.FlushFileBuffers.argtypes=[w.HANDLE];self.k.FlushFileBuffers.restype=w.BOOL
 def check(self,ok):
  if not ok:raise ctypes.WinError(ctypes.get_last_error())
 def open(self,path,role):
  access=0 if role=="directory" else 0x80000000|(0x40000000 if role=="output" else 0)
  h=self.k.CreateFileW(str(path),access,0 if role=="output" else 1,None,3,0x02200000,None)
  if h==ctypes.c_void_p(-1).value:raise ctypes.WinError(ctypes.get_last_error())
  return h
 def info(self,h):
  r=self.m.INFO();self.check(self.k.GetFileInformationByHandle(h,ctypes.byref(r)))
  out=self.m.info(h);out.update(created=(r.created.high<<32)|r.created.low,links=r.links)
  return out
 def seek(self,h):self.check(self.k.SetFilePointerEx(h,0,None,0))
 def read(self,h,limit,tick):
  self.seek(h);out=[];total=0
  while total<limit:
   tick();b=ctypes.create_string_buffer(min(65536,limit-total));n=self.w.DWORD()
   self.check(self.k.ReadFile(h,b,len(b),ctypes.byref(n),None))
   if not n.value:break
   total+=n.value;out.append(b.raw[:n.value])
  return b"".join(out)
 def write(self,h,data,tick):
  self.seek(h);done=0
  while done<len(data):
   tick();part=data[done:done+65536];n=self.w.DWORD();b=ctypes.create_string_buffer(part)
   self.check(self.k.WriteFile(h,b,len(part),ctypes.byref(n),None))
   need(n.value==len(part),"WRITER_SHORT_WRITE");done+=n.value
  tick();self.check(self.k.SetEndOfFile(h));self.check(self.k.FlushFileBuffers(h))
 def close(self,h):return bool(self.k.CloseHandle(h))
def transaction(api,root,manifest,*,apply=False,fixture=False,resource=lambda:None,clock=time.monotonic):
 # No production caller exists. Fixture admission is mandatory even for apply.
 need(fixture is True,"WRITER_PRODUCTION_DISABLED")
 need(type(apply) is bool,"WRITER_APPLY_TYPE")
 raw=str(root);root=pathlib.PureWindowsPath(raw)
 need(str(root)==raw and re.fullmatch(r"[A-Za-z]:\\",root.anchor) is not None and root.is_absolute() and not str(root).startswith("\\\\") and len(root.parts)<=20 and all(x not in (".","..") for x in root.parts),"WRITER_ROOT_SCOPE")
 need(set(manifest)=={"Makefile","Configure","Configurations/unix-Makefile.tmpl"},"WRITER_MANIFEST_SCOPE")
 for pin in manifest.values():
  need(type(pin) is dict and set(pin)=={"bytes","sha256"} and type(pin["bytes"]) is int and 0<pin["bytes"]<=MAX and isinstance(pin["sha256"],str) and re.fullmatch("[a-f0-9]{64}",pin["sha256"]),"WRITER_PIN")
 started=clock();held=[];rows=[];cache={};failure=None;report=None;changed=False
 def tick():
  resource();need(clock()-started<5,"WRITER_DEADLINE")
 def acquire(path,directory,role):
  tick();token=str(path).lower()
  if token in cache:return cache[token]
  h=api.open(path,role);held.append(h);row=api.info(h);k=key(row,directory);rows.append((h,k,directory,row["bytes"]));cache[token]=(h,row);return h,row
 def verify(after=False):
  for h,k,directory,size in rows:
   tick();row=api.info(h);need(key(row,directory)==k,"WRITER_IDENTITY_CHANGED")
   if not directory and not (after and h==output):need(row["bytes"]==size,"WRITER_INPUT_SIZE_CHANGED")
 def read_pin(name,role):
  path=root.joinpath(*name.split("/"));parent=pathlib.PureWindowsPath(path.anchor)
  for component in path.parts[1:-1]:
   parent=parent/component;acquire(parent,True,"directory")
  h,row=acquire(path,False,role);pin=manifest[name]
  need(row["bytes"]==pin["bytes"],"WRITER_PIN_SIZE")
  b=api.read(h,pin["bytes"]+1,tick)
  need(len(b)==pin["bytes"] and sha(b)==pin["sha256"],"WRITER_PIN_HASH")
  return h,b
 try:
  # Holding every ancestor denies replacement/delete throughout the transaction.
  acquire(pathlib.PureWindowsPath(root.anchor),True,"directory")
  _,template=read_pin("Configurations/unix-Makefile.tmpl","input")
  _,configure=read_pin("Configure","input")
  output,before=read_pin("Makefile","output")
  proposed,plan_report=plan(before);need(len(proposed)<=MAX,"WRITER_OUTPUT_BOUND")
  verify()
  report={"state":"DISABLED_WRITE_PLAN","inputSHA256":sha(before),"outputSHA256":sha(proposed),"bytes":len(proposed),"cTargets":plan_report["cTargets"],"productionEnabled":False,"fileWritten":False}
  if apply:
   changed=True;api.write(output,proposed,tick);verify(True)
   need(api.info(output)["bytes"]==len(proposed),"WRITER_OUTPUT_SIZE")
   actual=api.read(output,len(proposed)+1,tick)
   need(actual==proposed,"WRITER_READBACK")
   verify(True);report.update(state="FIXTURE_WRITE_VERIFIED",fileWritten=True)
 except BaseException as e:
  failure=e
 finally:
  cleanup=[]
  for h in reversed(held):
   try:
    if not api.close(h):cleanup.append("HANDLE_CLOSE_FAILED")
   except BaseException:cleanup.append("HANDLE_CLOSE_EXCEPTION")
  if cleanup:
   code=failure.code if isinstance(failure,Stop) else "WRITER_PRIMARY_OS_ERROR" if isinstance(failure,OSError) else "WRITER_FAILURE" if failure else "WRITER_CLEANUP_FAILED"
   raise Stop(code,cleanup) from None
 if failure:raise failure
 return report


import re
def hook_contract(env,*,configure_succeeded,android,configure_identity_held):
 required=("VIBETRAM_OPENSSL_CARGO_BRIDGE","VIBETRAM_OPENSSL_WORK","VIBETRAM_OPENSSL_CONFIGURE_SHA")
 assert all(isinstance(env.get(k),str) and env[k] for k in required),"HOOK_ENV_MISSING"
 assert env[required[0]]=="1" and re.fullmatch("[a-f0-9]{64}",env[required[2]]),"HOOK_ENV_PIN"
 assert configure_succeeded is True and android is True and configure_identity_held is True,"HOOK_SCOPE"
 assert env.get("VIBETRAM_OPENSSL_DIRECT_OUTPUT_MODE")=="plan","HOOK_APPLY_UNQUALIFIED"
 return {"stage":"AFTER_SUCCESSFUL_PINNED_CONFIGURE_BEFORE_MAKE","activation":"DISABLED_PLAN_ONLY","environmentInheritedByParent":False,"livePerlQualified":False,"writerProductionEnabled":False,"requiredFutureQualification":["PINNED_PERL_END_EXIT_STATUS","NATIVE_LIST_ARGV_TRANSPORT","PINNED_PYTHON_HELPER_IMAGE","ACTUAL_GENERATED_MAKEFILE_GRAMMAR","HELD_INPUT_MANIFEST_HANDOFF"]}


import hashlib,json,pathlib,re
MAX=8388608
def model_need(ok,code):
 if not ok:raise AssertionError(code)
def safe_posix(value):
 model_need(isinstance(value,str) and value.startswith("/") and not value.startswith("//") and len(value)<=4096 and re.fullmatch(r"/[A-Za-z0-9_./+ -]+",value),"MODEL_PATH")
 model_need(str(pathlib.PurePosixPath(value))==value and all(x not in (".","..") for x in value.split("/")),"MODEL_PATH")
 return value
def arm(program,mode,root,cwd,argv,pin,configure):
 if not isinstance(program,str) or re.split(r"[/\\]",program)[-1]!="Configure":return None
 if mode=="":return None
 model_need(mode=="observe","MODEL_APPLY_DISABLED")
 root=safe_posix(root);cwd=safe_posix(cwd)
 model_need(cwd.lower().startswith(root.lower()+"/"),"MODEL_SCOPE")
 model_need(type(argv) is list and len(argv)<=128 and all(isinstance(x,str) and len(x)<=4096 for x in argv),"MODEL_ARGV")
 model_need(argv.count("linux-aarch64")==1,"MODEL_TARGET")
 prefixes=[v[9:] for v in argv if v.startswith("--prefix=")]
 model_need(len(prefixes)==1,"MODEL_PREFIX")
 prefix=safe_posix(prefixes[0]);model_need(re.fullmatch(r"/[A-Za-z0-9_./+-]+",prefix),"MODEL_PREFIX");model_need(prefix.lower().startswith(root.lower()+"/"),"MODEL_SCOPE")
 relative=prefix[len(root)+1:]
 model_need(relative=="install" or re.fullmatch("target/aarch64-linux-android/ci-test/build/openssl-sys-[a-f0-9]{1,64}/out/openssl-build/install",relative),"MODEL_PREFIX")
 model_need(isinstance(pin,str) and re.fullmatch("[a-f0-9]{64}",pin),"MODEL_PIN")
 model_need(isinstance(configure,bytes) and 0<len(configure)<=1048576 and hashlib.sha256(configure).hexdigest()==pin,"MODEL_PIN")
 return {"cwd":cwd,"pin":pin}
def finish(ctx,status,cwd,reader):
 model_need(type(status) is int and 0<=status<=255,"MODEL_EXIT")
 if ctx is None or status!=0:return {"exit":status,"read":False,"report":None}
 try:
  model_need(cwd==ctx["cwd"],"MODEL_CWD_CHANGED")
  configure=reader("Configure",1048576)
  model_need(isinstance(configure,bytes) and 0<len(configure)<=1048576 and hashlib.sha256(configure).hexdigest()==ctx["pin"],"MODEL_PIN")
  make=reader("Makefile",MAX);model_need(isinstance(make,bytes) and 0<len(make)<=MAX,"MODEL_MAKEFILE_BOUND")
  row={"state":"OBSERVE_ONLY_NO_WRITE_AUTHORITY","configureSHA256":ctx["pin"],"makefileSHA256":hashlib.sha256(make).hexdigest(),"makefileBytes":len(make),"windowsHeldIdentityQualified":False,"productionEnabled":False}
  model_need(len(json.dumps(row,separators=(",",":")).encode())<=1024,"MODEL_REPORT_BOUND")
  return {"exit":0,"read":True,"report":row}
 except BaseException:
  return {"exit":90,"read":True,"report":None,"failureCode":"OBSERVATION_FAILED"}
def inspect_source(source):
 model_need(isinstance(source,str) and len(source)<=8192,"SOURCE_BOUND")
 model_need(source.count("END {")==1 and 'my $saved=$?;' in source and '$?=$saved;' in source and '$armed && $saved==0' in source,"SOURCE_EXIT")
 model_need('unless $mode eq "observe"' in source and "OBSERVE_APPLY_DISABLED" in source,"SOURCE_MODE")
 model_need("OBSERVE_ONLY_NO_WRITE_AUTHORITY" in source and "windowsHeldIdentityQualified=>JSON::PP::false" in source,"SOURCE_AUTHORITY")
 model_need(not re.search(r"\b(?:system|exec|unlink|rename|mkdir|qx)\b|\x60|open[^;\n]*[\x22\x27][>+]",source),"SOURCE_SIDE_EFFECT")
 model_need('bounded_hash("./Makefile",8388608)' in source and 'length($line)>1024' in source,"SOURCE_BOUNDS")
 return {"state":"STATIC_REVIEW_ONLY","perlExecuted":False,"perlSyntaxQualified":False,"writeAuthority":False}

OBSERVER_SOURCE='package Vibetram::DirectOutputObserve;\nuse strict;\nuse warnings;\nuse Cwd ();\nuse Digest::SHA ();\nuse JSON::PP ();\nmy ($armed,$cwd,$pin);\nsub bounded_hash {\n my ($name,$limit)=@_;\n my @before=lstat($name);die "OBSERVE_INPUT" unless @before && -f _ && !-l _ && $before[7]>0 && $before[7]<=$limit;\n open my $f,"<",$name or die "OBSERVE_OPEN";binmode($f) or die "OBSERVE_BINARY";\n my @opened=stat($f);die "OBSERVE_OPEN_CHANGED" unless @opened && join(":",@before[0,1,2,7,9,10]) eq join(":",@opened[0,1,2,7,9,10]);\n my $hash=Digest::SHA->new(256);my $total=0;\n while (1) {\n  my $n=read($f,my $bytes,65536);die "OBSERVE_READ" unless defined($n);\n  last if $n==0;$total+=$n;die "OBSERVE_BOUND" if $total>$limit;$hash->add($bytes);\n }\n my @after=stat($f);close($f) or die "OBSERVE_CLOSE";\n my @path=lstat($name);\n die "OBSERVE_CHANGED" unless @after && @path && $total==$before[7] && join(":",@before[0,1,2,7,9,10]) eq join(":",@after[0,1,2,7,9,10]) && join(":",@before[0,1,2,7,9,10]) eq join(":",@path[0,1,2,7,9,10]);\n return ($hash->hexdigest,$total);\n}\nsub import {\n return unless $0 =~ m{(?:^|[/\\\\])Configure$};\n my $mode=$ENV{VIBETRAM_OPENSSL_DIRECT_OUTPUT_MODE}//"";\n return if $mode eq "";\n die "OBSERVE_APPLY_DISABLED" unless $mode eq "observe";\n die "OBSERVE_BRIDGE" unless ($ENV{VIBETRAM_OPENSSL_CARGO_BRIDGE}//"") eq "1";\n my $root=$ENV{VIBETRAM_OPENSSL_WORK};$pin=$ENV{VIBETRAM_OPENSSL_CONFIGURE_SHA};\n die "OBSERVE_PIN" unless defined($root) && defined($pin) && $pin =~ /^[a-f0-9]{64}$/;\n $root=Cygwin::win_to_posix_path($root,1);$root=~s{/$}{};\n $cwd=Cwd::getcwd();die "OBSERVE_PATH_BOUND" if length($root)>4096 || length($cwd)>4096;\n die "OBSERVE_SCOPE" unless index(lc($cwd),lc($root)."/")==0;\n die "OBSERVE_ARGV_BOUND" if @ARGV>128 || grep {length($_)>4096} @ARGV;\n die "OBSERVE_TARGET" unless scalar(grep {$_ eq "linux-aarch64"} @ARGV)==1;\n my @prefix=grep {/^--prefix=/} @ARGV;die "OBSERVE_PREFIX" unless @prefix==1;\n my $value=substr($prefix[0],9);die "OBSERVE_PREFIX" unless $value =~ m{^(?:[A-Za-z]:)?/[A-Za-z0-9_./+-]+$};\n die "OBSERVE_TRAVERSAL" if grep {$_ eq "." || $_ eq ".."} split m{/},$value;\n my $posix=Cygwin::win_to_posix_path($value,1);\n die "OBSERVE_SCOPE" unless index(lc($posix),lc($root)."/")==0;\n my $relative=substr($posix,length($root)+1);\n die "OBSERVE_PREFIX" unless $relative eq "install" || $relative =~ m{^target/aarch64-linux-android/ci-test/build/openssl-sys-[a-f0-9]{1,64}/out/openssl-build/install$};\n my ($sha)=bounded_hash("./Configure",1048576);die "OBSERVE_PIN" unless $sha eq $pin;\n $armed=1;\n}\nEND {\n my $saved=$?;\n if ($armed && $saved==0) {\n  my $ok=eval {\n   die "OBSERVE_CWD_CHANGED" unless Cwd::getcwd() eq $cwd;\n   my ($config)=bounded_hash("./Configure",1048576);die "OBSERVE_PIN" unless $config eq $pin;\n   my ($make,$bytes)=bounded_hash("./Makefile",8388608);\n   my $line=JSON::PP::encode_json({state=>"OBSERVE_ONLY_NO_WRITE_AUTHORITY",configureSHA256=>$config,makefileSHA256=>$make,makefileBytes=>$bytes,windowsHeldIdentityQualified=>JSON::PP::false,productionEnabled=>JSON::PP::false});\n   die "OBSERVE_REPORT_BOUND" if length($line)>1024;\n   print STDERR "VIBETRAM_DIRECT_OUTPUT_OBSERVATION ".$line."\\n" or die "OBSERVE_REPORT_WRITE";\n   1;\n  };\n  if (!$ok) { print STDERR "VIBETRAM_DIRECT_OUTPUT_OBSERVATION_FAILED\\n";$saved=90; }\n }\n $?=$saved;\n}\n1;\n'
CONTROLLER_SOURCE='use strict;use warnings;use Cwd ();use Digest::SHA ();use JSON::PP ();\nmy $start=Cwd::getcwd();my $work=Cygwin::win_to_posix_path($ENV{VIBETRAM_OPENSSL_WORK},1);$work=~s{/$}{};\ndie "CONTROLLER_SCOPE" unless index(lc($start),lc($work)."/")==0;\nmy $cases=$work."/hook-cases";mkdir($cases) or die "CONTROLLER_FRESH";\nmy $base=$ENV{PERL5OPT}//"";die "CONTROLLER_BRIDGE" unless $base eq "-MVibetram::ConfigurePaths";\nmy $output=\'open my $f,">","Makefile" or die "CONTROLLED_OPEN";binmode($f);print $f "CONTROLLED_MAKEFILE\\n";close($f) or die "CONTROLLED_CLOSE";\';\nmy @cases=(["success",$output.\'exit 0;\',0],["exit7",$output.\'exit 7;\',7],["die",\'die "CONTROLLED_DIE\\n";\',undef],["missing",\'exit 0;\',90],["cwd",$output.\'chdir("..") or die "CONTROLLED_CHDIR";exit 0;\',90],["host",$output.\'exit 0;\',undef],["apply",$output.\'exit 0;\',undef]);\nmy @rows;\nfor my $case (@cases) {\n my ($name,$body,$expected)=@$case;my @statuses;\n for my $observed (0,1) {\n  my $dir=$cases."/".$name."-".$observed;mkdir($dir) or die "CONTROLLER_FRESH";chdir($dir) or die "CONTROLLER_CWD";\n  open my $f,">","Configure" or die "CONTROLLER_FILE";binmode($f);print $f $body;close($f) or die "CONTROLLER_CLOSE";\n  {\n   local %ENV=%ENV;$ENV{VIBETRAM_OPENSSL_CONFIGURE_SHA}=Digest::SHA::sha256_hex($body);\n   $ENV{PERL5OPT}=$base.($observed?" -MVibetram::DirectOutputObserve":"");\n   $ENV{VIBETRAM_OPENSSL_DIRECT_OUTPUT_MODE}=$name eq "apply"?"apply":"observe";\n   my $target=$name eq "host"?"VC-WIN64A":"linux-aarch64";\n   my $result=system { $^X } $^X,"./Configure",$target,"--prefix=".$work."/install";\n   die "CONTROLLER_SPAWN" if $result==-1 || ($result&127);push @statuses,($result>>8);\n  }\n }\n if ($name eq "success") {die "CONTROLLER_SUCCESS" unless $statuses[0]==0 && $statuses[1]==0;}\n elsif ($name eq "exit7" || $name eq "die") {die "CONTROLLER_EXIT_PRESERVE" unless $statuses[0]!=0 && $statuses[0]==$statuses[1];}\n else {die "CONTROLLER_REJECT" unless $statuses[0]==0 && $statuses[1]!=0;}\n if (defined($expected) && $name ne "exit7" && $name ne "success") {die "CONTROLLER_EXPECTED" unless $statuses[1]==$expected;}\n push @rows,{case=>$name,baselineExit=>$statuses[0],observedExit=>$statuses[1]};\n}\nchdir($start) or die "CONTROLLER_RESTORE";\nprint JSON::PP::encode_json({state=>"PASS_PINNED_PERL_END_CASES",cases=>\\@rows,compilerExecuted=>JSON::PP::false}),"\\n";\n'
MARKER="[configure-hook-only-191]"

def allowed_entry(event,repo,ref,message):
 return event=="push" and repo=="TroubledPerson/Vibetram" and ref=="refs/heads/main" and isinstance(message,str) and MARKER in message and not any(x in message for x in ("[metadata-image-only-191]","[tool-metadata-only-191]"))
def parse_observation(text):
 prefix="VIBETRAM_DIRECT_OUTPUT_OBSERVATION "
 lines=[line[len(prefix):] for line in text.splitlines() if line.startswith(prefix)]
 need(len(lines)==1 and len(lines[0])<=1024,"OBSERVATION_COUNT_OR_BOUND")
 row=json.loads(lines[0]);need(set(row)=={"state","configureSHA256","makefileSHA256","makefileBytes","windowsHeldIdentityQualified","productionEnabled"},"OBSERVATION_SCHEMA")
 need(row["state"]=="OBSERVE_ONLY_NO_WRITE_AUTHORITY" and row["windowsHeldIdentityQualified"] is False and row["productionEnabled"] is False,"OBSERVATION_AUTHORITY")
 need(all(isinstance(row[k],str) and re.fullmatch("[a-f0-9]{64}",row[k]) for k in ("configureSHA256","makefileSHA256")) and type(row["makefileBytes"]) is int and 0<row["makefileBytes"]<=MAX_BYTES,"OBSERVATION_INPUT")
 return row
def safe_monitor(guard):
 if guard is None:return {"started":False,"zeroOwnedMembers":None}
 report=guard.report();rows=[]
 for command in report["commands"]:
  proof=command.get("ownedJobTeardown") or command.get("teardownDiagnostic") or {}
  rows.append({"stage":command["stage"],"exit":command.get("exit"),"activeMembers":proof.get("activeMembers"),"verified":proof.get("processTreeExitIndependentlyVerified") is True,"completeAccounting":proof.get("completeActiveMemberAccounting") is True})
 need(len(rows)<=128,"HOOK_COMMAND_BOUND")
 return {"started":True,"commands":rows,"zeroOwnedMembers":bool(rows) and all(r["activeMembers"]==0 and r["verified"] and r["completeAccounting"] for r in rows),"censusPending":bool(report["censusPending"]),"censusCleanupFailures":report["censusCleanupFailures"],"censusFailure":report["censusFailureDiagnostic"] is not None,"retainedPeakBytes":report["retainedPeakBytes"],"maximumObservedSupervisionGap":report["maximumObservedSupervisionGap"]}
def run_qualification(guard,env,work,out,src):
 import perl_overlay as po
 original=po.configure_with_runtime;observations=[];cases=[];writes=[]
 def wrapped(active,qualified_env,owned,outputs,source,perl,ndk,tools,cargo_commands=False):
  need(cargo_commands is True and owned==work and outputs==out and source==src,"HOOK_QUALIFICATION_SCOPE")
  module=work/"runtime-overlay/lib/Vibetram/DirectOutputObserve.pm"
  with module.open("x",encoding="ascii",newline="\n") as f:f.write(OBSERVER_SOURCE)
  controller=work/"hook-controller.pl"
  with controller.open("x",encoding="ascii",newline="\n") as f:f.write(CONTROLLER_SOURCE)
  cross=po.cargo_command_environment(active,qualified_env,ndk,tools,perl)
  completed=active.run([perl,controller],cwd=src,env=cross,capture=True,timeout=90)
  result=json.loads(completed.stdout)
  need(set(result)=={"state","cases","compilerExecuted"} and result["state"]=="PASS_PINNED_PERL_END_CASES" and result["compilerExecuted"] is False,"HOOK_CONTROLLER")
  need(len(result["cases"])==7 and {r["case"] for r in result["cases"]}=={"success","exit7","die","missing","cwd","host","apply"},"HOOK_CONTROLLER_CASES")
  for row in result["cases"]:
   need(set(row)=={"case","baselineExit","observedExit"} and all(type(row[k]) is int and 0<=row[k]<=255 for k in ("baselineExit","observedExit")),"HOOK_CONTROLLER_ROW")
  cases.extend(result["cases"])
  class Proxy:
   def __getattr__(self,name):return getattr(active,name)
   def run(self,args,**kwargs):
    argv=[str(x) for x in args]
    actual=len(argv)>1 and argv[0]==str(perl) and "linux-aarch64" in argv
    if actual:
     child=(kwargs.get("env") or qualified_env).copy()
     need(child.get("PERL5OPT")=="-MVibetram::ConfigurePaths","HOOK_BASE_MODULE")
     child.update(PERL5OPT=child["PERL5OPT"]+" -MVibetram::DirectOutputObserve",VIBETRAM_OPENSSL_DIRECT_OUTPUT_MODE="observe")
     kwargs["env"]=child
    completed=active.run(args,**kwargs)
    if actual:observations.append(parse_observation(completed.stderr))
    return completed
  configured=original(Proxy(),qualified_env,work,out,src,perl,ndk,tools,cargo_commands=True)
  need(len(observations)==1,"HOOK_ACTUAL_CONFIGURE_COUNT");observation=observations[0]
  need(observation["configureSHA256"]==qualified_env["VIBETRAM_OPENSSL_CONFIGURE_SHA"] and observation["makefileSHA256"]==configured["files"]["Makefile"]["sha256"],"HOOK_NATIVE_OBSERVATION_MATCH")
  template=po.qualify_openssl_template(src,active._resource_sample)
  need(template["sha256"]==TEMPLATE_SHA256 and template["bytes"]==TEMPLATE_BYTES,"HOOK_TEMPLATE_PIN")
  api=WinAPI();h=None
  try:
   h=api.open(src/"Configure","input");r=api.info(h);key(r,False);configure_bytes=r["bytes"]
  finally:
   if h is not None:need(api.close(h),"HOOK_CONFIGURE_CLOSE")
  manifest={"Configure":{"bytes":configure_bytes,"sha256":observation["configureSHA256"]},"Makefile":{"bytes":observation["makefileBytes"],"sha256":observation["makefileSHA256"]},"Configurations/unix-Makefile.tmpl":{"bytes":TEMPLATE_BYTES,"sha256":TEMPLATE_SHA256}}
  written=transaction(WinAPI(),str(src),manifest,fixture=True,apply=True,resource=active._resource_sample)
  need(written["fileWritten"] and written["productionEnabled"] is False,"HOOK_DIAGNOSTIC_WRITE")
  writes.append(written)
  return configured
 po.configure_with_runtime=wrapped
 try:
  _,_,runtime=po.qualify_prepared_runtime(guard,env,work,out,src,configure=True,cargo_commands=True)
 finally:po.configure_with_runtime=original
 need(len(cases)==7 and len(writes)==1 and len(observations)==1,"HOOK_QUALIFICATION_INCOMPLETE")
 return {"state":"PASS_CONFIGURE_ONLY_HOOK_AND_GENERATED_FILE","controlledCases":cases,"actualConfigureObservation":observations[0],"generatedMakefileQualification":writes[0],"pinnedPerlSHA256":po.GIT_PERL_SHA,"templateSHA256":TEMPLATE_SHA256,"productionEnabled":False,"CargoHookWriterActivated":False,"objectCompilationRequested":False,"APKCreated":False,"signed":False,"release":False}
def seal_report(report,monitor):
 report=dict(report);report["monitor"]=monitor
 verified=isinstance(monitor,dict) and monitor.get("started") is True and monitor.get("zeroOwnedMembers") is True and monitor.get("censusPending") is False and not monitor.get("censusCleanupFailures") and monitor.get("censusFailure") is False
 if not verified:
  report["state"]="FAILED"
  report.setdefault("code","HOOK_FINAL_SUPERVISION")
 return report
def main():
 import os,sys,shutil,contextlib
 from check_source import source_check
 from openssl_probe import ROOT,PREFIX,probe_layout,probe_environment
 from build_guard import Guard,MIN_FREE,MAX_OUTPUT
 need(os.name=="nt","HOOK_WINDOWS_ONLY")
 event=json.loads(pathlib.Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
 need(allowed_entry(os.environ["GITHUB_EVENT_NAME"],os.environ["GITHUB_REPOSITORY"],os.environ["GITHUB_REF"],event.get("head_commit",{}).get("message")),"HOOK_ENTRY")
 source_check(ROOT);work,out,cargo,rustup=probe_layout(ROOT)
 need(not any(p.exists() for p in (work,out,cargo,rustup)),"HOOK_FRESH_OUTPUTS")
 need(shutil.disk_usage(ROOT).free>=MIN_FREE+MAX_OUTPUT,"HOOK_INITIAL_HEADROOM")
 for p in (work,out,cargo,rustup):p.mkdir()
 for name in ("tmp","home","profile","profile/AppData/Local","profile/AppData/Roaming"):(work/name).mkdir(parents=True,exist_ok=True)
 report_path=out/"configure-hook-summary.json"
 with report_path.open("x+b",buffering=0) as receipt:
  receipt.write(b" "*16384);os.fsync(receipt.fileno());receipt_id=os.fstat(receipt.fileno());root_id=out.lstat()
  guard=None;failure=None;report={"state":"FAILED","productionEnabled":False,"objectCompilationRequested":False,"APKCreated":False,"signed":False,"release":False}
  class Discard:
   def __init__(self):self.bytes=0
   def write(self,text):
    self.bytes+=len(text.encode());need(self.bytes<=2097152,"HOOK_INTERNAL_LOG_BOUND");return len(text)
   def flush(self):pass
  try:
   env=probe_environment(work,cargo,rustup);env["VIBETRAM_OPENSSL_CARGO_BRIDGE"]="1";guard=Guard(ROOT,work,out,env)
   deadline=time.monotonic()+540;sample=guard._resource_sample
   def bounded():
    need(time.monotonic()<=deadline,"HOOK_INTERNAL_DEADLINE");sample()
   guard._resource_sample=bounded
   with contextlib.redirect_stdout(Discard()):
    guard.run([sys.executable,"-B",ROOT/"ci/openssl_probe.py","--materialize",work],env=env,timeout=180)
    src=work/"crate"/PREFIX/"openssl"
    before=set(p.relative_to(work).as_posix() for p in work.rglob("*.o"))
    report=run_qualification(guard,env,work,out,src)
    after=set(p.relative_to(work).as_posix() for p in work.rglob("*.o"))
    need(after==before,"HOOK_UNEXPECTED_OBJECT")
    guard.check()
   monitor=safe_monitor(guard);need(monitor["zeroOwnedMembers"] and not monitor["censusPending"] and not monitor["censusCleanupFailures"] and not monitor["censusFailure"],"HOOK_FINAL_SUPERVISION")
  except BaseException as e:
   failure=e;report={"state":"FAILED","errorClass":type(e).__name__,"errno":getattr(e,"errno",None),"winerror":getattr(e,"winerror",None),"code":e.args[0] if e.args and isinstance(e.args[0],str) and re.fullmatch("[A-Z_0-9]{1,80}",e.args[0]) else None,"productionEnabled":False,"objectCompilationRequested":False,"APKCreated":False,"signed":False,"release":False}
  finally:
   try:report=seal_report(report,safe_monitor(guard))
   except BaseException:report=seal_report(report,{"zeroOwnedMembers":None,"diagnosticFailure":True})
   if report["state"]=="FAILED" and failure is None:failure=Stop("HOOK_FINAL_SUPERVISION")
   need((out.lstat().st_dev,out.lstat().st_ino)==(root_id.st_dev,root_id.st_ino) and not out.lstat().st_file_attributes&0x400,"HOOK_REPORT_ROOT")
   st=os.fstat(receipt.fileno());need((st.st_dev,st.st_ino,st.st_size)==(receipt_id.st_dev,receipt_id.st_ino,16384),"HOOK_RECEIPT_IDENTITY")
   b=(json.dumps(report,sort_keys=True,separators=(",",":"))+"\n").encode();need(len(b)<=16384,"HOOK_REPORT_BOUND")
   receipt.seek(0);need(receipt.write(b+b" "*(16384-len(b)))==16384,"HOOK_RECEIPT_WRITE");os.fsync(receipt.fileno())
  print(json.dumps({"state":report["state"],"objectCompilationRequested":False,"APKCreated":False,"productionEnabled":False,"zeroOwnedMembers":report.get("monitor",{}).get("zeroOwnedMembers")}),flush=True)
  if failure:raise Stop("CONFIGURE_HOOK_QUALIFICATION_FAILED") from None
if __name__=="__main__":main()
