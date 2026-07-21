from datetime import datetime, timezone
from pathlib import Path
import upload
from s3 import Response

BASE={"S3_UPLOAD_ACCESS_KEY_ID":"ACCESS12345678","S3_UPLOAD_SECRET_ACCESS_KEY":"do-not-log","S3_UPLOAD_BUCKET":"bucket","S3_UPLOAD_ENDPOINT":"localhost:9000","S3_UPLOAD_PUBLIC_BASE_URL":"https://cdn.example"}
def test_dry_run_does_not_read_or_transport(tmp_path,capsys,monkeypatch):
    f=tmp_path/"a file.txt"; f.write_text("hello")
    monkeypatch.setattr(Path,"read_bytes",lambda self: (_ for _ in ()).throw(AssertionError("read")))
    rc=upload.main(["--file",str(f),"--dry-run"],environ=BASE,cwd=str(tmp_path),config_home=str(tmp_path/"home"),transport=lambda *a: (_ for _ in ()).throw(AssertionError("transport")))
    o=capsys.readouterr(); assert rc==0 and o.out=="" and "dry_run" in o.err and "do-not-log" not in o.err
def test_dry_run_rejects_unreadable_without_reading_body(tmp_path,capsys,monkeypatch):
    f=tmp_path/"x"; f.write_text("x")
    original=Path.open
    monkeypatch.setattr(Path,"open",lambda self,*a,**k: (_ for _ in ()).throw(PermissionError("denied")) if self==f else original(self,*a,**k))
    rc=upload.main(["--file",str(f),"--dry-run"],environ=BASE,cwd=str(tmp_path))
    assert rc==3 and "file_error" in capsys.readouterr().err
def test_public_upload_contract(tmp_path,capsys):
    f=tmp_path/"a file.txt"; f.write_text("hello"); calls=[]
    def tx(*args): calls.append(args); return Response(200)
    rc=upload.main(["--file",str(f),"--prefix","docs"],environ=BASE,cwd=str(tmp_path),transport=tx,now=datetime(2020,1,1,tzinfo=timezone.utc))
    o=capsys.readouterr(); assert rc==0 and o.out=="https://cdn.example/docs/a%20file.txt\n"
    assert calls[0][0]=="PUT" and calls[0][1].endswith("/bucket/docs/a%20file.txt") and calls[0][3]==b"hello"
    assert "url_kind=public" in o.err and "do-not-log" not in o.err
def test_presigned_upload_contract(tmp_path,capsys):
    f=tmp_path/"a.txt"; f.write_text("hello"); env={k:v for k,v in BASE.items() if k!="S3_UPLOAD_PUBLIC_BASE_URL"}
    rc=upload.main(["--file",str(f)],environ=env,cwd=str(tmp_path),transport=lambda *a:Response(200),now=datetime(2020,1,1,tzinfo=timezone.utc))
    o=capsys.readouterr(); assert rc==0 and "X-Amz-Signature=" in o.out and "expires_at=2020-01-01T01:00:00Z" in o.err
def test_file_and_http_errors(tmp_path,capsys):
    assert upload.main(["--file",str(tmp_path/"none")],environ=BASE,cwd=str(tmp_path))==3
    f=tmp_path/"x"; f.write_text("x")
    assert upload.main(["--file",str(f)],environ=BASE,cwd=str(tmp_path),transport=lambda *a:Response(403,b"denied"))==1
    assert capsys.readouterr().out==""
def test_key_rules(tmp_path):
    f=tmp_path/"x"; f.write_text("x")
    for key in ["","/x","x/","a/../x"]:
        assert upload.main(["--file",str(f),"--key",key,"--dry-run"],environ=BASE,cwd=str(tmp_path))==2
    assert upload.main(["--file",str(f),"--key","report..pdf","--dry-run"],environ=BASE,cwd=str(tmp_path))==0
def test_url_failure_after_put_reports_partial_success(tmp_path,capsys,monkeypatch):
    f=tmp_path/"x"; f.write_text("x"); env={k:v for k,v in BASE.items() if k!="S3_UPLOAD_PUBLIC_BASE_URL"}
    monkeypatch.setattr(upload,"presign_get",lambda *args: (_ for _ in ()).throw(RuntimeError("do-not-leak")))
    rc=upload.main(["--file",str(f)],environ=env,cwd=str(tmp_path),transport=lambda *args:Response(200))
    output=capsys.readouterr()
    assert rc==1 and output.out=="" and "object_written=true" in output.err and "do-not-leak" not in output.err
def test_size_mime_and_content_type_guards(tmp_path,capsys,monkeypatch):
    f=tmp_path/"image.unknownext"; f.write_bytes(b"12")
    assert upload.main(["--file",str(f),"--dry-run"],environ={**BASE,"S3_UPLOAD_MAX_BYTES":"1"},cwd=str(tmp_path))==3
    calls=[]
    assert upload.main(["--file",str(f),"--content-type","application/custom"],environ=BASE,cwd=str(tmp_path),transport=lambda *a:(calls.append(a) or Response(200)))==0
    assert calls[0][2]["content-type"]=="application/custom"
    original_open=Path.open
    class GrowingFile:
        def __init__(self,wrapped): self.wrapped=wrapped
        def __enter__(self): return self
        def __exit__(self,*args): self.wrapped.close()
        def fileno(self): return self.wrapped.fileno()
        def read(self,*args): return b"x"*3
    monkeypatch.setattr(Path,"open",lambda self,*a,**k:GrowingFile(original_open(self,*a,**k)) if self==f else original_open(self,*a,**k))
    assert upload.main(["--file",str(f)],environ={**BASE,"S3_UPLOAD_MAX_BYTES":"2"},cwd=str(tmp_path),transport=lambda *a:Response(200))==3
def test_error_body_is_truncated_and_credentials_do_not_leak(tmp_path,capsys):
    f=tmp_path/"x"; f.write_text("x"); env={**BASE,"S3_UPLOAD_SESSION_TOKEN":"session-do-not-log"}
    rc=upload.main(["--file",str(f)],environ=env,cwd=str(tmp_path),transport=lambda *a:Response(403,b"z"*3000))
    output=capsys.readouterr(); assert rc==1 and len(output.err)<2200 and "session-do-not-log" not in output.err and "do-not-log" not in output.err
def test_error_body_reflected_credentials_are_redacted(tmp_path,capsys):
    f=tmp_path/"x"; f.write_text("x"); env={**BASE,"S3_UPLOAD_SESSION_TOKEN":"session-do-not-log"}
    reflected=(env["S3_UPLOAD_ACCESS_KEY_ID"]+" "+env["S3_UPLOAD_SECRET_ACCESS_KEY"]+" "+env["S3_UPLOAD_SESSION_TOKEN"]).encode()
    rc=upload.main(["--file",str(f)],environ=env,cwd=str(tmp_path),transport=lambda *a:Response(403,reflected))
    error=capsys.readouterr().err
    assert rc==1 and "do-not-log" not in error and "session-do-not-log" not in error and "ACCESS12345678" not in error and "ACCE****5678" in error
def test_reflected_credential_crossing_truncation_boundary_is_redacted(tmp_path,capsys):
    f=tmp_path/"x"; f.write_text("x"); secret="SECRET-BOUNDARY-LEAK"
    env={**BASE,"S3_UPLOAD_SECRET_ACCESS_KEY":secret}
    reflected=b"z"*1995+secret.encode()+b" trailing"
    rc=upload.main(["--file",str(f)],environ=env,cwd=str(tmp_path),transport=lambda *a:Response(403,reflected))
    error=capsys.readouterr().err
    assert rc==1 and secret not in error and "SECRE" not in error and len(error)<2200
def test_overlapping_credentials_are_redacted_longest_first(tmp_path,capsys):
    f=tmp_path/"x"; f.write_text("x")
    env={**BASE,"S3_UPLOAD_SECRET_ACCESS_KEY":"SHARED-PREFIX","S3_UPLOAD_SESSION_TOKEN":"SHARED-PREFIX-SENSITIVE-SUFFIX"}
    reflected=env["S3_UPLOAD_SESSION_TOKEN"].encode()
    rc=upload.main(["--file",str(f)],environ=env,cwd=str(tmp_path),transport=lambda *a:Response(403,reflected))
    error=capsys.readouterr().err
    assert rc==1 and "SHARED" not in error and "SENSITIVE-SUFFIX" not in error
def test_path_swap_after_open_uploads_original_descriptor(tmp_path,capsys,monkeypatch):
    safe=tmp_path/"safe"; sensitive=tmp_path/"sensitive"; link=tmp_path/"input"
    safe.write_bytes(b"safe"); sensitive.write_bytes(b"sensitive"); link.symlink_to(safe)
    original_open=Path.open
    def open_then_swap(self,*args,**kwargs):
        handle=original_open(self,*args,**kwargs)
        if self==link:
            link.unlink(); link.symlink_to(sensitive)
        return handle
    monkeypatch.setattr(Path,"open",open_then_swap); calls=[]
    rc=upload.main(["--file",str(link)],environ=BASE,cwd=str(tmp_path),transport=lambda *a:(calls.append(a) or Response(200)))
    assert rc==0 and calls[0][3]==b"safe"
