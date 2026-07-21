from datetime import datetime, timezone
from config import Connection
from s3 import build_put_request, encode_key, object_url, presign_get, public_url

def conn(**kw):
    d=dict(access_key_id="AKIDEXAMPLE",secret_access_key="wJalrXUtnFEMI/K7MDENG+bPxRfiCYEXAMPLEKEY",bucket="bucket",endpoint="https://s3.amazonaws.com",region="us-east-1",addressing="virtual")
    d.update(kw); return Connection(**d)
NOW=datetime(2013,5,24,0,0,0,tzinfo=timezone.utc)
def test_key_encoding_shared():
    assert encode_key("a b/中+%.txt")=="a%20b/%E4%B8%AD%2B%25.txt"
    assert object_url(conn(),"a b/中+%.txt")=="https://bucket.s3.amazonaws.com/a%20b/%E4%B8%AD%2B%25.txt"
def test_put_signature_is_deterministic():
    url,h,b=build_put_request(conn(),"test.txt",b"hello","text/plain",NOW)
    assert url=="https://bucket.s3.amazonaws.com/test.txt"
    # Independently cross-checked against botocore 1.42.97 S3SigV4Auth.
    assert h["authorization"].endswith("Signature=e225efe81d5d14ab1fa6592aef323342207dd6ca77569cc9de00a2a04b671098")
    assert b==b"hello"
def test_presign_deterministic_and_token_encoded():
    u=presign_get(conn(session_token="a+b c"),"test.txt",3600,NOW)
    assert "X-Amz-Security-Token=a%2Bb%20c" in u
    # Independently cross-checked against botocore 1.42.97 S3SigV4QueryAuth.
    assert u.endswith("X-Amz-Signature=c839df845c4a4a945a398b87eef04ac8fe9a6a73342658ef66ea1684f2401978")
def test_path_style_put_and_session_token_are_signed():
    c=conn(endpoint="https://localhost:9000",bucket="my.bucket",addressing="path",session_token="token")
    url,headers,_=build_put_request(c,"a//./中.txt",b"hello","text/plain",NOW)
    assert url=="https://localhost:9000/my.bucket/a//./%E4%B8%AD.txt"
    assert headers["x-amz-security-token"]=="token"
    assert "x-amz-security-token" in headers["authorization"] and "x-amz-acl" not in headers
    # Independently cross-checked against botocore 1.42.97 S3SigV4Auth.
    assert headers["authorization"].endswith("Signature=9199e1a536ac0283952f01ddb64925ee6cdfab16cca63d874c4ba7c97d5111e6")
def test_put_presign_and_public_url_share_key_encoding():
    key="a//./中 +%.txt"; encoded="a//./%E4%B8%AD%20%2B%25.txt"; c=conn()
    assert object_url(c,key).endswith("/"+encoded)
    assert presign_get(c,key,60,NOW).split("?",1)[0].endswith("/"+encoded)
    assert public_url("https://cdn.example/",key)=="https://cdn.example/"+encoded
