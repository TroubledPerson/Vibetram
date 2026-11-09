"""Monitored hosted unsigned-trial helpers; no signing or credential access."""
import pathlib,os,subprocess,time,shutil,json,re,hashlib
from reparse_metadata import capture as capture_reparse_metadata,EXPECTED_ALIAS,EXPECTED_TARGET
from alias_accounting import ALIAS_METADATA_BYTES,AliasAppeared,exact_alias,safe_absence,disjoint_roots,lease_key,compare_baseline
MIN_FREE=40*1024**3
MAX_OUTPUT=64*1024**3
MAX_SECONDS=5400
MAX_LOG=64*1024**2
NUCLEO_COMMIT='4253de9faabb4e5c6d81d946a5e35a90f87347ee'
NUCLEO_LICENSE_BLOB='a612ad9813b006ce81d1ee438dd784da99a54007'
H3_COMMIT='e07e69412876f7e26f026bd75a48b2704d8c8283'
H3_LICENSE_BLOB='97d180d899ac03e8db023a2aec14f3d223e7df39'
LICENSE_RULES=[('nucleo',NUCLEO_COMMIT,('matcher','LICENSE'),NUCLEO_LICENSE_BLOB,16725)]+[('h3',H3_COMMIT,(name,'LICENSE'),H3_LICENSE_BLOB,1054) for name in ('h3','h3-datagram','h3-quinn','h3-webtransport')]
def license_rule(relative,target):
 parts=pathlib.PurePosixPath(relative.replace(chr(92),'/')).parts
 if len(parts)!=6 or parts[:2]!=('git','checkouts') or target.replace(chr(92),'/')!='../LICENSE':return None
 matches=[r for r in LICENSE_RULES if re.fullmatch(re.escape(r[0])+'-[0-9a-f]+',parts[2]) and len(parts[3])>=7 and r[1].startswith(parts[3]) and parts[4:]==r[2]]
 return matches[0] if len(matches)==1 else None
def qualified_license_link(relative,target,license_blob):
 rule=license_rule(relative,target)
 return rule is not None and license_blob==rule[3]

def git_blob_identity(data):
 return hashlib.sha1(b'blob '+str(len(data)).encode()+bytes([0])+data).hexdigest()
def normalized_license_blob(data):
 data.decode('utf-8')
 return git_blob_identity(data.replace(bytes([13,10]),bytes([10])))
def limits(free,used,elapsed,log):
 if free<MIN_FREE:return 'FREE_SPACE_GUARD'
 if used>MAX_OUTPUT:return 'OUTPUT_THRESHOLD'
 if elapsed>MAX_SECONDS:return 'TRIAL_DEADLINE'
 if log>MAX_LOG:return 'COMMAND_LOG_THRESHOLD'
 return None
def clean_env(parent,work):
 keys=('SystemRoot','WINDIR','COMSPEC','PATHEXT','PATH','PROCESSOR_ARCHITECTURE','NUMBER_OF_PROCESSORS','PROGRAMFILES','PROGRAMFILES(X86)','RUSTUP_HOME','CARGO_HOME','RUSTUP_TOOLCHAIN','RUSTUP_AUTO_INSTALL','JAVA_HOME_17_X64','ANDROID_HOME')
 e={k:parent[k] for k in keys if k in parent}
 e.update(TEMP=str(work/'tmp'),TMP=str(work/'tmp'),HOME=str(work/'home'),USERPROFILE=str(work/'profile'),APPDATA=str(work/'profile/AppData/Roaming'),LOCALAPPDATA=str(work/'profile/AppData/Local'),CARGO_TARGET_DIR=str(work/'target'),CARGO_INCREMENTAL='0',CARGO_PROFILE_CI_TEST_DEBUG='0',CARGO_BUILD_JOBS='2',CMAKE_BUILD_PARALLEL_LEVEL='2',NUM_JOBS='2',RAYON_NUM_THREADS='2',CARGO_NET_RETRY='1',CARGO_HTTP_TIMEOUT='60',CARGO_NET_GIT_FETCH_WITH_CLI='true',GIT_TERMINAL_PROMPT='0',GCM_INTERACTIVE='Never',GCM_TRACE='0',GIT_TRACE='0')
 return e
def android_env(base,ndk):
 e=base.copy();tool=ndk/'toolchains/llvm/prebuilt/windows-x86_64/bin'
 e.update(ANDROID_NDK_HOME=str(ndk),ANDROID_NDK_ROOT=str(ndk),ANDROID_NDK=str(ndk),CARGO_TARGET_AARCH64_LINUX_ANDROID_LINKER=str(tool/'clang.exe'),CC_aarch64_linux_android=str(tool/'clang.exe'),CXX_aarch64_linux_android=str(tool/'clang++.exe'),AR_aarch64_linux_android=str(tool/'llvm-ar.exe'),CFLAGS_aarch64_linux_android='--target=aarch64-linux-android29',CXXFLAGS_aarch64_linux_android='--target=aarch64-linux-android29',CXXSTDLIB_aarch64_linux_android='c++_static')
 e['CARGO_ENCODED_RUSTFLAGS']='\x1f'.join(['-C','link-arg=--target=aarch64-linux-android29','-C','link-arg=-Wl,-z,max-page-size=16384','-C','debuginfo=0'])
 return e
def artifact(text):
 found=[]
 for line in text.splitlines():
  try:x=json.loads(line)
  except ValueError:continue
  if x.get('reason')=='compiler-artifact' and x.get('target',{}).get('name')=='codex_app_server_transport' and x.get('profile',{}).get('test') and x.get('executable'):found.append(pathlib.Path(x['executable']))
 assert len(set(found))==1,'EXPECTED_ONE_NATIVE_TEST_EXECUTABLE'
 return found[0]
def test_count(text):
 m=re.search(r'test result: ok\. (\d+) passed; 0 failed; (\d+) ignored;',text)
 assert m and int(m[1])>0 and int(m[2])==0,'EMPTY_FAILED_OR_IGNORED_TEST_FILTER'
 return int(m[1])
def redact(text):
 text=re.sub(r'(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})','<redacted-token-shape>',text)
 text=re.sub(r'(?i)C:\\Users\\[^\\\r\n]+',r'<runner-profile>',text)
 return text
class Guard:
 def __init__(self,root,work,out,env):
  self.root=root;self.work=work;self.out=out;self.env=env;self.start=time.monotonic();self.count=0;self.peak=0;self.races=0
  self.roots=[work,out,pathlib.Path(env['CARGO_HOME']),pathlib.Path(env['RUSTUP_HOME'])]
  assert shutil.disk_usage(root).free>=MIN_FREE+MAX_OUTPUT,'INSUFFICIENT_INITIAL_TRIAL_RESERVATION'
  self.qualified_links=set();self.commands=[];self.pending_reparse=None;self.reparse_result=None;self.alias_baseline=None;self.alias_last_result=None;self.alias_failure=None;self.alias_passes=0;self.alias_charged_bytes=0;self.check()
 def _leased_pass(self):
  holder={}
  def scan(report):
   key=lease_key(report);compare_baseline(self.alias_baseline,key);holder['key']=key;holder['bytes']=self._walk(report);return holder['bytes']
  result=capture_reparse_metadata(self.work,EXPECTED_ALIAS,callback=scan);self.alias_last_result=result
  if result.get('state')=='PASS_EXACT_ALIAS_LEASED_ACCOUNTING_METADATA':
   key=lease_key(result);compare_baseline(self.alias_baseline,key);compare_baseline(holder.get('key'),key)
   assert result.get('leasedScanCompleted') is True and 'bytes' in holder,'INCOMPLETE_LEASED_ACCOUNTING'
   first=self.alias_baseline is None;self.alias_baseline=key;self.alias_passes+=1;self.alias_charged_bytes=ALIAS_METADATA_BYTES
   if first:print('QUALIFIED_JOB_ALIAS_ACCOUNTING '+json.dumps({'alias':EXPECTED_ALIAS,'independentTarget':EXPECTED_TARGET,'aliasIdentity':result['fileIdentity'],'targetIdentity':result['physicalTargetIdentity'],'reparseTag':result['reparseTagHex'],'targetTag':result['physicalTargetTagHex'],'rawRecordSHA256':result['rawRecordSHA256'],'aliasMetadataBytes':ALIAS_METADATA_BYTES,'aliasTraversed':False,'sameVolumeRegularAncestors':result['physicalAncestorCount']}),flush=True)
   return holder['bytes']
  if self.alias_baseline is None and safe_absence(result):return None
  raise AssertionError('ALIAS_METADATA_ACCOUNTING_STOP:'+result.get('state','UNKNOWN')+':'+str(result.get('osError',result.get('reason','UNQUALIFIED'))))
 def size(self):
  if self.alias_failure is not None:raise AssertionError(self.alias_failure)
  try:
   disjoint_roots(self.roots)
   for attempt in range(2):
    total=self._leased_pass()
    if total is not None:return total
    try:total=self._walk(None)
    except AliasAppeared:continue
    # Ensure an alias that appeared after the bare snapshot is scanned only under a lease.
    after=self._leased_pass()
    return after if after is not None else total
   raise AssertionError('ALIAS_APPEARANCE_OR_IDENTITY_RACE')
  except (AssertionError,OSError,RuntimeError) as error:
   self.alias_failure=str(error)[:300];raise
 def _walk(self,lease):
  total=0;alias_visits=0;target_visits=0
  def walk_error(error):raise error
  for root in self.roots:
   assert not root.is_symlink() and not root.is_junction(),'UNQUALIFIED_ACCOUNTING_ROOT_LINK'
   assert root.exists(),'ACCOUNTING_ROOT_MISSING'
   for folder,dirs,files in os.walk(root,followlinks=False,onerror=walk_error):
    if root==self.work and pathlib.Path(folder)==self.work/EXPECTED_TARGET:target_visits+=1
    for name in list(dirs):
     d=pathlib.Path(folder)/name
     if d.is_symlink() or d.is_junction():
      if root==self.work and exact_alias(d.relative_to(root)):
       if lease is None:raise AliasAppeared('EXACT_ALIAS_APPEARED_DURING_UNLEASED_SNAPSHOT')
       alias_visits+=1;assert alias_visits==1,'DUPLICATE_ALIAS_ENUMERATION';dirs.remove(name);total+=ALIAS_METADATA_BYTES;continue
      self.pending_reparse=(root,d.relative_to(root))
      raise AssertionError('UNQUALIFIED_OUTPUT_DIRECTORY_LINK:'+str(d.relative_to(root)))
    for name in files:
     p=pathlib.Path(folder)/name
     try:
      assert not p.is_junction(),'UNQUALIFIED_OUTPUT_FILE_JUNCTION'
      if p.is_symlink():
       cargo=pathlib.Path(self.env['CARGO_HOME']);relative=p.relative_to(cargo).as_posix();target=os.readlink(p)
       rule=license_rule(relative,target);assert rule is not None,'UNQUALIFIED_OUTPUT_FILE_LINK:'+relative
       sibling=p.parent.parent/'LICENSE';assert sibling.is_file() and not sibling.is_symlink(),'PINNED_LICENSE_TARGET_NOT_REGULAR'
       for ancestor in sibling.parents:
        assert not ancestor.is_symlink() and not ancestor.is_junction(),'PINNED_LICENSE_ANCESTOR_LINK'
        if ancestor==cargo:break
       assert sibling.stat().st_size<=32768,'PINNED_LICENSE_SIZE_LIMIT'
       data=sibling.read_bytes();assert len(data.replace(bytes([13,10]),bytes([10])))==rule[4],'PINNED_LICENSE_SIZE_CHANGED';blob=normalized_license_blob(data)
       assert qualified_license_link(relative,target,blob),'PINNED_LICENSE_IDENTITY_CHANGED'
       total+=max(4096,p.lstat().st_size)
       self.qualified_links.add(relative)
      else:total+=p.stat().st_size
     except FileNotFoundError:
      if lease is not None and root==self.work and p.is_relative_to(self.work/EXPECTED_TARGET):raise AssertionError('IE_TARGET_FILE_SNAPSHOT_RACE')
      self.races+=1
  if lease is not None:assert alias_visits==1 and target_visits==1,'ALIAS_OR_INDEPENDENT_TARGET_ENUMERATION_COUNT'
  return total
 def check(self,log=0):
  used=self.size();self.peak=max(self.peak,used);elapsed=time.monotonic()-self.start
  reason=limits(shutil.disk_usage(self.root).free,used,elapsed,log)
  assert not reason,reason
  return elapsed,used
 def report(self):
  return {'elapsedSeconds':round(time.monotonic()-self.start,3),'retainedPeakBytes':self.peak,'monitoredOutputThresholdBytes':MAX_OUTPUT,'minimumFreeBytes':MIN_FREE,'maximumSeconds':MAX_SECONDS,'snapshotDisappearanceRaces':self.races,'hardCumulativeWriteQuota':False,'qualifiedPinnedLicenseLinks':sorted(self.qualified_links),'directoryAliasAccounting':{'qualifiedPasses':self.alias_passes,'aliasMetadataBytesPerPass':self.alias_charged_bytes,'aliasTraversed':False,'lastMetadataState':(self.alias_last_result or {}).get('state'),'latchedFailure':self.alias_failure},'commands':self.commands,'signed':False,'releasable':False}
 def run(self,args,cwd=None,env=None,capture=False,timeout=None):
  self.check();self.count+=1;index=self.count;label=pathlib.Path(str(args[0])).name
  stdout=self.work/f'command-{index:02d}.stdout.log';stderr=self.work/f'command-{index:02d}.stderr.log'
  print(f'TRIAL_STAGE {index} {label}',flush=True);proc=None;started=time.monotonic();last=started;code=None
  try:
   with stdout.open('xb') as a,stderr.open('xb') as b:
    proc=subprocess.Popen([str(x) for x in args],cwd=cwd or self.root,env=env or self.env,stdout=a,stderr=b)
    while True:
     assert timeout is None or time.monotonic()-started<=timeout,'COMMAND_DEADLINE'
     elapsed,used=self.check(stdout.stat().st_size+stderr.stat().st_size)
     if proc.poll() is not None:break
     if time.monotonic()-last>=30:
      print(f'TRIAL_PROGRESS stage={index} elapsed={int(elapsed)} retainedBytes={used} freeBytes={shutil.disk_usage(self.root).free}',flush=True);last=time.monotonic()
     time.sleep(5)
   code=proc.returncode;self.check(stdout.stat().st_size+stderr.stat().st_size)
   assert code==0,'SUBPROCESS_FAILED'
   result=subprocess.CompletedProcess(args,code,stdout.read_text(encoding='utf-8',errors='replace') if capture else None,stderr.read_text(encoding='utf-8',errors='replace') if capture else None)
   self.commands.append({'stage':index,'tool':label,'exit':code,'seconds':round(time.monotonic()-started,3)})
   (self.work/'trial-progress.json').write_text(json.dumps(self.report(),indent=2),encoding='utf-8')
   return result
  except BaseException as error:
   if proc and proc.poll() is None:
    subprocess.run([str(pathlib.Path(os.environ['SystemRoot'])/'System32/taskkill.exe'),'/PID',str(proc.pid),'/T','/F'],capture_output=True,timeout=20)
    proc.wait(timeout=10)
   if self.pending_reparse and self.reparse_result is None:
    root,relative=self.pending_reparse
    self.reparse_result=capture_reparse_metadata(root,relative)
    self.reparse_result.update(commandStage=index,observedDuringTool=label,phaseProcessId=proc.pid if proc else None,creatorProcessProven=False,childStoppedBeforeMetadata=proc is None or proc.poll() is not None)
    payload=json.dumps(self.reparse_result,indent=2);assert len(payload.encode())<=65536 and shutil.disk_usage(self.root).free>=MIN_FREE,'METADATA_REPORT_BOUND'
    with (self.work/'reparse-stop.json').open('x',encoding='utf-8') as f:f.write(payload)
    print('REPARSE_METADATA_STOP '+json.dumps(self.reparse_result),flush=True)
   tails={}
   for name,path in [('stdoutTail',stdout),('stderrTail',stderr)]:
    if path.exists():
     with path.open('rb') as f:f.seek(max(0,path.stat().st_size-16000));tails[name]=redact(f.read().decode('utf-8',errors='replace'))
   report={**self.report(),'state':'FAILED_PARTIALS_PRESERVED','failedStage':index,'tool':label,'exit':code,'category':str(error)[:200],**tails}
   (self.work/'failure-summary.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
   print(json.dumps(report,indent=2),flush=True)
   raise

