"""One process-local bounded census; input contains paths/baselines, never credentials."""
import pathlib,sys,time,json,hashlib,contextlib
from build_guard import Guard
from census_supervisor import MAX_FRAME,CENSUS_SECONDS
FIELDS=('peak','races','alias_baseline','alias_passes','alias_charged_bytes','scratch_baselines','scratch_parent_baselines','snapshot_incomplete','ordinary_churn_count','recent_churn','accepted_snapshot_peak','last_completed_bytes','last_completed_root_scans','enumeration_resource_checks','census_walk_count')
def freeze(x):return tuple(freeze(y) for y in x) if isinstance(x,list) else x
def export_state(g):
 r={k:getattr(g,k) for k in FIELDS};r['qualified_links']=sorted(g.qualified_links);r['root_scans']=g.root_scans;r['alias_last_result']=g.alias_last_result
 if g.pending_reparse:
  root,rel=g.pending_reparse;r['pending_reparse']={'rootIndex':g.roots.index(root),'relative':rel.as_posix()}
 return r
def import_state(g,state):
 assert isinstance(state,dict) and set(state)<=set(FIELDS)|{'qualified_links','root_scans','alias_last_result','pending_reparse'},'UNKNOWN_CENSUS_STATE'
 for k in FIELDS:
  if k in state:setattr(g,k,state[k])
 g.alias_baseline=freeze(g.alias_baseline)
 g.scratch_baselines={k:freeze(v) for k,v in g.scratch_baselines.items()}
 g.scratch_parent_baselines={k:freeze(v) for k,v in g.scratch_parent_baselines.items()}
 g.qualified_links=set(state.get('qualified_links',[]))
def spec_hash(spec):return hashlib.sha256(json.dumps(spec,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def main():
 wire=sys.stdin.buffer.readline(MAX_FRAME+1);assert len(wire)<=MAX_FRAME and wire.endswith(b'\n'),'REQUEST_BOUND'
 request=json.loads(wire);assert set(request)=={'nonce','generation','specHash','spec','state','deadline'},'UNKNOWN_CENSUS_REQUEST'
 assert isinstance(request['nonce'],str) and len(request['nonce'])==32 and type(request['generation']) is int
 spec=request['spec'];assert set(spec)=={'root','work','out','cargo','rustup','globalStart'},'UNKNOWN_CENSUS_SPEC';assert spec_hash(spec)==request['specHash']
 assert all(pathlib.Path(spec[k]).is_absolute() and not str(spec[k]).startswith('\\\\') for k in ('root','work','out','cargo','rustup'))
 deadline=request['deadline'];assert type(deadline) in (int,float) and 0<deadline-time.monotonic()<=CENSUS_SECONDS,'CENSUS_DEADLINE'
 output=sys.stdout;last=[0.0];base={k:request[k] for k in ('nonce','generation','specHash')}
 def emit(kind,**kw):
  data=json.dumps({**base,'kind':kind,**kw},separators=(',',':'));assert len(data.encode())<MAX_FRAME
  output.write(data+'\n');output.flush()
 def progress(n):
  now=time.monotonic()
  if now-last[0]>=.25:emit('progress',confirmedPeakBytes=n);last[0]=now
 class BoundedSink:
  def __init__(self):self.total=0
  def write(self,s):self.total+=len(s.encode());assert self.total<=65536,'CENSUS_INTERNAL_LOG_BOUND';return len(s)
  def flush(self):pass
 g=object.__new__(Guard);g._setup(pathlib.Path(spec['root']),pathlib.Path(spec['work']),pathlib.Path(spec['out']),{'CARGO_HOME':spec['cargo'],'RUSTUP_HOME':spec['rustup']});g.start=spec['globalStart'];g.worker_mode=True;g._census_progress=progress
 import_state(g,request['state'])
 try:
  with contextlib.redirect_stdout(BoundedSink()):used=g.scan_epoch(deadline)
  payload={'bytes':used,'state':export_state(g),'rootCount':len(g.roots),'completedAt':time.monotonic()}
  emit('complete',complete=True,payload=payload)
 except BaseException as error:
  code='CENSUS_PERMISSION_DENIED' if isinstance(error,PermissionError) else str(error).split(':',1)[0]
  if not code or len(code)>100 or any(not(c.isupper() or c.isdigit() or c=='_') for c in code):code='CENSUS_'+type(error).__name__.upper()
  emit('error',code=code,payload={'state':export_state(g),'partialPeak':g.peak,'osError':getattr(error,'winerror',None)})
  raise SystemExit(1)
if __name__=='__main__':main()
