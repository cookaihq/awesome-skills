# API and error notes

## Output

- 成功：stdout 严格一行 URL；stderr 为 `[s3-upload]` 元数据。
- public：用户配置 `S3_UPLOAD_PUBLIC_BASE_URL` 即声明拼接结果可读；Skill 不做 GET/HEAD。
- presigned：stderr 含 `expires_in` 与 UTC `expires_at`。
- Put 成功而 URL 失败：退出 1、stdout 空、stderr 含 `partial_success object_written=true bucket=... key=...`；不得重试 Put。

## Exit codes

| Code | Meaning |
|---|---|
| 0 | 成功，或 dry-run 预检通过 |
| 1 | 网络、HTTP、签名或 URL 运行时错误；检查是否 `object_written=true` |
| 2 | CLI 或连接配置错误、profile 错误 |
| 3 | 本地文件不存在、不可读或超过软上限 |

argparse 用法错误保持 2。v1 不自动重试 429/5xx/网络错误，也不在 401/403 后切换 profile。

## PutObject

单次 PUT，直接覆盖同 key，不先 Head。发送 Content-Length、Content-Type 与 SigV4 headers；不发送 `x-amz-acl: public-read`。响应 body 最多回传前 2000 字符。

对象键是 UTF-8；`/` 保留为分隔符，segment 按 RFC 3986 编码。空格 `%20`、加号 `%2B`、百分号 `%25`。Put、presign、public URL 使用同一编码函数。
