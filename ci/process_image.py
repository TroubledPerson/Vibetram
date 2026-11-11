"""Alive image evidence retained only for the exact held owned process."""
import ctypes,pathlib,os

def key(row):return (row['pid'],row['creationFiletime'])
def snapshot(proc,handle,stage):
 try:return proc.api.snapshot(handle)
 except BaseException as e:e.api_stage=getattr(e,'api_stage',stage);raise

def capture(proc,handle,identity,env,sample=None,expected=None):
 from build_guard import executable_snapshot
 from host_linker import KEY,binding
 before=snapshot(proc,handle,'IMAGE_SNAPSHOT_BEFORE');assert key(before)==key(identity) and not before['exited'],'IMAGE_CAPTURE_REQUIRES_LIVE_HELD_IDENTITY'
 assert not proc.closed and proc.api.in_job(handle,proc.job),'IMAGE_CAPTURE_OWNED_JOB'
 api=proc.api;query=api.k.QueryFullProcessImageNameW;query.argtypes=[api.w.HANDLE,api.w.DWORD,api.w.LPWSTR,ctypes.POINTER(api.w.DWORD)];query.restype=api.w.BOOL;n=api.w.DWORD(32768);buf=ctypes.create_unicode_buffer(n.value);ctypes.set_last_error(0);ok=query(handle,0,buf,ctypes.byref(n));code=ctypes.get_last_error()
 if not ok:
  e=ctypes.WinError(code);e.api_stage='QueryFullProcessImageNameW';e.raw_winerror=code;raise e
 path=pathlib.Path(buf.value);assert path.is_absolute(),'IMAGE_ABSOLUTE_PATH'
 if expected is not None:assert os.path.normcase(str(path))==os.path.normcase(str(expected)),'IMAGE_ROOT_EXECUTABLE_BINDING'
 pin=binding(env) if KEY in env else None
 try:
  from ndk_linker import select
  from ndk_compilers import select as select_compiler
  ndk_pin=select(env,path);compiler_pin=select_compiler(env,path);file=executable_snapshot(path,sample,large_lld_binding=pin if pin and str(path)==pin['path'] else None,**({'large_ndk_binding':ndk_pin} if ndk_pin else {}),**({'large_ndk_compiler_binding':compiler_pin} if compiler_pin else {}))
 except BaseException as e:e.api_stage='IMAGE_FILE_SNAPSHOT';raise
 after=snapshot(proc,handle,'IMAGE_SNAPSHOT_AFTER');assert key(after)==key(before),'IMAGE_HELD_IDENTITY_CHANGED'
 return {'processIdentity':key(before),'ownerJob':proc.job,'path':str(path),'file':file,'observedWhileAlive':True}

def retained(proc,handle,row,env,sample=None):
 from build_guard import executable_snapshot
 from host_linker import KEY,binding
 assert not proc.closed,'IMAGE_CACHE_JOB_CLOSED';identity=key(row);cache=getattr(proc,'image_evidence',{});saved=cache.get(identity)
 if saved is None:
  assert not row['exited'],'EXITED_PROCESS_IMAGE_EVIDENCE_MISSING'
  saved=capture(proc,handle,row,env,sample);cache[identity]=saved;proc.image_evidence=cache
 assert saved['processIdentity']==identity and saved['ownerJob']==proc.job and saved['observedWhileAlive'] is True,'IMAGE_CACHE_IDENTITY_BINDING'
 before=snapshot(proc,handle,'CACHED_IMAGE_SNAPSHOT_BEFORE');assert key(before)==identity,'IMAGE_CACHE_HELD_IDENTITY_CHANGED';pin=binding(env) if KEY in env else None
 try:
  from ndk_linker import select
  from ndk_compilers import select as select_compiler
  ndk_pin=select(env,pathlib.Path(saved['path']));compiler_pin=select_compiler(env,pathlib.Path(saved['path']));now=executable_snapshot(pathlib.Path(saved['path']),sample,large_lld_binding=pin if pin and saved['path']==pin['path'] else None,**({'large_ndk_binding':ndk_pin} if ndk_pin else {}),**({'large_ndk_compiler_binding':compiler_pin} if compiler_pin else {}))
 except BaseException as e:e.api_stage='IMAGE_FILE_RECHECK';raise
 assert now==saved['file'],'CACHED_IMAGE_FILE_CHANGED';after=snapshot(proc,handle,'CACHED_IMAGE_SNAPSHOT_AFTER');assert key(after)==identity,'IMAGE_CACHE_HELD_IDENTITY_CHANGED'
 return {'pid':identity[0],'creationFiletime':identity[1],'imageBaseName':pathlib.Path(saved['path']).name,'imageSHA256':now['sha256'],'imageBytes':now['bytes'],'imageIdentity':now['identity'],'heldIdentityVerified':True,'imageObservedWhileAlive':True,'imageRecheckedBeforeClose':True,'rawPathWithheld':True,'qualifiedForNormalCompletion':False}


def error_info(error):
 prior=getattr(error,'image_evidence_failure',None)
 if prior is not None:return dict(prior,priorFailureLatched=True)
 return {'apiStage':getattr(error,'api_stage','IDENTITY_VALIDATION' if isinstance(error,AssertionError) else 'UNSPECIFIED'),'exceptionClass':type(error).__name__,'errno':getattr(error,'errno',None),'winerror':getattr(error,'winerror',None),'rawWinerror':getattr(error,'raw_winerror',None)}

def latched(proc,identity):
 prior=getattr(proc,'image_failures',{}).get(identity)
 if prior is not None:
  e=RuntimeError('OWNED_IMAGE_CAPTURE_PREVIOUSLY_FAILED');e.image_evidence_failure=prior;raise e

def remember(proc,handle,row,env,sample=None,expected=None):
 identity=key(row);latched(proc,identity)
 try:
  saved=capture(proc,handle,row,env,sample,expected);proc.image_evidence[identity]=saved;return saved
 except BaseException as e:
  if not hasattr(proc,'image_failures'):proc.image_failures={}
  proc.image_failures[identity]=error_info(e);raise

_retained=retained
def retained(proc,handle,row,env,sample=None):
 identity=key(row);latched(proc,identity)
 try:return _retained(proc,handle,row,env,sample)
 except BaseException as e:
  if not hasattr(proc,'image_failures'):proc.image_failures={}
  proc.image_failures[identity]=error_info(e);raise
