"""Harmless process fixtures for census framing only; not scanner evidence."""
import sys,json,time
def main():
 r=json.loads(sys.stdin.buffer.readline());mode=sys.argv[1];base={k:r[k] for k in ('nonce','generation','specHash')}
 def emit(kind,**kw):print(json.dumps({**base,'kind':kind,**kw}),flush=True)
 if mode=='hang':time.sleep(2)
 elif mode=='stale':base['generation']+=1;emit('complete',complete=True,payload={'synthetic':True})
 elif mode=='partial':emit('complete',complete=False,payload={'synthetic':True})
 elif mode=='error':emit('error',code='CENSUS_PERMISSION_DENIED',payload={'synthetic':True})
 elif mode=='concurrent':
  for _ in range(4):emit('progress',confirmedPeakBytes=12);time.sleep(.15)
  emit('complete',complete=True,payload={'synthetic':True})
 elif mode=='credentials':
  import os
  assert not any(k in os.environ for k in ('GITHUB_TOKEN','ACTIONS_RUNTIME_TOKEN','AWS_ACCESS_KEY_ID'))
  emit('complete',complete=True,payload={'synthetic':True})
 else:emit('complete',complete=True,payload={'synthetic':True})
 
if __name__=='__main__':main()
