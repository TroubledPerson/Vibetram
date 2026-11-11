"""Tiny real recursive NDK make/Unix Perl boundary qualification; no compiler."""
import pathlib,json,hashlib,re,sys
MAKE_SHA='246668acaeb0308cdf80215e21ad2bb2600df6f01363ecb3bc10b042b3c16662'
MAKE_BYTES=300184
PERL_SHA='c0e2fb0e8be3962cdc7aa1391f104df6502191029ec15977a37623afb32c7b36'

def safe_native(path):
 value=pathlib.Path(path).as_posix()
 assert re.fullmatch(r'[A-Za-z]:/[A-Za-z0-9_ ./+-]+',value) and '..' not in pathlib.PurePosixPath(value).parts,'PROBE_NATIVE_PATH'
 return value

def scripts(python,bridge,makefile):
 py=safe_native(python);hop=safe_native(bridge)
 recipe='.PHONY: outer inner\nouter:\n\t@true && "$(MAKE)" --no-print-directory -f '+makefile+' inner\ninner:\n\t@"'+py+'" "'+hop+'"\n'
 native=r'''import os,subprocess,json,hashlib
expected=os.environ['VIBETRAM_FIXTURE_LIB_SHA']
r=subprocess.run([os.environ['VIBETRAM_FIXTURE_PERL'],os.environ['VIBETRAM_FIXTURE_PROBE']],capture_output=True,text=True,timeout=10)
assert len(r.stdout.encode())<=4096 and len(r.stderr.encode())<=4096
try:loaded=json.loads(r.stdout).get('state')=='MODULES_LOADED'
except (ValueError,TypeError):loaded=False
print(json.dumps({'preserved':hashlib.sha256(os.environ.get('PERL5LIB','').encode()).hexdigest()==expected,'moduleLoaded':loaded,'perlExit':r.returncode}))
'''
 return recipe,native

def qualify(guard,env,work,out,perl,ndk):
 from build_guard import executable_snapshot
 from perl_overlay import cargo_prefix_bridge_program,preserve_cargo_perl_paths
 from ndk_input_metadata import capture_one
 work=pathlib.Path(work);out=pathlib.Path(out);perl=pathlib.Path(perl);ndk=pathlib.Path(ndk)
 assert work.is_absolute() and out.is_absolute() and perl.is_absolute(),'PROBE_SCOPE'
 assert 'Pkg.Revision = 30.0.16248370' in (ndk/'source.properties').read_text(),'PROBE_NDK_REVISION'
 make=ndk/'prebuilt/windows-x86_64/bin/make.exe';shell=perl.parent/'sh.exe'
 make_pin=executable_snapshot(make,guard._resource_sample);perl_pin=executable_snapshot(perl,guard._resource_sample)
 assert make_pin['sha256']==MAKE_SHA and make_pin['bytes']==MAKE_BYTES,'PROBE_MAKE_PIN'
 assert perl_pin['sha256']==PERL_SHA,'PROBE_PERL_PIN'
 case=work/'perl-path-check space';assert not case.exists(),'PRESERVE_PERL_PATH_PROBE'
 paths=[case/'runtime-overlay/lib',case/'perl-overlay/lib'];result={}
 def put(path,text):
  data=text.encode('ascii');assert len(data)<=4096,'PROBE_FILE_BOUND';path.parent.mkdir(parents=True,exist_ok=True)
  with path.open('xb') as f:f.write(data)
 put(paths[0]/'Vibetram/ConfigurePaths.pm',cargo_prefix_bridge_program())
 put(paths[1]/'Fixture/Second.pm','package Fixture::Second;our $VALUE="SECOND_OVERLAY";1;\n')
 probe=case/'probe.pl';put(probe,'use strict;use warnings;use Fixture::Second;use JSON::PP;print encode_json({state=>"MODULES_LOADED",second=>$Fixture::Second::VALUE}),chr(10);\n')
 bridge=case/'native-hop.py';mk=case/'probe.mk';recipe,native=scripts(sys.executable,bridge,mk.name);put(bridge,native);put(mk,recipe)
 convert=guard.run([perl,'-MJSON::PP','-e','print encode_json([map {Cygwin::win_to_posix_path($_,1)} @ARGV]),chr(10);',*[str(p) for p in paths]],env={k:v for k,v in env.items() if k not in ('PERL5LIB','PERL5OPT')},cwd=case,capture=True,timeout=15)
 unix=json.loads(convert.stdout);assert len(unix)==2 and all(isinstance(x,str) and x.startswith('/') and ':' not in x and ';' not in x and '\\' not in x for x in unix),'PROBE_UNIX_PATH_LIST'
 lib=':'.join(unix);base=env.copy();base.update(PERL5LIB=lib,PERL5OPT='-MVibetram::ConfigurePaths',VIBETRAM_OPENSSL_CARGO_BRIDGE='1',SHELL=safe_native(shell),MAKEFLAGS='-j1',VIBETRAM_FIXTURE_PERL=str(perl),VIBETRAM_FIXTURE_PROBE=str(probe),VIBETRAM_FIXTURE_LIB_SHA=hashlib.sha256(lib.encode()).hexdigest())
 base.pop('MSYS2_ENV_CONV_EXCL',None)
 def run_chain():
  raw=guard.run([make,'--no-print-directory','-f',mk.name,'outer'],env=base,cwd=case,capture=True,timeout=30).stdout
  lines=[x for x in raw.splitlines() if x.startswith('{')];assert len(lines)==1 and len(lines[0])<=4096,'PROBE_RESULT_BOUND';return json.loads(lines[0])
 def execute():
  baseline=run_chain();assert baseline['preserved'] is False and baseline['moduleLoaded'] is False and baseline['perlExit']!=0,'BASELINE_CONVERSION_NOT_REPRODUCED'
  fixed=preserve_cargo_perl_paths(base);base.clear();base.update(fixed);actual=run_chain()
  assert actual=={'preserved':True,'moduleLoaded':True,'perlExit':0},'FIXED_NESTED_MODULE_RESOLUTION_FAILED'
  result.update(state='PASS_PINNED_RECURSIVE_MAKE_PERL_PATHS',baseline=baseline,fixed=actual,exactExclusion='PERL5LIB=',makeSHA256=make_pin['sha256'],perlSHA256=perl_pin['sha256'],compilerExecuted=False,configureExecuted=False,spacesAndTwoIncludeEntries=True,recursiveNativeMake=True)
 lease=capture_one(ndk,make,callback=execute)
 assert lease.get('qualified') and lease.get('callbackSucceeded'),'PROBE_MAKE_LEASE'
 text=json.dumps(result,indent=2);assert len(text.encode())<=4096
 with (out/'nested-perl-paths.json').open('x',encoding='utf-8') as f:f.write(text)
 print(json.dumps(result),flush=True);return result
