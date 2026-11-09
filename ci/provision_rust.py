"""Explicit official Rust provisioning on a temporary standard hosted runner only."""
import pathlib,os,subprocess,shutil,time,json
MIN_FREE=40*1024**3
MAX_OUTPUT=8*1024**3
MAX_SECONDS=600
MAX_LOG=4*1024**2
MARKER='[provision-rust195]'
def limits(free,used,elapsed,log):
 if free<MIN_FREE:return 'FREE_SPACE_GUARD'
 if used>MAX_OUTPUT:return 'OUTPUT_THRESHOLD'
 if elapsed>MAX_SECONDS:return 'TIME_LIMIT'
 if log>MAX_LOG:return 'LOG_LIMIT'
 return None
def install_args(rustup):
 return [str(rustup),'toolchain','install','1.95.0-x86_64-pc-windows-msvc','--profile','minimal','--component','clippy','--component','rustfmt','--component','rust-src','--target','aarch64-linux-android','--no-self-update']
def child_environment(parent,base):
 keys=('SystemRoot','WINDIR','COMSPEC','PATHEXT','PATH','PROCESSOR_ARCHITECTURE','NUMBER_OF_PROCESSORS','USERPROFILE','APPDATA','LOCALAPPDATA','PROGRAMFILES','PROGRAMFILES(X86)','HOME')
 env={k:parent[k] for k in keys if k in parent}
 env.update(RUSTUP_HOME=str(base/'rustup'),CARGO_HOME=str(base/'cargo'),TEMP=str(base/'temp'),TMP=str(base/'temp'),RUSTUP_DIST_SERVER='https://static.rust-lang.org',RUSTUP_UPDATE_ROOT='https://static.rust-lang.org/rustup',RUSTUP_TOOLCHAIN='1.95.0-x86_64-pc-windows-msvc',RUSTUP_AUTO_INSTALL='0',RUSTUP_IO_THREADS='2',RUSTUP_CONCURRENT_DOWNLOADS='2',RUSTUP_UNPACK_RAM='536870912',RUSTUP_TERM_COLOR='never')
 return env
def size(root):
 n=0
 for p in root.rglob('*'):
  assert not p.is_symlink(),'Unexpected link in owned output'
  if p.is_file():n+=p.stat().st_size
 return n
def main():
 assert os.name=='nt' and os.environ.get('GITHUB_REPOSITORY')=='TroubledPerson/Vibetram' and os.environ.get('GITHUB_REF')=='refs/heads/main'
 assert os.environ.get('GITHUB_EVENT_NAME')=='push'
 event=json.loads(pathlib.Path(os.environ['GITHUB_EVENT_PATH']).read_text(encoding='utf-8'));assert MARKER in event['head_commit']['message']
 root=pathlib.Path(__file__).resolve().parents[1];temp=pathlib.Path(os.environ['RUNNER_TEMP'])
 assert shutil.disk_usage(root).free>=MIN_FREE+MAX_OUTPUT and shutil.disk_usage(temp).free>=MIN_FREE+MAX_OUTPUT
 rustup=shutil.which('rustup');assert rustup,'Existing official runner rustup required'
 base=temp/('vibetram-rust195-'+os.environ['GITHUB_RUN_ID']);assert not base.exists();base.mkdir()
 for name in ('cargo','rustup','temp'):(base/name).mkdir()
 env=child_environment(os.environ,base);args=install_args(rustup);log=base/'rustup-install.log';start=time.monotonic();peak=0;status='STARTING';proc=None
 try:
  with log.open('xb') as stream:
   proc=subprocess.Popen(args,cwd=root,env=env,stdout=stream,stderr=subprocess.STDOUT)
   while True:
    used=size(base);peak=max(peak,used);elapsed=time.monotonic()-start
    reason=limits(min(shutil.disk_usage(root).free,shutil.disk_usage(base).free),used,elapsed,log.stat().st_size)
    if reason:raise RuntimeError(reason)
    if proc.poll() is not None:break
    time.sleep(2)
  assert proc.returncode==0,'RUSTUP_INSTALL_FAILED'
  used=size(base);peak=max(peak,used);assert not limits(min(shutil.disk_usage(root).free,shutil.disk_usage(base).free),used,time.monotonic()-start,log.stat().st_size)
  status='PINNED_TOOLS_INSTALLED_RECHECK_REQUIRED'
  # These settings apply only to later steps in this same temporary job.
  values={k:env[k] for k in ('RUSTUP_HOME','CARGO_HOME','RUSTUP_TOOLCHAIN','RUSTUP_AUTO_INSTALL','TEMP','TMP')};values['VIBETRAM_PROVISIONED_RUST']='1'
  with open(os.environ['GITHUB_ENV'],'a',encoding='utf-8') as f:
   for key,value in values.items():assert '\n' not in value;f.write(key+'='+value+'\n')
 except BaseException:
  status='FAILED_STOPPED_PARTIALS_PRESERVED'
  raise
 finally:
  if proc and proc.poll() is None:
   proc.terminate()
   try:proc.wait(timeout=15)
   except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=5)
  report={'kind':'PINNED_RUST_SETUP_NOT_A_BUILD','status':status,'toolchain':'1.95.0-x86_64-pc-windows-msvc','components':['clippy','rustfmt','rust-src'],'target':'aarch64-linux-android','distribution':'https://static.rust-lang.org','selfUpdate':False,'elapsedSeconds':round(time.monotonic()-start,3),'retainedPeakBytes':peak,'monitoredOutputThresholdBytes':MAX_OUTPUT,'workspaceFreeBytes':shutil.disk_usage(root).free,'minimumFreeBytes':MIN_FREE,'maximumSeconds':MAX_SECONDS,'logThresholdBytes':MAX_LOG,'ioWorkers':2,'downloadWorkers':2,'unpackMemoryHintBytes':536870912,'hardCumulativeWriteQuota':False,'compiledAnything':False,'signedAnything':False,'credentialsPassedToChild':False,'partialsDeletedByThisScript':False}
  out=root/'provision-output';assert not out.exists();out.mkdir();payload=json.dumps(report,indent=2)+'\n';assert len(payload.encode())<16384;(out/'provisioning.json').write_text(payload,encoding='utf-8');print(payload)
if __name__=='__main__':main()
