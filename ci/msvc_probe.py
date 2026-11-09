"""Tiny installed-tool qualification only; never invoke Cargo or app compilation."""
import os,pathlib,json,shutil
from check_source import source_check
from build_guard import Guard,clean_env,MIN_FREE,MAX_OUTPUT
from msvc_env import qualify_msvc
ROOT=pathlib.Path(__file__).resolve().parents[1]
def main():
 assert os.name=='nt' and os.environ.get('GITHUB_REPOSITORY')=='TroubledPerson/Vibetram' and os.environ.get('GITHUB_REF')=='refs/heads/main'
 event=json.loads(pathlib.Path(os.environ['GITHUB_EVENT_PATH']).read_text())
 assert os.environ['GITHUB_EVENT_NAME']=='push' and '[msvc-probe-191]' in event['head_commit']['message']
 source_check(ROOT);work=ROOT/'msvc-probe-work';out=ROOT/'msvc-probe-output';assert not work.exists() and not out.exists()
 assert shutil.disk_usage(ROOT).free>=MIN_FREE+MAX_OUTPUT
 work.mkdir();out.mkdir()
 for name in ('tmp','home','profile','profile/AppData/Local','profile/AppData/Roaming'):(work/name).mkdir(parents=True,exist_ok=True)
 env=clean_env(os.environ,work);guard=Guard(ROOT,work,out,env)
 _,result=qualify_msvc(env,work,guard)
 assert result['state']=='PASS_INSTALLED_MSVC_X64_AND_WINDOWS_SDK' and result['compiledTinyFixtures']==2 and not result['executedFixture']
 source_check(ROOT)
if __name__=='__main__':main()
