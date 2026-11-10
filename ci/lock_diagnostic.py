"""No-compile Cargo lock proposal and pinned Git licence-link metadata audit."""
import os,pathlib,posixpath,re,json,tomllib,hashlib,subprocess,shutil,time,urllib.parse,difflib
ROOT=pathlib.Path(__file__).resolve().parents[1];WORK=ROOT/'lock-diagnostic-work';OUT=ROOT/'lock-diagnostic-output'
MIN_FREE=40*1024**3;MAX_OUTPUT=8*1024**3;MAX_SECONDS=600;MAX_LOG=32*1024**2
ENTRY_MARKERS=("[lock-diagnostic-191]","[unsigned-trial-191]")

def allowed_entry(event_name,repository,ref,message):
 return (event_name=="push" and repository=="TroubledPerson/Vibetram" and ref=="refs/heads/main" and isinstance(message,str) and any(marker in message for marker in ENTRY_MARKERS))

def blob(data):return hashlib.sha1(b'blob '+str(len(data)).encode()+bytes([0])+data).hexdigest()
def lock_delta(before,after):
 def key(p):return (p['name'],p['version'],p.get('source',''))
 a={key(p):p for p in before['package']};b={key(p):p for p in after['package']}
 added=[b[k] for k in sorted(b.keys()-a.keys())];removed=[a[k] for k in sorted(a.keys()-b.keys())];changed=[]
 for k in sorted(a.keys()&b.keys()):
  if a[k]!=b[k]:changed.append({'name':k[0],'version':k[1],'source':k[2],'before':a[k],'after':b[k]})
 external=[x for x in added+removed if x.get('source')]+[x for x in changed if x['source'] and x['before'].get('checksum')!=x['after'].get('checksum')]
 return {'addedPackages':added,'removedPackages':removed,'changedEntries':changed,'externalIdentitiesAndChecksumsUnchanged':not external,'externalPinDifferences':external}
def resolve_link(entries,path):
 seen=set();at=path
 for _ in range(8):
  assert at not in seen,'GIT_LINK_CYCLE';seen.add(at);item=entries[at]
  if item['mode']=='100644':return at,item
  assert item['mode']=='120000' and 'target' in item,'NON_REGULAR_GIT_LICENSE_TARGET'
  value=item['target'].replace(chr(92),'/');assert not value.startswith('/') and ':' not in value,'ABSOLUTE_GIT_LINK_TARGET'
  at=posixpath.normpath(posixpath.join(posixpath.dirname(at),value));assert at!='..' and not at.startswith('../'),'GIT_LINK_ESCAPE'
 raise AssertionError('GIT_LINK_DEPTH')
def allowed_cargo(args):return args in (['metadata','--locked','--format-version','1'],['update','--workspace','--offline'])
class Diagnostic:
 def __init__(self,env):
  self.env=env;self.start=time.monotonic();self.peak=0;self.count=0;self.races=0;self.catalog=[];self.observed=set();self.commands=[]
  self.roots=[WORK,OUT,pathlib.Path(env['CARGO_HOME']),pathlib.Path(env['RUSTUP_HOME'])];assert shutil.disk_usage(ROOT).free>=MIN_FREE+MAX_OUTPUT
 def size(self):
  n=0;cargo=pathlib.Path(self.env['CARGO_HOME'])
  for root in self.roots:
   if not root.exists():continue
   for folder,dirs,files in os.walk(root,followlinks=False):
    for name in dirs:
     p=pathlib.Path(folder)/name;assert not p.is_symlink() and not p.is_junction(),'UNQUALIFIED_DIRECTORY_LINK'
    for name in files:
     p=pathlib.Path(folder)/name
     try:
      if p.is_symlink():
       parts=p.relative_to(cargo).parts;assert len(parts)>=5 and parts[:2]==('git','checkouts'),'LINK_OUTSIDE_OWNED_GIT_CHECKOUT'
       matching=[r for r in self.catalog if re.fullmatch(re.escape(r['repoName'])+'-[0-9a-f]+',parts[2]) and len(parts[3])>=7 and r['commit'].startswith(parts[3]) and '/'.join(parts[4:])==r['linkPath']]
       assert len(matching)==1,'UNQUALIFIED_FILE_LINK:'+str(p.relative_to(root));rule=matching[0]
       assert os.readlink(p).replace(chr(92),'/')==rule['target'].replace(chr(92),'/'),'LINK_TARGET_CHANGED'
       checkout=cargo.joinpath(*parts[:4]);target=checkout.joinpath(*pathlib.PurePosixPath(rule['resolvedTarget']).parts)
       for parent in [target,*target.parents]:
        assert not parent.is_symlink() and not parent.is_junction(),'LICENSE_TARGET_ANCESTOR_LINK'
        if parent==checkout:break
       assert target.is_file() and target.stat().st_size<=131072,'LICENSE_TARGET_BOUND'
       raw=target.read_bytes();raw.decode('utf-8');assert rule['targetBlob'] in (blob(raw),blob(raw.replace(bytes([13,10]),bytes([10])))),'LICENSE_TARGET_BLOB_CHANGED'
       n+=max(4096,p.lstat().st_size);self.observed.add('/'.join(parts[4:])+'@'+rule['commit'])
      else:n+=p.stat().st_size
     except FileNotFoundError:self.races+=1
  return n
 def check(self,log=0):
  used=self.size();self.peak=max(self.peak,used);assert used<=MAX_OUTPUT,'DIAGNOSTIC_OUTPUT_BOUND';assert shutil.disk_usage(ROOT).free>=MIN_FREE,'DIAGNOSTIC_DISK_FLOOR';assert time.monotonic()-self.start<=MAX_SECONDS,'DIAGNOSTIC_DEADLINE';assert log<=MAX_LOG,'DIAGNOSTIC_LOG_BOUND'
 def run(self,args,cwd=None,expected_failure=False):
  tool=pathlib.Path(str(args[0])).stem.lower()
  assert tool in ('git','cargo'),'NO_COMPILER_OR_OTHER_TOOL_ALLOWED'
  if tool=='cargo':assert allowed_cargo([str(x) for x in args[1:]]) and pathlib.Path(cwd)==WORK/'source','CARGO_DIAGNOSTIC_ONLY'
  else:assert not any(str(x) in ('push','credential','config','checkout','reset','clean') for x in args),'GIT_METADATA_ONLY'
  self.check();self.count+=1;a=WORK/f'command-{self.count:02d}.out';b=WORK/f'command-{self.count:02d}.err';proc=None;last=time.monotonic()
  print('NO_COMPILE_DIAGNOSTIC_STAGE',self.count,tool,flush=True)
  try:
   with a.open('xb') as out,b.open('xb') as err:
    proc=subprocess.Popen([str(x) for x in args],cwd=cwd or ROOT,env=self.env,stdout=out,stderr=err)
    while True:
     self.check(a.stat().st_size+b.stat().st_size)
     if proc.poll() is not None:break
     if time.monotonic()-last>30:print('DIAGNOSTIC_PROGRESS',self.count,int(time.monotonic()-self.start),self.peak,flush=True);last=time.monotonic()
     time.sleep(2)
   self.commands.append({'stage':self.count,'tool':tool,'exit':proc.returncode})
   assert expected_failure or proc.returncode==0,'DIAGNOSTIC_SUBPROCESS_FAILED: '+b.read_bytes().decode('utf-8',errors='replace')[-4000:]
   return proc.returncode,a.read_bytes(),b.read_bytes()
  finally:
   if proc and proc.poll() is None:
    subprocess.run([str(pathlib.Path(os.environ['SystemRoot'])/'System32/taskkill.exe'),'/PID',str(proc.pid),'/T','/F'],capture_output=True,timeout=20);proc.wait(timeout=10)
def main():
 from build_guard import clean_env
 from check_source import source_check
 assert os.name=='nt' and os.environ.get('GITHUB_REPOSITORY')=='TroubledPerson/Vibetram' and os.environ.get('GITHUB_REF')=='refs/heads/main'
 event=json.loads(pathlib.Path(os.environ['GITHUB_EVENT_PATH']).read_text());assert allowed_entry(os.environ.get('GITHUB_EVENT_NAME'),os.environ.get('GITHUB_REPOSITORY'),os.environ.get('GITHUB_REF'),event['head_commit']['message']),'LOCK_DIAGNOSTIC_ENTRY_GATE'
 source_check(ROOT);assert not WORK.exists() and not OUT.exists();WORK.mkdir();OUT.mkdir()
 for name in ('tmp','home','profile','profile/AppData/Local','profile/AppData/Roaming'):(WORK/name).mkdir(parents=True,exist_ok=True)
 env=clean_env(os.environ,WORK);d=Diagnostic(env);original=(ROOT/'codex-rs/Cargo.lock').read_bytes();original_hash=hashlib.sha256(original).hexdigest();old=tomllib.loads(original.decode())
 result={'kind':'NO_COMPILE_LOCK_DIAGNOSTIC','commit':os.environ['GITHUB_SHA'],'rootLockSHA256':original_hash,'compiledAnything':False,'committedLockChanged':False,'candidateAdopted':False,'linkCatalog':[],'unqualifiedLinks':[]}
 try:
  sources=sorted({p.get('source','') for p in old['package'] if p.get('source','').startswith('git+')});assert len(sources)==7
  for i,source in enumerate(sources):
   url=urllib.parse.urlsplit(source[4:]);assert url.scheme=='https' and url.netloc=='github.com' and url.username is None and re.fullmatch('[0-9a-f]{40}',url.fragment)
   assert urllib.parse.parse_qs(url.query).get('rev')==[url.fragment]
   repo_url=urllib.parse.urlunsplit((url.scheme,url.netloc,url.path,'',''));repo_name=pathlib.PurePosixPath(url.path).name.removesuffix('.git');bare=WORK/f'bare-{i}'
   d.run(['git','init','--bare',bare]);d.run(['git','-c','pack.threads=2','-C',bare,'fetch','--no-tags','--depth=1',repo_url,url.fragment])
   _,tree,_=d.run(['git','-C',bare,'ls-tree','-rz',url.fragment]);entries={}
   for row in tree.split(bytes([0])):
    if not row:continue
    meta,path=row.split(bytes([9]),1);mode,kind,identity=meta.decode().split();name=path.decode('utf-8');entries[name]={'mode':mode,'sha':identity}
   links=[name for name,r in entries.items() if r['mode']=='120000']
   for name in links:
    _,raw,_=d.run(['git','-C',bare,'cat-file','blob',entries[name]['sha']]);assert len(raw)<4096 and blob(raw)==entries[name]['sha'];entries[name]['target']=raw.decode('utf-8')
   for name in links:
    if pathlib.PurePosixPath(name).name.upper() not in ('LICENSE','COPYING','LICENSE-MIT','LICENSE-APACHE'):result['unqualifiedLinks'].append({'source':source,'path':name,'reason':'NOT_A_LICENSE_LINK'});continue
    try:
     target,item=resolve_link(entries,name);_,raw,_=d.run(['git','-C',bare,'cat-file','blob',item['sha']]);assert 0<len(raw)<=131072 and blob(raw)==item['sha'];text=raw.decode('utf-8');assert re.search('license|copyright|permission',text,re.I)
     rule={'source':source,'repoName':repo_name,'commit':url.fragment,'linkPath':name,'linkBlob':entries[name]['sha'],'target':entries[name]['target'],'resolvedTarget':target,'targetBlob':item['sha'],'targetBytes':len(raw),'licenseTextUnmodified':True};d.catalog.append(rule);result['linkCatalog'].append(rule)
    except (AssertionError,KeyError,UnicodeError) as error:result['unqualifiedLinks'].append({'source':source,'path':name,'reason':type(error).__name__})
  (OUT/'pinned-license-links.json').write_text(json.dumps({'qualified':result['linkCatalog'],'unqualified':result['unqualifiedLinks']},indent=2),encoding='utf-8')
  assert not result['unqualifiedLinks'],'UNQUALIFIED_PINNED_LINKS_STOP_RESOLUTION'
  copy=WORK/'source';shutil.copytree(ROOT/'codex-rs',copy);d.check()
  code,stdout,stderr=d.run(['cargo','metadata','--locked','--format-version','1'],cwd=copy,expected_failure=True)
  result['lockedMetadataExit']=code;result['lockedMetadataNeedsLockUpdate']=b'lock' in stderr.lower() and b'--locked' in stderr
  if code and not result['lockedMetadataNeedsLockUpdate']:
   result['lockedMetadataError']=stderr.decode('utf-8',errors='replace')[-8000:];raise AssertionError('LOCKED_METADATA_OTHER_FAILURE')
  if '[unsigned-trial-191]' in event['head_commit']['message']:assert code==0,'REPAIRED_LOCKED_METADATA_MUST_PASS_BEFORE_BUILD'
  proposal_code,proposal_out,proposal_err=d.run(['cargo','update','--workspace','--offline'],cwd=copy,expected_failure=True);result['proposalExit']=proposal_code
  result['proposalDiagnostic']=proposal_err.decode('utf-8',errors='replace')[-16000:]
  proposed=(copy/'Cargo.lock').read_bytes();after=tomllib.loads(proposed.decode('utf-8'));delta=lock_delta(old,after);result['proposedDelta']=delta
  result['proposalLockSHA256']=hashlib.sha256(proposed).hexdigest();result['proposedLockChanged']=proposed!=original
  if '[unsigned-trial-191]' in event['head_commit']['message']:assert proposal_code==0 and proposed==original,'REPAIRED_LOCK_MUST_REMAIN_IDENTICAL'
  if proposed!=original:
   (OUT/'Cargo.lock.PROPOSED_NOT_ADOPTED').write_bytes(proposed)
   (OUT/'Cargo.lock.delta.txt').write_text(''.join(difflib.unified_diff(original.decode().splitlines(True),proposed.decode().splitlines(True),fromfile='committed/Cargo.lock',tofile='disposable-proposal/Cargo.lock')),encoding='utf-8')
  result['state']='PROPOSAL_AVAILABLE_NOT_ADOPTED' if proposal_code==0 else 'OFFLINE_PROPOSAL_INCOMPLETE_NOT_ADOPTED'
 except BaseException as error:
  result['state']='FAILED_NO_COMPILE';result['error']=str(error)[:8000]
  raise
 finally:
  assert (ROOT/'codex-rs/Cargo.lock').read_bytes()==original,'COMMITTED_LOCK_CHANGED'
  source_check(ROOT);d.check()
  result.update(elapsedSeconds=round(time.monotonic()-d.start,3),retainedPeakBytes=d.peak,outputThresholdBytes=MAX_OUTPUT,minimumFreeBytes=MIN_FREE,maximumSeconds=MAX_SECONDS,observedQualifiedLinks=sorted(d.observed),snapshotRaces=d.races,commands=d.commands,hardCumulativeQuota=False)
  payload=json.dumps(result,indent=2);assert len(payload.encode())<2*1024**2;(OUT/'diagnostic.json').write_text(payload,encoding='utf-8');print(payload,flush=True)
if __name__=='__main__':main()

