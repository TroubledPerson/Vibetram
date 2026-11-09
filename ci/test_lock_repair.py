"""No-compile consistency checks for the narrowly reviewed Cargo lock repair."""
import pathlib,tomllib,hashlib,json,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
class LockRepair(unittest.TestCase):
 def setUp(self):self.raw=(ROOT/'codex-rs/Cargo.lock').read_bytes();self.lock=tomllib.loads(self.raw.decode())
 def test_exact_reviewed_proposal(self):self.assertEqual(hashlib.sha256(self.raw).hexdigest(),'a52305dae660c260e5b33a6dd4b3d0cecb9bf4ef56836dfc0dbf9e587754ff0d')
 def test_all_local_versions_match_manifest(self):
  version=tomllib.loads((ROOT/'codex-rs/Cargo.toml').read_text())['workspace']['package']['version']
  local=[p for p in self.lock['package'] if not p.get('source')]
  self.assertEqual(sum(p['version']==version for p in local),155)
  self.assertTrue(all(p['version']==version for p in local))
 def test_android_libc_declared_and_locked(self):
  manifest=tomllib.loads((ROOT/'codex-rs/arg0/Cargo.toml').read_text())
  self.assertEqual(manifest['target']['cfg(target_os = "android")']['dependencies']['libc'],{'workspace':True})
  entry=next(p for p in self.lock['package'] if p['name']=='codex-arg0')
  self.assertEqual(entry['dependencies'].count('libc'),1)
 def test_external_packages_exactly_preserved(self):
  external=[p for p in self.lock['package'] if p.get('source')]
  self.assertEqual(hashlib.sha256(json.dumps(external,sort_keys=True,separators=(',',':')).encode()).hexdigest(),'65112e5dcab9440d6c1b44a15c4a4e8ac8fe087aba1e97cf87875e20b124de64')
if __name__=='__main__':unittest.main()
