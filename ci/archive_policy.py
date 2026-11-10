"""Android Cargo owns ar operations; pinned OpenSSL Configure owns its mode."""
import pathlib,hashlib,struct

def cargo_environment(env):
 assert pathlib.Path(env['CARGO_TARGET_AARCH64_LINUX_ANDROID_LINKER']).name.lower()=='clang.exe' and env.get('AR_aarch64_linux_android')=='llvm-ar.exe','ANDROID_CARGO_ARCHIVER_SCOPE'
 assert env.get('ARFLAGS')=='crs','EXPECTED_OPENSSL_OPERATION_ONLY'
 # cc-rs 1.2.55 concatenates generic, TARGET and target-specific envflags.
 for key in ('TARGET_ARFLAGS','ARFLAGS_aarch64_linux_android','ARFLAGS_aarch64-linux-android'):
  assert env.get(key) in (None,''),'UNQUALIFIED_ADDITIONAL_ANDROID_ARFLAGS'
 result=env.copy();del result['ARFLAGS'];result['VIBETRAM_OPENSSL_ARFLAGS']='crs';return result

def cc_argv(tool,operation,archive,objects=()):
 archive=pathlib.Path(archive);assert archive.is_absolute() and '..' not in archive.parts and archive.suffix=='.a','CARGO_ARCHIVE_PATH'
 assert operation in ('cq','s','t'),'SINGLE_CALLER_ARCHIVE_OPERATION'
 assert (operation=='cq' and len(objects)==1) or (operation in ('s','t') and not objects),'CARGO_ARCHIVE_ARGUMENT_SCOPE'
 for obj in objects:assert pathlib.Path(obj).is_absolute() and pathlib.Path(obj).suffix=='.o','CARGO_OBJECT_PATH'
 return [tool,operation,archive,*objects]

def indexed_archive(data,obj,expected_symbol):
 assert data.startswith(b'!<arch>\n') and len(data)<=8*1024**2,'ARCHIVE_MAGIC_OR_BOUND';at=8;members={};index=None
 while at<len(data):
  assert at+60<=len(data) and data[at+58:at+60]==b'`\n','ARCHIVE_HEADER';name=data[at:at+16].decode('ascii').rstrip();size=int(data[at+48:at+58]);start=at+60;end=start+size;assert size>=0 and end<=len(data),'ARCHIVE_MEMBER_BOUND';body=data[start:end]
  if name=='/':assert index is None;index=body
  elif name=='//':pass
  else:assert name.rstrip('/')=='probe object.o','ARCHIVE_EXPECTED_MEMBER';members[at]=body
  at=end+(size%2)
 assert at==len(data) and len(members)==1 and index is not None and len(index)>=4,'ARCHIVE_INDEX_REQUIRED';count=struct.unpack_from('>I',index)[0];assert 0<count<=128 and 4+count*4<=len(index),'ARCHIVE_INDEX_COUNT';offsets=struct.unpack_from('>'+'I'*count,index,4);names=index[4+count*4:].split(b'\0');assert names[-1]==b'' and len(names)==count+1,'ARCHIVE_INDEX_NAMES';assert expected_symbol.encode() in names and all(x in members for x in offsets),'ARCHIVE_SYMBOL_TARGET'
 assert next(iter(members.values()))==obj,'ARCHIVE_OBJECT_IDENTITY';return {'objectSHA256':hashlib.sha256(obj).hexdigest(),'archiveSHA256':hashlib.sha256(data).hexdigest(),'symbolCount':count,'indexVerified':True}

def qualify(guard,cross,tools,smoke):
 env=cargo_environment(cross);tool=tools/'llvm-ar.exe';obj=smoke/'probe object.o';archive=smoke/'cc archive.a';before=obj.read_bytes();assert not archive.exists()
 guard.run(cc_argv(tool,'cq',archive,[obj]),env=env,capture=True,timeout=30);guard.run(cc_argv(tool,'s',archive),env=env,capture=True,timeout=30);listed=guard.run(cc_argv(tool,'t',archive),env=env,capture=True,timeout=30).stdout.splitlines();assert listed==['probe object.o'],'CC_ARCHIVE_MEMBER_LIST'
 result=indexed_archive(archive.read_bytes(),before,'vibetram_offline_link_probe');assert obj.read_bytes()==before,'CC_ARCHIVE_INPUT_CHANGED';return {'state':'PASS_CC_RS_ANDROID_ARCHIVE_OPERATIONS',**result,'genericCargoARFLAGSAbsent':'ARFLAGS' not in env,'openSSLConfigureOperationPreserved':env['VIBETRAM_OPENSSL_ARFLAGS']=='crs'}
