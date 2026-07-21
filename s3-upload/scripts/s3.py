from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit, urlunsplit
from urllib.request import Request, urlopen
from typing import Dict, Optional, Tuple

from config import Connection, mask_access_key

@dataclass
class Response:
    status: int
    body: bytes = b""
    headers: Optional[Dict[str, str]] = None

class TransportError(RuntimeError):
    pass

def encode_key(key: str) -> str:
    return quote(key, safe="/-_.~", encoding="utf-8", errors="strict")

def object_url(conn: Connection, key: str) -> str:
    encoded = encode_key(key)
    p = urlsplit(conn.endpoint)
    if conn.addressing == "virtual":
        host = f"{conn.bucket}.{p.hostname}"
        if p.port:
            host += f":{p.port}"
        return urlunsplit((p.scheme, host, "/" + encoded, "", ""))
    return conn.endpoint.rstrip("/") + "/" + quote(conn.bucket, safe="-_.~") + "/" + encoded

def public_url(base: str, key: str) -> str:
    return base.rstrip("/") + "/" + encode_key(key)

def _sign(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode(), hashlib.sha256).digest()

def _signing_key(secret: str, date: str, region: str) -> bytes:
    return _sign(_sign(_sign(_sign(("AWS4" + secret).encode(), date), region), "s3"), "aws4_request")

def _now(now: Optional[datetime]) -> datetime:
    return (now or datetime.now(timezone.utc)).astimezone(timezone.utc)

def build_put_request(conn: Connection, key: str, body: bytes, content_type: str,
                      now: Optional[datetime] = None) -> Tuple[str, Dict[str, str], bytes]:
    moment = _now(now); amz_date = moment.strftime("%Y%m%dT%H%M%SZ"); date = moment.strftime("%Y%m%d")
    url = object_url(conn, key); parts = urlsplit(url); payload_hash = hashlib.sha256(body).hexdigest()
    headers = {"content-length": str(len(body)), "content-type": content_type, "host": parts.netloc,
               "x-amz-content-sha256": payload_hash, "x-amz-date": amz_date}
    if conn.session_token: headers["x-amz-security-token"] = conn.session_token
    names = sorted(headers); canonical_headers = "".join(f"{n}:{headers[n].strip()}\n" for n in names)
    signed_headers = ";".join(names)
    canonical = "\n".join(["PUT", parts.path or "/", "", canonical_headers, signed_headers, payload_hash])
    scope = f"{date}/{conn.region}/s3/aws4_request"
    string = "\n".join(["AWS4-HMAC-SHA256", amz_date, scope, hashlib.sha256(canonical.encode()).hexdigest()])
    signature = hmac.new(_signing_key(conn.secret_access_key, date, conn.region), string.encode(), hashlib.sha256).hexdigest()
    headers["authorization"] = f"AWS4-HMAC-SHA256 Credential={conn.access_key_id}/{scope}, SignedHeaders={signed_headers}, Signature={signature}"
    return url, headers, body

def presign_get(conn: Connection, key: str, expires: int, now: Optional[datetime] = None) -> str:
    moment = _now(now); amz_date = moment.strftime("%Y%m%dT%H%M%SZ"); date = moment.strftime("%Y%m%d")
    url = object_url(conn, key); parts = urlsplit(url); scope = f"{date}/{conn.region}/s3/aws4_request"
    params = {
        "X-Amz-Algorithm": "AWS4-HMAC-SHA256", "X-Amz-Credential": f"{conn.access_key_id}/{scope}",
        "X-Amz-Date": amz_date, "X-Amz-Expires": str(expires), "X-Amz-SignedHeaders": "host",
    }
    if conn.session_token: params["X-Amz-Security-Token"] = conn.session_token
    query = "&".join(f"{quote(k, safe='-_.~')}={quote(v, safe='-_.~')}" for k, v in sorted(params.items()))
    canonical = "\n".join(["GET", parts.path or "/", query, f"host:{parts.netloc}\n", "host", "UNSIGNED-PAYLOAD"])
    string = "\n".join(["AWS4-HMAC-SHA256", amz_date, scope, hashlib.sha256(canonical.encode()).hexdigest()])
    signature = hmac.new(_signing_key(conn.secret_access_key, date, conn.region), string.encode(), hashlib.sha256).hexdigest()
    return url + "?" + query + "&X-Amz-Signature=" + signature

def http_request(method: str, url: str, headers: Dict[str, str], body: bytes, timeout: int = 30) -> Response:
    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            return Response(response.status, response.read(8192), dict(response.headers))
    except HTTPError as exc:
        return Response(exc.code, exc.read(8192), dict(exc.headers or {}))
    except (URLError, OSError) as exc:
        raise TransportError(str(exc.reason if isinstance(exc, URLError) else exc)) from exc

def put_object(conn: Connection, key: str, body: bytes, content_type: str, *, transport=http_request,
               now: Optional[datetime] = None) -> Response:
    url, headers, payload = build_put_request(conn, key, body, content_type, now)
    response = transport("PUT", url, headers, payload)
    if not 200 <= response.status < 300:
        # Redact before truncating so a credential crossing the output boundary
        # cannot leave a visible prefix in stderr.
        text = response.body.decode("utf-8", "replace")
        replacements = sorted([
            (conn.secret_access_key, "****"),
            (conn.session_token, "****"),
            (conn.access_key_id, mask_access_key(conn.access_key_id)),
        ], key=lambda item: len(item[0]), reverse=True)
        for credential, replacement in replacements:
            if credential:
                text = text.replace(credential, replacement)
                # The transport intentionally bounds response bodies. If that
                # bound cuts a reflected credential, remove its trailing prefix.
                for length in range(len(credential) - 1, 0, -1):
                    if text.endswith(credential[:length]):
                        text = text[:-length] + "****"
                        break
        text = text[:2000]
        raise TransportError(f"HTTP {response.status}: {text}")
    return response
