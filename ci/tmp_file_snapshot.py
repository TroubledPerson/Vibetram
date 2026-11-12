"""Held-identity proof for exact job-owned tmp files; no skipped totals."""
import pathlib,time
from scratch_snapshot import ScratchTracker,MetadataAPI,identity
from build_guard import OrdinaryScratchChurn
class API(MetadataAPI):
 def standard(self,h):
  row=self.STANDARD();self.checked(self.k.GetFileInformationByHandleEx(h,1,self.c_byref(row),self.c_sizeof(row)))
  return {'deletePending':bool(row.delete),'directory':bool(row.directory),'allocationBytes':row.allocated,'length':row.length}
 def c_byref(self,row):
  import ctypes
  return ctypes.byref(row)
 def c_sizeof(self,row):
  import ctypes
  return ctypes.sizeof(row)
 def close(self,h):self.checked(self.k.CloseHandle(h))
class TmpFileProof:
 """Requires prior held regular-file identity and confirmed pending deletion.
 A rename is NOT qualified by this prototype. Nothing is skipped or zeroed.
 """
 def __init__(self,work,deadline,api=None,cancelled=lambda:False,clock=time.monotonic,sample=None,parent_baselines=None):
  self.work=pathlib.Path(work);assert self.work.is_absolute() and '..' not in self.work.parts and not str(self.work).startswith('\\\\') and len(self.work.parts)<=30,'TMP_ROOT_SCOPE'
  self.clock=clock;self.deadline=deadline;self.cancelled=cancelled;assert 0<deadline-clock()<=30,'TMP_WINDOW_BOUND'
  self.api=api or API();self.tracker=ScratchTracker(self.work,{}, {} if parent_baselines is None else parent_baselines,self.api);self.files={};self.events=[];self.closed=False;self.sample=sample
 def __enter__(self):return self
 def __exit__(self,kind,error,tb):
  failures=[]
  for h in reversed(self.tracker.handles):
   try:self.api.close(h)
   except BaseException as e:failures.append(type(e).__name__)
  self.closed=True
  if failures:
   failure=RuntimeError('TMP_HANDLE_CLEANUP_UNVERIFIED');failure.tmp_cleanup_failures=failures
   raise failure from error
 def check(self):
  assert not self.closed,'TMP_PROOF_CLOSED'
  if self.cancelled():raise RuntimeError('TMP_PROOF_CANCELLED')
  assert self.clock()<self.deadline,'TMP_PROOF_DEADLINE'
  if self.sample:self.sample()
  assert self.clock()<self.deadline,'TMP_PROOF_DEADLINE'
 def scope(self,path):
  self.check();p=pathlib.Path(path)
  assert p.parent==self.work/'tmp' and p.name not in ('','.','..') and len(p.name)<=240 and '..' not in p.parts,'TMP_EXACT_SCOPE'
  return p
 def regular(self,meta,standard,volume):
  assert meta['tag']==0 and not meta['attributes']&(16|0x400),'TMP_FILE_REPARSE_OR_TYPE'
  assert meta['identity'][0]==volume,'TMP_FILE_CROSS_VOLUME'
  assert standard['directory'] is False and type(standard['allocationBytes']) is int and standard['allocationBytes']>=0 and type(standard['length']) is int and standard['length']>=0,'TMP_FILE_STANDARD_METADATA'
 def observe(self,path):
  p=self.scope(path);assert p not in self.files and len(self.files)<64,'TMP_PRIOR_RECORD_BOUND'
  volume=self.tracker.lease_parent(p.parent);self.check();h=self.tracker._open(p,7)
  before=self.api.info(h);standard=self.api.standard(h);self.regular(before,standard,volume)
  assert standard['deletePending'] is False,'TMP_PRIOR_ALREADY_DELETING'
  self.tracker.verify_parents();after=self.api.info(h);assert identity(after)==identity(before) and after['tag']==0 and not after['attributes']&(16|0x400),'TMP_PRIOR_IDENTITY_CHANGED'
  self.check();self.files[p]=(h,before,max(4096,standard['allocationBytes'],standard['length']))
  return {'priorRegularIdentity':True,'parentsHeld':True}
 def confirm(self,path,error,partial):
  p=self.scope(path);assert type(partial) is int and partial>=0,'TMP_PARTIAL_BOUND'
  assert p in self.files,'TMP_NO_PRIOR_REGULAR_IDENTITY'
  assert type(error) is FileNotFoundError and type(getattr(error,'winerror',None)) is int and error.winerror==2,'TMP_NOT_EXACT_FILE_NOT_FOUND'
  assert type(error.filename) is str and pathlib.PureWindowsPath(error.filename)==pathlib.PureWindowsPath(p) and '..' not in pathlib.PureWindowsPath(error.filename).parts,'TMP_ERROR_PATH_UNBOUND'
  h,before,reserve=self.files[p];self.tracker.verify_parents();self.check()
  current=self.api.info(h);standard=self.api.standard(h);self.regular(current,standard,before['identity'][0]);assert identity(current)==identity(before),'TMP_HELD_IDENTITY_CHANGED'
  assert standard['deletePending'] is True,'TMP_NOT_CONFIRMED_DELETE_PENDING'
  reserve=max(reserve,standard['allocationBytes'],standard['length'])
  try:self.tracker._open(p,7)
  except FileNotFoundError as probe:
   assert type(probe) is FileNotFoundError and type(getattr(probe,'winerror',None)) is int and probe.winerror==2,'TMP_ABSENCE_UNQUALIFIED'
  else:raise AssertionError('TMP_NAME_PRESENT_OR_REPLACED')
  self.check();self.tracker.verify_parents();current=self.api.info(h);standard=self.api.standard(h);self.regular(current,standard,before['identity'][0])
  assert identity(current)==identity(before) and standard['deletePending'] is True,'TMP_CONFIRMATION_IDENTITY_RACE'
  reserve=max(reserve,standard['allocationBytes'],standard['length']);self.check()
  self.events.append({'relative':p.relative_to(self.work).as_posix(),'priorIdentityHeld':True,'parentsStable':True,'deletePending':True,'freshAbsence':True,'completeTotalAccepted':False})
  raise OrdinaryScratchChurn(p.relative_to(self.work).as_posix(),partial+reserve)

 def count_file(self,path,partial):
  p=self.scope(path);self.observe(p);self.check()
  try:fresh=self.tracker._open(p,7)
  except FileNotFoundError as error:
   error.filename=str(p);self.confirm(p,error,partial)
   raise AssertionError('TMP_CONFIRMATION_RETURNED')
  h,before,reserve=self.files[p]
  named=self.api.info(fresh);standard=self.api.standard(fresh);self.regular(named,standard,before['identity'][0])
  assert identity(named)==identity(before),'TMP_NAMED_FILE_REPLACED'
  assert not standard['deletePending'],'TMP_DELETE_WITHOUT_PROVEN_ABSENCE'
  assert self.api.final_name(h)==pathlib.PureWindowsPath(p) and self.api.final_name(fresh)==pathlib.PureWindowsPath(p),'TMP_FILE_RENAMED_OR_PATH_ALIAS'
  self.check();self.tracker.verify_parents()
  named=self.api.info(fresh);standard=self.api.standard(fresh);self.regular(named,standard,before['identity'][0])
  assert identity(named)==identity(before) and not standard['deletePending'],'TMP_FINAL_FILE_IDENTITY_RACE'
  self.check();return standard['length']
