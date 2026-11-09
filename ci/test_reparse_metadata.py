import unittest,struct
from reparse_metadata import decode_record,classify_target,stable,stable_record,os_failure,MOUNT_POINT,SYMLINK
def fixture(substitute,printed='',tag=MOUNT_POINT,flags=0):
 a=substitute.encode('utf-16-le');b=printed.encode('utf-16-le');body=struct.pack('<HHHH',0,len(a),len(a),len(b))+(struct.pack('<I',flags) if tag==SYMLINK else b'')+a+b
 return struct.pack('<IHH',tag,len(body),0)+body
class ReparseMetadata(unittest.TestCase):
 root=r'D:\job\work';link=r'D:\job\work\profile\cache\Content.IE5'
 def test_junction_metadata(self):
  x=decode_record(fixture(r'\??\D:\job\work\profile\cache\IE'));self.assertEqual(x['kind'],'JUNCTION');self.assertEqual(classify_target(x,self.root,self.link)['targetJobRelative'],'profile/cache/IE')
 def test_relative_symlink(self):
  x=decode_record(fixture('IE',tag=SYMLINK,flags=1));self.assertEqual(classify_target(x,self.root,self.link)['targetClass'],'INTERNAL_LEXICAL_ONLY_NOT_QUALIFIED')
 def test_unknown_tag(self):
  with self.assertRaises(AssertionError):decode_record(fixture('x',tag=0x8000001B))
 def test_truncated(self):
  for b in (b'',fixture('x')[:-1]):
   with self.assertRaises(AssertionError):decode_record(b)
 def test_oversized(self):
  with self.assertRaises(AssertionError):decode_record(b'x'*17000)
 def test_bad_offsets(self):
  x=bytearray(fixture('x'));struct.pack_into('<H',x,8,3)
  with self.assertRaises(AssertionError):decode_record(x)
 def test_invalid_utf16(self):
  x=bytearray(fixture('x'));x[-2:]=b'\x00\xd8'
  with self.assertRaises(UnicodeError):decode_record(x)
 def test_unknown_flags(self):
  with self.assertRaises(AssertionError):decode_record(fixture('x',tag=SYMLINK,flags=2))
 def test_external_fatal_and_redacted(self):
  x=classify_target(decode_record(fixture(r'\??\C:\outside\private')),self.root,self.link);self.assertEqual(x['targetClass'],'EXTERNAL_TARGET_FATAL');self.assertNotIn('substituteName',x)
 def test_unc_fatal(self):
  x=classify_target(decode_record(fixture(r'\??\UNC\server\share')),self.root,self.link);self.assertEqual(x['targetClass'],'EXTERNAL_OR_AMBIGUOUS_FATAL')
 def test_parent_escape_fatal(self):
  x=classify_target(decode_record(fixture(r'..\..\..\..\outside',tag=SYMLINK,flags=1)),self.root,self.link);self.assertEqual(x['targetClass'],'EXTERNAL_TARGET_FATAL')
 def test_self_cycle_fatal(self):
  x=classify_target(decode_record(fixture(r'\??\D:\job\work\profile\cache\Content.IE5')),self.root,self.link);self.assertEqual(x['targetClass'],'SELF_OR_ANCESTOR_CYCLE_FATAL')
 def test_ancestor_cycle_fatal(self):
  x=classify_target(decode_record(fixture(r'\??\D:\job\work\profile')),self.root,self.link);self.assertEqual(x['targetClass'],'SELF_OR_ANCESTOR_CYCLE_FATAL')
 def test_identity_race_fatal(self):
  with self.assertRaises(AssertionError):stable([{'identity':[1,2,3],'tag':MOUNT_POINT}],[{'identity':[1,2,4],'tag':MOUNT_POINT}])
 def test_tag_race_fatal(self):
  with self.assertRaises(AssertionError):stable([{'identity':[1,2,3],'tag':MOUNT_POINT}],[{'identity':[1,2,3],'tag':SYMLINK}])
 def test_stable(self):stable([{'identity':[1,2,3],'tag':MOUNT_POINT}],[{'identity':[1,2,3],'tag':MOUNT_POINT}])
 def test_target_record_race_fatal(self):
  with self.assertRaises(AssertionError):stable_record(fixture('A'),fixture('B'))
 def test_unfollowed_two_link_cycle_remains_unqualified(self):
  a=classify_target(decode_record(fixture('B',tag=SYMLINK,flags=1)),self.root,r'D:\job\work\A')
  b=classify_target(decode_record(fixture('A',tag=SYMLINK,flags=1)),self.root,r'D:\job\work\B')
  self.assertEqual(a['targetClass'],'INTERNAL_LEXICAL_ONLY_NOT_QUALIFIED');self.assertEqual(b['targetClass'],'INTERNAL_LEXICAL_ONLY_NOT_QUALIFIED')
 def test_access_denied_fatal(self):self.assertEqual(os_failure(5)['state'],'OS_ACCESS_DENIED_STOP')
 def test_sharing_conflict_fatal(self):self.assertEqual(os_failure(32)['state'],'OS_METADATA_UNAVAILABLE_STOP')
if __name__=='__main__':unittest.main()
