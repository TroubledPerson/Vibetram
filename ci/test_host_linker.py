import unittest,pathlib,json,os,types,sys,ctypes,ctypes.wintypes as w,ast
from unittest.mock import patch
import host_linker as h

def environment():
 root=pathlib.Path('C:/fixture/rustup');lld=root/'toolchains/1.95.0-x86_64-pc-windows-msvc/lib/rustlib/x86_64-pc-windows-msvc/bin/rust-lld.exe';tools=pathlib.Path('C:/fixture/msvc');pin={'path':str(lld),'identity':[1,2],'bytes':h.SIZE,'sha256':h.SHA}
 env={'RUSTUP_HOME':str(root),h.KEY:json.dumps(pin),'VIBETRAM_DIRECT_MSVC_LINKER':str(tools/'link.exe'),'CARGO_TARGET_X86_64_PC_WINDOWS_MSVC_LINKER':str(lld),'CARGO_PROFILE_CI_TEST_DEBUG':'1','PATH':str(tools)}
 for key,name in [('CC_x86_64_pc_windows_msvc','cl.exe'),('CXX_x86_64_pc_windows_msvc','cl.exe'),('HOST_CC','cl.exe'),('HOST_CXX','cl.exe'),('AR_x86_64_pc_windows_msvc','lib.exe')]:env[key]=str(tools/name)
 return env,pin
class Tests(unittest.TestCase):
 def test_trusted_full_trial_only(self):
  msg='[qualified-lld-host-191] [unsigned-trial-191]';self.assertTrue(h.trusted_request('TroubledPerson/Vibetram','refs/heads/main','push',msg))
  for repo,ref,event,message in [('other/repo','refs/heads/main','push',msg),('TroubledPerson/Vibetram','refs/heads/other','push',msg),('TroubledPerson/Vibetram','refs/heads/main','pull_request',msg),('TroubledPerson/Vibetram','refs/heads/main','push','[unsigned-trial-191]'),('TroubledPerson/Vibetram','refs/heads/main','push',msg+' [qualified-rust-vctip-cleanup-191]')]:self.assertFalse(h.trusted_request(repo,ref,event,message))
 def test_no_route_preserves_old_behavior(self):self.assertEqual(h.direct_msvc_linker({'CARGO_TARGET_X86_64_PC_WINDOWS_MSVC_LINKER':'old-link'}),'old-link');self.assertIsNone(h.verify_runtime({}))
 def test_exact_binding(self):
  e,p=environment();self.assertEqual(h.binding(e),p)
 def test_wrong_digest_size_identity_or_route(self):
  for key,value in [('sha256','0'*64),('bytes',64),('identity',[True,2]),('path','other')]:
   e,p=environment();p[key]=value;e[h.KEY]=json.dumps(p)
   with self.subTest(key=key),self.assertRaises(AssertionError):h.binding(e)
 def test_binding_bound(self):
  e,p=environment();e[h.KEY]='x'*2049
  with self.assertRaises(AssertionError):h.binding(e)
 def test_forced_rust_marker_rejected(self):
  e,p=environment();e['VIBETRAM_QUALIFIED_RUST_VCTIP']='1'
  with self.assertRaisesRegex(AssertionError,'FORCED'):h.binding(e)
 def test_microsoft_tools_remain_separate(self):
  e,p=environment();self.assertEqual(h.direct_msvc_linker(e),e['VIBETRAM_DIRECT_MSVC_LINKER']);self.assertNotEqual(h.direct_msvc_linker(e),p['path'])
 def test_other_microsoft_tool_root_rejected(self):
  e,p=environment();e['HOST_CC']='C:/other/cl.exe'
  with self.assertRaisesRegex(AssertionError,'TOOL_ROUTES'):h.direct_msvc_linker(e)
 def test_microsoft_linker_name_rejected(self):
  e,p=environment();e['VIBETRAM_DIRECT_MSVC_LINKER']='C:/fixture/msvc/rust-lld.exe'
  with self.assertRaisesRegex(AssertionError,'DIRECT_MSVC_LINKER'):h.direct_msvc_linker(e)
 def run_verify(self,e,row=None,which=None):
  p=json.loads(e[h.KEY]);mock=types.ModuleType('build_guard');calls=[]
  def snapshot(path,sample=None,**kw):calls.append((path,kw));return row or {'identity':p['identity'],'bytes':h.SIZE,'sha256':h.SHA}
  mock.executable_snapshot=snapshot
  with patch.dict(sys.modules,{'build_guard':mock}),patch.object(h.shutil,'which',return_value=which or e['VIBETRAM_DIRECT_MSVC_LINKER']):result=h.verify_runtime(e)
  return result,calls
 def test_runtime_rechecks_exact_large_pin(self):
  e,p=environment();r,c=self.run_verify(e);self.assertEqual(c[0][1]['large_lld_binding'],p);self.assertEqual(r['sha256'],h.SHA)
 def test_runtime_changed_identity_rejected(self):
  e,p=environment()
  with self.assertRaisesRegex(AssertionError,'CHANGED'):self.run_verify(e,{'identity':[9,9],'bytes':h.SIZE,'sha256':h.SHA})
 def test_microsoft_path_collision_rejected(self):
  e,p=environment()
  with self.assertRaisesRegex(AssertionError,'COLLISION'):self.run_verify(e,which='C:/git/link.exe')
 def test_debug_or_global_host_flags_rejected(self):
  for key,value in [('CARGO_PROFILE_CI_TEST_DEBUG','0'),('RUSTFLAGS','-Cdebuginfo=0'),('CARGO_ENCODED_RUSTFLAGS','-Clinker=other')]:
   e,p=environment();e[key]=value
   with self.subTest(key=key),self.assertRaises(AssertionError):self.run_verify(e)
 def test_android_route_keeps_host_lld(self):
  e,p=environment();e.update(CARGO_TARGET_AARCH64_LINUX_ANDROID_LINKER='C:/ndk/clang.exe',CARGO_ENCODED_RUSTFLAGS='-C\x1flink-arg=--target=aarch64-linux-android29\x1f-C\x1flink-arg=-Wl,-z,max-page-size=16384');self.run_verify(e);self.assertEqual(e['CARGO_TARGET_X86_64_PC_WINDOWS_MSVC_LINKER'],p['path'])
 def test_android_cannot_use_coff_linker(self):
  e,p=environment();e['CARGO_TARGET_AARCH64_LINUX_ANDROID_LINKER']=p['path']
  with self.assertRaisesRegex(AssertionError,'ANDROID_LINKER'):self.run_verify(e)
 def test_android_alignment_flags_required(self):
  e,p=environment();e.update(CARGO_TARGET_AARCH64_LINUX_ANDROID_LINKER='C:/ndk/clang.exe',CARGO_ENCODED_RUSTFLAGS='--target=aarch64-linux-android29')
  with self.assertRaisesRegex(AssertionError,'ANDROID_FLAGS'):self.run_verify(e)
 def test_tiny_rust_preserves_required_flags(self):
  e,p=environment();a=h.tiny_rust_arguments(pathlib.Path('tiny.rs'),pathlib.Path('tiny.exe'),e)
  for flag in ('linker='+p['path'],'target-feature=+crt-static','link-arg=/STACK:8388608','debuginfo=1','linker-flavor=lld-link'):self.assertIn(flag,a)
 def test_msvc_default_arguments_unchanged(self):
  e={'CARGO_TARGET_X86_64_PC_WINDOWS_MSVC_LINKER':'exact-link'};a=h.tiny_rust_arguments(pathlib.Path('tiny.rs'),pathlib.Path('tiny.exe'),e);self.assertEqual(a,['rustc','--edition','2024','--target','x86_64-pc-windows-msvc','-C','linker=exact-link','tiny.rs','-o','tiny.exe'])
 def test_integration_order_and_boundaries(self):
  self.assertLess(SOURCES['ci/msvc_env.py'].index("out['compiledTinyFixtures']=1"),SOURCES['ci/msvc_env.py'].index('configure_lld(env,guard,work)'))
  g=SOURCES['ci/build_guard.py'];self.assertLess(g.index('verify_runtime(env or self.env,self._sampler.tick)'),g.index('proc.start(launch_args'));self.assertIn('facts=freeze_failure(',g);self.assertIn("'teardownDiagnostic'",g)
  for fn in ('configure_environment','qualify_make_link','prepare_cargo_runtime_source'):
   tree=ast.parse(SOURCES['ci/perl_overlay.py']);node=next(x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name==fn);self.assertIn('direct_msvc_linker',ast.unparse(node))
 def fake_proc(self):
  class Query:
   def __call__(self,handle,flags,buf,n):buf.value='C:/owned/'+('cargo.exe' if handle==1 else 'helper.exe');return True
  rows={1:{'pid':10,'creationFiletime':100,'exited':True},2:{'pid':20,'creationFiletime':200,'exited':True}}
  api=types.SimpleNamespace(w=w,k=types.SimpleNamespace(QueryFullProcessImageNameW=Query()),snapshot=lambda handle:dict(rows[handle]),ok=lambda x:None)
  return types.SimpleNamespace(process=1,initial=rows[1],members_held={20:(2,None)},api=api,observe=lambda:[])
 def test_failure_captures_held_exited_descendants(self):
  fake=types.ModuleType('build_guard');fake.executable_snapshot=lambda *a,**kw:{'identity':[1,2],'sha256':'0'*64,'bytes':64}
  with patch.dict(sys.modules,{'build_guard':fake}):rows=h.failure_members(self.fake_proc(),{})
  self.assertEqual({r['pid'] for r in rows},{10,20});self.assertTrue(all(r['heldIdentityVerified'] for r in rows));self.assertTrue(all(r['qualifiedForNormalCompletion'] is False for r in rows))
 def test_metadata_denial_retains_basename_and_identity(self):
  fake=types.ModuleType('build_guard')
  def denied(*a,**kw):raise PermissionError('synthetic denial')
  fake.executable_snapshot=denied
  with patch.dict(sys.modules,{'build_guard':fake}):rows=h.failure_members(self.fake_proc(),{})
  self.assertEqual(rows[1]['imageBaseName'],'helper.exe');self.assertEqual(rows[1]['creationFiletime'],200);self.assertEqual(rows[1]['metadataFailureClass'],'PermissionError');self.assertFalse(rows[1]['qualifiedForNormalCompletion'])
if __name__=='__main__':
 root=pathlib.Path(__file__).parent;SOURCES={p:(root/pathlib.PurePosixPath(p).name).read_text() for p in ('ci/msvc_env.py','ci/build_guard.py','ci/perl_overlay.py')};unittest.main()
