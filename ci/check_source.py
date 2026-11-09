import pathlib,json,hashlib,xml.etree.ElementTree as ET
def safe_path(root,value):
 assert isinstance(value,str) and value and '\\' not in value and ':' not in value
 p=pathlib.PurePosixPath(value);assert not p.is_absolute() and '..' not in p.parts
 f=root.joinpath(*p.parts);assert f.resolve().is_relative_to(root.resolve())
 assert not any(x.is_symlink() for x in [f,*f.parents] if x.is_relative_to(root))
 return f
def validate_manifest(text):
 root=ET.fromstring(text);ns='{http://schemas.android.com/apk/res/android}'
 assert root.attrib['package']=='org.local.vibetrammobile'
 assert not list(root.findall('uses-permission')) and not list(root.findall('uses-permission-sdk-23'))
 assert not any(root.findall('.//'+x) for x in ['service','provider','receiver','uses-library'])
 app=root.find('application');assert app is not None and app.attrib.get(ns+'allowBackup')=='false'
 assert len(app.findall('activity'))==1
def source_check(root):
 validate_manifest((root/'android/AndroidManifest.xml').read_text(encoding='utf-8'))
 policy=json.loads((root/'ci/publication-policy.json').read_text())
 assert policy['privacy_review_complete'] is True,'Expanded source privacy/provenance review incomplete'
 assert policy['offline_only'] is True
 data=json.loads((root/'ci/source-bindings.json').read_text())
 for r in data:
  f=safe_path(root,r['path']);assert f.is_file()
  assert hashlib.sha256(f.read_bytes()).hexdigest()==r['sha256'],r['path']
 return len(data)
if __name__=='__main__':print('PASS source policy:',source_check(pathlib.Path(__file__).resolve().parents[1]))
