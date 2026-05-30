---
name: template-preview
description: Use when the user wants to turn a folder of images + copy into a styled showcase page that mimics a known app's UI — phrases like "把这个文件夹做成小红书预览"、"做成小红书个人主页"、"生成小红书风格展示页"、"把这些图做成 XX 风格的页面". v1 ships the xiaohongshu (小红书) personal-homepage template. Generates a self-contained output folder (index.html + assets/) that opens locally and can be uploaded by the preview-share skill. Do NOT use for real deploys, or for uploading/publishing (that's preview-share's job).
---

# template-preview

## Overview

把用户的内容（一组图片 + 文案）渲染成**指定模板风格的自包含展示 HTML 页**。v1 交付**小红书个人主页**模板：头像 + 昵称 + 简介 + 关注/粉丝/获赞 + 笔记双列瀑布流。

输出是一个自包含文件夹（`index.html` + `content.json` + `assets/`），本地双击可打开；所有图片用相对 `<img src="assets/...">` 引用，可被 `preview-share` 依赖扫描整体上传。

**分工**：Claude 负责「理解」（读文件夹、看图、补齐卡片标题等内容字段）；薄脚本 `scripts/generate.py` 负责「机械活」（解析配置、建输出目录、拷素材、套模板渲染）。

## When to Use

- 用户想把一个文件夹的图片+文案做成小红书风格的展示/预览页
- 用户说「做成小红书个人主页」「生成小红书风格页面」

## When NOT to Use

- 像素级 App 克隆（本 skill 只做「神似版式」）
- 发布/上传（那是 `preview-share` 的职责；本 skill 只生成）
- 正式部署到生产环境

## Config Reading（配置读取优先级）

每个变量独立按以下顺序取「首个非空来源」（详见仓库 `CLAUDE.md` 通用约定，本 skill **不读 `~/.config`**）：

1. 进程环境变量（本轮显式注入 `TPL_XHS_NICKNAME=... python3 ...` 或已 export）
2. `$PWD/.env.local`（自动读，不向上递归）
3. `$PWD/.env`（自动读，不向上递归）
4. 内置默认（模板级在 `templates/<t>/defaults.env` 与内置素材；skill 级写在 `generate.py`）

`.env` 解析与 `preview-share` 一致：极简、非 shell。

### 配置变量

skill 级（输出位置）：

| 变量 | 含义 | 默认 |
|------|------|------|
| `TPL_OUTPUT_ROOT` | 输出父目录（在 `$PWD` 下，也可填绝对路径） | `template-preview` |
| `TPL_SUBDIR_PATTERN` | 子目录命名，占位符 `{date}`/`{time}`/`{label}` | `{date}-{time}-{label}` |

xiaohongshu 模板级（人设，前缀 `TPL_XHS_`，均有内置默认）：

| 变量 | 含义 |
|------|------|
| `TPL_XHS_NICKNAME` | 昵称 |
| `TPL_XHS_BIO` | 简介 |
| `TPL_XHS_RED_ID` | 小红书号 |
| `TPL_XHS_AVATAR` | 头像图路径（留空用内置默认） |
| `TPL_XHS_FOLLOWING` | 关注数 |
| `TPL_XHS_FOLLOWERS` | 粉丝数 |
| `TPL_XHS_LIKES` | 获赞与收藏数 |
| `TPL_XHS_FILLER_CARDS` | 填充卡素材目录（留空用内置默认） |
| `TPL_XHS_MIN_CARDS` | 网格补足到的卡片数（默认 6） |

## Workflow（照做）

1. 用户：「把 `<文件夹>` 做成小红书预览」。
2. 列目录、识别内容图（封面）。
3. 补齐内容字段：卡片标题等能推断就推断；**关键缺项（如标题）一次性问用户**；人设用配置/默认，用户想换再说。
4. 写出 `content.json`（见下「数据契约」），`cover` 用绝对路径或相对 `$PWD` 的路径。
5. 跑：`python3 scripts/generate.py --template xiaohongshu --content content.json --label <标签>`
   （先 `--dry-run` 看将生成的路径与素材清单，再正式生成。）
6. 把脚本打印的 `index.html` 路径交给用户。
7. **主动询问用户是否需要在线预览链接**：需要则调用 `preview-share` skill，以该 `index.html` 为入口上传（其依赖扫描自动带上 `assets/`），把同一个 `--label` 透传过去；不需要则到此为止，**不擅自上传**（上传是对外发布动作）。

## content.json 数据契约

```json
{
  "label": "iot-power",
  "notes": [
    { "cover": "/abs/or/$PWD-relative/img1.jpg", "title": "笔记标题", "likes": 1234 }
  ]
}
```

- `notes`：用户本次内容卡，按顺序排在网格前部；作者头像/昵称统一用人设。
- `likes` 可省略，脚本给确定性占位（重渲不跳数）。
- `cover`：绝对路径直接用；相对路径以 `$PWD` 为基准；脚本拷进 `assets/` 并改为相对引用，扩展名保留。

## Options（generate.py）

| 选项 | 说明 |
|------|------|
| `--template NAME` | 模板（v1 仅 `xiaohongshu`） |
| `--content PATH` | content.json 路径 |
| `--label TEXT` | 子目录标签，参与 pattern |
| `--out DIR` | 直接指定输出目录（最高优先级，覆盖 root/pattern；此时 label/pattern 不参与） |
| `--dry-run` | 只打印计划，不写盘 |

## 与 preview-share 的关系

两个独立 skill：`template-preview` 生成自包含文件夹 → `preview-share` 扫描并上传 `index.html` 及其相对资源。本 skill 自身不上传；移交是「询问 + 按需」，真正的待传清单/URL 确认由 `preview-share` 自己的 dry-run 负责，移交时把同一 `--label` 透传过去。

## Pre-Response Checklist

- 是否先看了文件夹、补齐了卡片标题（关键缺项问过用户）
- 是否先 `--dry-run` 看过清单再正式生成
- 是否把可打开的 `index.html` 路径交给用户
- 是否**询问后才**移交 `preview-share`，没擅自上传
