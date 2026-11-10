import unittest,pathlib,struct,types,json,ast,sys,io,hashlib,time,subprocess
from unittest.mock import patch
import archive_policy as a
import failure_lifecycle as f

def ar_fixture():
 obj=b'object';symbol=b'vibetram_offline_link_probe\0';index=struct.pack('>II',1,8+60+8+len(symbol))+symbol
 def member(name,body):
  h=(name.ljust(16)+'0'.ljust(12)+'0'.ljust(6)+'0'.ljust(6)+'644'.ljust(8)+str(len(body)).ljust(10)+'`\n').encode();return h+body+(b'\n' if len(body)%2 else b'')
 return b'!<arch>\n'+member('/',index)+member('probe object.o/',obj),obj
class Archive(unittest.TestCase):
 def env(self):return {'CARGO_TARGET_AARCH64_LINUX_ANDROID_LINKER':'C:/ndk/clang.exe','AR_aarch64_linux_android':'llvm-ar.exe','ARFLAGS':'crs','HOST_ARFLAGS':'host-fixture','other':'preserve'}
 def test_narrow_cargo_only_scope(self):
  e=self.env();r=a.cargo_environment(e);self.assertNotIn('ARFLAGS',r);self.assertEqual(e['ARFLAGS'],'crs');self.assertEqual(r['HOST_ARFLAGS'],'host-fixture');self.assertEqual(r['VIBETRAM_OPENSSL_ARFLAGS'],'crs');self.assertEqual(r['other'],'preserve')
 def test_other_target_rejected(self):
  e=self.env();e['CARGO_TARGET_AARCH64_LINUX_ANDROID_LINKER']='C:/msvc/link.exe'
  with self.assertRaises(AssertionError):a.cargo_environment(e)
 def test_unknown_custom_flags_not_erased(self):
  for key in ('ARFLAGS','TARGET_ARFLAGS','ARFLAGS_aarch64_linux_android','ARFLAGS_aarch64-linux-android'):
   e=self.env();e[key]='unknown-custom'
   with self.subTest(key=key),self.assertRaises(AssertionError):a.cargo_environment(e)
 def test_single_caller_mode(self):
  d=pathlib.Path('C:/job/a.a');o=pathlib.Path('C:/job/probe object.o');self.assertEqual(a.cc_argv('llvm-ar.exe','cq',d,[o]),['llvm-ar.exe','cq',d,o]);self.assertEqual(a.cc_argv('llvm-ar.exe','s',d),['llvm-ar.exe','s',d])
 def test_duplicate_operations_rejected(self):
  for op in ('crs','crs cq','cq crs','cq s'):
   with self.subTest(op=op),self.assertRaises(AssertionError):a.cc_argv('llvm-ar.exe',op,pathlib.Path('C:/job/a.a'),[pathlib.Path('C:/job/x.o')])
  with self.assertRaises(AssertionError):a.cc_argv('llvm-ar.exe','cq',pathlib.Path('crs'),[pathlib.Path('C:/job/x.o')])
 def test_valid_archive_creation_and_index(self):
  data,obj=ar_fixture();self.assertTrue(a.indexed_archive(data,obj,'vibetram_offline_link_probe')['indexVerified'])
 def test_missing_index_or_wrong_symbol(self):
  data,obj=ar_fixture()
  with self.assertRaises(AssertionError):a.indexed_archive(data,obj,'other')
  with self.assertRaises(AssertionError):a.indexed_archive(data[0:8]+data[104:],obj,'vibetram_offline_link_probe')
 def test_wrong_object_and_index_offset(self):
  data,obj=ar_fixture()
  with self.assertRaises(AssertionError):a.indexed_archive(data,b'other','vibetram_offline_link_probe')
  b=bytearray(data);struct.pack_into('>I',b,72,999)
  with self.assertRaises(AssertionError):a.indexed_archive(bytes(b),obj,'vibetram_offline_link_probe')
 def test_openssl_bridge_after_hash_and_scope(self):
  s=SOURCES['ci/perl_overlay.py'];tree=ast.parse(s);node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='cargo_prefix_bridge_program');program=node.body[0].value.value;self.assertLess(program.index('Configure identity changed'),program.index('$ENV{ARFLAGS}="crs"'));self.assertLess(program.index('unexpected OpenSSL install scope'),program.index('$ENV{ARFLAGS}="crs"'));self.assertIn('VIBETRAM_OPENSSL_ARFLAGS="crs"',s);self.assertIn('cargo_environment(build_android_environment',SOURCES['ci/cloud_build.py'])
class Proc:
 def __init__(self,code=101,closed=False,proof=True,finish_error=False,close_error=False):self.returncode=code;self.closed=closed;self.teardown={'treeState':'VERIFIED_OWNED_JOB_ZERO_MEMBERS','processTreeExitIndependentlyVerified':True,'activeMembers':0,'knownHandlesExited':True} if proof else None;self.cleanup_errors=[];self.initial={'pid':10};self.calls=[];self.finish_error=finish_error;self.close_error=close_error
 def poll(self):assert not self.closed,'closed poll';self.calls.append('poll');return self.returncode
 def finish(self,**kw):assert not self.closed,'closed finish';self.calls.append('finish');
 def close(self):self.calls.append('close');self.closed=True
class Lifecycle(unittest.TestCase):
 def test_evidence_before_close_and_primary_code(self):
  p=Proc();seen=[]
  def reader(x):self.assertFalse(x.closed);seen.append(1);return [{'pid':10,'creationFiletime':100}]
  r=f.freeze_failure(p,reader,None,101);self.assertEqual(seen,[1]);self.assertEqual(p.calls,['close']);self.assertEqual(r['knownParentExitCode'],101);self.assertTrue(r['teardownDiagnostic']['processTreeExitIndependentlyVerified'])
 def test_closed_handles_never_retried(self):
  p=Proc(closed=True);r=f.freeze_failure(p,lambda x:(_ for _ in ()).throw(AssertionError('must not capture')),None,101);self.assertEqual(p.calls,[]);self.assertTrue(r['ownedFailureImages'][0]['metadataUnavailableClosedHandles']);self.assertEqual(r['knownParentExitCode'],101)
 def test_capture_exception_does_not_block_cleanup(self):
  p=Proc();r=f.freeze_failure(p,lambda x:(_ for _ in ()).throw(PermissionError('fixture')),None,101);self.assertTrue(p.closed);self.assertEqual(r['ownedFailureImages'][0]['metadataCaptureFailureClass'],'PermissionError')
 def test_cleanup_failure_preserved(self):
  p=Proc(proof=False)
  def fail(**kw):p.calls.append('finish');raise RuntimeError('fixture')
  p.finish=fail;r=f.freeze_failure(p,lambda x:[],None,101);self.assertIn('RuntimeError',r['teardownFailures']);self.assertFalse(r['teardownDiagnostic']['processTreeExitIndependentlyVerified']);self.assertTrue(p.closed)
 def test_close_failure_preserves_exit_and_zero_proof(self):
  p=Proc()
  def fail():p.closed=True;raise OSError('fixture')
  p.close=fail;r=f.freeze_failure(p,lambda x:[{'pid':10}],None,101);self.assertEqual(r['knownParentExitCode'],101);self.assertTrue(r['teardownDiagnostic']['processTreeExitIndependentlyVerified']);self.assertIn('CLOSE_OSError',r['teardownFailures'])
 def test_preclose_capture_used_after_close_error(self):
  p=Proc(closed=True);r=f.freeze_failure(p,lambda x:(_ for _ in ()).throw(AssertionError()),None,0,[{'imageBaseName':'fixture.exe'}]);self.assertEqual(r['ownedFailureImages'][0]['imageBaseName'],'fixture.exe');self.assertEqual(p.calls,[])
 def test_guard_finally_and_report_failure_preservation(self):
  tree=ast.parse(SOURCES['ci/build_guard.py']);guard=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Guard');run=next(n for n in guard.body if isinstance(n,ast.FunctionDef) and n.name=='run');code=ast.unparse(run);self.assertLess(code.index("assert code == 0"),code.index('preclose_images = capture_images'));self.assertLess(code.index('preclose_images = capture_images'),code.index('proc.close()'));self.assertIn("error.add_note('FAILURE_REPORT_FAILED:'",code);self.assertIn('if proc is not None and (not close_attempted)',code)

class RunnerFailures(unittest.TestCase):
 def run_guard(self,code=101,capture_error=False,close_error=False,finish_error=False,report_error=False):
  files={};instances=[]
  class MPath:
   def __init__(self,key):self.key=key
   def __truediv__(self,key):return MPath(self.key+'/'+key)
   def __str__(self):return self.key
   def exists(self):return self.key in files
   def stat(self):return types.SimpleNamespace(st_size=len(files[self.key]))
   def read_text(self,**kw):return files[self.key].decode()
   def write_text(self,text,**kw):
    if report_error and self.key.endswith('failure-summary.json'):raise OSError('synthetic report failure')
    files[self.key]=text.encode();return len(text)
   def open(self,mode):
    key=self.key
    class Handle(io.BytesIO):
     def __exit__(self,*a):
      if 'w' in mode or 'x' in mode:files[key]=self.getvalue()
      self.close()
    if 'x' in mode:assert key not in files;files[key]=b''
    return Handle(files.get(key,b''))
  class Workload:
   def __init__(self):self.closed=False;self.teardown=None;self.cleanup_errors=[];self.initial={'pid':10};self.pid=10;self.returncode=code;self.close_count=0;instances.append(self)
   def start(self,*a,**kw):pass
   def poll(self):assert not self.closed,'CLOSED_POLL';return self.returncode
   def finish(self,terminate=False,**kw):
    assert not self.closed,'CLOSED_FINISH'
    if finish_error:raise RuntimeError('synthetic finish failure')
    self.teardown={'treeState':'VERIFIED_OWNED_JOB_ZERO_MEMBERS','processTreeExitIndependentlyVerified':True,'activeMembers':0,'knownHandlesExited':True};return self.teardown
   def close(self):
    self.close_count+=1;self.closed=True
    if close_error:raise OSError('synthetic close failure')
  class Sample:
   def __init__(self,*a):self.max_gap=0;self.count=0
   def tick(self):self.count+=1
  def reader(proc,*a):
   assert not proc.closed,'CAPTURE_AFTER_CLOSE'
   if capture_error:raise PermissionError('synthetic metadata failure')
   return [{'pid':10,'creationFiletime':100,'heldIdentityVerified':True}]
  host=types.ModuleType('host_linker');host.verify_runtime=lambda *a:None;host.failure_members=reader;msvc=types.ModuleType('msvc_probe');msvc.compiler_completion=lambda *a:None
  tree=ast.parse(SOURCES['ci/build_guard.py']);guard=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Guard');run=next(n for n in guard.body if isinstance(n,ast.FunctionDef) and n.name=='run');scope={'pathlib':pathlib,'time':time,'json':json,'subprocess':subprocess,'Sampler':Sample,'OwnedProcess':Workload,'qualified_executable':lambda args,*a:(args,{}),'redact':lambda s:s}
  exec(compile(ast.Module(body=[run],type_ignores=[]),'<actual-Guard.run>','exec'),scope)
  obj=types.SimpleNamespace(work=MPath('/mem/work'),root=MPath('/mem/root'),env={},count=0,start=time.monotonic(),commands=[],pending_reparse=None,reparse_result=None,supervision_samples=0,supervision_max_gap=0,check=lambda *a:(0,0),_resource_sample=lambda:None);obj.report=lambda:{'commands':obj.commands};error=None
  with patch.dict(sys.modules,{'host_linker':host,'msvc_probe':msvc}),patch('sys.stdout',new=io.StringIO()):
   try:scope['run'](obj,['C:/owned/cargo.exe'],capture=True)
   except BaseException as e:error=e
  payload=files.get('/mem/work/failure-summary.json');return error,json.loads(payload) if payload else None,instances[0],obj
 def test_real_runner_nonzero_keeps_valid_evidence(self):
  error,report,p,obj=self.run_guard();self.assertIsInstance(error,AssertionError);self.assertEqual(str(error),'SUBPROCESS_FAILED');self.assertEqual(report['exit'],101);self.assertEqual(report['ownedFailureImages'][0]['pid'],10);self.assertEqual(report['teardownFailures'],[]);self.assertEqual(p.close_count,1);self.assertEqual(obj.commands,[])
 def test_real_runner_capture_exception_still_closes(self):
  error,report,p,obj=self.run_guard(capture_error=True);self.assertEqual(str(error),'SUBPROCESS_FAILED');self.assertEqual(report['ownedFailureImages'][0]['metadataCaptureFailureClass'],'PermissionError');self.assertTrue(p.closed);self.assertEqual(p.close_count,1)
 def test_real_runner_close_failure_does_not_mask_nonzero(self):
  error,report,p,obj=self.run_guard(close_error=True);self.assertEqual(str(error),'SUBPROCESS_FAILED');self.assertIn('CLOSE_OSError',report['teardownFailures']);self.assertTrue(report['teardownDiagnostic']['processTreeExitIndependentlyVerified']);self.assertEqual(p.close_count,1)
 def test_real_runner_success_close_failure_uses_preclose_evidence(self):
  error,report,p,obj=self.run_guard(code=0,close_error=True);self.assertIsInstance(error,OSError);self.assertEqual(report['ownedFailureImages'][0]['pid'],10);self.assertEqual(p.close_count,1);self.assertEqual(obj.commands,[])
 def test_real_runner_finish_failure_remains_unknown(self):
  error,report,p,obj=self.run_guard(finish_error=True);self.assertIsInstance(error,RuntimeError);self.assertFalse(report['teardownDiagnostic']['processTreeExitIndependentlyVerified']);self.assertIn('RuntimeError',report['teardownFailures']);self.assertTrue(p.closed)
 def test_real_runner_report_exception_preserves_primary(self):
  error,report,p,obj=self.run_guard(report_error=True);self.assertEqual(str(error),'SUBPROCESS_FAILED');self.assertIn('FAILURE_REPORT_FAILED:OSError',error.__notes__);self.assertTrue(p.closed);self.assertEqual(p.close_count,1)
 def test_real_runner_metadata_denial_cannot_pass(self):
  error,report,p,obj=self.run_guard(code=0,capture_error=True);self.assertEqual(str(error),'PRE_CLOSE_OWNED_IMAGE_METADATA_INCOMPLETE');self.assertEqual(obj.commands,[]);self.assertTrue(p.closed)
 def test_real_runner_clean_success(self):
  error,report,p,obj=self.run_guard(code=0);self.assertIsNone(error);self.assertIsNone(report);self.assertEqual(p.close_count,1);self.assertEqual(len(obj.commands),1)

if __name__=='__main__':
 root=pathlib.Path(__file__).parent;SOURCES={p:(root/pathlib.PurePosixPath(p).name).read_text() for p in ('ci/perl_overlay.py','ci/cloud_build.py','ci/build_guard.py')};unittest.main()
