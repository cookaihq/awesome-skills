# Provider rules

| Provider | Endpoint | Region | Addressing |
|---|---|---|---|
| `custom` | 必填；用户保证兼容 AWS SigV4 PutObject/presigned GET | 默认 `us-east-1` | 默认 `path` |
| `aws-s3` | 显式值优先；`us-east-1` → `https://s3.amazonaws.com`，其他 region → `https://s3.{region}.amazonaws.com` | 默认 `us-east-1` | 默认 `virtual` |
| `cloudflare-r2` | 必须给完整 `https://<account-id>.r2.cloudflarestorage.com` endpoint | 默认 `auto` | 默认 `path` |

显式 endpoint、region、addressing 始终覆盖 preset。签名 service 固定为 `s3`。

Endpoint 只允许 HTTP(S) host 和可选 port；禁止 userinfo、非根 path、query、fragment。缺 scheme 补 `https://`。virtual-style 只支持 DNS endpoint 和 DNS-compatible bucket；IP、localhost 使用 path-style。

OSS/COS 不是 v1 provider 值。加入新 preset 前必须以官方资料或真实桶契约测试确认同一 PutObject/presigned GET 实现，而不是引入厂商 SDK。
