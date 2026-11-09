import unittest,pathlib,sys
from check_source import validate_manifest,safe_path
GOOD='<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="org.local.vibetrammobile"><application android:allowBackup="false"><activity/></application></manifest>'
class Policy(unittest.TestCase):
 def test_relative_path(self):self.assertEqual(safe_path(pathlib.Path.cwd(),'android/src/a.java'),pathlib.Path.cwd()/'android/src/a.java')
 def test_traversal(self):
  with self.assertRaises(AssertionError):safe_path(pathlib.Path.cwd(),'../private')
 def test_absolute(self):
  with self.assertRaises(AssertionError):safe_path(pathlib.Path.cwd(),'/private')
 def test_windows_drive(self):
  with self.assertRaises(AssertionError):safe_path(pathlib.Path.cwd(),'C:/private')
 def test_unc(self):
  with self.assertRaises(AssertionError):safe_path(pathlib.Path.cwd(),'\\\\server\\private')
 def test_zero_permission(self):validate_manifest(GOOD)
 def test_internet_rejected(self):
  with self.assertRaises(AssertionError):validate_manifest(GOOD.replace('<application','<uses-permission android:name="android.permission.INTERNET"/><application'))
 def test_service_rejected(self):
  with self.assertRaises(AssertionError):validate_manifest(GOOD.replace('<activity/>','<activity/><service/>'))
 def test_provider_rejected(self):
  with self.assertRaises(AssertionError):validate_manifest(GOOD.replace('<activity/>','<activity/><provider/>'))
 def test_backup_rejected(self):
  with self.assertRaises(AssertionError):validate_manifest(GOOD.replace('"false"','"true"'))
 def test_wrong_package(self):
  with self.assertRaises(AssertionError):validate_manifest(GOOD.replace('org.local.vibetrammobile','org.local.other'))
 def test_second_activity(self):
  with self.assertRaises(AssertionError):validate_manifest(GOOD.replace('<activity/>','<activity/><activity/>'))
 def test_sdk_permission(self):
  with self.assertRaises(AssertionError):validate_manifest(GOOD.replace('<application','<uses-permission-sdk-23/><application'))
if __name__=='__main__':unittest.main()
