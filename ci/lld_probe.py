"""Isolated LLD compatibility diagnostic. No production compiler policy changes."""
import pathlib,hashlib,json,struct,os,shutil,time
LLD_SHA='3cf499fc8a03853722d19e3ae1c5cdd143ac7426f1405b9e6efacd7a94b7328a'
LLD_SIZE=113349120
MARKER='[lld-qualification-only-191]'

def rust_args(args,work,lld):
 expected=['rustc','--edition','2024','--target','x86_64-pc-windows-msvc','-C']
 assert [str(x) for x in args[:6]]==expected,'DIAGNOSTIC_RUST_ARGUMENT_SCOPE'
 assert len(args)==10 and str(args[6]).startswith('linker=') and pathlib.Path(str(args[6])[7:]).name.lower()=='link.exe','DIAGNOSTIC_ORIGINAL_MSVC_LINKER'
 assert [str(x) for x in args[7:]]==[str(work/'tiny-msvc.rs'),'-o',str(work/'tiny-msvc.exe')],'DIAGNOSTIC_FIXED_FIXTURE'
 return [*args[:6],'linker='+str(lld),'-C','linker-flavor=lld-link','-C','target-feature=+crt-static','-C','link-arg=/STACK:8388608','-C','debuginfo=1',*args[7:]]

def pe_debug(path):
 b=path.read_bytes();assert b[:2]==b'MZ' and len(b)<8*1024**2,'PE_BOUND'
 at=struct.unpack_from('<I',b,60)[0];assert b[at:at+4]==b'PE\0\0' and struct.unpack_from('<H',b,at+4)[0]==0x8664,'PE_X64'
 o=at+24;assert struct.unpack_from('<H',b,o)[0]==0x20b,'PE64'
 assert struct.unpack_from('<Q',b,o+72)[0]==8388608,'STACK_8M'
 flags=struct.unpack_from('<H',b,o+70)[0];assert flags&0x140==0x140,'NX_ASLR'
 sections=struct.unpack_from('<H',b,at+6)[0];st=o+struct.unpack_from('<H',b,at+20)[0]
 def rva(x):
  for i in range(sections):
   vsize,va,rawsize,offset=struct.unpack_from('<IIII',b,st+i*40+8)
   if va<=x<va+max(vsize,rawsize):assert x-va<rawsize;return offset+x-va
  raise AssertionError('RVA_UNMAPPED')
 imports=[];irva,isize=struct.unpack_from('<II',b,o+120)
 if irva:
  pos=rva(irva)
  for _ in range(256):
   row=struct.unpack_from('<IIIII',b,pos);pos+=20
   if not any(row):break
   x=rva(row[3]);end=b.index(b'\0',x,x+256);imports.append(b[x:end].decode('ascii').lower())
  else:raise AssertionError('IMPORT_COUNT')
 assert not any(x.startswith(('vcruntime','msvcp','ucrtbase','api-ms-win-crt')) for x in imports),'DYNAMIC_CRT_IMPORT'
 drva,dsize=struct.unpack_from('<II',b,o+112+6*8);assert drva and dsize and dsize%28==0,'DEBUG_DIRECTORY'
 codeviews=[]
 for x in range(rva(drva),rva(drva)+dsize,28):
  kind,size,addr,ptr=struct.unpack_from('<IIII',b,x+12)
  if kind==2:
   cv=b[ptr:ptr+size];assert cv[:4]==b'RSDS' and len(cv)>=25,'CODEVIEW_RSDS';name=cv[24:].split(b'\0',1)[0].decode('utf8');assert '/' not in name and '\\' not in name and name.endswith('.pdb'),'PDB_BASENAME_PRIVACY';codeviews.append((cv[4:20],struct.unpack_from('<I',cv,20)[0],name))
 assert len(codeviews)==1,'CODEVIEW_COUNT';guid,age,name=codeviews[0];pdb=path.with_name(name);p=pdb.read_bytes();assert len(p)<16*1024**2 and p.startswith(b'Microsoft C/C++ MSF 7.00'),'PDB_MSF7'
 page,free,nblocks,dirbytes,reserved,mapblock=struct.unpack_from('<IIIIII',p,32);assert page in (512,1024,2048,4096,8192) and dirbytes<1024**2 and len(p)==page*nblocks,'PDB_SUPERBLOCK'
 n=(dirbytes+page-1)//page;blocks=struct.unpack_from('<'+'I'*n,p,mapblock*page);directory=b''.join(p[i*page:(i+1)*page] for i in blocks)[:dirbytes];count=struct.unpack_from('<I',directory)[0];assert 2<=count<=4096,'PDB_STREAM_COUNT';sizes=struct.unpack_from('<'+'I'*count,directory,4);cursor=4+4*count;info=None
 for i,size in enumerate(sizes):
  pages=0 if size==0xffffffff else (size+page-1)//page;indexes=struct.unpack_from('<'+'I'*pages,directory,cursor);cursor+=pages*4
  if i==1:info=b''.join(p[j*page:(j+1)*page] for j in indexes)[:size]
 assert info and len(info)>=28 and struct.unpack_from('<I',info,8)[0]==age and info[12:28]==guid,'PDB_GUID_AGE_BINDING'
 return {'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'stackReserve':8388608,'staticCRTImportsVerified':True,'nxAndAslr':True,'pdbBytes':len(p),'pdbSHA256':hashlib.sha256(p).hexdigest(),'pdbGuidAgeBinding':True,'pdbBasenameOnly':True}

def main():
 from check_source import source_check
 from build_guard import Guard,clean_env,android_env,MIN_FREE,MAX_OUTPUT,executable_snapshot
 from msvc_env import qualify_msvc
 from openssl_probe import PHYSICAL_SDK,regular_chain
 from cloud_build import elf_check
 from unittest.mock import patch
 from census_supervisor import OwnedProcess
 import ctypes
 root=pathlib.Path(__file__).resolve().parents[1];event=json.loads(pathlib.Path(os.environ['GITHUB_EVENT_PATH']).read_text());message=event['head_commit']['message']
 assert os.name=='nt' and os.environ['GITHUB_REPOSITORY']=='TroubledPerson/Vibetram' and os.environ['GITHUB_REF']=='refs/heads/main' and os.environ['GITHUB_EVENT_NAME']=='push'
 assert MARKER in message and all(x not in message for x in ('[unsigned-trial-191]','[qualified-rust-vctip-cleanup-191]','[rust-cleanup-qualification-only-191]')),'DIAGNOSTIC_ONLY_GATES'
 source_check(root);work=root/'lld-probe-work';out=root/'lld-probe-output';assert not work.exists() and not out.exists();assert shutil.disk_usage(root).free>=MIN_FREE+MAX_OUTPUT
 work.mkdir();out.mkdir()
 for x in ('tmp','home','profile/AppData/Local','profile/AppData/Roaming'):(work/x).mkdir(parents=True,exist_ok=True)
 env=clean_env(os.environ,work);env['CARGO_NET_OFFLINE']='true';env['CARGO_PROFILE_CI_TEST_DEBUG']='1'
 lld=pathlib.Path(env['RUSTUP_HOME'])/'toolchains/1.95.0-x86_64-pc-windows-msvc/lib/rustlib/x86_64-pc-windows-msvc/bin/rust-lld.exe'
 binding=executable_snapshot(lld);assert binding['sha256']==LLD_SHA and binding['bytes']==LLD_SIZE,'LLD_OFFICIAL_ARCHIVE_IDENTITY'
 observations=[]
 class Observed(OwnedProcess):
  def finish(self,terminate=False,sampler=None,seconds=3):
   if self.teardown is None:
    rows=self.observe()
    for row in rows:
     key=(row['pid'],row['creationFiletime'])
     if any((x['pid'],x['creationFiletime'])==key for x in observations):continue
     try:
      handle=self.process if row['pid']==self.initial['pid'] else self.members_held[row['pid']][0];before=self.api.snapshot(handle);n=self.api.w.DWORD(32768);buf=ctypes.create_unicode_buffer(n.value)
      self.api.k.QueryFullProcessImageNameW.argtypes=[self.api.w.HANDLE,self.api.w.DWORD,self.api.w.LPWSTR,ctypes.POINTER(self.api.w.DWORD)];self.api.k.QueryFullProcessImageNameW.restype=self.api.w.BOOL;self.api.ok(self.api.k.QueryFullProcessImageNameW(handle,0,buf,ctypes.byref(n)))
      path=pathlib.Path(buf.value);identity=executable_snapshot(path,sampler.tick if sampler else None);after=self.api.snapshot(handle);assert (before['pid'],before['creationFiletime'])==(after['pid'],after['creationFiletime'])==key,'HELD_PROCESS_CHANGED'
      observations.append({'pid':key[0],'creationFiletime':key[1],'imageBaseName':path.name,'imageSHA256':identity['sha256'],'imageBytes':identity['bytes'],'imageIdentity':identity['identity'],'heldIdentityVerified':True,'rawPathWithheld':True})
     except BaseException as error:observations.append({'pid':key[0],'creationFiletime':key[1],'metadataFailure':type(error).__name__})
   if not terminate and any('metadataFailure' in x for x in observations):raise AssertionError('OWNED_IMAGE_METADATA_UNQUALIFIED')
   return super().finish(terminate,sampler,seconds)
 class DiagnosticGuard(Guard):
  def run(self,args,*a,**kw):
   if pathlib.Path(str(args[0])).name.lower()=='rustc' and str(work/'tiny-msvc.rs') in [str(x) for x in args]:args=rust_args(args,work,lld)
   return super().run(args,*a,**kw)
 guard=DiagnosticGuard(root,work,out,env);report={'state':'STARTED','fullBuildEnabled':False,'productionForcedRustCleanupEnabled':False,'lld':{'bytes':LLD_SIZE,'sha256':LLD_SHA},'ownedImages':observations,'sampledNotQuota':True}
 try:
  with patch('build_guard.OwnedProcess',Observed):
   env,msvc=qualify_msvc(env,work,guard);assert msvc['qualifiedToolPinsVerified'] and msvc['compiledTinyFixtures']==2,'DIRECT_MSVC_QUALIFICATION'
   assert 'VIBETRAM_QUALIFIED_RUST_VCTIP' not in env;env['CARGO_TARGET_X86_64_PC_WINDOWS_MSVC_LINKER']=str(lld);guard.env=env
   report['tinyWindows']=pe_debug(work/'tiny-msvc.exe');version=guard.run([lld,'-flavor','link','--version'],env=env,capture=True,timeout=30).stdout.strip();assert 'LLD 22.1.2' in version,'LLD_VERSION';report['lld']['version']=version
   fixture=work/'fixture';fixture.mkdir();(fixture/'src').mkdir();(fixture/'macro/src').mkdir(parents=True)
   (fixture/'Cargo.toml').write_text('[package]\nname="lld-routing-fixture"\nversion="0.0.0"\nedition="2024"\nbuild="build.rs"\n[dependencies]\nfixture-macro={path="macro"}\n[lib]\ncrate-type=["cdylib"]\n[profile.dev]\ndebug="limited"\npanic="abort"\n',encoding='utf8')
   (fixture/'macro/Cargo.toml').write_text('[package]\nname="fixture-macro"\nversion="0.0.0"\nedition="2024"\n[lib]\nproc-macro=true\n',encoding='utf8')
   (fixture/'macro/src/lib.rs').write_text('extern crate proc_macro; #[proc_macro] pub fn answer(_:proc_macro::TokenStream)->proc_macro::TokenStream { "42u32".parse().unwrap() }\n',encoding='utf8')
   (fixture/'build.rs').write_text('fn main(){println!("cargo:rustc-env=FIXTURE_READY=yes");}\n',encoding='utf8')
   (fixture/'src/lib.rs').write_text('use fixture_macro::answer; #[unsafe(no_mangle)] pub extern "C" fn fixture_answer()->u32 { let _=env!("FIXTURE_READY");answer!() }\n',encoding='utf8')
   (fixture/'src/main.rs').write_text('fn main(){assert_eq!(lld_routing_fixture::fixture_answer(),42);}\n',encoding='utf8')
   (fixture/'.cargo').mkdir();(fixture/'.cargo/config.toml').write_text('[target.x86_64-pc-windows-msvc]\nrustflags=["-C","target-feature=+crt-static","-C","link-arg=/STACK:8388608"]\n',encoding='utf8')
   host=guard.run(['cargo','build','--offline','--jobs','2','--message-format=json-render-diagnostics'],cwd=fixture,env=env,capture=True,timeout=180)
   report['cargoWindows']=pe_debug(work/'target/debug/lld-routing-fixture.exe')
   ndk=PHYSICAL_SDK/'ndk/30.0.16248370';clang=ndk/'toolchains/llvm/prebuilt/windows-x86_64/bin/clang.exe';regular_chain(clang);cross=android_env(env,ndk);assert pathlib.Path(cross['CARGO_TARGET_AARCH64_LINUX_ANDROID_LINKER'])==clang and cross['CARGO_TARGET_X86_64_PC_WINDOWS_MSVC_LINKER']==str(lld),'LINKER_ROUTING_SEPARATION'
   assert '--target=aarch64-linux-android29' in cross['CARGO_ENCODED_RUSTFLAGS'] and 'max-page-size=16384' in cross['CARGO_ENCODED_RUSTFLAGS'],'ANDROID_FLAGS'
   android=guard.run(['cargo','build','--offline','--jobs','2','--target','aarch64-linux-android','--lib','--message-format=json-render-diagnostics'],cwd=fixture,env=cross,capture=True,timeout=180)
   elf=work/'target/aarch64-linux-android/debug/liblld_routing_fixture.so';data=elf.read_bytes();elf_check(data);report['android']={'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'arm64Api29NdkClang':True,'loadAlignment16384':True}
   for label,text in [('host',host.stdout),('android',android.stdout)]:
    rows=[json.loads(x) for x in text.splitlines() if x.startswith('{')];targets=[x['target'] for x in rows if x.get('reason')=='compiler-artifact'];assert any('custom-build' in x['kind'] for x in targets) and any('proc-macro' in x['kind'] for x in targets),'CARGO_HOST_FIXTURES_NOT_COMPILED';report[label+'CargoHostFixturesCompiled']=True
   assert executable_snapshot(lld,guard._resource_sample)==binding,'LLD_CHANGED_AFTER_QUALIFICATION';source_check(root);report['state']='PASS_ISOLATED_LLD_HOST_ANDROID_COMPATIBILITY'
 except BaseException as error:report.update(state='FAILED_CLOSED',category=str(error)[:160],failureClass=type(error).__name__);raise
 finally:
  from runtime_report import write_runtime_report,read_runtime_report
  report['oneRunDoesNotProveReliableShutdown']=True;monitor=guard.report()
  summary=write_runtime_report({**report,'monitor':monitor},out,guard._resource_sample);actual,reconstructed=read_runtime_report(out);assert actual==summary and reconstructed==monitor,'DIAGNOSTIC_EVIDENCE_RECONSTRUCTION'
  compact={**report,'monitor':summary['monitor'],'commandCount':len(guard.commands)};text=json.dumps(compact,indent=2);assert len(text.encode())<=65536,'DIAGNOSTIC_REPORT_BOUND';(out/'lld-qualification.json').write_text(text,encoding='utf8');print('LLD_QUALIFICATION_REPORT '+text,flush=True)
if __name__=='__main__':main()
