# s3-upload

把一个本地文件上传到用户自己的 AWS SigV4-compatible S3 bucket，并输出 public 或 presigned URL。Python 3.9+ 标准库实现，无运行时第三方依赖。

## 支持范围

- AWS S3 (`aws-s3`)
- Cloudflare R2 (`cloudflare-r2`)
- 明确兼容 AWS SigV4 PutObject + presigned GET 的 custom/MinIO endpoint (`custom`)

v1 不含 OSS/COS preset、远程/base64/stdin 输入、ACL、list/delete/copy、multipart、自动重试或 JSON 输出。

## 快速开始

```bash
export S3_UPLOAD_ACCESS_KEY_ID='...'
export S3_UPLOAD_SECRET_ACCESS_KEY='...'
export S3_UPLOAD_BUCKET='my-bucket'
export S3_UPLOAD_ENDPOINT='https://s3.example.com'
export S3_UPLOAD_PUBLIC_BASE_URL='https://cdn.example.com'

python3 scripts/upload.py --file ./report.pdf --dry-run
python3 scripts/upload.py --file ./report.pdf
```

成功 stdout 只有一行 URL；元数据和错误写 stderr。没有 public base 时自动返回默认 3600 秒的 presigned GET URL。

## 命名凭证档案

```bash
# 剪贴板内容是 S3_UPLOAD_* dotenv 字段
pbpaste | ./scripts/set_profile.sh prod --stdin
python3 scripts/upload.py --file ./report.pdf --use-local-key --profile prod
```

档案目录为 `~/.config/s3-upload/profiles/`（目录 0700、文件 0600）。已有档案必须显式加 `--force` 才覆盖。项目可以只在 `.env.local` 钉选 `S3_UPLOAD_PROFILE=prod`。

## CLI

```text
--file PATH                 必填，本地普通文件
--key KEY                   完全覆盖默认对象键
--prefix PREFIX             仅没有 --key 时生效
--content-type TYPE         覆盖 MIME 推断
--profile NAME              选择命名凭证档案
--use-local-key             显式允许读取 home 档案
--provider NAME             custom / aws-s3 / cloudflare-r2
--presign-expires SEC       1…604800，默认 3600
--max-bytes N               1…536870912，默认 104857600
--public-base-url URL       本轮公开基址
--dry-run                   完整预检，不读 body、不签名、不访问网络
```

## 测试

从公开仓根运行：

```bash
python3 -m pytest s3-upload/tests -q
python3 -m compileall -q s3-upload/scripts
```

真实云 smoke 需要用户提供测试桶；CI 不需要云密钥。

详细 provider 规则见 [`references/providers.md`](references/providers.md)，错误合同见 [`references/api-notes.md`](references/api-notes.md)。
