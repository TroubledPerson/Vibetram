import unittest,types,pathlib,ctypes,json,ast,sys
from unittest.mock import patch
import process_image as image
class Query:
 def __init__(self,code=0):self.calls=0;self.code=code
 def __call__(self,h,flags,buf,n):
  self.calls+=1
  if self.code:ctypes.set_last_error(self.code);return False
  buf.value='C:/owned/python.exe';return True
class CacheTests(unittest.TestCase):
 def setup(self,code=0):
  import ctypes.wintypes as w
  q=Query(code);row={'pid':1,'creationFiletime':100,'exited':False};file={'identity':[1,2],'bytes':64,'modifiedNs':1,'sha256':'a'*64};api=types.SimpleNamespace(snapshot=lambda h:dict(row),in_job=lambda *a:True,w=w,k=types.SimpleNamespace(QueryFullProcessImageNameW=q));proc=types.SimpleNamespace(api=api,job=7,closed=False,image_evidence={},image_failures={});stub=types.ModuleType('build_guard');stub.executable_snapshot=lambda *a,**kw:dict(file);return proc,row,file,q,stub
 def test_live_capture_survives_exit_without_query(self):
  p,r,f,q,b=self.setup()
  with patch.dict(sys.modules,{'build_guard':b}):
   image.remember(p,1,dict(r),{},expected=pathlib.Path('C:/owned/python.exe'));r['exited']=True;out=image.retained(p,1,dict(r),{})
  self.assertTrue(out['heldIdentityVerified']);self.assertEqual(q.calls,1);self.assertNotIn('path',out)
 def test_exited_without_binding_fails_closed(self):
  p,r,f,q,b=self.setup();r['exited']=True
  with patch.dict(sys.modules,{'build_guard':b}),self.assertRaisesRegex(AssertionError,'EVIDENCE_MISSING'):image.retained(p,1,r,{})
  self.assertEqual(q.calls,0)
 def test_creation_identity_mismatch_not_reused(self):
  p,r,f,q,b=self.setup()
  with patch.dict(sys.modules,{'build_guard':b}):
   image.remember(p,1,dict(r),{});r.update(creationFiletime=101,exited=True)
   with self.assertRaisesRegex(AssertionError,'EVIDENCE_MISSING'):image.retained(p,1,r,{})
  self.assertEqual(q.calls,1)
 def test_file_change_and_job_change_fail_closed(self):
  for kind in ('file','job','closed'):
   p,r,f,q,b=self.setup()
   with patch.dict(sys.modules,{'build_guard':b}):
    image.remember(p,1,dict(r),{});r['exited']=True
    if kind=='file':f['modifiedNs']=2
    elif kind=='job':p.job=8
    else:p.closed=True
    with self.subTest(kind=kind),self.assertRaises(AssertionError):image.retained(p,1,r,{})
   self.assertEqual(q.calls,1)
 def test_errors_preserved_and_denial_never_retried(self):
  for code in (5,31):
   p,r,f,q,b=self.setup(code)
   with patch.dict(sys.modules,{'build_guard':b}):
    with self.assertRaises(OSError) as caught:image.remember(p,1,r,{})
    info=image.error_info(caught.exception);self.assertEqual(info['apiStage'],'QueryFullProcessImageNameW');self.assertEqual(info['winerror'],code);self.assertEqual(info['rawWinerror'],code);self.assertIsNotNone(info['errno'])
    with self.assertRaises(RuntimeError) as prior:image.remember(p,1,r,{})
    self.assertTrue(image.error_info(prior.exception)['priorFailureLatched'])
   self.assertEqual(q.calls,1)
 def test_expected_root_image_must_match(self):
  p,r,f,q,b=self.setup()
  with patch.dict(sys.modules,{'build_guard':b}),self.assertRaisesRegex(AssertionError,'ROOT_EXECUTABLE'):image.remember(p,1,r,{},expected=pathlib.Path('C:/other/python.exe'))
 def test_snapshot_api_errno_and_stage_preserved(self):
  tree=ast.parse(SOURCES['ci/census_supervisor.py']);c=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='WindowsOwnedJobAPI');fn=next(n for n in c.body if isinstance(n,ast.FunctionDef) and n.name=='ok');s={};exec(compile(ast.Module(body=[fn],type_ignores=[]),'<error-adapter>','exec'),s)
  with self.assertRaises(OSError) as caught:s['ok'](types.SimpleNamespace(c=types.SimpleNamespace(get_last_error=lambda:31)),False,'GetProcessTimes')
  info=image.error_info(caught.exception);self.assertEqual(info['errno'],31);self.assertEqual(info['rawWinerror'],31);self.assertEqual(info['apiStage'],'GetProcessTimes')
 def test_capture_precedes_resume(self):
  s=SOURCES['ci/census_supervisor.py'].split('class OwnedProcess(')[1];self.assertLess(s.index('self.api.in_job(self.process,self.job)'),s.index('if self.image_capture:self.image_evidence'));self.assertLess(s.index('if self.image_capture:self.image_evidence'),s.index('self.api.resume(self.thread)'));self.assertIn('image_capture=lambda',SOURCES['ci/build_guard.py'])

if __name__=='__main__':
 root=pathlib.Path(__file__).parent;SOURCES={p:(root/pathlib.PurePosixPath(p).name).read_text() for p in ('ci/census_supervisor.py','ci/build_guard.py')};unittest.main()
