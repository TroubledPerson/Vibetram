"""Read-only hosted runner inventory. Never install, compile, clean or sign."""
import pathlib,os,sys,json,subprocess,shutil,ctypes,re
ROOT=pathlib.Path(__file__).resolve().parents[1]
MIN_FREE=40*1024**3
REQUIRED=('sdk35','build_tools35','ndk30','jdk17','rust195','android_target','rust_components','perl','cmake','ninja','msvc')
def evaluate(free,tools):
 reasons=[]
 if not isinstance(free,int) or isinstance(free,bool) or free<MIN_FREE:reasons.append('WORKSPACE_FREE_BELOW_40_GIB')
 reasons += ['MISSING_OR_MISMATCHED_'+key.upper() for key in REQUIRED if tools.get(key) is not True]
 return {'qualified':not reasons,'reasons':reasons}
def probe(args,cwd=ROOT):
 env=os.environ.copy();env['RUSTUP_AUTO_INSTALL']='0'
 try:
  p=subprocess.run([str(x) for x in args],cwd=cwd,env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=15)
  return {'ok':p.returncode==0,'exit':p.returncode,'text':(p.stdout+'\n'+p.stderr).strip()[:2048]}
 except (OSError,subprocess.TimeoutExpired):return {'ok':False,'exit':None,'text':'UNAVAILABLE_OR_TIMED_OUT'}
def props(path):
 if not path.is_file():return {}
 assert path.stat().st_size<32768
 out={}
 for line in path.read_text(encoding='utf-8',errors='replace').splitlines():
  if '=' in line:
   key,value=line.split('=',1);out[key.strip()]=value.strip()
 return out
def disk(path):
 while not path.exists() and path!=path.parent:path=path.parent
 d=shutil.disk_usage(path);return {'volume':path.anchor,'freeBytes':d.free,'totalBytes':d.total}
def main():
 assert os.name=='nt','Windows runner only'
 assert os.environ.get('GITHUB_REPOSITORY')=='TroubledPerson/Vibetram'
 assert os.environ.get('GITHUB_REF')=='refs/heads/main'
 commit=os.environ.get('GITHUB_SHA','');assert re.fullmatch('[0-9a-f]{40}',commit)
 sdk=pathlib.Path(os.environ.get('ANDROID_HOME',r'C:\Android\android-sdk'))
 ndkroot=sdk/'ndk/30.0.16248370';ndk=ndkroot/'toolchains/llvm/prebuilt/windows-x86_64/bin';bt=sdk/'build-tools/35.0.0';platform=sdk/'platforms/android-35'
 javaHome=os.environ.get('JAVA_HOME_17_X64');java=pathlib.Path(javaHome)/'bin' if javaHome else None
 metadata={'ndkRevision':props(ndkroot/'source.properties').get('Pkg.Revision'),'buildToolsRevision':props(bt/'source.properties').get('Pkg.Revision'),'platformAPI':props(platform/'source.properties').get('AndroidVersion.ApiLevel')}
 tools={'sdk35':metadata['platformAPI']=='35' and (platform/'android.jar').is_file(),'build_tools35':metadata['buildToolsRevision']=='35.0.0' and all((bt/p).is_file() for p in ('aapt2.exe','zipalign.exe','lib/d8.jar')),'ndk30':metadata['ndkRevision']=='30.0.16248370' and all((ndk/p).is_file() for p in ('aarch64-linux-android29-clang.cmd','llvm-strip.exe','llvm-ar.exe'))}
 versions={}
 if java and all((java/p).is_file() for p in ('javac.exe','java.exe','jar.exe')):
  versions['javac']=probe([java/'javac.exe','-version']);tools['jdk17']=versions['javac']['ok'] and bool(re.search(r'\bjavac 17(?:\.|\s)',versions['javac']['text']))
 else:tools['jdk17']=False
 rustup=shutil.which('rustup');installed=probe([rustup,'toolchain','list']) if rustup else {'ok':False,'text':''}
 # Only list installed state; do not call a missing pinned toolchain proxy.
 pinned=installed['ok'] and any(x.split()[0]=='1.95.0' or x.split()[0].startswith('1.95.0-') for x in installed['text'].splitlines() if x.strip())
 versions['installedRustToolchains']=installed
 tools.update(rust195=False,android_target=False,rust_components=False)
 if pinned:
  versions['pinnedRust']=probe([rustup,'run','1.95.0','rustc','--version'])
  targets=probe([rustup,'target','list','--installed','--toolchain','1.95.0']);components=probe([rustup,'component','list','--installed','--toolchain','1.95.0'])
  versions['pinnedRustTargets']=targets;versions['pinnedRustComponents']=components
  tools['rust195']=versions['pinnedRust']['ok'] and versions['pinnedRust']['text'].startswith('rustc 1.95.0 ')
  tools['android_target']=targets['ok'] and 'aarch64-linux-android' in targets['text'].splitlines()
  tools['rust_components']=components['ok'] and all(any(line==name or line.startswith(name+'-') for line in components['text'].splitlines()) for name in ('clippy','rustfmt','rust-src'))
 for name,args in [('perl',['-e','print $^V']),('cmake',['--version']),('ninja',['--version'])]:
  executable=shutil.which(name);versions[name]=probe([executable,*args]) if executable else {'ok':False,'text':'NOT_ON_PATH'};tools[name]=versions[name]['ok']
 vswhere=pathlib.Path(os.environ.get('ProgramFiles(x86)',r'C:\Program Files (x86)'))/'Microsoft Visual Studio/Installer/vswhere.exe'
 versions['msvc']=probe([vswhere,'-latest','-products','*','-requires','Microsoft.VisualStudio.Component.VC.Tools.x86.x64','-property','installationVersion']) if vswhere.is_file() else {'ok':False,'text':'NOT_FOUND'}
 tools['msvc']=versions['msvc']['ok'] and bool(versions['msvc']['text'])
 class Memory(ctypes.Structure):
  _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(x,ctypes.c_ulonglong) for x in ('totalPhys','availPhys','totalPage','availPage','totalVirtual','availVirtual','extended')]
 memory=Memory();memory.length=ctypes.sizeof(Memory);assert ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory))
 disks={'workspace':disk(ROOT),'runnerTemp':disk(pathlib.Path(os.environ.get('RUNNER_TEMP',str(ROOT)))),'sdk':disk(sdk),'cargo':disk(pathlib.Path(os.environ.get('CARGO_HOME',str(pathlib.Path.home()/'.cargo')))),'rustup':disk(pathlib.Path(os.environ.get('RUSTUP_HOME',str(pathlib.Path.home()/'.rustup'))))}
 result={'kind':'READ_ONLY_PREFLIGHT_NOT_A_BUILD','commit':commit,'imageVersion':os.environ.get('ImageVersion','UNREPORTED'),'imageOS':os.environ.get('ImageOS','UNREPORTED'),'cpuCount':os.cpu_count(),'ramTotalBytes':memory.totalPhys,'ramAvailableBytes':memory.availPhys,'disks':disks,'requiredWorkspaceFreeBytes':MIN_FREE,'tools':tools,'versions':versions,'androidMetadata':metadata,**evaluate(disks['workspace']['freeBytes'],tools),'installedAnything':False,'compiledAnything':False,'signedAnything':False}
 out=ROOT/'preflight-output';assert not out.exists();out.mkdir();payload=json.dumps(result,indent=2)+'\n';assert len(payload.encode())<=32768
 (out/'runner-preflight.json').write_text(payload,encoding='utf-8');print(payload)
 output=os.environ.get('GITHUB_OUTPUT')
 if output:
  with open(output,'a',encoding='utf-8') as f:f.write('qualified='+str(result['qualified']).lower()+'\n')
 summary=os.environ.get('GITHUB_STEP_SUMMARY')
 if summary:
  with open(summary,'a',encoding='utf-8') as f:f.write('## Read-only runner preflight\n\nQualified: **'+str(result['qualified'])+'**. This is not a build.\n\nWorkspace free bytes: '+str(disks['workspace']['freeBytes'])+'; required: '+str(MIN_FREE)+'.\n\nReasons: '+(', '.join(result['reasons']) or 'none')+'.\n')
if __name__=='__main__':main()
