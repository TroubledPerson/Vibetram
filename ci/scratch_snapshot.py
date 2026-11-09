"""Bounded metadata snapshots of exact observed Rust scratch leaves; no skipped totals."""
import os,pathlib,re,ctypes,struct
MAX_TRACKED=8192;MAX_ATTEMPTS=3;MAX_INTERRUPTS=256;META_RESERVE=4096
class IncompleteScratchSnapshot(RuntimeError):
 def __init__(self,relative,identity,partial,allocation):
  assert type(partial) is int and partial>=0 and type(allocation) is int and allocation>=0
  self.relative=relative;self.identity=identity;self.partial_bytes=partial;self.allocation_bytes=max(META_RESERVE,allocation)
  super().__init__('INCOMPLETE_VERIFIED_SCRATCH_SNAPSHOT:'+relative)
def eligible(work,path):
 try:parts=pathlib.PureWindowsPath(path).relative_to(pathlib.PureWindowsPath(work)).parts
 except ValueError:return False
 return (parts[:-1] in (('target','ci-test','deps'),('target','aarch64-linux-android','ci-test','deps')) and re.fullmatch(r'rmeta[A-Za-z0-9]{6}',parts[-1]) is not None)
def regular(info,volume=None):
 assert info['tag']==0 and info['attributes']&16 and not info['attributes']&0x400,'SCRATCH_REPARSE_OR_NON_DIRECTORY'
 if volume is not None:assert info['identity'][0]==volume,'SCRATCH_CROSS_VOLUME'
def identity(info):return (tuple(info['identity']),info['created'])
def directory_records(raw):
 # FILE_ID_BOTH_DIR_INFO has a 104-byte fixed prefix on Windows.
 records=[];offset=0
 for _ in range(66):
  assert offset+104<=len(raw),'MALFORMED_DIRECTORY_RECORD'
  next_offset=struct.unpack_from('<I',raw,offset)[0];size=struct.unpack_from('<q',raw,offset+40)[0]
  attrs,namebytes=struct.unpack_from('<II',raw,offset+56);file_id=struct.unpack_from('<Q',raw,offset+96)[0]
  assert size>=0 and namebytes%2==0 and offset+104+namebytes<=len(raw),'MALFORMED_DIRECTORY_ENTRY_BOUNDS'
  name=raw[offset+104:offset+104+namebytes].decode('utf-16-le','strict');assert name and not any(c in name for c in '/\\:\0'),'UNSAFE_DIRECTORY_ENTRY_NAME'
  records.append({'name':name,'attributes':attrs,'size':size,'fileId':file_id})
  if not next_offset:return records
  assert next_offset>=104+namebytes and next_offset%8==0,'MALFORMED_DIRECTORY_NEXT_OFFSET';offset+=next_offset
 raise AssertionError('SCRATCH_DIRECTORY_PAGE_ENTRY_BOUND')
class MetadataAPI:
 def __init__(self):
  assert os.name=='nt';from ctypes import wintypes as w
  self.w=w;self.k=ctypes.WinDLL('kernel32',use_last_error=True)
  class FT(ctypes.Structure):_fields_=[('low',w.DWORD),('high',w.DWORD)]
  class INFO(ctypes.Structure):_fields_=[('attrs',w.DWORD),('created',FT),('accessed',FT),('written',FT),('volume',w.DWORD),('sizeHigh',w.DWORD),('sizeLow',w.DWORD),('links',w.DWORD),('indexHigh',w.DWORD),('indexLow',w.DWORD)]
  class TAG(ctypes.Structure):_fields_=[('attrs',w.DWORD),('tag',w.DWORD)]
  class STANDARD(ctypes.Structure):_fields_=[('allocated',ctypes.c_longlong),('length',ctypes.c_longlong),('links',w.DWORD),('delete',ctypes.c_ubyte),('directory',ctypes.c_ubyte)]
  self.INFO=INFO;self.TAG=TAG;self.STANDARD=STANDARD
  self.k.CreateFileW.argtypes=[w.LPCWSTR,w.DWORD,w.DWORD,ctypes.c_void_p,w.DWORD,w.DWORD,w.HANDLE];self.k.CreateFileW.restype=w.HANDLE
  self.k.GetFileInformationByHandle.argtypes=[w.HANDLE,ctypes.POINTER(INFO)];self.k.GetFileInformationByHandle.restype=w.BOOL
  self.k.GetFileInformationByHandleEx.argtypes=[w.HANDLE,ctypes.c_int,ctypes.c_void_p,w.DWORD];self.k.GetFileInformationByHandleEx.restype=w.BOOL
  self.k.GetFinalPathNameByHandleW.argtypes=[w.HANDLE,w.LPWSTR,w.DWORD,w.DWORD];self.k.GetFinalPathNameByHandleW.restype=w.DWORD
  self.k.CloseHandle.argtypes=[w.HANDLE];self.k.CloseHandle.restype=w.BOOL
 def checked(self,ok):
  if not ok:raise ctypes.WinError(ctypes.get_last_error())
 def open(self,path,share,list_directory=False):
  h=self.k.CreateFileW(str(path),0x80|(1 if list_directory else 0),share,None,3,0x02200000,None)
  if h==ctypes.c_void_p(-1).value:raise ctypes.WinError(ctypes.get_last_error())
  return h
 def info(self,h):
  row=self.INFO();tag=self.TAG();self.checked(self.k.GetFileInformationByHandle(h,ctypes.byref(row)));self.checked(self.k.GetFileInformationByHandleEx(h,9,ctypes.byref(tag),ctypes.sizeof(tag)))
  return {'identity':[row.volume,row.indexHigh,row.indexLow],'created':(row.created.high<<32)|row.created.low,'tag':tag.tag,'attributes':tag.attrs}
 def standard(self,h):
  row=self.STANDARD();self.checked(self.k.GetFileInformationByHandleEx(h,1,ctypes.byref(row),ctypes.sizeof(row)))
  return {'deletePending':bool(row.delete),'directory':bool(row.directory),'allocationBytes':row.allocated}
 def entries(self,h):
  result=[];seen=set()
  for page in range(4):
   buffer=ctypes.create_string_buffer(65536);assert ctypes.addressof(buffer)%8==0,'DIRECTORY_BUFFER_ALIGNMENT'
   ok=self.k.GetFileInformationByHandleEx(h,11 if page==0 else 10,buffer,65536)
   if not ok:
    error=ctypes.get_last_error()
    if error==18:return result
    raise ctypes.WinError(error)
   for row in directory_records(buffer.raw):
    if row['name'] in ('.','..'):continue
    assert row['name'].lower() not in seen,'SCRATCH_DUPLICATE_DIRECTORY_ENTRY';seen.add(row['name'].lower())
    assert not row['attributes']&(16|0x400),'SCRATCH_CHILD_DIRECTORY_OR_REPARSE'
    result.append(row);assert len(result)<=64,'SCRATCH_DIRECTORY_ENTRY_BOUND'
  raise AssertionError('SCRATCH_DIRECTORY_PAGE_BOUND')
 def final_name(self,h):
  value=ctypes.create_unicode_buffer(32768);n=self.k.GetFinalPathNameByHandleW(h,value,32768,0);self.checked(n)
  assert n<32768,'SCRATCH_FINAL_NAME_BOUND';name=value.value
  if name.startswith('\\\\?\\'):name=name[4:]
  return pathlib.PureWindowsPath(name)
 def close(self,h):self.k.CloseHandle(h)
class ScratchTracker:
 def __init__(self,work,baselines,parent_baselines,api=None):
  self.work=pathlib.Path(work);self.baselines=baselines;self.parent_baselines=parent_baselines;self.api=api;self.handles=[];self.parents={};self.entries={}
 def __enter__(self):return self
 def __exit__(self,*exc):
  if self.api:
   for h in reversed(self.handles):self.api.close(h)
 def _open(self,path,share,list_directory=False):
  if self.api is None:self.api=MetadataAPI()
  h=self.api.open(path,share,list_directory);self.handles.append(h);return h
 def verify_parents(self):
  for _,(h,before) in self.parents.items():
   after=self.api.info(h);regular(after,before['identity'][0]);assert identity(after)==identity(before),'SCRATCH_PARENT_IDENTITY_RACE'
 def observe(self,path):
  path=pathlib.Path(path);assert eligible(self.work,path),'UNQUALIFIED_SCRATCH_SCOPE';assert len(path.parts)<=32
  key=str(path);assert len(self.baselines)<MAX_TRACKED or key in self.baselines,'SCRATCH_IDENTITY_BUDGET'
  current=pathlib.Path(path.anchor);volume=None
  for i,part in enumerate(path.parent.parts):
   if i:current=current/part
   parent=str(current)
   if parent not in self.parents:
    ph=self._open(current,1);meta=self.api.info(ph);regular(meta,volume);self.parents[parent]=(ph,meta)
   ph,meta=self.parents[parent];fresh=self.api.info(ph);regular(fresh,volume);assert identity(fresh)==identity(meta),'SCRATCH_PARENT_IDENTITY_RACE'
   old=self.parent_baselines.get(parent);assert old is None or old==identity(fresh),'SCRATCH_PARENT_REPLACED';self.parent_baselines[parent]=identity(fresh)
   if volume is None:volume=fresh['identity'][0]
  h=self._open(path,7,True);meta=self.api.info(h);regular(meta,volume)
  old=self.baselines.get(key);assert old is None or old==identity(meta),'SCRATCH_ENTRY_REPLACED'
  self.baselines[key]=identity(meta);self.entries[key]=(h,meta);return h,meta
 def confirmed_delete(self,path,h,before,partial):
  self.verify_parents();after=self.api.info(h);regular(after,before['identity'][0]);assert identity(after)==identity(before),'SCRATCH_ENTRY_IDENTITY_RACE'
  standard=self.api.standard(h);assert standard['directory'] is True and standard['deletePending'] is True and type(standard['allocationBytes']) is int and standard['allocationBytes']>=0,'SCRATCH_DISAPPEARANCE_NOT_CONFIRMED_DELETE'
  raise IncompleteScratchSnapshot(path.relative_to(self.work).as_posix(),list(after['identity']),partial,standard['allocationBytes'])
 def scan(self,path,partial):
  path=pathlib.Path(path);h,before=self.observe(path);known=0
  try:
   standard=self.api.standard(h);assert standard['directory'] and standard['allocationBytes']>=0,'SCRATCH_STANDARD_METADATA_INVALID'
   if standard['deletePending']:self.confirmed_delete(path,h,before,partial)
   rows=self.api.entries(h);seen=set()
   for row in rows:
    assert row['name'] not in ('.','..') and row['name'].lower() not in seen and not row['attributes']&(16|0x400),'SCRATCH_AMBIGUOUS_ENTRY'
    assert type(row['size']) is int and row['size']>=0;seen.add(row['name'].lower());known+=row['size']
   self.verify_parents();after=self.api.info(h);regular(after,before['identity'][0]);assert identity(after)==identity(before),'SCRATCH_ENTRY_IDENTITY_RACE'
   if self.api.standard(h)['deletePending']:self.confirmed_delete(path,h,before,partial+known)
   assert self.api.final_name(h)==pathlib.PureWindowsPath(path),'SCRATCH_ENTRY_RENAMED'
   self.verify_parents();after=self.api.info(h);regular(after,before['identity'][0]);assert identity(after)==identity(before),'SCRATCH_ENTRY_IDENTITY_RACE'
   standard=self.api.standard(h)
   if standard['deletePending']:self.confirmed_delete(path,h,before,partial+known)
   return known+max(META_RESERVE,standard['allocationBytes'])
  except FileNotFoundError:
   self.confirmed_delete(path,h,before,partial+known)
