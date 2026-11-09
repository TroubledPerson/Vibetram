"""Unsigned clean-runner qualification. Not executed during local preparation."""
import os,pathlib,subprocess,json,hashlib,shutil,re,zipfile,struct
from check_source import source_check
ROOT=pathlib.Path(__file__).resolve().parents[1]
WORK=ROOT/'ci-work';OUT=ROOT/'dist'
def run(argv,cwd=ROOT,env=None,capture=False):
 return subprocess.run([str(a) for a in argv],cwd=cwd,env=env,check=True,text=True,encoding='utf-8',stdout=subprocess.PIPE if capture else None,timeout=6600)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert os.name=='nt','Qualified preparation targets Windows runner tooling only'
 source_check(ROOT)
 assert not WORK.exists() and not OUT.exists(),'No overwrites/retries into prior partial output'
 assert shutil.disk_usage(ROOT).free>=40*1024**3,'Need 40GiB runner headroom; do not delete runner data to work around'
 commit=os.environ.get('GITHUB_SHA','');assert re.fullmatch('[0-9a-f]{40}',commit)
 assert run(['git','rev-parse','HEAD'],capture=True).stdout.strip()==commit
 sdk=pathlib.Path(os.environ['ANDROID_HOME']);bt=sdk/'build-tools/35.0.0';jar=sdk/'platforms/android-35/android.jar'
 ndk=sdk/'ndk/30.0.16248370/toolchains/llvm/prebuilt/windows-x86_64/bin'
 java=pathlib.Path(os.environ['JAVA_HOME_17_X64'])/'bin'
 required=[bt/'aapt2.exe',bt/'zipalign.exe',bt/'lib/d8.jar',jar,ndk/'aarch64-linux-android29-clang.cmd',ndk/'llvm-strip.exe',java/'javac.exe',java/'java.exe',java/'jar.exe']
 assert all(p.is_file() for p in required),'Required pinned SDK35/NDK30/JDK17 tool missing; no silent version substitution or licence acceptance'
 assert '1.95.0' in run(['rustc','--version'],cwd=ROOT/'codex-rs',capture=True).stdout,'Pinned Rust1.95 required; no silent upgrade'
 assert 'aarch64-linux-android' in run(['rustup','target','list','--installed','--toolchain','1.95.0'],capture=True).stdout,'Android target missing; qualify setup separately'
 WORK.mkdir();OUT.mkdir();env=os.environ.copy();env['CARGO_TARGET_DIR']=str(WORK/'target');env['CARGO_INCREMENTAL']='0';env['CARGO_PROFILE_CI_TEST_DEBUG']='0'
 env['CARGO_BUILD_JOBS']='2';env['CARGO_TARGET_AARCH64_LINUX_ANDROID_LINKER']=str(ndk/'aarch64-linux-android29-clang.cmd')
 # Build-time dependency traffic is distinct from the APK's absent Internet permission.
 for case in ['status_only_gate','monitored_native_unit','status_session_','managed_pairing_']:
  run(['cargo','test','--locked','--profile','ci-test','--lib','-p','codex-app-server-transport',case,'--','--skip','phone_realtime'],cwd=ROOT/'codex-rs',env=env)
 env['RUSTFLAGS']='-C link-arg=-Wl,-z,max-page-size=16384 -C debuginfo=0'
 built=run(['cargo','test','--locked','--profile','ci-test','--lib','-p','codex-app-server-transport','--target','aarch64-linux-android','--no-run','--message-format=json-render-diagnostics'],cwd=ROOT/'codex-rs',env=env,capture=True)
 candidates=[]
 for line in built.stdout.splitlines():
  try:x=json.loads(line)
  except ValueError:continue
  if x.get('reason')=='compiler-artifact' and x.get('target',{}).get('name')=='codex_app_server_transport' and x.get('profile',{}).get('test') and x.get('executable'):candidates.append(pathlib.Path(x['executable']))
 assert len(candidates)==1,'Expected exactly one real native test binary'
 native=WORK/'libvibetramoffline.so';shutil.copyfile(candidates[0],native);run([ndk/'llvm-strip.exe','--strip-unneeded',native])
 b=native.read_bytes();assert b[:5]==b'\x7fELF\x02' and struct.unpack_from('<H',b,18)[0]==183
 phoff=struct.unpack_from('<Q',b,32)[0];ents,n=struct.unpack_from('<HH',b,54)
 loads=[struct.unpack_from('<IIQQQQQQ',b,phoff+i*ents) for i in range(n) if struct.unpack_from('<I',b,phoff+i*ents)[0]==1]
 assert loads and all(p[7]>=16384 and p[2]%16384==p[3]%16384 for p in loads),'Native 16KiB LOAD alignment failed'
 app=WORK/'src';shutil.copytree(ROOT/'android/src',app);pins=app/'org/local/codexisolation/BuildPins.java'
 original=json.loads((ROOT/'SOURCE_ID_MATERIAL.json').read_text())
 nh=sha(native);source_id=hashlib.sha256(json.dumps({'commit':commit,'nativeSHA256':nh},sort_keys=True,separators=(',',':')).encode()).hexdigest()
 p=pins.read_text();assert original['sourceID'] in p and '6a5433d6e50835e29bbf0fa1dd4bd56a865faa835ad171aa7184c8d86dce0914' in p
 pins.write_text(p.replace(original['sourceID'],source_id).replace('6a5433d6e50835e29bbf0fa1dd4bd56a865faa835ad171aa7184c8d86dce0914',nh),encoding='utf-8')
 classes=WORK/'classes';classes.mkdir();dex=WORK/'dex';dex.mkdir()
 run([java/'javac.exe','-encoding','UTF-8','-source','17','-target','17','-classpath',jar,'-d',classes,*sorted(app.rglob('*.java'))])
 cj=WORK/'classes.jar';run([java/'jar.exe','--create','--file',cj,'-C',classes,'.'])
 run([java/'java.exe','-Djava.io.tmpdir='+str(WORK),'-cp',bt/'lib/d8.jar','com.android.tools.r8.D8','--min-api','29','--lib',jar,'--output',dex,cj])
 res=WORK/'resources.apk';run([bt/'aapt2.exe','link','-o',res,'--manifest',ROOT/'android/AndroidManifest.xml','-I',jar,'--min-sdk-version','29','--target-sdk-version','35'])
 raw=WORK/'unsigned-unaligned.apk'
 with zipfile.ZipFile(res) as rz,zipfile.ZipFile(raw,'x') as z:
  for name in ['AndroidManifest.xml','resources.arsc']:z.writestr(name,rz.read(name),compress_type=zipfile.ZIP_STORED)
  z.write(dex/'classes.dex','classes.dex',compress_type=zipfile.ZIP_DEFLATED)
  z.write(native,'lib/arm64-v8a/libvibetramoffline.so',compress_type=zipfile.ZIP_STORED)
  for f in sorted((ROOT/'android/assets').iterdir()):
   if f.is_file() and f.name!='build-provenance.json':z.write(f,'assets/'+f.name,compress_type=zipfile.ZIP_DEFLATED)
  z.writestr('assets/build-provenance.json',json.dumps({'commit':commit,'nativeSHA256':nh,'appSourceID':source_id,'signed':False,'phoneTesting':'PENDING','offlineOnly':True}))
 apk=OUT/'Vibetram-Alpha-1.91-Android-UNSIGNED.apk';run([bt/'zipalign.exe','-f','-P','16','4',raw,apk]);run([bt/'zipalign.exe','-c','-P','16','4',apk])
 with zipfile.ZipFile(apk) as z:
  assert z.testzip() is None
  for name,align in [('resources.arsc',4),('lib/arm64-v8a/libvibetramoffline.so',16384)]:
   e=z.getinfo(name);hdr=apk.read_bytes()[e.header_offset:e.header_offset+30];a,c=struct.unpack_from('<HH',hdr,26);offset=e.header_offset+30+a+c
   assert e.compress_type==0 and offset%align==0
  assert hashlib.sha256(z.read('lib/arm64-v8a/libvibetramoffline.so')).hexdigest()==nh
 source=OUT/'Vibetram-Alpha-1.91-source.zip';run(['git','archive','--format=zip','--output',source,commit])
 (OUT/'provenance.json').write_text(json.dumps({'commit':commit,'APK':apk.name,'APK_SHA256':sha(apk),'sourceZipSHA256':sha(source),'nativeSHA256':nh,'signed':False,'releasable':False,'phoneTesting':'PENDING'},indent=2))
 print('UNSIGNED BUILD QUALIFIED; not an installable signed public release')
if __name__=='__main__':main()
