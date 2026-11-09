"""Qualify installed Microsoft x64 tools in a sanitized job-local environment."""
import pathlib,os,re,json,hashlib,shutil,struct,time
EXPORTS=('PATH','INCLUDE','LIB','LIBPATH','VCToolsInstallDir','VCToolsVersion','VCINSTALLDIR','VSINSTALLDIR','WindowsSdkDir','WindowsSDKVersion','UniversalCRTSdkDir','UCRTVersion','VSCMD_ARG_TGT_ARCH','VSCMD_ARG_HOST_ARCH','WindowsSdkBinPath','WindowsSdkVerBinPath','WindowsLibPath')
def parse_exports(text):
 allowed={k.lower():k for k in EXPORTS};out={}
 for line in text.splitlines():
  key,sep,value=line.partition('=')
  if sep and key.lower() in allowed:
   normalized=allowed[key.lower()];assert '\x00' not in value
   if normalized in out:assert out[normalized]==value,'CONFLICTING_VC_ENVIRONMENT_KEY'
   else:out[normalized]=value
 for key in ('PATH','INCLUDE','LIB','LIBPATH','VCToolsInstallDir','VCToolsVersion','WindowsSdkDir','WindowsSDKVersion','VSCMD_ARG_TGT_ARCH','VSCMD_ARG_HOST_ARCH'):assert out.get(key),'MISSING_VC_ENVIRONMENT_'+key
 assert out['VSCMD_ARG_TGT_ARCH']=='x64' and out['VSCMD_ARG_HOST_ARCH']=='x64','MSVC_X64_HOST_AND_TARGET_REQUIRED'
 return out
def discovery_env(base,machine):
 out=base.copy()
 for name in ('ProgramData','ALLUSERSPROFILE'):
  value=machine.get(name)
  assert value and pathlib.PureWindowsPath(value)==pathlib.PureWindowsPath(r'C:\ProgramData'),'EXPECTED_PUBLIC_PROGRAMDATA_LOCATION_REQUIRED'
  out[name]=value
 return out
def apply_exports(base,exports,link,compiler,archiver):
 # Do not import the full developer-shell environment or any credentials.
 out=base.copy();out.update({k:v for k,v in exports.items() if k in EXPORTS})
 out.update(CARGO_TARGET_X86_64_PC_WINDOWS_MSVC_LINKER=str(link),CC_x86_64_pc_windows_msvc=str(compiler),CXX_x86_64_pc_windows_msvc=str(compiler),AR_x86_64_pc_windows_msvc=str(archiver),HOST_CC=str(compiler),HOST_CXX=str(compiler))
 return out
def required_inputs(tools,sdk,version):
 return [tools/'lib/x64/libcmt.lib',sdk/'Lib'/version/'um/x64/kernel32.lib',sdk/'Lib'/version/'ucrt/x64/ucrt.lib',tools/'include/vcruntime.h',sdk/'Include'/version/'ucrt/stdio.h',sdk/'Include'/version/'um/Windows.h']
def library_directories(value):
 paths=[pathlib.PureWindowsPath(p.strip().strip('"')) for p in value.split(';') if p.strip()]
 assert paths and all(p.is_absolute() and '..' not in p.parts for p in paths),'INVALID_MSVC_LIBRARY_DIRECTORY'
 return paths
def pe_x64(data):
 assert data[:2]==b'MZ' and len(data)>=64,'QUALIFICATION_PE_MISSING';at=struct.unpack_from('<I',data,60)[0]
 assert at+6<=len(data) and data[at:at+4]==b'PE\0\0' and struct.unpack_from('<H',data,at+4)[0]==0x8664,'QUALIFICATION_NOT_X64_PE'
def qualify_msvc(base,work,guard):
 assert os.name=='nt';begin=time.monotonic();out={'state':'MSVC_QUALIFICATION_PENDING','compiledTinyFixtures':0,'executedFixture':False};result=work/'msvc-qualification.json'
 def run(args,env=base,timeout=60):
  assert time.monotonic()-begin<180,'TINY_MSVC_QUALIFICATION_DEADLINE'
  return guard.run(args,cwd=work,env=env,capture=True,timeout=timeout)
 def identities(files):
  script=work/('msvc-identity-'+str(len(list(work.glob('msvc-identity-*.ps1'))))+'.ps1')
  values=','.join("'"+str(p).replace("'","''")+"'" for p in files)
  script.write_text("$ErrorActionPreference='Stop'; $rows=@(); foreach($p in @("+values+")){$s=Get-AuthenticodeSignature -LiteralPath $p; $v=(Get-Item -LiteralPath $p).VersionInfo; if($s.Status -ne 'Valid' -or $s.SignerCertificate.Subject -notmatch 'CN=Microsoft Corporation(?:,|$)' -or $v.CompanyName.Trim() -ne 'Microsoft Corporation'){throw 'MICROSOFT_EXECUTABLE_PROVENANCE_FAILED'}; $rows+=@{name=[IO.Path]::GetFileName($p); fileVersion=$v.FileVersion; company=$v.CompanyName; authenticode='Valid'; sha256=(Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash.ToLowerInvariant()}}; ConvertTo-Json -InputObject @($rows) -Depth 4 -Compress",encoding='utf-8')
  pwsh=shutil.which('pwsh',path=base['PATH']);assert pwsh,'HOSTED_POWERSHELL_MISSING'
  return json.loads(run([pwsh,'-NoLogo','-NoProfile','-NonInteractive','-File',script],timeout=30).stdout)
 try:
  original=shutil.which('link.exe',path=base['PATH']);out['previousPathResolvedLink']=original
  vswhere=pathlib.Path(base.get('PROGRAMFILES(X86)',os.environ.get('ProgramFiles(x86)',r'C:\Program Files (x86)')))/'Microsoft Visual Studio/Installer/vswhere.exe'
  assert vswhere.is_file(),'PREINSTALLED_VSWHERE_MISSING';out['vswhereIdentity']=identities([vswhere])
  args=[vswhere,'-latest','-products','*','-requires','Microsoft.VisualStudio.Component.VC.Tools.x86.x64','-property','installationPath']
  raw=run(args,timeout=30).stdout.strip();out['sanitizedBaselineInstallationCount']=len(raw.splitlines()) if raw else 0
  discovery=discovery_env(base,os.environ)
  raw=run(args,env=discovery,timeout=30).stdout.strip();out['publicProgramDataInstallationCount']=len(raw.splitlines()) if raw else 0
  assert raw,'VS_INSTALLATION_DISCOVERY_EMPTY_WITH_PUBLIC_PROGRAMDATA'
  assert len(raw.splitlines())==1,'AMBIGUOUS_VS_INSTALLATION'
  assert not any(c in raw for c in '\r\n"&|<>^%!'),'UNSAFE_VS_INSTALLATION_PATH'
  install=pathlib.Path(raw);setup=install/'Common7/Tools/VsDevCmd.bat';assert setup.is_file(),'OFFICIAL_VSDEV_CMD_MISSING'
  batch=work/'msvc-setup.cmd';batch.write_text('@echo off\r\ncall "'+str(setup)+'" -no_logo -arch=x64 -host_arch=x64 >nul\r\nif errorlevel 1 exit /b 1\r\n'+'\r\n'.join('set '+k for k in EXPORTS)+'\r\nexit /b 0\r\n',encoding='utf-8')
  cmd=pathlib.Path(base['SystemRoot'])/'System32/cmd.exe'
  exported=parse_exports(run([cmd,'/d','/c',str(batch)],env=discovery,timeout=60).stdout)
  tools=pathlib.Path(exported['VCToolsInstallDir']);sdk=pathlib.Path(exported['WindowsSdkDir']);sdkversion=exported['WindowsSDKVersion'].rstrip('\\/')
  assert tools.resolve().is_relative_to((install/'VC/Tools/MSVC').resolve()),'VC_TOOLS_OUTSIDE_DISCOVERED_INSTALLATION'
  assert re.fullmatch(r'14\.\d+\.\d+',exported['VCToolsVersion']) and tools.name==exported['VCToolsVersion'],'UNEXPECTED_MSVC_TOOLSET_IDENTITY'
  assert re.fullmatch(r'10\.0\.\d+\.0',sdkversion),'UNEXPECTED_WINDOWS_SDK_IDENTITY'
  bin=tools/'bin/Hostx64/x64';cl=bin/'cl.exe';link=bin/'link.exe';lib=bin/'lib.exe'
  assert all(p.is_file() for p in (cl,link,lib)),'X64_MSVC_EXECUTABLE_MISSING';out['toolIdentities']=identities([cl,link,lib])
  required=required_inputs(tools,sdk,sdkversion)
  out.update(installation=raw,toolset=exported['VCToolsVersion'],sdkVersion=sdkversion,explicitLinker=str(link),requiredInputs=[{'relative':str(p.relative_to(tools if p.is_relative_to(tools) else sdk)),'present':p.is_file()} for p in required])
  assert all(p.is_file() for p in required),'MSVC_OR_WINDOWS_SDK_INPUT_MISSING'
  env=apply_exports(base,exported,link,cl,lib)
  assert pathlib.Path(shutil.which('link.exe',path=env['PATH']) or '').resolve()==link.resolve(),'PATH_STILL_RESOLVES_NON_MSVC_LINKER'
  libraries=library_directories(env['LIB']);out['libraryDirectories']=[str(p) for p in libraries]
  assert pathlib.PureWindowsPath(tools/'lib/x64') in libraries and pathlib.PureWindowsPath(sdk/'Lib'/sdkversion/'um/x64') in libraries,'MSVC_OR_SDK_LIBRARY_PATH_MISSING'
  # Signed Microsoft file/version plus real tiny links qualify the linker, not help-command exit semantics.
  c=work/'tiny-sdk.c';c.write_text('#include <windows.h>\nint main(void) { return GetCurrentProcessId() == 0; }\n',encoding='utf-8');cexe=work/'tiny-sdk.exe'
  run([cl,'/nologo','/WX','/W4','/MT',str(c),'/Fo'+str(work/'tiny-sdk.obj'),'/Fe'+str(cexe)],env,timeout=60);pe_x64(cexe.read_bytes());out['compiledTinyFixtures']=1
  rust=work/'tiny-msvc.rs';rust.write_text('fn main() {}\n',encoding='utf-8');rexe=work/'tiny-msvc.exe'
  version=run(['rustc','--version'],env,timeout=30).stdout.strip();assert version.startswith('rustc 1.95.0 '),'PINNED_RUST_REQUIRED_FOR_LINK_PROBE'
  run(['rustc','--edition','2024','--target','x86_64-pc-windows-msvc','-C','linker='+str(link),str(rust),'-o',str(rexe)],env,timeout=60);pe_x64(rexe.read_bytes());out['compiledTinyFixtures']=2
  assert time.monotonic()-begin<180,'TINY_MSVC_QUALIFICATION_DEADLINE'
  out.update(state='PASS_INSTALLED_MSVC_X64_AND_WINDOWS_SDK',installation=raw,setupSHA256=hashlib.sha256(setup.read_bytes()).hexdigest(),toolset=exported['VCToolsVersion'],sdkVersion=sdkversion,explicitLinker=str(link),rustVersion=version,libraryInputs=[{'relative':str(p.relative_to(tools if p.is_relative_to(tools) else sdk)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in required],fixtures=[{'name':p.name,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in (cexe,rexe)])
  return env,out
 except BaseException as error:
  out.update(state='FAILED_MSVC_QUALIFICATION_NO_FULL_BUILD',error=str(error)[:500]);raise
 finally:
  out['elapsedSeconds']=round(time.monotonic()-begin,3);result.write_text(json.dumps(out,indent=2),encoding='utf-8');guard.check();print(json.dumps(out,indent=2),flush=True)
