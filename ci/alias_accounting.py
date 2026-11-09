"""Exact job-owned alias accounting policy; no filesystem access."""
import pathlib,re
from reparse_metadata import EXPECTED_ALIAS,EXPECTED_TARGET,MOUNT_POINT,regular_chain
ALIAS_METADATA_BYTES=32768
class AliasAppeared(RuntimeError):pass
def exact_alias(relative):return pathlib.PureWindowsPath(relative)==pathlib.PureWindowsPath(EXPECTED_ALIAS)
def safe_absence(report):
 return report.get('state')=='OS_METADATA_UNAVAILABLE_STOP' and report.get('osError') in (2,3) and report.get('missingUnderOwnedRoot') is True and not report.get('fileIdentity') and not report.get('targetOpened')
def disjoint_roots(roots):
 paths=[pathlib.PureWindowsPath(p) for p in roots];assert all(p.is_absolute() and not p.drive.startswith('\\\\') for p in paths),'AMBIGUOUS_ACCOUNTING_ROOT'
 for i,a in enumerate(paths):
  for b in paths[i+1:]:assert a!=b and not a.is_relative_to(b) and not b.is_relative_to(a),'OVERLAPPING_ACCOUNTING_ROOTS'
def lease_key(report):
 assert report.get('state') in ('CAPTURED_ALIAS_AND_REGULAR_TARGET_METADATA_STOP','PASS_EXACT_ALIAS_LEASED_ACCOUNTING_METADATA'),'UNQUALIFIED_ALIAS_METADATA_STATE'
 assert exact_alias(report.get('relativePath','')) and report.get('reparseTagHex')==hex(MOUNT_POINT),'CHANGED_ALIAS_PATH_OR_TAG'
 assert report.get('targetClass')=='INTERNAL_LEXICAL_ONLY_NOT_QUALIFIED','EXTERNAL_OR_AMBIGUOUS_ALIAS_TARGET'
 assert report.get('physicalTargetMetadataQualified') is True and report.get('targetMetadataOpenedIndependently') is True and report.get('linkTraversed') is False,'PHYSICAL_ALIAS_TARGET_NOT_QUALIFIED'
 assert pathlib.PureWindowsPath(report.get('physicalTargetRelative',''))==pathlib.PureWindowsPath(EXPECTED_TARGET) and pathlib.PureWindowsPath(report.get('targetJobRelative',''))==pathlib.PureWindowsPath(EXPECTED_TARGET),'CHANGED_ALIAS_TARGET'
 assert report.get('physicalTargetTagHex')=='0x0','REPARSE_ALIAS_TARGET'
 link=report.get('fileIdentity');target=report.get('physicalTargetIdentity')
 assert all(isinstance(x,list) and len(x)==3 and all(type(n) is int and n>=0 for n in x) for x in (link,target)),'INVALID_ALIAS_FILE_IDENTITIES'
 rows=report.get('physicalAncestors',[]);assert rows and report.get('physicalAncestorCount')==len(rows),'INCOMPLETE_PHYSICAL_CHAIN'
 normalized=[]
 for i,r in enumerate(rows):
  assert r.get('depth')==i,'AMBIGUOUS_PHYSICAL_CHAIN'
  normalized.append({'identity':r['identity'],'tag':int(r['tagHex'],16),'attributes':int(r['attributes'],16)})
 regular_chain(normalized,link[0],link);assert normalized[-1]['identity']==target,'PHYSICAL_TARGET_IDENTITY_MISMATCH'
 digest=report.get('rawRecordSHA256','');assert re.fullmatch('[0-9a-f]{64}',digest),'INVALID_REPARSE_RECORD_IDENTITY'
 assert type(report.get('rawRecordBytes')) is int and 8<=report['rawRecordBytes']<=16384,'INVALID_REPARSE_RECORD_SIZE'
 return (tuple(link),tuple(target),digest,tuple(tuple(r['identity']) for r in normalized))
def compare_baseline(previous,current):
 if previous is not None:assert previous==current,'ALIAS_OR_PHYSICAL_TARGET_REPLACED'
