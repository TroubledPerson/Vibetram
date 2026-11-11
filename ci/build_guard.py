"""Monitored hosted unsigned-trial helpers; no signing or credential access."""
import pathlib,os,subprocess,time,shutil,json,re,hashlib,stat,sys,uuid
from census_supervisor import Sampler,run_census,CensusFailure,OwnedProcess
from reparse_metadata import capture as capture_reparse_metadata,EXPECTED_ALIAS,EXPECTED_TARGET
from scratch_snapshot import ScratchTracker,IncompleteScratchSnapshot,eligible as eligible_scratch,MAX_ATTEMPTS,MAX_INTERRUPTS
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

RUST_TOOLCHAIN='1.95.0-x86_64-pc-windows-msvc'
def pinned_large_lld(path,before,binding,environment):
 """Only the official-byte-pinned LLD under this job's provisioned Rust root.
 Caller must retain this exact file identity and compare subsequent snapshots.
 """
 assert isinstance(binding,dict) and set(binding)=={'path','identity','bytes','sha256'},'LARGE_LLD_BINDING_SCHEMA'
 home=pathlib.Path(environment.get('RUSTUP_HOME',''));expected=home/'toolchains/1.95.0-x86_64-pc-windows-msvc/lib/rustlib/x86_64-pc-windows-msvc/bin/rust-lld.exe'
 assert home.is_absolute() and '..' not in home.parts and environment.get('VIBETRAM_PROVISIONED_RUST')=='1','LARGE_LLD_PROVISIONED_ROOT'
 assert path==expected and binding['path']==str(expected),'LARGE_LLD_EXACT_PATH'
 assert binding['identity']==[before.st_dev,before.st_ino] and all(type(x) is int for x in binding['identity']),'LARGE_LLD_EXACT_IDENTITY'
 assert binding['bytes']==before.st_size==113349120,'LARGE_LLD_EXACT_LENGTH'
 assert binding['sha256']=='3cf499fc8a03853722d19e3ae1c5cdd143ac7426f1405b9e6efacd7a94b7328a','LARGE_LLD_OFFICIAL_HASH_PIN'
 return binding['sha256']

def executable_snapshot(path,sample=None,*,large_lld_binding=None,large_ndk_binding=None,large_ndk_compiler_binding=None):
 """Fresh no-follow identity, hash and regular ancestry for a selected input.
 This is a checked launch binding, not protection from every filesystem race.
 Existing pinned compiler-version checks remain mandatory after resolution.
 """
 p=pathlib.Path(path);assert p.is_absolute() and '..' not in p.parts and len(p.parts)<=32,'EXECUTABLE_ABSOLUTE_SCOPE'
 chain=[]
 for directory in reversed(p.parents):
  m=directory.lstat();assert stat.S_ISDIR(m.st_mode) and not getattr(m,'st_file_attributes',0)&0x400 and not getattr(m,'st_reparse_tag',0),'EXECUTABLE_ANCESTOR_LINK_OR_TYPE'
  chain.append((directory,(m.st_dev,m.st_ino,m.st_mode,getattr(m,'st_reparse_tag',0))))
 before=p.lstat();assert stat.S_ISREG(before.st_mode) and not getattr(before,'st_file_attributes',0)&0x400 and not getattr(before,'st_reparse_tag',0),'EXECUTABLE_LINK_OR_TYPE'
 pinned_digest=None
 if large_ndk_compiler_binding is not None:
  assert large_lld_binding is None and large_ndk_binding is None,'AMBIGUOUS_LARGE_EXECUTABLE_BINDING'
  from ndk_compilers import pinned as pinned_compiler
  pinned_digest=pinned_compiler(p,before,large_ndk_compiler_binding)
 elif large_ndk_binding is not None:
  assert large_lld_binding is None,'AMBIGUOUS_LARGE_EXECUTABLE_BINDING'
  from ndk_linker import pinned
  pinned_digest=pinned(p,before,large_ndk_binding)
 elif large_lld_binding is not None:pinned_digest=pinned_large_lld(p,before,large_lld_binding,os.environ)
 else:assert 64<=before.st_size<=64*1024**2,'EXECUTABLE_SIZE_BOUND'
 with p.open('rb') as f:
  assert f.read(2)==b'MZ','EXECUTABLE_PE_HEADER';f.seek(0);digest=hashlib.sha256();last=time.monotonic()
  if sample:sample()
  while chunk:=f.read(1024**2):
   digest.update(chunk)
   if sample and time.monotonic()-last>=.1:sample();last=time.monotonic()
  digest=digest.hexdigest()
  if sample:sample()
 if pinned_digest is not None:assert digest==pinned_digest,'LARGE_EXECUTABLE_PIN_HASH_MISMATCH' if large_ndk_binding is not None or large_ndk_compiler_binding is not None else 'LARGE_LLD_ARCHIVE_HASH_MISMATCH'
 after=p.lstat();key=lambda m:(m.st_dev,m.st_ino,m.st_size,m.st_mtime_ns,m.st_mode,getattr(m,'st_reparse_tag',0))
 assert key(before)==key(after),'EXECUTABLE_IDENTITY_CHANGED'
 for directory,identity in chain:
  m=directory.lstat();assert (m.st_dev,m.st_ino,m.st_mode,getattr(m,'st_reparse_tag',0))==identity and not getattr(m,'st_file_attributes',0)&0x400,'EXECUTABLE_ANCESTOR_CHANGED'
 return {'identity':[after.st_dev,after.st_ino],'bytes':after.st_size,'modifiedNs':after.st_mtime_ns,'sha256':digest}

def qualified_executable(args,env,sample=None):
 """Only existing Rust bare entry points may resolve through clean PATH.
 Reject a different/ambiguous binary rather than searching the parent process
 environment, current directory, PATHEXT scripts, or downloading a tool.
 """
 assert args,'EMPTY_COMMAND';name=str(args[0])
 if pathlib.Path(name).is_absolute():return list(args),None
 assert name.lower() in ('cargo','rustc','cargo.exe','rustc.exe'),'UNQUALIFIED_BARE_EXECUTABLE'
 assert env.get('RUSTUP_TOOLCHAIN')==RUST_TOOLCHAIN and env.get('RUSTUP_AUTO_INSTALL')=='0','PINNED_RUST_ENV_REQUIRED'
 rustup=pathlib.Path(env.get('RUSTUP_HOME',''));cargo=pathlib.Path(env.get('CARGO_HOME',''))
 assert rustup.is_absolute() and cargo.is_absolute(),'PINNED_RUST_HOME_REQUIRED'
 filename=name.lower().removesuffix('.exe')+'.exe';path=env.get('PATH','');parts=[x for x in path.split(os.pathsep) if x]
 assert path and len(parts)<=256 and all(x and pathlib.Path(x).is_absolute() and '..' not in pathlib.Path(x).parts for x in parts),'QUALIFIED_PATH_REQUIRED'
 hits={}
 for directory in parts:
  candidate=pathlib.Path(directory)/filename
  try:m=candidate.lstat()
  except FileNotFoundError:continue
  assert stat.S_ISREG(m.st_mode) and not getattr(m,'st_file_attributes',0)&0x400 and not getattr(m,'st_reparse_tag',0),'PATH_EXECUTABLE_UNQUALIFIED'
  hits.setdefault(os.path.normcase(os.path.normpath(str(candidate))),candidate)
 assert len(hits)==1,'MISSING_OR_AMBIGUOUS_PATH_EXECUTABLE'
 selected=next(iter(hits.values()));identity=executable_snapshot(selected,sample)
 pinned=rustup/'toolchains'/RUST_TOOLCHAIN/'bin'/filename;pinned_identity=executable_snapshot(pinned,sample)
 if os.path.normcase(str(selected))==os.path.normcase(str(pinned)):route='PINNED_NATIVE_ON_PATH'
 else:
  # Official rustup multicall proxies are byte-identical to their adjacent
  # rustup executable. Pinned env selects the installed toolchain, never fetch.
  proxy=executable_snapshot(selected.with_name('rustup.exe'),sample);assert identity['sha256']==proxy['sha256'],'UNQUALIFIED_RUSTUP_PROXY';route='PINNED_RUSTUP_PROXY_ON_PATH'
 assert executable_snapshot(selected,sample)==identity and executable_snapshot(pinned,sample)==pinned_identity,'EXECUTABLE_BINDING_CHANGED'
 return [str(selected),*args[1:]],{'tool':filename,'route':route,'toolchain':RUST_TOOLCHAIN,'selected':identity,'pinned':pinned_identity,'versionRecheckRequired':True}

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
def fresh_entry(path):
 meta=os.lstat(path)
 assert type(meta.st_file_attributes) is int and type(meta.st_reparse_tag) is int,'UNQUALIFIED_ENTRY_METADATA'
 assert type(meta.st_size) is int and meta.st_size>=0,'INVALID_ENTRY_SIZE'
 return meta

class OrdinaryScratchChurn(RuntimeError):
 def __init__(self,relative,partial):
  assert type(partial) is int and partial>=0
  self.relative=relative;self.partial=partial
  super().__init__('ORDINARY_COMPILER_SNAPSHOT_INVALIDATED')
def compiler_scratch_root(work,path):
 try:r=pathlib.PureWindowsPath(path).relative_to(pathlib.PureWindowsPath(work)).parts
 except ValueError:return False
 return r in (('target','ci-test','deps'),('target','aarch64-linux-android','ci-test','deps'))
def qualified_ordinary_churn(work,path,error):
 return type(getattr(error,'winerror',None)) is int and error.winerror==2 and isinstance(error,FileNotFoundError) and compiler_scratch_root(work,path.parent) and re.fullmatch(r'[A-Za-z0-9_.-]{1,240}\.rcgu\.o',path.name) is not None

class Guard:
 def __init__(self,root,work,out,env):
  self._setup(root,work,out,env)
  assert shutil.disk_usage(root).free>=MIN_FREE+MAX_OUTPUT,'INSUFFICIENT_INITIAL_TRIAL_RESERVATION'
  self.check()
 def _setup(self,root,work,out,env):
  self.root=root;self.work=work;self.out=out;self.env=env;self.start=time.monotonic();self.count=0;self.peak=0;self.races=0
  self.roots=[work,out,pathlib.Path(env['CARGO_HOME']),pathlib.Path(env['RUSTUP_HOME'])]
  self.qualified_links=set();self.commands=[];self.pending_reparse=None;self.reparse_result=None;self.alias_baseline=None;self.alias_last_result=None;self.alias_failure=None;self.alias_passes=0;self.alias_charged_bytes=0;self.scratch_baselines={};self.scratch_parent_baselines={};self.last_completed_root_scans=[];self.accepted_snapshot_peak=0;self.ordinary_churn_count=0;self.recent_churn=[];self.snapshot_deadline=None;self.root_scans=[];self.enumeration_resource_checks=0;self.active_log_bytes=0;self.snapshot_incomplete=0;self.last_completed_bytes=None;self.last_snapshot_complete=False;self._sampler=None;self._log_paths=[];self.census_generation=0;self.census_pending=False;self.last_census_at=None;self.census_walk_count=0;self.supervision_samples=0;self.supervision_max_gap=0;self._command_deadline=None;self.worker_mode=False;self.census_cleanup_failures=[];self.census_location={'phase':'NOT_STARTED'};self.census_failure_diagnostic=None
 def _census_at(self,phase,root=None,path=None):
  self.census_location={"phase":phase}
  if root is not None and root in self.roots:
   self.census_location["rootIndex"]=self.roots.index(root)
   if path is not None:
    try:self.census_location["relative"]=path.relative_to(root).as_posix()
    except ValueError:pass
 def _leased_pass(self):
  self._census_at("ALIAS_METADATA",self.work,self.work/EXPECTED_ALIAS)
  holder={}
  def scan(report):
   key=lease_key(report);compare_baseline(self.alias_baseline,key)
   if self.alias_baseline is None:self.alias_baseline=key
   holder['key']=key;holder['bytes']=self._walk(report);return holder['bytes']
  result=capture_reparse_metadata(self.work,EXPECTED_ALIAS,callback=scan,**({'census_deadline':self.snapshot_deadline} if getattr(self,'worker_mode',False) else {}));self.alias_last_result=result
  if result.get('state')=='PASS_EXACT_ALIAS_LEASED_ACCOUNTING_METADATA':
   key=lease_key(result);compare_baseline(self.alias_baseline,key);compare_baseline(holder.get('key'),key)
   assert result.get('leasedScanCompleted') is True and 'bytes' in holder,'INCOMPLETE_LEASED_ACCOUNTING'
   first=self.alias_passes==0;self.alias_baseline=key;self.alias_passes+=1;self.alias_charged_bytes=ALIAS_METADATA_BYTES
   if first:print('QUALIFIED_JOB_ALIAS_ACCOUNTING '+json.dumps({'alias':EXPECTED_ALIAS,'independentTarget':EXPECTED_TARGET,'aliasIdentity':result['fileIdentity'],'targetIdentity':result['physicalTargetIdentity'],'reparseTag':result['reparseTagHex'],'targetTag':result['physicalTargetTagHex'],'rawRecordSHA256':result['rawRecordSHA256'],'aliasMetadataBytes':ALIAS_METADATA_BYTES,'aliasTraversed':False,'sameVolumeRegularAncestors':result['physicalAncestorCount']}),flush=True)
   return holder['bytes']
  if self.alias_baseline is None and safe_absence(result):return None
  raise AssertionError('ALIAS_METADATA_ACCOUNTING_STOP:'+result.get('state','UNKNOWN')+':'+str(result.get('osError',result.get('reason','UNQUALIFIED'))))
 def scan_epoch(self,deadline):
  self.worker_mode=True;self.census_walk_count=0
  self.snapshot_deadline=deadline
  try:
   for attempt in range(2):
    self._enumeration_resources(0)
    try:
     total=self._size_once();self._enumeration_resources(total);return total
    except (OrdinaryScratchChurn,IncompleteScratchSnapshot) as error:
     self.last_snapshot_complete=False
     partial=error.partial if isinstance(error,OrdinaryScratchChurn) else error.partial_bytes+error.allocation_bytes
     self.peak=max(self.peak,partial);self.snapshot_incomplete+=1
     if isinstance(error,OrdinaryScratchChurn):self.ordinary_churn_count+=1
     assert self.snapshot_incomplete<=256,'CENSUS_CHURN_GLOBAL_BOUND'
     self.recent_churn=(self.recent_churn+[{'attempt':attempt+1,'confirmedPartialBytes':partial,'unmeasuredResidualBytes':None,'completedTotalReported':False}])[-2:]
     self._enumeration_resources(partial)
   raise AssertionError('CENSUS_TWO_ATTEMPTS_EXHAUSTED')
  finally:self.snapshot_deadline=None
 def size(self):
  if self.alias_failure is not None:raise AssertionError(self.alias_failure)
  self.snapshot_deadline=time.monotonic()+5
  try:
   for attempt in range(3):
    self._enumeration_resources(0)
    try:
     total=self._size_once();self._enumeration_resources(total);return total
    except OrdinaryScratchChurn as error:
     self.last_snapshot_complete=False
     self.peak=max(self.peak,error.partial)
     self.ordinary_churn_count=getattr(self,'ordinary_churn_count',0)+1
     assert self.ordinary_churn_count<=256,'ORDINARY_CHURN_GLOBAL_BOUND'
     event={'attempt':attempt+1,'relative':error.relative,'confirmedPartialBytes':error.partial,'unmeasuredResidualBytes':None,'completedTotalReported':False,'discardedRootScans':getattr(self,'root_scans',[])}
     self.recent_churn=(getattr(self,'recent_churn',[])+[event])[-3:]
     self._enumeration_resources(error.partial)
     print('INVALIDATED_ORDINARY_SNAPSHOT '+json.dumps(event),flush=True)
   raise AssertionError('ORDINARY_CHURN_RESCAN_BOUND')
  except (IncompleteScratchSnapshot,OrdinaryScratchChurn):raise
  except (AssertionError,OSError,RuntimeError) as error:
   self.alias_failure=str(error)[:300];raise
  finally:self.snapshot_deadline=None
 def _size_once(self):
  if self.alias_failure is not None:raise AssertionError(self.alias_failure)
  try:
   self._census_at("ROOT_DISJOINT_VALIDATION");disjoint_roots(self.roots)
   for attempt in range(2):
    total=self._leased_pass()
    if total is not None:return total
    try:total=self._walk(None)
    except AliasAppeared:continue
    # Ensure an alias that appeared after the bare snapshot is scanned only under a lease.
    after=self._leased_pass()
    return after if after is not None else total
   raise AssertionError('ALIAS_APPEARANCE_OR_IDENTITY_RACE')
  except (IncompleteScratchSnapshot,OrdinaryScratchChurn):raise
  except (AssertionError,OSError,RuntimeError) as error:
   self.alias_failure=str(error)[:300];raise
 def _enumeration_resources(self,partial):
  self._census_at("ENUMERATION_RESOURCE_CHECK")
  self.enumeration_resource_checks=getattr(self,'enumeration_resource_checks',0)+1
  self.peak=max(self.peak,partial)
  reason=limits(shutil.disk_usage(self.root).free,self.peak,time.monotonic()-self.start,getattr(self,'active_log_bytes',0))
  assert not reason,reason
  progress=getattr(self,'_census_progress',None)
  if progress:progress(self.peak)
  deadline=getattr(self,'snapshot_deadline',None)
  assert deadline is None or time.monotonic()<deadline,'SNAPSHOT_VALIDATION_DEADLINE'
 def _walk(self,lease):
  if getattr(self,'worker_mode',False):
   assert self.census_walk_count<2,'CENSUS_TWO_WALKS_EXHAUSTED'
   self.census_walk_count+=1
  self.root_scans=[]
  self._census_at('SCRATCH_TRACKER_OPEN',self.work,self.work)
  with ScratchTracker(self.work,self.scratch_baselines,self.scratch_parent_baselines) as scratch:return self._walk_tracked(lease,scratch)
 def _walk_tracked(self,lease,scratch):
  total=0;alias_visits=0;target_visits=0
  observed_dirs=set()
  def walk_error(error):
   path=pathlib.Path(error.filename) if getattr(error,'filename',None) else None
   self._census_at("DIRECTORY_ENUMERATION",root,path)
   if root==self.work and path in observed_dirs and compiler_scratch_root(self.work,path.parent) and isinstance(error,FileNotFoundError) and getattr(error,'winerror',None) in (2,3):
    scratch.verify_parents();raise OrdinaryScratchChurn(path.relative_to(self.work).as_posix(),total)
   raise error
  for index,root in enumerate(self.roots):
   begin=time.monotonic();last=begin;since=0;before=total
   row={'rootIndex':index,'ordinaryFileEntries':0,'directoryEntries':0,'scratchLeaves':0,'complete':False,'completedRootBytes':None}
   self.root_scans.append(row)
   def tick(force=False):
    nonlocal last,since
    now=time.monotonic()
    if force or since>=256 or now-last>=0.25:
     self._enumeration_resources(total);last=now;since=0
   try:
    tick(True)
    self._census_at('ROOT_METADATA',root,root)
    assert not root.is_symlink() and not root.is_junction(),'UNQUALIFIED_ACCOUNTING_ROOT_LINK'
    assert root.exists(),'ACCOUNTING_ROOT_MISSING'
    for folder,dirs,files in os.walk(root,followlinks=False,onerror=walk_error):
     if root==self.work and compiler_scratch_root(self.work,pathlib.Path(folder)):self._census_at("SCRATCH_PARENT_LEASE",root,pathlib.Path(folder));scratch.lease_parent(pathlib.Path(folder));scratch.verify_parents()
     if root==self.work and pathlib.Path(folder)==self.work/EXPECTED_TARGET:target_visits+=1
     self._census_at("DIRECTORY_ENUMERATION",root,pathlib.Path(folder))
     for name in list(dirs):
      d=pathlib.Path(folder)/name
      self._census_at("DIRECTORY_ENTRY_METADATA",root,d)
      try:meta=fresh_entry(d)
      except FileNotFoundError as error:
       if root==self.work and compiler_scratch_root(self.work,d.parent) and getattr(error,'winerror',None)==2:
        scratch.verify_parents();raise OrdinaryScratchChurn(d.relative_to(self.work).as_posix(),total)
       raise
      row['directoryEntries']+=1;since+=1
      if meta.st_file_attributes&0x400:
       if root==self.work and exact_alias(d.relative_to(root)):
        if lease is None:raise AliasAppeared('EXACT_ALIAS_APPEARED_DURING_UNLEASED_SNAPSHOT')
        alias_visits+=1;assert alias_visits==1,'DUPLICATE_ALIAS_ENUMERATION';dirs.remove(name);total+=ALIAS_METADATA_BYTES;tick();continue
       self.pending_reparse=(root,d.relative_to(root))
       raise AssertionError('UNQUALIFIED_OUTPUT_DIRECTORY_LINK:'+str(d.relative_to(root)))
      assert stat.S_ISDIR(meta.st_mode) and meta.st_reparse_tag==0,'DIRECTORY_ENTRY_TYPE_OR_TAG_CHANGED'
      observed_dirs.add(d)
      if root==self.work and compiler_scratch_root(self.work,d):self._census_at("SCRATCH_PARENT_LEASE",root,d);scratch.lease_parent(d);scratch.verify_parents()
      if root==self.work and eligible_scratch(self.work,d):
       self._census_at('SCRATCH_LEAF_SCAN',root,d)
       total+=scratch.scan(d,total);dirs.remove(name);row['scratchLeaves']+=1
      tick()
     for name in files:
      p=pathlib.Path(folder)/name
      self._census_at("FILE_ENTRY_METADATA",root,p)
      reading_entry=True
      try:
       meta=fresh_entry(p);reading_entry=False;row['ordinaryFileEntries']+=1;since+=1
       if meta.st_file_attributes&0x400:
        assert stat.S_ISLNK(meta.st_mode) and meta.st_reparse_tag==0xa000000c,'UNQUALIFIED_OUTPUT_FILE_JUNCTION'
        cargo=pathlib.Path(self.env['CARGO_HOME']);assert p.is_relative_to(cargo),'OUTPUT_LINK_OUTSIDE_PINNED_CACHE';relative=p.relative_to(cargo).as_posix();target=os.readlink(p)
        self._census_at('PINNED_LICENSE_CHECK',root,p);rule=license_rule(relative,target);assert rule is not None,'UNQUALIFIED_OUTPUT_FILE_LINK:'+relative
        sibling=p.parent.parent/'LICENSE';assert sibling.is_file() and not sibling.is_symlink(),'PINNED_LICENSE_TARGET_NOT_REGULAR'
        for ancestor in sibling.parents:
         assert not ancestor.is_symlink() and not ancestor.is_junction(),'PINNED_LICENSE_ANCESTOR_LINK'
         if ancestor==cargo:break
        assert sibling.stat().st_size<=32768,'PINNED_LICENSE_SIZE_LIMIT'
        data=sibling.read_bytes();assert len(data.replace(bytes([13,10]),bytes([10])))==rule[4],'PINNED_LICENSE_SIZE_CHANGED';blob=normalized_license_blob(data)
        assert qualified_license_link(relative,target,blob),'PINNED_LICENSE_IDENTITY_CHANGED'
        total+=max(4096,meta.st_size)
        self.qualified_links.add(relative)
       else:
        assert stat.S_ISREG(meta.st_mode) and meta.st_reparse_tag==0,'FILE_ENTRY_TYPE_OR_TAG_CHANGED'
        total+=meta.st_size
      except FileNotFoundError as error:
       if lease is not None and root==self.work and p.is_relative_to(self.work/EXPECTED_TARGET):raise AssertionError('IE_TARGET_FILE_SNAPSHOT_RACE')
       self.races+=1
       if reading_entry and root==self.work and qualified_ordinary_churn(self.work,p,error):
        scratch.verify_parents();raise OrdinaryScratchChurn(p.relative_to(self.work).as_posix(),total)
       raise AssertionError('UNVERIFIED_FILE_DISAPPEARANCE')
      tick()
    tick(True);row['complete']=True;row['completedRootBytes']=total-before
   finally:
    row['seconds']=round(time.monotonic()-begin,6);row['confirmedPartialRootBytes']=total-before
  if lease is not None:assert alias_visits==1 and target_visits==1,'ALIAS_OR_INDEPENDENT_TARGET_ENUMERATION_COUNT'
  return total
 def _resource_sample(self):
  assert self._command_deadline is None or time.monotonic()<=self._command_deadline,'COMMAND_DEADLINE'
  log=0
  for path in self._log_paths:
   meta=fresh_entry(path);assert stat.S_ISREG(meta.st_mode) and not meta.st_file_attributes&0x400 and meta.st_reparse_tag==0,'COMMAND_LOG_IDENTITY_UNQUALIFIED';log+=meta.st_size
  reason=limits(shutil.disk_usage(self.root).free,self.peak,time.monotonic()-self.start,log)
  assert not reason,reason
 def check(self,log=0):
  from census_worker import export_state,import_state,spec_hash
  self.census_generation+=1;self.census_pending=True
  spec={'root':str(self.root),'work':str(self.work),'out':str(self.out),'cargo':self.env['CARGO_HOME'],'rustup':self.env['RUSTUP_HOME'],'globalStart':self.start}
  request={'nonce':uuid.uuid4().hex,'generation':self.census_generation,'specHash':spec_hash(spec),'spec':spec,'state':export_state(self)}
  own=self._sampler is None
  if own:self._sampler=Sampler(self._resource_sample)
  try:
   def progress(n):self.peak=max(self.peak,n)
   result=run_census([sys.executable,'-B',str(pathlib.Path(__file__).with_name('census_worker.py'))],request,self._sampler,progress)
   assert isinstance(result,dict) and set(result)=={'bytes','state','rootCount','completedAt'},'INVALID_CENSUS_RESULT'
   used=result['bytes'];assert type(used) is int and 0<=used<=MAX_OUTPUT and result['rootCount']==len(self.roots),'INVALID_CENSUS_TOTAL'
   rows=result['state'].get('root_scans');assert isinstance(rows,list) and [r['rootIndex'] for r in rows]==list(range(len(self.roots))) and all(r['complete'] is True and type(r['completedRootBytes']) is int for r in rows),'INCOMPLETE_ROOT_CENSUS'
   peak=self.peak;import_state(self,result['state']);self.peak=max(peak,self.peak,used);self.root_scans=rows
   self.alias_last_result=result['state'].get('alias_last_result')
   self.last_completed_bytes=used;self.last_snapshot_complete=True;self.last_completed_root_scans=rows
   self.accepted_snapshot_peak=max(self.accepted_snapshot_peak,used);self.last_census_at=time.monotonic()
   self._sampler.tick();return self.last_census_at-self.start,used
  except BaseException as error:
   self.last_snapshot_complete=False;self.census_cleanup_failures=getattr(error,'cleanup_failures',[])
   payload=getattr(error,'payload',None)
   if isinstance(payload,dict) and payload.get('diagnostic') is not None:
    from census_supervisor import validate_census_diagnostic
    self.census_failure_diagnostic={**validate_census_diagnostic(payload['diagnostic']),'commandStage':self.count}
   if isinstance(payload,dict) and isinstance(payload.get('state'),dict):
    state=payload['state'];self.root_scans=state.get('root_scans',[]);self.alias_last_result=state.get('alias_last_result')
    for key in ('snapshot_incomplete','ordinary_churn_count','enumeration_resource_checks'):
     value=state.get(key,0);assert type(value) is int and value>=0,'INVALID_FAILURE_COUNTER';setattr(self,key,max(getattr(self,key),value))
    self.recent_churn=state.get('recent_churn',[])
    count=state.get('census_walk_count',0);assert type(count) is int and 0<=count<=2,'INVALID_WALK_COUNT';self.census_walk_count=count
    pending=state.get('pending_reparse')
    if pending:
     index=pending['rootIndex'];rel=pathlib.PurePosixPath(pending['relative']);assert type(index) is int and 0<=index<len(self.roots) and not rel.is_absolute() and '..' not in rel.parts
     self.pending_reparse=(self.roots[index],rel)
   self.alias_failure=str(error)[:200];raise
  finally:
   self.census_pending=False
   self.supervision_max_gap=max(self.supervision_max_gap,self._sampler.max_gap)
   if own:self.supervision_samples+=self._sampler.count;self._sampler=None
 def report(self):
  return {'elapsedSeconds':round(time.monotonic()-self.start,3),'censusPending':self.census_pending,'censusCleanupFailures':self.census_cleanup_failures,'censusFailureDiagnostic':self.census_failure_diagnostic,'lastCensusAgeSeconds':None if self.last_census_at is None else round(time.monotonic()-self.last_census_at,3),'currentAtomicTotalAvailable':False,'supervisionTargetSeconds':.25,'missedSupervisionLimitSeconds':1.0,'supervisionSamples':self.supervision_samples+(self._sampler.count if self._sampler else 0),'maximumObservedSupervisionGap':max(self.supervision_max_gap,self._sampler.max_gap if self._sampler else 0),'censusWindowSeconds':30,'censusAttemptBound':2,'lastReportedCensusWalkCount':self.census_walk_count,'retainedPeakBytes':self.peak,'monitoredOutputThresholdBytes':MAX_OUTPUT,'minimumFreeBytes':MIN_FREE,'maximumSeconds':MAX_SECONDS,'lastCompletedRootScans':self.last_completed_root_scans,'acceptedSnapshotPeakBytes':self.accepted_snapshot_peak,'ordinaryChurnInvalidations':self.ordinary_churn_count,'recentDiscardedSnapshots':self.recent_churn,'rootScans':self.root_scans,'enumerationResourceChecks':self.enumeration_resource_checks,'enumerationCheckMaxEntries':256,'enumerationCheckIntervalSeconds':0.25,'snapshotDisappearanceRaces':self.races,'churnInvalidatedCensusSnapshots':self.snapshot_incomplete,'lastSnapshotComplete':self.last_snapshot_complete,'lastCompletedSnapshotBytes':self.last_completed_bytes,'unmeasuredIncompleteResidualBytes':None,'peakIsExactHistoricalMaximum':False,'snapshotAttemptBound':2,'hardCumulativeWriteQuota':False,'qualifiedPinnedLicenseLinks':sorted(self.qualified_links),'directoryAliasAccounting':{'qualifiedPasses':self.alias_passes,'aliasMetadataBytesPerPass':self.alias_charged_bytes,'aliasTraversed':False,'lastMetadataState':(self.alias_last_result or {}).get('state'),'latchedFailure':self.alias_failure},'commands':self.commands,'signed':False,'releasable':False}
 def run(self,args,cwd=None,env=None,capture=False,timeout=None):
  self.check();self.count+=1;index=self.count;label=pathlib.Path(str(args[0])).name
  stdout=self.work/f'command-{index:02d}.stdout.log';stderr=self.work/f'command-{index:02d}.stderr.log'
  print(f'TRIAL_STAGE {index} {label}',flush=True);proc=None;started=time.monotonic();last=started;code=None;preclose_images=None;close_attempted=False;primary_error=None;self._command_deadline=None if timeout is None else started+timeout;self._sampler=Sampler(self._resource_sample)
  try:
   with stdout.open('xb') as a,stderr.open('xb') as b:
    self._log_paths=[stdout,stderr];self._sampler.tick()
    from host_linker import verify_runtime
    verify_runtime(env or self.env,self._sampler.tick)
    launch_args,executable_binding=qualified_executable([str(x) for x in args],env or self.env,self._sampler.tick)
    from process_image import remember
    self._sampler.tick();proc=OwnedProcess();proc.start(launch_args,cwd or self.root,env or self.env,stdout=a,stderr=b,image_capture=lambda p,h,row:remember(p,h,row,env or self.env,self._sampler.tick,launch_args[0] if row['pid']==p.initial['pid'] else None))
    next_census=time.monotonic()
    while True:
     assert timeout is None or time.monotonic()-started<=timeout,'COMMAND_DEADLINE'
     self._sampler.tick()
     if time.monotonic()>=next_census:
      elapsed,used=self.check();next_census=time.monotonic()+5
     else:elapsed=time.monotonic()-self.start;used=self.last_completed_bytes
     if proc.poll() is not None:break
     if time.monotonic()-last>=30:
      print(f'TRIAL_PROGRESS stage={index} elapsed={int(elapsed)} retainedBytes={used} freeBytes={shutil.disk_usage(self.root).free}',flush=True);last=time.monotonic()
     time.sleep(.25)
   code=proc.returncode;self._command_deadline=None
   from msvc_probe import compiler_completion
   compiler_completion(proc,launch_args,env or self.env,self.work,stdout,stderr,self._sampler)
   proc.finish(sampler=self._sampler);assert not proc.cleanup_errors,'OWNED_PROCESS_SUPERVISION_FAILED'
   verify_runtime(env or self.env,self._sampler.tick);self.check(stdout.stat().st_size+stderr.stat().st_size)
   assert code==0,'SUBPROCESS_FAILED'
   result=subprocess.CompletedProcess(args,code,stdout.read_text(encoding='utf-8',errors='replace') if capture else None,stderr.read_text(encoding='utf-8',errors='replace') if capture else None)
   from failure_lifecycle import capture_images
   from host_linker import failure_members
   preclose_images=capture_images(proc,lambda p:failure_members(p,env or self.env,self._sampler))
   assert preclose_images and all(r.get('heldIdentityVerified') is True for r in preclose_images),'PRE_CLOSE_OWNED_IMAGE_METADATA_INCOMPLETE'
   close_attempted=True;proc.close()
   self.commands.append({'stage':index,'tool':label,'exit':code,'seconds':round(time.monotonic()-started,3),'ownedJobTeardown':proc.teardown,'executableBinding':executable_binding})
   (self.work/'trial-progress.json').write_text(json.dumps(self.report(),indent=2),encoding='utf-8')
   return result
  except BaseException as error:
   primary_error=error;self._command_deadline=None
   from process_image import error_info
   primary_api=error_info(error)
   from failure_lifecycle import freeze_failure
   from host_linker import failure_members
   facts=freeze_failure(proc,lambda p:failure_members(p,env or self.env,self._sampler),self._sampler,code,preclose_images);close_attempted=proc is not None
   proof=facts['teardownDiagnostic']
   if not proof.get('processTreeExitIndependentlyVerified') and getattr(error,'owned_teardown',None):proof=error.owned_teardown;facts['teardownDiagnostic']=proof
   diagnostics=[];tails={}
   try:
    if not facts['teardownFailures'] and self.pending_reparse and self.reparse_result is None:
     root,relative=self.pending_reparse;self.reparse_result=capture_reparse_metadata(root,relative)
     self.reparse_result.update(commandStage=index,observedDuringTool=label,phaseProcessId=facts['phaseProcessId'],creatorProcessProven=False,childStoppedBeforeMetadata=facts['knownParentExitObserved'])
     payload=json.dumps(self.reparse_result,indent=2);assert len(payload.encode())<=65536 and shutil.disk_usage(self.root).free>=MIN_FREE,'METADATA_REPORT_BOUND'
     with (self.work/'reparse-stop.json').open('x',encoding='utf-8') as f:f.write(payload)
     print('REPARSE_METADATA_STOP '+payload,flush=True)
   except BaseException as diagnostic:diagnostics.append({'stage':'reparse-report','failureClass':type(diagnostic).__name__})
   for name,path in [('stdoutTail',stdout),('stderrTail',stderr)]:
    try:
     if path.exists():
      with path.open('rb') as f:f.seek(max(0,path.stat().st_size-16000));tails[name]=redact(f.read().decode('utf-8',errors='replace'))
    except BaseException as diagnostic:diagnostics.append({'stage':name,'failureClass':type(diagnostic).__name__})
   try:
    report={**self.report(),'state':'FAILED_PARTIALS_PRESERVED','failedStage':index,'tool':label,'exit':code,**facts,'diagnosticFailures':diagnostics,'primaryAPIFailure':primary_api,'processTreeExitIndependentlyVerified':proof.get('processTreeExitIndependentlyVerified',False),'censusWorkerTeardown':getattr(error,'census_teardown',None),'category':str(error)[:200],**tails}
    (self.work/'failure-summary.json').write_text(json.dumps(report,indent=2),encoding='utf-8');print(json.dumps(report,indent=2),flush=True)
   except BaseException as diagnostic:
    error.add_note('FAILURE_REPORT_FAILED:'+type(diagnostic).__name__)
    try:print(json.dumps({'state':'FAILURE_REPORT_INCOMPLETE','primaryFailureClass':type(error).__name__,'exit':code,'failedStage':index,'teardownDiagnostic':proof,'teardownFailures':facts['teardownFailures'],'diagnosticFailureClass':type(diagnostic).__name__}),flush=True)
    except BaseException:pass
   raise
  finally:
   if proc is not None and not close_attempted:
    try:proc.close()
    except BaseException as cleanup:
     if primary_error is None:raise
     primary_error.add_note('FINAL_OWNED_CLOSE_FAILED:'+type(cleanup).__name__)
     try:print('FINAL_OWNED_CLOSE_FAILED '+type(cleanup).__name__,flush=True)
     except BaseException:pass
   if self._sampler:self.supervision_samples+=self._sampler.count;self.supervision_max_gap=max(self.supervision_max_gap,self._sampler.max_gap)
   self._sampler=None;self._command_deadline=None
