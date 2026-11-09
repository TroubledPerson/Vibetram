"""Publication privacy regression checks; no credential values are printed."""
import unittest,pathlib,re,json,zipfile
ROOT=pathlib.Path(__file__).resolve().parents[1]
class FixturePrivacy(unittest.TestCase):
 def test_no_contiguous_temporary_identifier_in_bound_rust_sources(self):
  rows=json.loads((ROOT/'ci/source-bindings.json').read_text())
  matches=[r['path'] for r in rows if r['path'].endswith('.rs') and re.search(rb'\bASIA[A-Z0-9]{16}\b',(ROOT/r['path']).read_bytes())]
  self.assertEqual(matches,[],'Credential-shaped temporary identifier literal remains; inspect paths privately')
 def test_actual_rust_test_retains_both_synthetic_cases(self):
  text=(ROOT/'codex-rs/cli/src/doctor/output.rs').read_text();body=text.split('fn redact_detail_preserves_missing_env_diagnostics()',1)[1].split('\n    #[test]',1)[0]
  for prefix,name in [('AKIA','synthetic_access_key_id'),('ASIA','synthetic_temporary_access_key_id')]:
   self.assertIn('format!("{}{}", "'+prefix+'", "TEST".repeat(4))',body)
   self.assertIn('('+name+'.as_str(), "<redacted>")',body)
 def test_legacy_source_zip_has_no_temporary_identifier_literal(self):
  p=ROOT/'Vibetram-Alpha-1.91-Source.zip'
  if not p.exists():return
  with zipfile.ZipFile(p) as z:
   for item in z.infolist():
    self.assertLess(item.file_size,10485760)
    if not item.is_dir():self.assertIsNone(re.search(rb'\bASIA[A-Z0-9]{16}\b',z.read(item)),'Legacy archive needs private review')
if __name__=='__main__':unittest.main()
