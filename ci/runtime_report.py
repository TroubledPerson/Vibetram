"""Bounded, lossless runtime-monitor evidence. Sampled snapshots, never quotas."""
import hashlib,json,pathlib,re,stat

LIMIT=65536
BUNDLE_LIMIT=1024**2
MAX_COMMANDS=512

def encode(value):
 return (json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+'\n').encode('utf-8')

def digest(value):
 return hashlib.sha256(encode(value)).hexdigest()

def metadata(path,directory=False):
 m=path.lstat()
 assert (stat.S_ISDIR(m.st_mode) if directory else stat.S_ISREG(m.st_mode)) and not getattr(m,'st_file_attributes',0)&0x400 and not getattr(m,'st_reparse_tag',0),'RUNTIME_EVIDENCE_TYPE_OR_LINK'
 return (m.st_dev,m.st_ino,m.st_mode,m.st_size,m.st_mtime_ns)

def directory_identity(path):
 return metadata(path,True)[:3]

def load_bytes(path):
 before=metadata(path);assert 0<before[3]<LIMIT,'RUNTIME_EVIDENCE_FILE_BOUND'
 data=path.read_bytes();assert metadata(path)==before and len(data)==before[3],'RUNTIME_EVIDENCE_FILE_CHANGED'
 return data

def parse(data):
 def pairs(items):
  result={}
  for k,v in items:
   assert k not in result,'RUNTIME_EVIDENCE_DUPLICATE_KEY'
   result[k]=v
  return result
 def invalid(value):raise AssertionError('RUNTIME_EVIDENCE_NONFINITE')
 return json.loads(data,object_pairs_hook=pairs,parse_constant=invalid)

def validate_monitor(m):
 assert isinstance(m,dict),'RUNTIME_MONITOR_TYPE'
 assert m['minimumFreeBytes']==40*1024**3 and m['monitoredOutputThresholdBytes']==64*1024**3 and m['maximumSeconds']==5400,'RUNTIME_MONITOR_LIMIT_CHANGED'
 assert m['censusPending'] is False and m['lastSnapshotComplete'] is True and m['censusCleanupFailures']==[],'RUNTIME_MONITOR_INCOMPLETE'
 commands=m['commands'];assert isinstance(commands,list) and 0<len(commands)<=MAX_COMMANDS,'RUNTIME_COMMAND_COUNT'
 for i,c in enumerate(commands,1):
  assert type(c['stage']) is int and c['stage']==i and type(c['exit']) is int and c['exit']==0,'RUNTIME_COMMAND_INCOMPLETE'
  t=c['ownedJobTeardown']
  assert t['treeState']=='VERIFIED_OWNED_JOB_ZERO_MEMBERS' and t['processTreeExitIndependentlyVerified'] is True and t['completeActiveMemberAccounting'] is True and type(t['activeMembers']) is int and t['activeMembers']==0 and t['knownHandlesExited'] is True and t['supervisionFailures']==[],'RUNTIME_COMMAND_TEARDOWN_UNVERIFIED'
  held=t['heldIdentities'];assert isinstance(held,list) and 0<len(held)<=256 and t['heldIdentityCount']==len(held),'RUNTIME_HELD_COUNT'
  ids=[]
  for h in held:
   assert type(h['pid']) is int and h['pid']>0 and type(h['creationFiletime']) is int and h['creationFiletime']>0 and h['exited'] is True and type(h['exitCode']) is int,'RUNTIME_HELD_IDENTITY'
   ids.append((h['pid'],h['creationFiletime']))
  assert len(set(ids))==len(ids),'RUNTIME_HELD_DUPLICATE'
 assert 0<=m['retainedPeakBytes']<=m['monitoredOutputThresholdBytes'],'RUNTIME_PEAK_BOUND'
 scans=m['lastCompletedRootScans'];assert isinstance(scans,list) and 0<len(scans)<=16,'RUNTIME_ROOT_CENSUS_COUNT'
 assert all(r['rootIndex']==i and r['complete'] is True and type(r['completedRootBytes']) is int and r['completedRootBytes']>=0 for i,r in enumerate(scans)),'RUNTIME_ROOT_CENSUS_INCOMPLETE'
 assert 0<=m['maximumObservedSupervisionGap']<=1.0,'RUNTIME_SUPERVISION_GAP'
 encode(m) # Reject unsupported and nonfinite values without dropping any field.

def reference(name,data):
 assert re.fullmatch(r'runtime-evidence/(metadata|index|command-[0-9]{4})\.json',name),'RUNTIME_REFERENCE_PATH'
 assert 0<len(data)<LIMIT,'RUNTIME_EVIDENCE_PART_BOUND'
 return {'path':name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}

def read_reference(out,ref):
 assert isinstance(ref,dict) and set(ref)=={'path','bytes','sha256'},'RUNTIME_REFERENCE_SCHEMA'
 assert type(ref['bytes']) is int and 0<ref['bytes']<LIMIT and re.fullmatch('[a-f0-9]{64}',ref['sha256']),'RUNTIME_REFERENCE_BOUND'
 assert re.fullmatch(r'runtime-evidence/(metadata|index|command-[0-9]{4})\.json',ref['path']),'RUNTIME_REFERENCE_ESCAPE'
 data=load_bytes(out/ref['path'])
 assert len(data)==ref['bytes'] and hashlib.sha256(data).hexdigest()==ref['sha256'],'RUNTIME_EVIDENCE_DIGEST'
 return parse(data)

def verify_bundle(out,summary):
 root=directory_identity(out);directory=out/'runtime-evidence';identity=directory_identity(directory)
 manifest=summary['monitor']
 assert set(manifest)=={'state','index','commandCount','originalSHA256'} and manifest['state']=='COMPLETE_BOUNDED_MONITOR_EVIDENCE','RUNTIME_MANIFEST_INCOMPLETE'
 assert manifest['index']['path']=='runtime-evidence/index.json','RUNTIME_INDEX_PATH'
 index=read_reference(out,manifest['index'])
 assert set(index)=={'metadata','commands','commandCount','originalSHA256'},'RUNTIME_INDEX_SCHEMA'
 refs=index['commands'];assert isinstance(refs,list) and 0<len(refs)<=MAX_COMMANDS and index['commandCount']==manifest['commandCount']==len(refs),'RUNTIME_INDEX_COUNT'
 assert index['metadata']['path']=='runtime-evidence/metadata.json','RUNTIME_METADATA_PATH'
 m=read_reference(out,index['metadata']);assert 'commands' not in m,'RUNTIME_METADATA_COMMANDS'
 commands=[]
 expected={'metadata.json','index.json'}
 total=manifest['index']['bytes']+index['metadata']['bytes']+len(encode(summary))
 for i,ref in enumerate(refs,1):
  name=f'command-{i:04d}.json';assert ref['path']=='runtime-evidence/'+name,'RUNTIME_COMMAND_ORDER'
  commands.append(read_reference(out,ref));expected.add(name);total+=ref['bytes']
 assert total<=BUNDLE_LIMIT,'RUNTIME_BUNDLE_BOUND'
 assert {x.name for x in directory.iterdir()}==expected,'RUNTIME_UNEXPECTED_OR_MISSING_PART'
 m['commands']=commands;validate_monitor(m)
 assert digest(m)==index['originalSHA256']==manifest['originalSHA256'],'RUNTIME_MONITOR_LOSS_OR_MUTATION'
 assert directory_identity(out)==root and directory_identity(directory)==identity,'RUNTIME_EVIDENCE_DIRECTORY_CHANGED'
 return m

def read_runtime_report(out):
 out=pathlib.Path(out);identity=directory_identity(out)
 summary=parse(load_bytes(out/'runtime-qualification.json'))
 m=verify_bundle(out,summary)
 assert directory_identity(out)==identity,'RUNTIME_REPORT_ROOT_CHANGED'
 return summary,m

def plan_runtime_report(report):
 """Lossless preflight in memory; reject oversized parts before writing."""
 validate_monitor(report['monitor'])
 monitor=report['monitor'];parts={};refs=[]
 meta={k:v for k,v in monitor.items() if k!='commands'}
 name='runtime-evidence/metadata.json';parts[name]=encode(meta);meta_ref=reference(name,parts[name])
 for i,command in enumerate(monitor['commands'],1):
  name=f'runtime-evidence/command-{i:04d}.json';parts[name]=encode(command);refs.append(reference(name,parts[name]))
 index={'metadata':meta_ref,'commands':refs,'commandCount':len(refs),'originalSHA256':digest(monitor)}
 name='runtime-evidence/index.json';parts[name]=encode(index);index_ref=reference(name,parts[name])
 summary={**report,'monitor':{'state':'COMPLETE_BOUNDED_MONITOR_EVIDENCE','index':index_ref,'commandCount':len(refs),'originalSHA256':digest(monitor)}}
 final=encode(summary);assert 0<len(final)<LIMIT,'RUNTIME_SUMMARY_BOUND'
 assert sum(map(len,parts.values()))+len(final)<=BUNDLE_LIMIT,'RUNTIME_BUNDLE_BOUND'
 bundle_bytes=sum(map(len,parts.values()))+len(final)
 assert monitor['retainedPeakBytes']+bundle_bytes<=monitor['monitoredOutputThresholdBytes'],'RUNTIME_KNOWN_OUTPUT_MARGIN'
 return summary,parts,final

def _write_runtime_report(report,out,safety_check):
 out=pathlib.Path(out);identity=directory_identity(out)
 summary,parts,final=plan_runtime_report(report);monitor=report['monitor']
 safety_check();assert directory_identity(out)==identity,'RUNTIME_REPORT_ROOT_CHANGED'
 directory=out/'runtime-evidence';directory.mkdir();directory_id=directory_identity(directory)
 def write(name,data):
  safety_check()
  assert directory_identity(out)==identity and directory_identity(directory)==directory_id,'RUNTIME_WRITE_PARENT_CHANGED'
  with (out/name).open('xb') as f:assert f.write(data)==len(data),'RUNTIME_SHORT_WRITE'
  assert load_bytes(out/name)==data,'RUNTIME_WRITE_READBACK'
 for name,data in parts.items():write(name,data)
 verify_bundle(out,summary);write('runtime-qualification.json',final)
 actual,reconstructed=read_runtime_report(out)
 assert actual==summary and reconstructed==monitor,'RUNTIME_LOSSLESS_ROUNDTRIP'
 safety_check()
 return actual


def write_runtime_report(report,out,safety_check):
 """Summary last; all files stay below 64 KiB and bundle at most 1 MiB.
 Failed partials are preserved. Sampling remains non-atomic, not quota control.
 """
 try:return _write_runtime_report(report,out,safety_check)
 except BaseException as error:
  arg=error.args[0] if error.args else None
  code=arg if isinstance(arg,str) and arg.startswith('RUNTIME_') else 'RUNTIME_EVIDENCE_IO_OR_SERIALIZATION'
  diagnostic={'state':'FAILED_RUNTIME_REPORT_EVIDENCE','category':type(error).__name__,'code':code[:100],'osError':getattr(error,'winerror',getattr(error,'errno',None))}
  text=json.dumps(diagnostic,allow_nan=False);assert len(text.encode())<4096
  print('RUNTIME_REPORT_FAILURE '+text,flush=True)
  raise
