---
name: s3-upload
description: Use when the user wants to upload one local file into their own AWS SigV4-compatible S3 bucket (AWS S3, Cloudflare R2, MinIO/custom) and receive a public or presigned URL. Do not use for hosted temporary URLs without a user bucket, HTML preview, remote/base64 input, or bucket administration.
---

# s3-upload

## Overview

将一个本地文件写入用户自己的 AWS SigV4-compatible S3 bucket，并返回可引用 URL。对象键是权威身份；stdout 成功时严格只有一行 URL。

## When to Use

- 用户明确要写入自己的 AWS S3、Cloudflare R2 或已知兼容的 custom/MinIO endpoint。
- 用户有 Access Key、Secret、bucket 和所需 endpoint/region。

不要用于：无自有桶的 72h 临时托管（用 `upload-for-url`）、远程 URL/base64/stdin、HTML 预览、list/delete/copy、建桶、ACL、multipart。

v1 没有 OSS/COS 内置 preset；只有用户明确提供已知兼容本 Skill SigV4 合同的 custom endpoint 时才可尝试。

## CRITICAL

- 上传前告知用户同对象键会直接覆盖；敏感场景先执行 `--dry-run`。
- 默认不发送公开 ACL、不修改桶策略、不自动重试、不做 multipart。
- stdout 只能是一行 URL；日志写 stderr，Access Key 掩码，Secret/Session Token 永不回显。
- 读取凭证档案必须显式使用 `--use-local-key`；未授权不得读取或写入 `~/.config/s3-upload/`。
- presigned URL 必须告知 `expires_in`/`expires_at`。
- 若 stderr 包含 `object_written=true`，对象已经写入但 URL 失败：**不得自动重试 Put**，先报告 bucket/object key。

## Upload Workflow

1. 收集本地文件、bucket、provider/endpoint、region 和凭证。不要让用户在聊天中回显 Secret。
2. 若覆盖风险不明确，先运行：

```bash
python3 scripts/upload.py --file ./artifact.pdf --dry-run
```

3. 用户确认 bucket/object key 后上传：

```bash
python3 scripts/upload.py --file ./artifact.pdf
```

4. 把 stdout URL 返回用户；同时说明 stderr 中的 `url_kind`。presigned 时说明具体到期时间。

## Configuration

普通字段优先级：CLI → process env → `$PWD/.env.local` → `$PWD/.env` → credential profile → provider preset → defaults。dotenv 只读当前目录，不向上递归，不执行 shell。

主字段：`S3_UPLOAD_ACCESS_KEY_ID`、`S3_UPLOAD_SECRET_ACCESS_KEY`、`S3_UPLOAD_SESSION_TOKEN`、`S3_UPLOAD_BUCKET`、`S3_UPLOAD_ENDPOINT`、`S3_UPLOAD_REGION`、`S3_UPLOAD_PROVIDER`、`S3_UPLOAD_PUBLIC_BASE_URL`、`S3_UPLOAD_PREFIX`、`S3_UPLOAD_MAX_BYTES`、`S3_UPLOAD_PRESIGN_EXPIRES`、`S3_UPLOAD_ADDRESSING`、`S3_UPLOAD_PROFILE`。

### Credential profiles

档案位于 `~/.config/s3-upload/profiles/<name>.env`，只在 `--use-local-key` 下读取：

```bash
pbpaste | ./scripts/set_profile.sh prod --stdin
python3 scripts/upload.py --file ./a.png --use-local-key --profile prod
```

项目可在 `.env.local` 中仅钉选 `S3_UPLOAD_PROFILE=prod`，但执行仍须 `--use-local-key`。不要读取 `~/.aws/credentials`。

## Providers

- `custom`（默认）：必须显式 endpoint，默认 `us-east-1` + path-style。
- `aws-s3`：默认 `us-east-1` + virtual-style，并按 region 推导 AWS endpoint。
- `cloudflare-r2`：必须给完整 endpoint，默认 region `auto` + path-style。

完整规则见 [references/providers.md](references/providers.md)，错误和输出合同见 [references/api-notes.md](references/api-notes.md)。

## Common Pitfalls

1. 公开基址是用户声明，不会 GET/HEAD 验证；确认桶/CDN 策略后再依赖它。
2. `--key` 完全覆盖 prefix；空 key、首/尾 `/`、完整 `..` 段会被拒绝。
3. 文件软上限默认 100 MiB，最高 512 MiB；超限不会自动 multipart。
4. local/MinIO endpoint 通常使用 path-style；virtual-style 不支持 IP/localhost。
5. 本地时钟偏差可能造成 403；不自动切换档案或重试。

## Verification Checklist

- [ ] 已提醒同 key 覆盖并在需要时 dry-run
- [ ] stdout 只有 URL，Secret/Session Token 未回显
- [ ] 已说明 public/presigned URL 种类及过期信息
- [ ] `object_written=true` 时未重试 Put
- [ ] 没有修改 ACL、桶策略或读取未授权 home credentials
