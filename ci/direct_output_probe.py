"""Isolated four-object direct-output qualification; never a full build."""
import hashlib,json,pathlib,shlex,struct,sys,tarfile,re
C_TARGET="crypto/libcrypto-lib-ctype.o"
ASM_TARGET="crypto/aes/libcrypto-lib-aes-sha1-armv8.o"
FLAG="-fno-temp-file"
OBJECT_LIMIT=2*1024**2

def make_command(make,target,fields,arm,dryrun):
 from perl_overlay import _recipe_word
 assert arm in ("baseline","candidate") and type(dryrun) is bool,"DIRECT_ARM"
 assert target in (C_TARGET,ASM_TARGET),"DIRECT_TARGET"
 argv=[make,"-f","Makefile"]
 if dryrun:argv.append("--dry-run")
 argv+=["-j1",target]
 if arm=="candidate" and target==C_TARGET:
  value=fields.get("CFLAGS")
  assert isinstance(value,str) and 0<len(value)<=8192 and not any(x in value for x in ("\n","\r","\x00","$",chr(96))),"DIRECT_CFLAGS"
  words=shlex.split(value);assert 0<len(words)<=64 and all(_recipe_word(x) for x in words),"DIRECT_CFLAGS"
  assert not any(x in words for x in (FLAG,"-Xclang","-o","-c")),"DIRECT_FLAG_ALREADY_PRESENT"
  argv.append("CFLAGS="+value+" "+FLAG)
 return argv

def arm_scope(work,out,src,arm):
 from openssl_probe import ROOT,PREFIX
 assert arm in ("baseline","candidate"),"DIRECT_ARM"
 assert work==ROOT/"openssl-probe-work" and out==ROOT/"openssl-probe-output","DIRECT_ROOT"
 base=work if arm=="baseline" else work/"candidate"
 assert src==base/"crate"/PREFIX/"openssl","DIRECT_SOURCE_SCOPE"
 return out/arm

def elf_signature(data):
 assert isinstance(data,bytes) and 64<=len(data)<=OBJECT_LIMIT,"DIRECT_ELF_BOUND"
 assert data[:7]==b"\x7fELF\x02\x01\x01","DIRECT_ELF_CLASS"
 assert struct.unpack_from("<HHI",data,16)==(1,183,1) and struct.unpack_from("<HHH",data,52)==(64,0,0) and struct.unpack_from("<Q",data,32)[0]==0,"DIRECT_ELF_TARGET"
 shoff=struct.unpack_from("<Q",data,40)[0]
 entsize,count,namesindex=struct.unpack_from("<HHH",data,58)
 assert entsize==64 and 0<count<=1024 and 0<namesindex<count and 64<=shoff and shoff+count*64<=len(data),"DIRECT_ELF_TABLE"
 rows=[struct.unpack_from("<IIQQQQIIQQ",data,shoff+i*64) for i in range(count)]
 def payload(row):
  size=row[5];offset=row[4];assert size<=OBJECT_LIMIT,"DIRECT_ELF_SECTION_SIZE"
  if row[1]==8:return None
  assert offset<=len(data) and offset+size<=len(data),"DIRECT_ELF_SECTION_BOUNDS"
  return data[offset:offset+size]
 assert rows[namesindex][1]==3,"DIRECT_ELF_NAMES"
 namesdata=payload(rows[namesindex])
 def string(table,offset):
  assert 0<=offset<len(table),"DIRECT_ELF_STRING"
  end=table.find(b"\0",offset,min(len(table),offset+257));assert 0<=end-offset<=256,"DIRECT_ELF_STRING"
  text=table[offset:end].decode("utf-8")
  assert not any(ord(x)<32 or ord(x)>126 for x in text),"DIRECT_ELF_STRING"
  return text
 names=[string(namesdata,r[0]) for r in rows]
 assert names[0]=="" and len(names)==len(set(names)),"DIRECT_ELF_DUPLICATE_NAMES"
 def label(index):
  if index in (0,0xfff1,0xfff2):return ("special",index)
  assert 0<index<count,"DIRECT_ELF_SYMBOL_SECTION"
  return ("section",names[index])
 symbols={};symbol_count=0
 for index,row in enumerate(rows):
  payload(row)
  if row[1]!=2:continue
  assert row[9]==24 and row[5]%24==0 and 0<row[6]<count and rows[row[6]][1]==3,"DIRECT_ELF_SYMBOL_TABLE"
  assert symbol_count+row[5]//24<=4096,"DIRECT_ELF_SYMBOL_BOUND"
  table=payload(rows[row[6]]);items=[]
  for offset in range(0,row[5],24):
   name,info,other,section,value,size=struct.unpack_from("<IBBHQQ",data,row[4]+offset)
   items.append((string(table,name),info,other,label(section),value,size))
  symbols[index]=items;symbol_count+=len(items)
 assert len(symbols)==1,"DIRECT_ELF_SYMBOL_COUNT"
 def debug(name):return name.startswith((".debug",".zdebug",".rel.debug",".rela.debug"))
 sections=[];relocations=[];retained=0;relocation_count=0
 for index,row in enumerate(rows):
  if index==0 or row[1] in (2,3) or debug(names[index]):continue
  retained+=1
  if row[1] in (4,9):
   size=24 if row[1]==4 else 16
   assert row[9]==size and row[5]%size==0 and row[6] in symbols and 0<row[7]<count,"DIRECT_ELF_RELOC_TABLE"
   relocation_count+=row[5]//size;assert relocation_count<=8192,"DIRECT_ELF_RELOC_BOUND"
   entries=[]
   for off in range(0,row[5],size):
    offset,info=struct.unpack_from("<QQ",data,row[4]+off);symbol=info>>32;kind=info&0xffffffff
    assert symbol<len(symbols[row[6]]) and offset<rows[row[7]][5],"DIRECT_ELF_RELOC"
    addend=struct.unpack_from("<q",data,row[4]+off+16)[0] if size==24 else None
    entries.append((offset,kind,symbols[row[6]][symbol],addend))
   relocations.append((names[index],row[1],row[2],row[8],names[row[7]],sorted(entries)))
  else:
   body=payload(row);digest=hashlib.sha256(body).hexdigest() if body is not None else None
   assert row[6]<count,"DIRECT_ELF_SECTION_LINK"
   sections.append((names[index],row[1],row[2],row[3],row[5],names[row[6]],row[7],row[8],row[9],digest))
 normalized={"flags":struct.unpack_from("<I",data,48)[0],"ident":data[:16].hex(),"sections":sorted(sections),"symbols":sorted(next(iter(symbols.values()))),"relocations":sorted(relocations)}
 digest=hashlib.sha256(json.dumps(normalized,sort_keys=True,separators=(",",":")).encode()).hexdigest()
 return {"sha256":digest,"sections":retained,"symbols":symbol_count,"relocations":sum(len(x[5]) for x in relocations),"debugCompared":False}

def read_object(path,expected):
 from perl_overlay import smoke_artifact_identity
 before=smoke_artifact_identity(path);assert before==expected and 64<=before["bytes"]<=OBJECT_LIMIT,"DIRECT_OBJECT_IDENTITY"
 data=path.read_bytes()
 assert len(data)==before["bytes"] and hashlib.sha256(data).hexdigest()==before["sha256"] and smoke_artifact_identity(path)==before,"DIRECT_OBJECT_CHANGED"
 return data

def compare_pair(baseline,candidate,left,right):
 assert baseline["target"]==candidate["target"] and baseline["source"]==candidate["source"],"DIRECT_PAIR_SCOPE"
 assert baseline["sourceIdentity"]["sha256"]==candidate["sourceIdentity"]["sha256"],"DIRECT_SOURCE_CHANGED"
 a=baseline["compilerArgv"];b=candidate["compilerArgv"]
 if baseline["target"]==C_TARGET:
  assert FLAG not in a and b.count(FLAG)==1 and [x for x in b if x!=FLAG]==a,"DIRECT_C_ROLE"
 else:assert a==b and FLAG not in a,"DIRECT_ASSEMBLY_ROLE"
 ls=elf_signature(left);rs=elf_signature(right);assert ls==rs,"DIRECT_OBJECT_SEMANTICS_CHANGED"
 return {"target":baseline["target"],"baselineSHA256":hashlib.sha256(left).hexdigest(),"candidateSHA256":hashlib.sha256(right).hexdigest(),"semanticSHA256":ls["sha256"],"sections":ls["sections"],"symbols":ls["symbols"],"relocations":ls["relocations"],"debugCompared":False}

def materialize_candidate(work):
 from openssl_probe import ROOT,PREFIX,CHECKSUM,validate_members,sha,regular_chain
 assert work==ROOT/"openssl-probe-work","DIRECT_ROOT"
 destination=work/"candidate";archive=work/"openssl-src.crate"
 regular_chain(work);regular_chain(archive)
 assert destination.is_dir() and not any(destination.iterdir()),"DIRECT_PRESERVE_CANDIDATE"
 assert sha(archive)==CHECKSUM,"DIRECT_ARCHIVE"
 with tarfile.open(archive,"r:gz") as tar:
  members=tar.getmembers();validate_members(members)
  for member in members:
   path=destination/"crate"/member.name
   if member.isdir():path.mkdir(parents=True,exist_ok=True)
   else:
    path.parent.mkdir(parents=True,exist_ok=True)
    with tar.extractfile(member) as source,path.open("xb") as target:
     import shutil
     shutil.copyfileobj(source,target,65536)
 assert sha(archive)==CHECKSUM and (destination/"crate"/PREFIX/"openssl/Configure").is_file(),"DIRECT_ARCHIVE_CHANGED"

def _put(out,name,row):
 assert name in ("direct-output-qualification.json","direct-output-failure.json"),"DIRECT_RECEIPT_SCOPE"
 data=(json.dumps(row,indent=2)+"\n").encode();assert len(data)<=65536,"DIRECT_RECEIPT_BOUND"
 with (out/name).open("xb") as f:f.write(data)

def qualify_four_objects(guard,env,work,out,src,perl,configuration):
 from openssl_probe import ROOT,PREFIX,CHECKSUM,with_physical_ndk_inputs,sha
 from perl_overlay import qualify_cargo_objects,configure_with_runtime
 from ndk_input_metadata import capture_one
 stage="BASELINE"
 try:
  baseout=arm_scope(work,out,src,"baseline");baseout.mkdir()
  baseline=qualify_cargo_objects(guard,env,work,baseout,src,perl,configuration,direct_output_arm="baseline")
  stage="EXTRACTION";candidatework=work/"candidate";candidatework.mkdir()
  guard.run([sys.executable,"-B",ROOT/"ci/direct_output_probe.py","--materialize-candidate",work],env=env,timeout=180)
  candidatesrc=candidatework/"crate"/PREFIX/"openssl"
  candidateout=arm_scope(work,out,candidatesrc,"candidate");candidateout.mkdir()
  assert sha(candidatesrc/"Configure")==sha(src/"Configure"),"DIRECT_CONFIGURE_SOURCE"
  helpers={name:sha(work/name) for name in ("configure-tool-lookup.pl","generated-helper-checks.pl")}
  stage="CONFIGURE";candidate_configuration={}
  def configure(ndk,tools):
   candidate_configuration.update(configure_with_runtime(guard,env,work,candidateout,candidatesrc,perl,ndk,tools,cargo_commands=True))
  lease=capture_one(perl.parent,perl,callback=lambda:with_physical_ndk_inputs(guard,env,candidateout,configure))
  assert lease["qualified"] and lease.get("callbackSucceeded"),"DIRECT_CONFIGURE_LEASE"
  assert all(sha(work/name)==digest for name,digest in helpers.items()),"DIRECT_HELPER_CHANGED"
  stage="CANDIDATE"
  candidate=qualify_cargo_objects(guard,env,work,candidateout,candidatesrc,perl,candidate_configuration,direct_output_arm="candidate")
  stage="COMPARISON"
  assert len(baseline["objects"])==len(candidate["objects"])==2,"DIRECT_FOUR_OBJECT_COUNT"
  pairs=[]
  for left,right in zip(baseline["objects"],candidate["objects"]):
   guard._resource_sample()
   pairs.append(compare_pair(left,right,read_object(src/left["target"],left["object"]),read_object(candidatesrc/right["target"],right["object"])))
  assert [x["target"] for x in pairs]==[C_TARGET,ASM_TARGET],"DIRECT_PAIR_ORDER"
  guard._resource_sample()
  report={"state":"PASS_FOUR_OBJECT_DIRECT_OUTPUT_QUALIFICATION","pairs":pairs,"maximumObjects":4,"makeWorkers":1,"archiveSHA256":CHECKSUM,"flag":FLAG,"flagCOnly":True,"freshSourceTrees":True,"failedOutputsReused":False,"fullAndroidBuild":False,"rustProvisioning":False,"signed":False,"releasable":False,"monitor":{"commandCount":guard.count,"peakBytes":guard.peak,"sampledNotQuota":True}}
  _put(out,"direct-output-qualification.json",report);return report
 except BaseException as error:
  code=error.args[0] if error.args and isinstance(error.args[0],str) and re.fullmatch(r"[A-Z_0-9]{1,80}",error.args[0]) else "DIRECT_OUTPUT_FAILURE"
  failure={"state":"FATAL_NO_RETRY","stage":stage,"errorClass":type(error).__name__[:64],"code":code,"errno":getattr(error,"errno",None) if type(getattr(error,"errno",None)) is int else None,"winerror":getattr(error,"winerror",None) if type(getattr(error,"winerror",None)) is int else None,"partialAccepted":False}
  try:_put(out,"direct-output-failure.json",failure)
  except BaseException as report_error:error.add_note("DIRECT_FAILURE_RECEIPT_FAILED:"+type(report_error).__name__)
  raise

if __name__=="__main__":
 assert len(sys.argv)==3 and sys.argv[1]=="--materialize-candidate","DIRECT_ENTRY_SCOPE"
 materialize_candidate(pathlib.Path(sys.argv[2]))
