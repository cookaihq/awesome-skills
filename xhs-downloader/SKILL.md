---
name: xhs-downloader
description: Use when the user wants to download Xiaohongshu / 小红书 / RedNote work media (images, videos, livephotos) from a post link to a local folder — phrases like "下载这个小红书"、"把这个小红书链接的图/视频存下来"、"小红书视频下载"、"xhslink 下载"、"download this rednote post"、"采集这个小红书作品". Handles one or more post-detail links (space-separated), and when extraction fails for lack of login it opens a browser for QR-code login to obtain a Cookie. Do NOT use for account-wide bulk crawling (a user's whole feed/likes/collections/search lists), for image generation, or for video generation.
---

# xhs-downloader

## What it does

给定一个或多个小红书 / RedNote **作品详情链接**，把图片 / 视频 / livephoto 下载到本地文件夹，输出保存路径 + 元数据 JSON。无 Cookie 导致提取失败（或显式 `--login`）时，弹出有界面浏览器扫码登录，自动抓取 Cookie 并持久化复用。

底层复用本机 clone 的 [XHS-Downloader](https://github.com/JoeanAmier/XHS-Downloader)。上游接口/落盘/Cookie 细节见 [references/upstream-notes.md](references/upstream-notes.md)。

## When to use / NOT use

- ✅ 下载单条/多条作品链接的媒体；只要直链元数据（`--metadata-only`）。
- ❌ 账号批量采集（发布/收藏/点赞/搜索列表）；生成图片；视频生成。

## Setup（首次自动，无需手动）

**首次运行会自动下载并建好环境**——无需手动 clone。定位顺序：
1. `XHS_DOWNLOADER_PATH`（显式指定的 clone 根）
2. dev clone `forked-repos/XHS-Downloader`（本仓开发场景）
3. 托管 clone `vendor/XHS-Downloader`（skill 自己管，已 gitignore）
4. 都没有 → **自动 `git clone` + `uv sync --no-dev`** 到 `vendor/XHS-Downloader`（带进度提示）

前置：本机需有 `git` 和 `uv`。playwright + chromium **不在首次安装**，仅在首次需要扫码登录时按需装入该 venv（普通下载不下 chromium）。`--no-auto-setup` 可关闭自动下载（改为仅报错）。

### 更新上游代码

每次运行会做**短超时（5s）、24h 节流**的只读更新检查；若上游有新版本，stderr 会打印一行 `上游有更新（本地 X → 远端 Y）`。**脚本不会自动更新**——看到该提示应**询问用户**是否更新，用户同意后用 `--update` 重新运行（`git pull --ff-only` + `uv sync`）。`--no-update-check` 跳过检查。

## Usage

```bash
# 基本：下到默认目录（./xhs-downloads 或 XHS_OUTPUT_DIR）
python3 scripts/xhs_dl.py --url "https://www.xiaohongshu.com/explore/XXX?xsec_token=YYY"

# 多链接 + 指定目录 + 相册选图
python3 scripts/xhs_dl.py --url "<link1> <link2>" --output-dir ./out --index 1,2,5

# 只要元数据 + 直链，不下载
python3 scripts/xhs_dl.py --url "<link>" --metadata-only

# 强制先扫码登录再下载（高清视频）
python3 scripts/xhs_dl.py --url "<link>" --login

# 更新上游代码后再下载（用户同意更新时）
python3 scripts/xhs_dl.py --url "<link>" --update
```

**输出**：stdout 一行 JSON 数组（每个作品含 `作品标题/作品类型/作者昵称/作品链接/下载地址/动图地址/saved_dir`）；stderr 人类摘要。退出码 0 成功 / 3 提取为空 / 1 失败 / 2 参数错误。

## 配置（分层，每个变量独立取首个非空来源）

| 变量 | 含义 | 来源顺序 |
|---|---|---|
| `XHS_DOWNLOADER_PATH` | clone 根 | env → .env.local → .env → ~/.config(仅 `--use-local-key`) → 探测 |
| `XHS_COOKIE` | 网页 Cookie | env → .env.local → .env → ~/.config（**自动读**） |
| `XHS_OUTPUT_DIR` | 默认下载目录 | env → .env.local → .env |

`.env` 解析极简、非 shell（`KEY=value`/引号/`#`注释/空行，同名取最后，不展开 `${X}`/`$(...)`）。
Cookie 日志一律 `head4****tail4` 掩码。

> 注：本仓约定第 4 层 `~/.config` 通常仅 `--use-local-key` 才读；**`XHS_COOKIE` 例外，默认自动读**——Cookie 只是用户自己的登录态，无扣费/对外发布副作用，自动复用才符合预期。`XHS_DOWNLOADER_PATH` 仍受 `--use-local-key` 门控。

## 扫码登录流程

无 Cookie 时先无 Cookie 尝试；若提取为空（退出码 3）或用户传 `--login`，打开有界面 Chromium 到小红书，用户用 App 扫码登录（**无需也不要输入账号密码**）；脚本轮询到 `web_session` 后拼出 Cookie 串，存到 `~/.config/xhs-downloader/.env` 并重试一次。Cookie 过期会再次表现为提取为空，从而自然触发重新扫码。

## Pre-Response Checklist

- Cookie 是否全程 `head4****tail4` 掩码、未回显完整值
- 成功是否报告了 saved_dir 与作品数；失败是否如实回传退出码与原因
- 是否仅处理作品详情链接（未越界做账号批量采集）
