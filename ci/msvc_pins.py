"""Public hashes from the passing installed-tool probe; never substitute tools."""
import pathlib,json,re
def read_pins():return json.loads((pathlib.Path(__file__).parent/'qualified-msvc.json').read_text(encoding='utf-8'))
def tool_pins(pins,actual):
 for key in ('toolset','sdkVersion','setupSHA256'):assert actual.get(key)==pins[key],'QUALIFIED_MSVC_PIN_MISMATCH:'+key
 expected={x['name'].lower():(x['fileVersion'],x['sha256']) for x in pins['tools']}
 rows=actual.get('vswhereIdentity',[])+actual.get('toolIdentities',[])
 seen={x['name'].lower():(x['fileVersion'],x['sha256']) for x in rows}
 assert len(rows)==len(seen) and expected==seen,'QUALIFIED_MSVC_EXECUTABLE_IDENTITY_MISMATCH'
 normalize=lambda xs:{pathlib.PureWindowsPath(x['relative']).as_posix().lower():x['sha256'] for x in xs}
 assert normalize(pins['libraryInputs'])==normalize(actual.get('libraryInputs',[])),'QUALIFIED_WINDOWS_SDK_INPUT_IDENTITY_MISMATCH'
def rust_pin(pins,version):assert version==pins['rustVersion'],'QUALIFIED_RUST_VERSION_IDENTITY_MISMATCH'
