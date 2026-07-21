import os, subprocess
from pathlib import Path
import upload
from s3 import Response
SCRIPT=Path(__file__).parents[1]/"scripts/set_profile.sh"
DATA="S3_UPLOAD_ACCESS_KEY_ID=KEY12345678\nS3_UPLOAD_SECRET_ACCESS_KEY=secret\nS3_UPLOAD_BUCKET=bucket\nS3_UPLOAD_ENDPOINT=localhost:9000\n"
def run(tmp_path,*args,data=DATA):
    env={**os.environ,"S3_UPLOAD_CONFIG_HOME":str(tmp_path/"config")}
    return subprocess.run([str(SCRIPT),*args],input=data,text=True,capture_output=True,env=env)
def test_create_permissions_and_force(tmp_path):
    r=run(tmp_path,"prod","--stdin"); assert r.returncode==0 and "secret" not in r.stderr
    base=tmp_path/"config"; f=base/"profiles/prod.env"
    assert (base.stat().st_mode&0o777)==0o700 and (f.stat().st_mode&0o777)==0o600
    assert run(tmp_path,"prod","--stdin").returncode==1
    assert run(tmp_path,"prod","--stdin","--force").returncode==0
def test_reject_traversal(tmp_path): assert run(tmp_path,"../bad","--stdin").returncode==2
def test_reject_profiles_directory_symlink(tmp_path):
    config=tmp_path/"config"; outside=tmp_path/"outside"; config.mkdir(); outside.mkdir()
    (config/"profiles").symlink_to(outside, target_is_directory=True)
    result=run(tmp_path,"prod","--stdin")
    assert result.returncode==2 and not (outside/"prod.env").exists()
def test_reject_profile_target_symlink(tmp_path):
    config=tmp_path/"config"; profiles=config/"profiles"; outside=tmp_path/"outside.env"
    profiles.mkdir(parents=True); (profiles/"prod.env").symlink_to(outside)
    result=run(tmp_path,"prod","--stdin","--force")
    assert result.returncode==2 and not outside.exists()
def test_created_profile_drives_upload(tmp_path, capsys):
    assert run(tmp_path,"prod","--stdin").returncode==0
    artifact=tmp_path/"a.txt"; artifact.write_text("hello")
    rc=upload.main(["--file",str(artifact),"--use-local-key","--profile","prod"],
                   environ={},cwd=str(tmp_path),config_home=str(tmp_path/"config"),
                   transport=lambda *args: Response(200))
    out=capsys.readouterr()
    assert rc==0 and "X-Amz-Signature=" in out.out
def test_reject_empty_required_and_invalid_quoted_dotenv(tmp_path):
    empty=DATA.replace("S3_UPLOAD_SECRET_ACCESS_KEY=secret","S3_UPLOAD_SECRET_ACCESS_KEY=")
    invalid=DATA.replace("S3_UPLOAD_BUCKET=bucket","S3_UPLOAD_BUCKET='unterminated")
    assert run(tmp_path,"empty","--stdin",data=empty).returncode!=0
    assert run(tmp_path,"invalid","--stdin",data=invalid).returncode!=0
def test_force_replaces_atomically_and_leaves_no_temp(tmp_path):
    assert run(tmp_path,"prod","--stdin").returncode==0
    target=tmp_path/"config/profiles/prod.env"; before=target.stat().st_ino
    changed=DATA.replace("S3_UPLOAD_BUCKET=bucket","S3_UPLOAD_BUCKET=new-bucket")
    assert run(tmp_path,"prod","--stdin","--force",data=changed).returncode==0
    assert target.stat().st_ino!=before and "new-bucket" in target.read_text()
    assert list(target.parent.glob(".prod.*"))==[]
