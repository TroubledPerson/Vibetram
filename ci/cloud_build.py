"""One monitored unsigned hosted build; no signing, release or device execution."""
import os,pathlib,subprocess,json,hashlib,shutil,re,zipfile,struct,tomllib
from check_source import source_check
from build_guard import Guard,clean_env,android_env,artifact,test_count,MAX_OUTPUT,MIN_FREE
ROOT=pathlib.Path(__file__).resolve().parents[1]
WORK=ROOT/'ci-work';OUT=ROOT/'dist';GUARD=None;ENV=None
def run(argv,cwd=ROOT,env=None,capture=False):
 if GUARD:return GUARD.run(argv,cwd,env or ENV,capture)
 return subprocess.run([str(a) for a in argv],cwd=cwd,env=env,check=True,text=True,encoding='utf-8',stdout=subprocess.PIPE if capture else None,timeout=30)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def elf_check(b):
 assert len(b)>=64 and b[:5]==b'\x7fELF\x02' and struct.unpack_from('<H',b,18)[0]==183,'EXPECTED_ARM64_ELF'
 assert struct.unpack_from('<H',b,16)[0]==3,'EXPECTED_POSITION_INDEPENDENT_EXECUTABLE'
 phoff=struct.unpack_from('<Q',b,32)[0];ents,n=struct.unpack_from('<HH',b,54);assert ents>=56 and phoff+n*ents<=len(b)
 loads=[struct.unpack_from('<IIQQQQQQ',b,phoff+i*ents) for i in range(n) if struct.unpack_from('<I',b,phoff+i*ents)[0]==1]
 assert loads and all(p[7]>=16384 and p[2]%16384==p[3]%16384 for p in loads),'NATIVE_16K_ALIGNMENT_FAILED'
def notice_closure(cargo_text,lock):
 inventory=json.loads((ROOT/'android/assets/dependency-notice-inventory.json').read_text(encoding='utf-8'))['dependencies'];known={(x['name'],x['version']) for x in inventory}
 result={};missing=[]
 for line in cargo_text.splitlines():
  try:x=json.loads(line)
  except ValueError:continue
  if x.get('reason')!='compiler-artifact':continue
  package=x.get('package_id','');manifest=x.get('manifest_path')
  if not package or not manifest:continue
  p=pathlib.Path(manifest);assert p.is_file()
  if p.resolve().is_relative_to((ROOT/'codex-rs').resolve()):continue
  assert p.resolve().is_relative_to(pathlib.Path(ENV['CARGO_HOME']).resolve()),'EXTERNAL_MANIFEST_ESCAPE'
  data=tomllib.loads(p.read_text(encoding='utf-8'))['package'];name=data['name'];version=data.get('version')
  if not isinstance(version,str):
   tail=package.rsplit('#',1)[-1];assert '@' in tail,'UNRESOLVED_EXTERNAL_PACKAGE_VERSION';version=tail.rsplit('@',1)[-1]
  locked=[r for r in lock['package'] if r['name']==name and r['version']==version and r.get('source')]
  assert len(locked)==1,'AMBIGUOUS_OR_UNLOCKED_COMPILED_PACKAGE'
  r=locked[0];source=r['source'];assert source.startswith(('registry+https://','git+https://')) and not re.search(r'https://[^/]*@',source)
  result[(name,version)]={'name':name,'version':version,'source':source,'checksum':r.get('checksum')}
  if (name,version) not in known:missing.append({'name':name,'version':version,'source':source})
 (WORK/'compiled-dependency-notice-check.json').write_text(json.dumps({'compiledExternal':list(result.values()),'uncovered':missing},indent=2),encoding='utf-8')
 assert not missing,'COMPILED_DEPENDENCY_NOTICES_REQUIRE_REVIEW'
 return list(result.values())
def main():
 global GUARD,ENV
 assert os.name=='nt' and os.environ.get('GITHUB_REPOSITORY')=='TroubledPerson/Vibetram' and os.environ.get('GITHUB_REF')=='refs/heads/main'
 assert os.environ.get('GITHUB_EVENT_NAME')=='push'
 event=json.loads(pathlib.Path(os.environ['GITHUB_EVENT_PATH']).read_text(encoding='utf-8'));assert '[unsigned-trial-191]' in event['head_commit']['message']
 source_check(ROOT);assert not WORK.exists() and not OUT.exists(),'PRESERVE_EXISTING_PARTIALS'
 assert shutil.disk_usage(ROOT).free>=MIN_FREE+MAX_OUTPUT,'INITIAL_104_GIB_TRIAL_RESERVATION_REQUIRED'
 commit=os.environ['GITHUB_SHA'];assert re.fullmatch('[0-9a-f]{40}',commit)
 assert run(['git','rev-parse','HEAD'],capture=True).stdout.strip()==commit
 sdk=pathlib.Path(os.environ['ANDROID_HOME']);bt=sdk/'build-tools/35.0.0';jar=sdk/'platforms/android-35/android.jar';ndkroot=sdk/'ndk/30.0.16248370';ndk=ndkroot/'toolchains/llvm/prebuilt/windows-x86_64/bin';java=pathlib.Path(os.environ['JAVA_HOME_17_X64'])/'bin'
 required=[bt/'aapt2.exe',bt/'zipalign.exe',bt/'lib/d8.jar',jar,ndk/'clang.exe',ndk/'clang++.exe',ndk/'llvm-ar.exe',ndk/'llvm-strip.exe',ndk/'llvm-readelf.exe',java/'javac.exe',java/'java.exe',java/'jar.exe']
 assert all(p.is_file() for p in required),'PINNED_REQUIRED_TOOL_MISSING'
 WORK.mkdir();OUT.mkdir()
 for path in ('tmp','home','profile','profile/AppData/Roaming','profile/AppData/Local','host-fixtures/tmp','host-fixtures/profile'): (WORK/path).mkdir(parents=True,exist_ok=True)
 ENV=clean_env(os.environ,WORK);GUARD=Guard(ROOT,WORK,OUT,ENV)
 versions={}
 for name,args in [('rustc',['rustc','--version']),('ndkClang',[ndk/'clang.exe','--version']),('ndkArchiver',[ndk/'llvm-ar.exe','--version']),('javac',[java/'javac.exe','-version'])]:
  version_result=run(args,env=ENV,cwd=ROOT/'codex-rs',capture=True);versions[name]=(version_result.stdout or version_result.stderr or '').strip()
 assert versions['rustc'].startswith('rustc 1.95.0 '),'WRONG_RUST_VERSION'
 lockfile=ROOT/'codex-rs/Cargo.lock';lock_hash=sha(lockfile);lock=tomllib.loads(lockfile.read_text(encoding='utf-8'))
 host=run(['cargo','test','--locked','--profile','ci-test','--lib','-p','codex-app-server-transport','--no-run','--message-format=json-render-diagnostics'],cwd=ROOT/'codex-rs',env=ENV,capture=True)
 hostexe=artifact(host.stdout);assert hostexe.is_file() and hostexe.suffix=='.exe'
 listed=run([hostexe,'--list','--format','terse'],env=ENV,capture=True).stdout
 names=[line[:-6] for line in listed.splitlines() if line.endswith(': test')];assert names
 suite=[]
 for case,minimum in [('status_only_gate',27),('monitored_native_unit',19),('status_session_',16),('managed_pairing_',16)]:
  expected=[n for n in names if case in n and 'phone_realtime' not in n and 'stdio_driver' not in n];assert len(expected)>=minimum,'REQUIRED_PRODUCTION_TESTS_NOT_COLLECTED'
  result=run([hostexe,case,'--skip','phone_realtime','--skip','stdio_driver','--test-threads=1'],env=ENV,capture=True)
  count=test_count(result.stdout);assert count==len(expected),'COLLECTED_EXECUTED_TEST_COUNT_MISMATCH';suite.append({'filter':case,'passed':count})
 cross=android_env(ENV,ndkroot)
 built=run(['cargo','test','--locked','--profile','ci-test','--lib','-p','codex-app-server-transport','--target','aarch64-linux-android','--no-run','--message-format=json-render-diagnostics'],cwd=ROOT/'codex-rs',env=cross,capture=True)
 executable=artifact(built.stdout);assert executable.is_file()
 native=WORK/'libvibetramoffline.so';shutil.copyfile(executable,native);run([ndk/'llvm-strip.exe','--strip-unneeded',native]);elf_check(native.read_bytes())
 dynamic=run([ndk/'llvm-readelf.exe','-d',native],capture=True).stdout
 needed=re.findall(r'\(NEEDED\).*\[([^\]]+)\]',dynamic)
 assert all(x in ('libc.so','libdl.so','libm.so','liblog.so','libandroid.so') for x in needed),'UNPACKAGED_NATIVE_RUNTIME_DEPENDENCY'
 compiled_dependencies=notice_closure(built.stdout,lock)
 assert sha(lockfile)==lock_hash,'LOCKFILE_CHANGED'
 app=WORK/'src';shutil.copytree(ROOT/'android/src',app);pins=app/'org/local/codexisolation/BuildPins.java';original=json.loads((ROOT/'SOURCE_ID_MATERIAL.json').read_text());nh=sha(native)
 source_id=hashlib.sha256(json.dumps({'commit':commit,'nativeSHA256':nh},sort_keys=True,separators=(',',':')).encode()).hexdigest()
 p=pins.read_text();old_native='6a5433d6e50835e29bbf0fa1dd4bd56a865faa835ad171aa7184c8d86dce0914';assert original['sourceID'] in p and old_native in p
 pins.write_text(p.replace(original['sourceID'],source_id).replace(old_native,nh),encoding='utf-8')
 classes=WORK/'classes';classes.mkdir();dex=WORK/'dex';dex.mkdir();tests=WORK/'host-test-classes';tests.mkdir()
 run([java/'javac.exe','-encoding','UTF-8','-source','17','-target','17','-classpath',jar,'-d',classes,*sorted(app.rglob('*.java'))])
 run([java/'javac.exe','-encoding','UTF-8','-source','17','-target','17','-classpath',str(classes)+';'+str(jar),'-d',tests,*sorted((ROOT/'android/host-tests').glob('*.java'))])
 java_results=[]
 for name in ('MobileControllerTest','ManagedPairingIntegrationTest','MobileBridgeHostTest'):
  args=[java/'java.exe','-Djava.io.tmpdir='+str(WORK/'tmp'),'-cp',str(classes)+';'+str(tests),'org.local.codexisolation.'+name]
  if name!='MobileControllerTest':args += [hostexe,WORK/'host-fixtures']
  result=run(args,env=ENV,capture=True).stdout
  matches=re.findall(r'PASS_[A-Z_]+ checks=(\d+)',result);assert len(matches)==1 and int(matches[0])>0,'JAVA_TEST_DID_NOT_PASS'
  java_results.append({'suite':name,'checks':int(matches[0]),'summary':result.strip()})
 cj=WORK/'classes.jar';run([java/'jar.exe','--create','--file',cj,'-C',classes,'.'])
 class_files=sorted(classes.rglob('*.class'));assert class_files
 with zipfile.ZipFile(cj) as z:
  for f in class_files:assert z.read(f.relative_to(classes).as_posix())==f.read_bytes(),'TESTED_CLASS_D8_INPUT_MISMATCH'
 jar_hash=sha(cj)
 run([java/'java.exe','-Djava.io.tmpdir='+str(WORK/'tmp'),'-cp',bt/'lib/d8.jar','com.android.tools.r8.D8','--min-api','29','--lib',jar,'--output',dex,cj])
 assert sha(cj)==jar_hash
 resource_dir=WORK/'res/values';resource_dir.mkdir(parents=True)
 (resource_dir/'offline.xml').write_text('<resources><string name="vibetram_offline_build_marker">offline-only</string></resources>',encoding='utf-8')
 compiled=WORK/'compiled-resources.zip';run([bt/'aapt2.exe','compile','--dir',WORK/'res','-o',compiled])
 res=WORK/'resources.apk';run([bt/'aapt2.exe','link','-o',res,'--manifest',ROOT/'android/AndroidManifest.xml','-I',jar,'--min-sdk-version','29','--target-sdk-version','35',compiled])
 raw=WORK/'unsigned-unaligned.apk'
 with zipfile.ZipFile(res) as rz,zipfile.ZipFile(raw,'x') as z:
  for name in ('AndroidManifest.xml','resources.arsc'):z.writestr(name,rz.read(name),compress_type=zipfile.ZIP_STORED)
  z.write(dex/'classes.dex','classes.dex',compress_type=zipfile.ZIP_DEFLATED);z.write(native,'lib/arm64-v8a/libvibetramoffline.so',compress_type=zipfile.ZIP_STORED)
  for f in sorted((ROOT/'android/assets').iterdir()):
   if f.is_file() and f.name!='build-provenance.json':z.write(f,'assets/'+f.name,compress_type=zipfile.ZIP_DEFLATED)
  z.writestr('assets/compiled-dependencies.json',json.dumps(compiled_dependencies))
  z.writestr('assets/build-provenance.json',json.dumps({'commit':commit,'nativeSHA256':nh,'appSourceID':source_id,'signed':False,'phoneTesting':'PENDING','offlineOnly':True}))
 apk=OUT/'Vibetram-Alpha-1.91-Android-UNSIGNED.apk';run([bt/'zipalign.exe','-f','-P','16','4',raw,apk]);run([bt/'zipalign.exe','-c','-P','16','4',apk])
 payload=apk.read_bytes()
 with zipfile.ZipFile(apk) as z:
  assert z.testzip() is None
  for name,align in [('resources.arsc',4),('lib/arm64-v8a/libvibetramoffline.so',16384)]:
   e=z.getinfo(name);a,c=struct.unpack_from('<HH',payload,e.header_offset+26);assert e.compress_type==0 and (e.header_offset+30+a+c)%align==0
  assert hashlib.sha256(z.read('lib/arm64-v8a/libvibetramoffline.so')).hexdigest()==nh
 permissions=run([bt/'aapt2.exe','dump','permissions',apk],capture=True).stdout
 assert 'uses-permission' not in permissions.lower(),'COMPILED_PERMISSION_ADDED'
 badging=run([bt/'aapt2.exe','dump','badging',apk],capture=True).stdout
 assert "name='org.local.vibetrammobile'" in badging and "versionCode='93'" in badging and "versionName='1.91-alpha-offline'" in badging and "sdkVersion:'29'" in badging and "targetSdkVersion:'35'" in badging,'COMPILED_PACKAGE_IDENTITY_MISMATCH'
 assert sha(lockfile)==lock_hash;source_check(ROOT)
 source=OUT/'Vibetram-Alpha-1.91-source.zip';run(['git','archive','--format=zip','--output',source,commit])
 report={'state':'UNSIGNED_HOSTED_BUILD_VERIFIED_NOT_A_RELEASE','commit':commit,'APK':apk.name,'APKBytes':apk.stat().st_size,'APK_SHA256':sha(apk),'sourceZip':source.name,'sourceZipSHA256':sha(source),'nativeSHA256':nh,'hostNativeSHA256':sha(hostexe),'sourceID':source_id,'lockSHA256':lock_hash,'nativeTests':suite,'javaTests':java_results,'testedD8InputClasses':len(class_files),'nativeRuntimeDependencies':needed,'compiledDependenciesCovered':len(compiled_dependencies),'toolVersions':versions,'signed':False,'releasable':False,'phoneTesting':'PENDING','offlineOnly':True,'resourcesStoredAndAligned':True,'nativeFileAndLoad16KiBAligned':True,'compiledPermissions':0,'monitor':GUARD.report()}
 (OUT/'provenance.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2),flush=True)
if __name__=='__main__':main()

