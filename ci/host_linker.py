"""Qualified Windows Rust linker; Microsoft C tools and Android remain separate."""
import pathlib,os,json,hashlib,shutil
SHA='3cf499fc8a03853722d19e3ae1c5cdd143ac7426f1405b9e6efacd7a94b7328a'
SIZE=113349120
KEY='VIBETRAM_LLD_BINDING'
def trusted_request(repo,ref,event,message):
 return repo=='TroubledPerson/Vibetram' and ref=='refs/heads/main' and event=='push' and isinstance(message,str) and len(message)<=4096 and all(x in message for x in ('[qualified-lld-host-191]','[unsigned-trial-191]')) and '[qualified-rust-vctip-cleanup-191]' not in message

def requested():
 if os.environ.get('GITHUB_EVENT_NAME')!='push':return False
 p=pathlib.Path(os.environ['GITHUB_EVENT_PATH']);assert p.is_absolute() and 0<p.stat().st_size<=1048576,'HOST_LINKER_EVENT_BOUND'
 return trusted_request(os.environ.get('GITHUB_REPOSITORY'),os.environ.get('GITHUB_REF'),os.environ.get('GITHUB_EVENT_NAME'),json.loads(p.read_text(encoding='utf8'))['head_commit']['message'])

def binding(env):
 value=env.get(KEY);assert isinstance(value,str) and 0<len(value)<=2048,'HOST_LLD_BINDING_BOUND'
 x=json.loads(value);assert set(x)=={'path','identity','bytes','sha256'} and x['bytes']==SIZE and x['sha256']==SHA,'HOST_LLD_OFFICIAL_PIN'
 assert isinstance(x['identity'],list) and len(x['identity'])==2 and all(type(i) is int for i in x['identity']),'HOST_LLD_IDENTITY_SCHEMA'
 expected=pathlib.Path(env['RUSTUP_HOME'])/'toolchains/1.95.0-x86_64-pc-windows-msvc/lib/rustlib/x86_64-pc-windows-msvc/bin/rust-lld.exe'
 assert expected.is_absolute() and x['path']==str(expected) and env.get('CARGO_TARGET_X86_64_PC_WINDOWS_MSVC_LINKER')==str(expected),'HOST_LLD_EXACT_ROUTE'
 assert 'VIBETRAM_QUALIFIED_RUST_VCTIP' not in env,'FORCED_RUST_CLEANUP_DISABLED'
 return x

def direct_msvc_linker(env):
 if KEY not in env:return env.get('CARGO_TARGET_X86_64_PC_WINDOWS_MSVC_LINKER')
 binding(env);link=pathlib.Path(env.get('VIBETRAM_DIRECT_MSVC_LINKER',''));assert link.is_absolute() and link.name.lower()=='link.exe','DIRECT_MSVC_LINKER_REQUIRED'
 for key,name in [('CC_x86_64_pc_windows_msvc','cl.exe'),('CXX_x86_64_pc_windows_msvc','cl.exe'),('HOST_CC','cl.exe'),('HOST_CXX','cl.exe'),('AR_x86_64_pc_windows_msvc','lib.exe')]:
  p=pathlib.Path(env.get(key,''));assert p.is_absolute() and p.parent==link.parent and p.name.lower()==name,'DIRECT_MSVC_TOOL_ROUTES'
 return str(link)

def verify_runtime(env,sample=None):
 if KEY not in env:return None
 from build_guard import executable_snapshot
 x=binding(env);direct=direct_msvc_linker(env);assert pathlib.Path(shutil.which('link.exe',path=env['PATH']) or '')==pathlib.Path(direct),'DIRECT_MSVC_PATH_COLLISION'
 assert env.get('CARGO_PROFILE_CI_TEST_DEBUG')=='1' and not env.get('RUSTFLAGS'),'HOST_DEBUG_OR_GLOBAL_FLAGS_CHANGED'
 cross=env.get('CARGO_TARGET_AARCH64_LINUX_ANDROID_LINKER')
 if cross:
  assert pathlib.Path(cross).name.lower()=='clang.exe' and cross!=x['path'],'ANDROID_LINKER_ROLE'
  flags=env.get('CARGO_ENCODED_RUSTFLAGS','');assert '--target=aarch64-linux-android29' in flags and 'max-page-size=16384' in flags and '/STACK:' not in flags,'ANDROID_FLAGS_CHANGED'
 else:assert not env.get('CARGO_ENCODED_RUSTFLAGS'),'HOST_GLOBAL_FLAGS_CHANGED'
 row=executable_snapshot(pathlib.Path(x['path']),sample,large_lld_binding=x);assert row['identity']==x['identity'] and row['bytes']==SIZE and row['sha256']==SHA,'HOST_LLD_CHANGED'
 return row

def configure(env,guard,work):
 from build_guard import executable_snapshot
 assert requested() and KEY not in env and 'VIBETRAM_QUALIFIED_RUST_VCTIP' not in env,'TRUSTED_LLD_ACTIVATION_REQUIRED'
 p=pathlib.Path(env['RUSTUP_HOME'])/'toolchains/1.95.0-x86_64-pc-windows-msvc/lib/rustlib/x86_64-pc-windows-msvc/bin/rust-lld.exe';m=p.lstat();pin={'path':str(p),'identity':[m.st_dev,m.st_ino],'bytes':SIZE,'sha256':SHA}
 row=executable_snapshot(p,large_lld_binding=pin);assert row['sha256']==SHA and row['bytes']==SIZE
 result=env.copy();result.update(VIBETRAM_LLD_BINDING=json.dumps(pin,separators=(',',':')),VIBETRAM_DIRECT_MSVC_LINKER=env['CARGO_TARGET_X86_64_PC_WINDOWS_MSVC_LINKER'],CARGO_TARGET_X86_64_PC_WINDOWS_MSVC_LINKER=str(p),CARGO_PROFILE_CI_TEST_DEBUG='1')
 verify_runtime(result);version=guard.run([p,'-flavor','link','--version'],env=result,capture=True,timeout=30).stdout.strip();assert version.startswith('LLD 22.1.2 '),'HOST_LLD_VERSION'
 return result,{'sha256':SHA,'bytes':SIZE,'version':version,'staticCRTAnd8MiBStackFromPinnedProjectConfig':True,'debugLimited':True,'forcedRustCleanupEnabled':False,'qualifiedIsolatedRun':42815238096}

def tiny_rust_arguments(rust,rexe,env):
 link=env['CARGO_TARGET_X86_64_PC_WINDOWS_MSVC_LINKER'];args=['rustc','--edition','2024','--target','x86_64-pc-windows-msvc','-C','linker='+link]
 if KEY in env:binding(env);args+=['-C','linker-flavor=lld-link','-C','target-feature=+crt-static','-C','link-arg=/STACK:8388608','-C','debuginfo=1']
 return [*args,str(rust),'-o',str(rexe)]

def failure_members(proc,env,sampler=None):
 """Read held task-owned identities only. Never approve completion or cleanup."""
 import ctypes
 from build_guard import executable_snapshot
 rows=[]
 try:
  proc.observe();handles=[proc.process]+[x[0] for x in proc.members_held.values()];seen=set();observed=[]
  for handle in handles:
   row=proc.api.snapshot(handle);key=(row['pid'],row['creationFiletime'])
   if key not in seen:seen.add(key);observed.append(row)
  assert len(observed)<=256,'OWNED_FAILURE_MEMBER_BOUND'
  for r in observed:
   item={'pid':r['pid'],'creationFiletime':r['creationFiletime'],'qualifiedForNormalCompletion':False}
   try:
    handle=proc.process if r['pid']==proc.initial['pid'] else proc.members_held[r['pid']][0];before=proc.api.snapshot(handle);n=proc.api.w.DWORD(32768);buf=ctypes.create_unicode_buffer(n.value);api=proc.api
    api.k.QueryFullProcessImageNameW.argtypes=[api.w.HANDLE,api.w.DWORD,api.w.LPWSTR,ctypes.POINTER(api.w.DWORD)];api.k.QueryFullProcessImageNameW.restype=api.w.BOOL;api.ok(api.k.QueryFullProcessImageNameW(handle,0,buf,ctypes.byref(n)))
    path=pathlib.Path(buf.value);item.update(imageBaseName=path.name,rawPathWithheld=True,heldIdentityVerifiedBeforeHash=(before['pid'],before['creationFiletime'])==(r['pid'],r['creationFiletime']));pin=binding(env) if KEY in env else None;meta=executable_snapshot(path,sampler.tick if sampler else None,large_lld_binding=pin if pin and str(path)==pin['path'] else None);after=api.snapshot(handle)
    assert (before['pid'],before['creationFiletime'])==(after['pid'],after['creationFiletime'])==(r['pid'],r['creationFiletime']),'OWNED_FAILURE_HELD_IDENTITY_CHANGED'
    item.update(imageBaseName=path.name,imageSHA256=meta['sha256'],imageBytes=meta['bytes'],imageIdentity=meta['identity'],heldIdentityVerified=True,provenance='OFFICIAL_PINNED_RUST_LLD' if pin and str(path)==pin['path'] else 'RECORDED_HASH_NOT_A_COMPLETION_EXEMPTION',rawPathWithheld=True)
   except BaseException as e:item.update(metadataFailureClass=type(e).__name__,metadataFailureWinerror=getattr(e,'winerror',None),metadataFailureCategory=str(e)[:120] if isinstance(e,AssertionError) else 'IMAGE_METADATA_READ_FAILED')
   rows.append(item)
 except BaseException as e:rows.append({'enumerationFailureClass':type(e).__name__,'qualifiedForNormalCompletion':False})
 assert len(json.dumps(rows).encode())<=65536,'OWNED_FAILURE_METADATA_BOUND'
 return rows
