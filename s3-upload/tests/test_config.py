import os
from pathlib import Path
import pytest
from config import ConfigError, parse_dotenv, resolve_connection

BASE={"S3_UPLOAD_ACCESS_KEY_ID":"ACCESS12345678","S3_UPLOAD_SECRET_ACCESS_KEY":"secret-value","S3_UPLOAD_BUCKET":"bucket","S3_UPLOAD_ENDPOINT":"localhost:9000"}
def resolve(tmp_path, env=None, **cli):
    return resolve_connection(environ=env or BASE,cwd=str(tmp_path),use_local_key=False,config_home=str(tmp_path/"home"),cli=cli)
def test_dotenv_and_layering(tmp_path):
    (tmp_path/".env").write_text("S3_UPLOAD_BUCKET=low\nS3_UPLOAD_REGION=low\n")
    (tmp_path/".env.local").write_text("S3_UPLOAD_BUCKET=middle\n")
    c=resolve_connection(environ={**BASE,"S3_UPLOAD_BUCKET":"high"},cwd=str(tmp_path),use_local_key=False,config_home=str(tmp_path/"never"),cli={})
    assert (c.bucket,c.region)==("high","low")
    assert parse_dotenv("A=1\nA='2' # no inline after quoted\n")["A"].startswith("2")
def test_provider_defaults_and_overrides(tmp_path):
    env={k:v for k,v in BASE.items() if k!="S3_UPLOAD_ENDPOINT"}|{"S3_UPLOAD_PROVIDER":"aws-s3"}
    c=resolve(tmp_path,env); assert c.endpoint=="https://s3.amazonaws.com" and c.addressing=="virtual"
    env["S3_UPLOAD_REGION"]="eu-west-1"; assert resolve(tmp_path,env).endpoint=="https://s3.eu-west-1.amazonaws.com"
    r2={**BASE,"S3_UPLOAD_PROVIDER":"cloudflare-r2"}; c=resolve(tmp_path,r2); assert (c.region,c.addressing)==("auto","path")
def test_ranges_and_endpoint(tmp_path):
    for field,value in [("S3_UPLOAD_MAX_BYTES","0"),("S3_UPLOAD_PRESIGN_EXPIRES","604801")]:
        with pytest.raises(ConfigError): resolve(tmp_path,{**BASE,field:value})
    with pytest.raises(ConfigError): resolve(tmp_path,{**BASE,"S3_UPLOAD_ENDPOINT":"https://user@host/path"})
    with pytest.raises(ConfigError): resolve(tmp_path,{**BASE,"S3_UPLOAD_ENDPOINT":"https://host:abc"})
    with pytest.raises(ConfigError): resolve(tmp_path,{**BASE,"S3_UPLOAD_ENDPOINT":"https://host:99999"})
    with pytest.raises(ConfigError): resolve(tmp_path,{**BASE,"S3_UPLOAD_PUBLIC_BASE_URL":"javascript:alert(1)"})
def test_dotenv_preserves_hash_inside_quotes():
    assert parse_dotenv("A='value # inside' # outside\n")["A"] == "value # inside"
def test_virtual_dns_and_ip_validation(tmp_path):
    ok={**BASE,"S3_UPLOAD_ENDPOINT":"dead.beef.example","S3_UPLOAD_ADDRESSING":"virtual"}
    assert resolve(tmp_path,ok).addressing=="virtual"
    invalid=[
        {**BASE,"S3_UPLOAD_ENDPOINT":"127.0.0.1","S3_UPLOAD_ADDRESSING":"virtual"},
        {**BASE,"S3_UPLOAD_ENDPOINT":"bad_host.example","S3_UPLOAD_ADDRESSING":"virtual"},
        {**BASE,"S3_UPLOAD_ENDPOINT":"s3.example","S3_UPLOAD_BUCKET":"a.-bad","S3_UPLOAD_ADDRESSING":"virtual"},
        {**BASE,"S3_UPLOAD_ENDPOINT":"s3.example","S3_UPLOAD_BUCKET":"192.168.1.1","S3_UPLOAD_ADDRESSING":"virtual"},
    ]
    for env in invalid:
        with pytest.raises(ConfigError): resolve(tmp_path,env)
def test_profile_requires_flag_and_is_secure(tmp_path):
    env={**BASE,"S3_UPLOAD_PROFILE":"prod"}
    with pytest.raises(ConfigError): resolve_connection(environ=env,cwd=str(tmp_path),use_local_key=False,config_home=str(tmp_path/"home"),cli={})
    home=tmp_path/"home"; p=home/"profiles"; p.mkdir(parents=True); home.chmod(0o700); p.chmod(0o700); f=p/"prod.env"
    f.write_text("S3_UPLOAD_ACCESS_KEY_ID=PKEY12345678\nS3_UPLOAD_SECRET_ACCESS_KEY=psecret\nS3_UPLOAD_BUCKET=profile\nS3_UPLOAD_ENDPOINT=localhost:9000\n"); f.chmod(0o600)
    c=resolve_connection(environ={"S3_UPLOAD_BUCKET":"override","S3_UPLOAD_PROFILE":"prod"},cwd=str(tmp_path),use_local_key=True,config_home=str(tmp_path/"home"),cli={})
    assert c.bucket=="override" and c.access_key_id.startswith("PKEY")
    f.chmod(0o644)
    with pytest.raises(ConfigError,match="0600"): resolve_connection(environ={"S3_UPLOAD_PROFILE":"prod"},cwd=str(tmp_path),use_local_key=True,config_home=str(tmp_path/"home"),cli={})
def test_profile_name_traversal(tmp_path):
    with pytest.raises(ConfigError): resolve_connection(environ={"S3_UPLOAD_PROFILE":"../x"},cwd=str(tmp_path),use_local_key=True,config_home=str(tmp_path),cli={})
def test_profile_force_path_style_alias(tmp_path):
    home=tmp_path/"home"; profiles=home/"profiles"; profiles.mkdir(parents=True); home.chmod(0o700); profiles.chmod(0o700)
    profile=profiles/"prod.env"; profile.write_text("S3_UPLOAD_ACCESS_KEY_ID=KEY12345678\nS3_UPLOAD_SECRET_ACCESS_KEY=secret\nS3_UPLOAD_BUCKET=bucket\nS3_UPLOAD_ENDPOINT=localhost:9000\nS3_UPLOAD_FORCE_PATH_STYLE=true\n"); profile.chmod(0o600)
    conn=resolve_connection(environ={"S3_UPLOAD_PROFILE":"prod"},cwd=str(tmp_path),use_local_key=True,config_home=str(home),cli={})
    assert conn.addressing=="path"
def make_profile(home, name, bucket):
    profiles=home/"profiles"; profiles.mkdir(parents=True,exist_ok=True); home.chmod(0o700); profiles.chmod(0o700)
    profile=profiles/f"{name}.env"; profile.write_text(f"S3_UPLOAD_ACCESS_KEY_ID={name.upper()}KEY1234\nS3_UPLOAD_SECRET_ACCESS_KEY=secret\nS3_UPLOAD_BUCKET={bucket}\nS3_UPLOAD_ENDPOINT=localhost:9000\n"); profile.chmod(0o600)
    return profile
def test_profile_selection_order_default_env_and_cli(tmp_path):
    home=tmp_path/"home"; make_profile(home,"default","default-bucket"); make_profile(home,"env","env-bucket"); make_profile(home,"cli","cli-bucket")
    default=resolve_connection(environ={},cwd=str(tmp_path),use_local_key=True,config_home=str(home),cli={})
    selected=resolve_connection(environ={"S3_UPLOAD_PROFILE":"env"},cwd=str(tmp_path),use_local_key=True,config_home=str(home),cli={"profile":"cli"})
    assert default.bucket=="default-bucket" and selected.bucket=="cli-bucket"
def test_profile_does_not_fallback_when_selected_missing(tmp_path):
    home=tmp_path/"home"; make_profile(home,"default","default-bucket")
    with pytest.raises(ConfigError,match="not found"):
        resolve_connection(environ={"S3_UPLOAD_PROFILE":"missing"},cwd=str(tmp_path),use_local_key=True,config_home=str(home),cli={})
def test_without_local_key_does_not_probe_home(tmp_path,monkeypatch):
    monkeypatch.setattr(Path,"exists",lambda self: (_ for _ in ()).throw(AssertionError("home probed")))
    assert resolve_connection(environ=BASE,cwd=str(tmp_path),use_local_key=False,config_home=str(tmp_path/"home"),cli={}).bucket=="bucket"
def test_profile_reader_rejects_symlinks(tmp_path):
    outside=tmp_path/"outside"; make_profile(outside,"prod","outside-bucket")
    home=tmp_path/"home"; home.mkdir(); home.chmod(0o700); (home/"profiles").symlink_to(outside/"profiles",target_is_directory=True)
    with pytest.raises(ConfigError,match="symlink"):
        resolve_connection(environ={"S3_UPLOAD_PROFILE":"prod"},cwd=str(tmp_path),use_local_key=True,config_home=str(home),cli={})
    real_home=tmp_path/"real-home"; profile=make_profile(real_home,"prod","bucket"); target=tmp_path/"external.env"; target.write_text(profile.read_text()); target.chmod(0o600); profile.unlink(); profile.symlink_to(target)
    with pytest.raises(ConfigError,match="symlink"):
        resolve_connection(environ={"S3_UPLOAD_PROFILE":"prod"},cwd=str(tmp_path),use_local_key=True,config_home=str(real_home),cli={})
    link_home=tmp_path/"link-home"; link_home.symlink_to(real_home,target_is_directory=True)
    with pytest.raises(ConfigError,match="symlink"):
        resolve_connection(environ={"S3_UPLOAD_PROFILE":"prod"},cwd=str(tmp_path),use_local_key=True,config_home=str(link_home),cli={})
def test_directory_permissions_and_cli_overrides(tmp_path):
    home=tmp_path/"home"; make_profile(home,"prod","profile-bucket"); home.chmod(0o755)
    with pytest.raises(ConfigError,match="0700"):
        resolve_connection(environ={"S3_UPLOAD_PROFILE":"prod"},cwd=str(tmp_path),use_local_key=True,config_home=str(home),cli={})
    home.chmod(0o700)
    conn=resolve_connection(environ={**BASE,"S3_UPLOAD_PREFIX":"env"},cwd=str(tmp_path),use_local_key=False,config_home=str(home),cli={"provider":"custom","prefix":"cli","max_bytes":5,"public_base_url":"https://cdn.example/","presign_expires":2})
    assert (conn.prefix,conn.max_bytes,conn.public_base_url,conn.presign_expires)==("cli",5,"https://cdn.example",2)
    with pytest.raises(ConfigError,match="cannot be empty"):
        resolve_connection(environ=BASE,cwd=str(tmp_path),use_local_key=False,config_home=str(home),cli={"prefix":""})
def test_addressing_standard_beats_lower_alias(tmp_path):
    (tmp_path/".env.local").write_text("S3_UPLOAD_FORCE_PATH_STYLE=true\n")
    conn=resolve_connection(environ={**BASE,"S3_UPLOAD_ADDRESSING":"virtual","S3_UPLOAD_ENDPOINT":"s3.example"},cwd=str(tmp_path),use_local_key=False,config_home=str(tmp_path/"home"),cli={})
    assert conn.addressing=="virtual"
