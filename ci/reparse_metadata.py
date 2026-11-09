"""Read only a stopped job-owned reparse object's metadata; never open its target."""
import pathlib,ntpath,struct,hashlib,time,os,ctypes
MOUNT_POINT=0xA0000003;SYMLINK=0xA000000C;MAX_RECORD=16384
def decode_record(raw):
 assert 8<=len(raw)<=MAX_RECORD,'MALFORMED_REPARSE_LENGTH'
 tag,length,reserved=struct.unpack_from('<IHH',raw);assert reserved==0 and length==len(raw)-8,'MALFORMED_REPARSE_HEADER'
 assert tag in (MOUNT_POINT,SYMLINK),'UNKNOWN_REPARSE_TAG'
 header=8 if tag==MOUNT_POINT else 12;assert length>=header,'MALFORMED_REPARSE_BODY'
 a,b,c,d=struct.unpack_from('<HHHH',raw,8);flags=0 if tag==MOUNT_POINT else struct.unpack_from('<I',raw,16)[0]
 assert flags in (0,1),'UNKNOWN_SYMLINK_FLAGS';buf=raw[8+header:]
 def text(offset,size):
  assert offset%2==0 and size%2==0 and offset+size<=len(buf),'MALFORMED_REPARSE_OFFSETS'
  value=buf[offset:offset+size].decode('utf-16-le','strict');assert '\0' not in value,'EMBEDDED_TARGET_NUL';return value
 substitute=text(a,b);printed=text(c,d);assert substitute,'EMPTY_REPARSE_TARGET'
 return {'tag':tag,'kind':'JUNCTION' if tag==MOUNT_POINT else 'SYMLINK','substituteName':substitute,'printName':printed,'relative':flags==1}
def classify_target(record,root,link):
 root=pathlib.PureWindowsPath(root);link=pathlib.PureWindowsPath(link);assert root.is_absolute() and link.is_relative_to(root)
 name=record['substituteName']
 if record['relative']:
  assert not pathlib.PureWindowsPath(name).is_absolute() and not pathlib.PureWindowsPath(name).drive,'AMBIGUOUS_RELATIVE_TARGET'
  target=ntpath.normpath(str(link.parent/name))
 else:
  if name.startswith('\\??\\'):name=name[4:]
  elif name.startswith('\\\\?\\'):name=name[4:]
  target=ntpath.normpath(name)
 p=pathlib.PureWindowsPath(target)
 if not p.is_absolute() or p.drive.startswith('\\\\'):return {'targetClass':'EXTERNAL_OR_AMBIGUOUS_FATAL','targetSHA256':hashlib.sha256(record['substituteName'].encode('utf-16-le')).hexdigest()}
 if p==link or p in link.parents:return {'targetClass':'SELF_OR_ANCESTOR_CYCLE_FATAL','targetSHA256':hashlib.sha256(record['substituteName'].encode('utf-16-le')).hexdigest()}
 if not p.is_relative_to(root):return {'targetClass':'EXTERNAL_TARGET_FATAL','targetVolume':p.drive,'targetSHA256':hashlib.sha256(record['substituteName'].encode('utf-16-le')).hexdigest()}
 return {'targetClass':'INTERNAL_LEXICAL_ONLY_NOT_QUALIFIED','targetJobRelative':p.relative_to(root).as_posix(),'substituteName':record['substituteName'],'printName':record['printName']}
def stable(before,after):
 assert len(before)==len(after) and all((a['identity'],a['tag'])==(b['identity'],b['tag']) for a,b in zip(before,after)),'METADATA_IDENTITY_OR_TAG_RACE'
def stable_record(before,after):
 assert before==after,'REPARSE_DATA_RACE'
def os_failure(code):
 return {'state':'OS_ACCESS_DENIED_STOP' if code==5 else 'OS_METADATA_UNAVAILABLE_STOP','osError':code,'targetOpened':False}
def capture(root,relative):
 result={'state':'UNQUALIFIED_METADATA_ONLY_STOP','relativePath':str(relative).replace(chr(92),'/'),'targetOpened':False,'linkTraversed':False,'permissionsChanged':False,'accountingRuleChanged':False}
 handles=[];start=time.monotonic()
 try:
  assert os.name=='nt','WINDOWS_METADATA_ONLY'
  root=pathlib.Path(root);rel=pathlib.PureWindowsPath(relative)
  assert root.is_absolute() and not rel.is_absolute() and not rel.drive and '..' not in rel.parts,'OUTSIDE_JOB_METADATA_SCOPE'
  full=root.joinpath(*rel.parts);assert len(full.parts)<=32,'METADATA_PATH_DEPTH_BOUND'
  kernel=ctypes.WinDLL('kernel32',use_last_error=True)
  from ctypes import wintypes as w
  class FT(ctypes.Structure):_fields_=[('low',w.DWORD),('high',w.DWORD)]
  class INFO(ctypes.Structure):
   _fields_=[('attrs',w.DWORD),('created',FT),('accessed',FT),('written',FT),('volume',w.DWORD),('sizeHigh',w.DWORD),('sizeLow',w.DWORD),('links',w.DWORD),('indexHigh',w.DWORD),('indexLow',w.DWORD)]
  class TAG(ctypes.Structure):_fields_=[('attrs',w.DWORD),('tag',w.DWORD)]
  kernel.CreateFileW.argtypes=[w.LPCWSTR,w.DWORD,w.DWORD,ctypes.c_void_p,w.DWORD,w.DWORD,w.HANDLE];kernel.CreateFileW.restype=w.HANDLE
  kernel.GetFileInformationByHandle.argtypes=[w.HANDLE,ctypes.POINTER(INFO)];kernel.GetFileInformationByHandle.restype=w.BOOL
  kernel.GetFileInformationByHandleEx.argtypes=[w.HANDLE,ctypes.c_int,ctypes.c_void_p,w.DWORD];kernel.GetFileInformationByHandleEx.restype=w.BOOL
  kernel.DeviceIoControl.argtypes=[w.HANDLE,w.DWORD,ctypes.c_void_p,w.DWORD,ctypes.c_void_p,w.DWORD,ctypes.POINTER(w.DWORD),ctypes.c_void_p];kernel.DeviceIoControl.restype=w.BOOL
  kernel.CloseHandle.argtypes=[w.HANDLE];kernel.CloseHandle.restype=w.BOOL
  def checked(ok):
   if not ok:raise OSError(ctypes.get_last_error(),'METADATA_HANDLE_QUERY_FAILED')
  def info(handle):
   row=INFO();tag=TAG();checked(kernel.GetFileInformationByHandle(handle,ctypes.byref(row)));checked(kernel.GetFileInformationByHandleEx(handle,9,ctypes.byref(tag),ctypes.sizeof(tag)))
   return {'identity':[row.volume,row.indexHigh,row.indexLow],'tag':tag.tag,'attributes':tag.attrs,'createdFileTime':(row.created.high<<32)|row.created.low,'writtenFileTime':(row.written.high<<32)|row.written.low}
  before=[];path=pathlib.Path(full.anchor)
  # Hold each verified regular ancestor without share-write/delete while opening descendants.
  for index,part in enumerate(full.parts):
   assert time.monotonic()-start<5,'METADATA_DEADLINE'
   if index:path=path/part
   handle=kernel.CreateFileW(str(path),0,1,None,3,0x02200000,None)
   if handle==ctypes.c_void_p(-1).value:raise OSError(ctypes.get_last_error(),'METADATA_OPEN_FAILED')
   handles.append(handle);row=info(handle);before.append(row);assert row['attributes']&0x10,'NON_DIRECTORY_METADATA_PATH'
   if index<len(full.parts)-1:assert row['tag']==0 and not row['attributes']&0x400,'REPARSE_ANCESTOR_FATAL'
  row=before[-1];assert row['attributes']&0x400 and row['tag'],'OBJECT_NO_LONGER_REPARSE'
  result.update(reparseTagHex=hex(row['tag']),attributeFlags=hex(row['attributes']),fileIdentity=row['identity'],createdFileTime=row['createdFileTime'],writtenFileTime=row['writtenFileTime'])
  def record():
   buffer=ctypes.create_string_buffer(MAX_RECORD);count=w.DWORD();checked(kernel.DeviceIoControl(handles[-1],0x000900A8,None,0,buffer,MAX_RECORD,ctypes.byref(count),None));assert count.value<=MAX_RECORD;return buffer.raw[:count.value]
  raw=record();stable_record(raw,record());stable(before,[info(h) for h in handles])
  result.update(rawRecordBytes=len(raw),rawRecordSHA256=hashlib.sha256(raw).hexdigest())
  decoded=decode_record(raw);assert decoded['tag']==row['tag'],'REPARSE_TAG_RECORD_MISMATCH'
  result.update(kind=decoded['kind'],relativeTarget=decoded['relative'],**classify_target(decoded,root,full))
  result['state']='CAPTURED_UNQUALIFIED_METADATA_STOP'
 except OSError as error:result.update(os_failure(error.errno or 0))
 except (AssertionError,UnicodeError,struct.error) as error:result.update(state='UNQUALIFIED_OR_MALFORMED_METADATA_STOP',reason=str(error)[:120])
 except Exception as error:result.update(state='METADATA_COLLECTOR_FAILED_STOP',reason=type(error).__name__)
 finally:
  for handle in reversed(handles):kernel.CloseHandle(handle)
  result['elapsedMilliseconds']=round((time.monotonic()-start)*1000,3)
 return result
