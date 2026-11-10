"""Qualify installed Microsoft x64 tools in a sanitized job-local environment."""
import pathlib,os,re,json,hashlib,shutil,struct,time
from msvc_pins import read_pins,tool_pins,rust_pin
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


# Exact normalized line identities from the installed script matching
# qualified-msvc.json, independently compared against a local identical branch.
# Whole vendor-script hash validation remains mandatory before environment use.
PINNED_TELEMETRY_LINES=(
 '19266f8294cc982a757221331f93a192faff9cc442f8dc1f0e37a0874f0cfe3f',
 'a83bfa357bed38963c39f95f4137b2f7805094345c2c5696ec3dc523fa459beb',
 'c7b598c8e65ffb9f7686be61e83b4185dbb62fa6694857fd665d6e5ab1795cb1',
 '74462b300bffafa6c9267a0671ca27a108d5775ae889baea87d54b16e1f38a43',
 'a483732ea58062ebc3db24cdd241e2188d10da781e576f70d0b555ac9c5f7261',
 '2a0b603eb2b22dc91d849de29a929aa9b0661577c25c0163c2c41cfad2f8e257',
 'ba5ec51d07a4ac0e951608704431d59a02b21a4e951acc10505a8dc407c501ee',
 'ba5ec51d07a4ac0e951608704431d59a02b21a4e951acc10505a8dc407c501ee')
def pinned_telemetry_contract(hashes,start,end):
 assert tuple(hashes)==PINNED_TELEMETRY_LINES and len(hashes)==8 and end-start==7,'SETUP_PINNED_BRANCH_CHANGED'
 return {'environmentVariable':'VSCMD_SKIP_SENDTELEMETRY','nonemptyValueSkipsBlock':True,'guardStartLine':start+1,'guardEndLine':end+1,'purpose':'Send-VsDevShellTelemetry -NewInstanceType Cmd','module':'Microsoft.VisualStudio.DevShell.dll','moduleRelativeToPinnedSetupDirectory':True,'moduleReference':'%~dp0','debugVariable':'VSCMD_DEBUG','debugNonemptySynchronousTelemetry':True,'debugEmptyAsynchronousTelemetry':True,'asynchronousPowerShellMajorMinimum':3,'synchronousCommands':1,'asyncCommands':1,'requiredBuildStatementsInBlock':False,'exactNormalizedLineIdentities':list(hashes),'rawVendorScriptNotPublished':True}

def telemetry_setup_contract(text):
 """Recognize only an explicit empty-variable guard around one async telemetry
 command. Unknown setup statements never become optional by their filename.
 Installed-script hash validation is separate and mandatory before using this.
 """
 lines=text.splitlines();headers=[]
 for i,line in enumerate(lines):
  clean=line.strip().lstrip('@').strip()
  if re.fullmatch(r'if\s+(?:/i\s+)?"%VSCMD_SKIP_SENDTELEMETRY%"\s*==\s*""\s*\(',clean,re.I) or re.fullmatch(r'if\s+not\s+defined\s+VSCMD_SKIP_SENDTELEMETRY\s*\(',clean,re.I):headers.append(i)
 assert len(headers)==1,'SETUP_OPTIONAL_GUARD_UNRECOGNIZED'
 start=headers[0];depth=0;body=[];end=None
 for i in range(start,min(len(lines),start+24)):
  line=lines[i];quoted=False;escaped=False
  for char in line:
   if escaped:escaped=False;continue
   if char=='^':escaped=True;continue
   if char=='"':quoted=not quoted
   elif not quoted:
    if char=='(':depth+=1
    elif char==')':depth-=1
   assert depth>=0,'SETUP_OPTIONAL_BLOCK_UNBALANCED'
  assert not quoted and not escaped,'SETUP_OPTIONAL_MULTILINE_COMMAND'
  body.append(line)
  if depth==0:end=i;break
 assert end is not None,'SETUP_OPTIONAL_BLOCK_BOUND'
 normalized=[line.strip().lstrip('@').strip() for line in body]
 identities=[hashlib.sha256(line.encode()).hexdigest() for line in normalized]
 if tuple(identities)==PINNED_TELEMETRY_LINES:return pinned_telemetry_contract(identities,start,end)
 commands=[]
 for line in body[1:]:
  clean=line.strip().lstrip('@').strip()
  if not clean or clean==')' or clean.lower().startswith(('rem ','::')):continue
  if re.fullmatch(r'if\s+exist\s+"[^"\r\n]+"\s*\(',clean,re.I):continue
  assert re.match(r'^start\s',clean,re.I),'SETUP_OPTIONAL_UNKNOWN_STATEMENT'
  assert re.search(r'\bpowershell(?:\.exe)?\b',clean,re.I) and re.search(r'\s-NoProfile\b',clean,re.I),'SETUP_OPTIONAL_NOT_POWERSHELL'
  assert 'Microsoft.VisualStudio.DevShell.dll'.lower() in clean.lower() and re.search(r'\bSend-VsDevShellTelemetry\s+-NewInstanceType\s+Cmd\b',clean,re.I),'SETUP_OPTIONAL_NOT_DEVSHELL_TELEMETRY'
  assert not re.search(r'\b(?:cl\.exe|link\.exe|lib\.exe|rustc|cargo|vcvarsall|set\s+(?:path|include|lib))\b',clean,re.I),'SETUP_OPTIONAL_BUILD_WORK_PRESENT'
  assert not re.search(r'(^|\s)/wait(\s|$)',clean,re.I),'SETUP_OPTIONAL_NOT_ASYNC'
  command=re.search(r'-Command\s+"(.*)"\s*(?:>\s*nul\s*(?:2>&1)?)?$',clean,re.I);assert command,'SETUP_OPTIONAL_COMMAND_SCHEMA'
  payload=re.sub(r"'%VSINSTALLDIR%[\\/]*Common7[\\/]Tools[\\/]Microsoft\.VisualStudio\.DevShell\.dll'","'MODULE'",command.group(1),flags=re.I)
  action=r"Import-Module\s+'MODULE'\s*;\s*Send-VsDevShellTelemetry\s+-NewInstanceType\s+Cmd\s*;?"
  simple=r'&\s*\{\s*'+action+r'\s*\}'
  guarded=r"&\s*\{\s*if\s*\(\s*Test-Path\s+'MODULE'\s*\)\s*\{\s*"+action+r'\s*\}\s*\}'
  assert re.fullmatch(simple,payload,re.I) or re.fullmatch(guarded,payload,re.I),'SETUP_OPTIONAL_PAYLOAD_SCHEMA'
  commands.append(clean)
 assert len(commands)==1,'SETUP_OPTIONAL_ASYNC_COMMAND_COUNT'
 return {'environmentVariable':'VSCMD_SKIP_SENDTELEMETRY','nonemptyValueSkipsBlock':True,'guardStartLine':start+1,'guardEndLine':end+1,'purpose':'Send-VsDevShellTelemetry -NewInstanceType Cmd','module':'Microsoft.VisualStudio.DevShell.dll','asyncCommands':1,'requiredBuildStatementsInBlock':False,'blockSHA256':hashlib.sha256('\n'.join(body).encode()).hexdigest()}

def optional_setup_environment(env,setup,pins=None):
 """Job-local optional telemetry suppression; never change security settings,
 system modules, compiler inputs, or the vendor's installed script.
 """
 import stat
 setup=pathlib.Path(setup);assert setup.is_absolute() and setup.name.lower()=='vsdevcmd.bat' and '..' not in setup.parts,'SETUP_SCRIPT_SCOPE'
 chain=[]
 for path in [*reversed(setup.parents),setup]:
  row=path.lstat();assert not getattr(row,'st_file_attributes',0)&0x400 and not getattr(row,'st_reparse_tag',0),'SETUP_SCRIPT_LINK'
  assert stat.S_ISREG(row.st_mode) if path==setup else stat.S_ISDIR(row.st_mode),'SETUP_SCRIPT_TYPE'
  chain.append((path,(row.st_dev,row.st_ino,row.st_mode)))
 before=setup.lstat();assert 0<before.st_size<=65536,'SETUP_SCRIPT_SIZE_BOUND';data=setup.read_bytes();pins=read_pins() if pins is None else pins
 digest=hashlib.sha256(data).hexdigest();assert digest==pins['setupSHA256'],'QUALIFIED_MSVC_PIN_MISMATCH:setupSHA256'
 text=data.decode('utf-8-sig')
 try:contract=telemetry_setup_contract(text)
 except BaseException as error:
  lines=text.splitlines();guards=[i for i,line in enumerate(lines) if 'VSCMD_SKIP_SENDTELEMETRY' in line];records=[]
  if guards:
   for i in range(guards[0],min(len(lines),guards[0]+24)):
    line=lines[i].strip().lstrip('@').strip()
    if not line or line.lower().startswith(('rem ','::')):continue
    variables=re.findall(r'%([A-Za-z_][A-Za-z0-9_]*)%',line)
    references=[v if v.upper().startswith(('VSCMD_','__VSCMD_','VSINSTALLDIR','VSAPPIDDIR','SYSTEMROOT')) else 'OTHER_VARIABLE_NAME_WITHHELD' for v in variables]
    words=re.findall(r'[A-Za-z_][A-Za-z0-9_.-]*',line.lower());known=[word for word in words if word in ('if','else','not','defined','echo','set','call','start','powershell.exe','powershell','send-vsdevshelltelemetry','import-module','test-path')]
    label=re.search(r'\bcall\s+:([A-Za-z_][A-Za-z0-9_]*)',line,re.I)
    records.append({'line':i+1,'statementKind':words[0] if words else 'PUNCTUATION','knownControlAndPurposeTokens':known[:16],'referencedVendorVariables':references[:8],'simpleConditionLiterals':re.findall(r'"([0-9]{0,4})"',line)[:4],'labelCall':label.group(1) if label else None,'lineSHA256':hashlib.sha256(line.encode()).hexdigest()})
  error.setup_contract_diagnostic={'setupSHA256':digest,'guardLineNumbers':[i+1 for i in guards][:4],'branchStatementMetadata':records,'telemetryMethodPresent':'Send-VsDevShellTelemetry' in text,'rawScriptNotPublished':True,'unrecognizedStatementsRemainFatal':True};raise
 after=setup.lstat();assert (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns)==(after.st_dev,after.st_ino,after.st_size,after.st_mtime_ns),'SETUP_SCRIPT_CHANGED'
 for path,identity in chain:
  row=path.lstat();assert (row.st_dev,row.st_ino,row.st_mode)==identity and not getattr(row,'st_file_attributes',0)&0x400 and not getattr(row,'st_reparse_tag',0),'SETUP_SCRIPT_ANCESTOR_CHANGED'
 result=env.copy();result['VSCMD_SKIP_SENDTELEMETRY']='1';return result,{**contract,'setupSHA256':digest,'installedScriptChanged':False,'securitySettingsChanged':False,'scope':'ONE_SANITIZED_SETUP_CHILD_ENVIRONMENT'}

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
  setup_env,setup_policy=optional_setup_environment(discovery,setup)
  out['setupBackgroundPolicy']=setup_policy
  exported=parse_exports(run([cmd,'/d','/c',str(batch)],env=setup_env,timeout=60).stdout)
  tools=pathlib.Path(exported['VCToolsInstallDir']);sdk=pathlib.Path(exported['WindowsSdkDir']);sdkversion=exported['WindowsSDKVersion'].rstrip('\\/')
  assert tools.resolve().is_relative_to((install/'VC/Tools/MSVC').resolve()),'VC_TOOLS_OUTSIDE_DISCOVERED_INSTALLATION'
  assert re.fullmatch(r'14\.\d+\.\d+',exported['VCToolsVersion']) and tools.name==exported['VCToolsVersion'],'UNEXPECTED_MSVC_TOOLSET_IDENTITY'
  assert re.fullmatch(r'10\.0\.\d+\.0',sdkversion),'UNEXPECTED_WINDOWS_SDK_IDENTITY'
  bin=tools/'bin/Hostx64/x64';cl=bin/'cl.exe';link=bin/'link.exe';lib=bin/'lib.exe'
  assert all(p.is_file() for p in (cl,link,lib)),'X64_MSVC_EXECUTABLE_MISSING';out['toolIdentities']=identities([cl,link,lib])
  required=required_inputs(tools,sdk,sdkversion)
  out.update(installation=raw,toolset=exported['VCToolsVersion'],sdkVersion=sdkversion,explicitLinker=str(link),requiredInputs=[{'relative':str(p.relative_to(tools if p.is_relative_to(tools) else sdk)),'present':p.is_file()} for p in required])
  assert all(p.is_file() for p in required),'MSVC_OR_WINDOWS_SDK_INPUT_MISSING'
  pins=read_pins();out.update(setupSHA256=hashlib.sha256(setup.read_bytes()).hexdigest(),libraryInputs=[{'relative':str(p.relative_to(tools if p.is_relative_to(tools) else sdk)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in required])
  tool_pins(pins,out);out['qualifiedToolPinsVerified']=True
  env=apply_exports(base,exported,link,cl,lib)
  assert pathlib.Path(shutil.which('link.exe',path=env['PATH']) or '').resolve()==link.resolve(),'PATH_STILL_RESOLVES_NON_MSVC_LINKER'
  libraries=library_directories(env['LIB']);out['libraryDirectories']=[str(p) for p in libraries]
  assert pathlib.PureWindowsPath(tools/'lib/x64') in libraries and pathlib.PureWindowsPath(sdk/'Lib'/sdkversion/'um/x64') in libraries,'MSVC_OR_SDK_LIBRARY_PATH_MISSING'
  # Signed Microsoft file/version plus real tiny links qualify the linker, not help-command exit semantics.
  c=work/'tiny-sdk.c';c.write_text('#include <windows.h>\nint main(void) { return GetCurrentProcessId() == 0; }\n',encoding='utf-8');cexe=work/'tiny-sdk.exe'
  run([cl,'/nologo','/WX','/W4','/MT',str(c),'/Fo'+str(work/'tiny-sdk.obj'),'/Fe'+str(cexe)],env,timeout=60);pe_x64(cexe.read_bytes());out['compiledTinyFixtures']=1
  rust=work/'tiny-msvc.rs';rust.write_text('fn main() {}\n',encoding='utf-8');rexe=work/'tiny-msvc.exe'
  version=run(['rustc','--version'],env,timeout=30).stdout.strip();rust_pin(pins,version)
  run(['rustc','--edition','2024','--target','x86_64-pc-windows-msvc','-C','linker='+str(link),str(rust),'-o',str(rexe)],env,timeout=60);pe_x64(rexe.read_bytes());out['compiledTinyFixtures']=2
  assert time.monotonic()-begin<180,'TINY_MSVC_QUALIFICATION_DEADLINE'
  out.update(state='PASS_INSTALLED_MSVC_X64_AND_WINDOWS_SDK',installation=raw,setupSHA256=hashlib.sha256(setup.read_bytes()).hexdigest(),toolset=exported['VCToolsVersion'],sdkVersion=sdkversion,explicitLinker=str(link),rustVersion=version,libraryInputs=[{'relative':str(p.relative_to(tools if p.is_relative_to(tools) else sdk)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in required],fixtures=[{'name':p.name,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in (cexe,rexe)])
  return env,out
 except BaseException as error:
  out.update(state='FAILED_MSVC_QUALIFICATION_NO_FULL_BUILD',error=str(error)[:500]);raise
 finally:
  out['elapsedSeconds']=round(time.monotonic()-begin,3);result.write_text(json.dumps(out,indent=2),encoding='utf-8');guard.check();print(json.dumps(out,indent=2),flush=True)
