---
name: memoji-sticker-pack
description: 从一张人物照片生成一套 Apple Memoji 风格（拟我表情）的表情贴纸包。当用户想"把这张照片/自拍做成 Memoji 表情包 / 拟我表情包 / 表情贴纸 / nimoji / Q 版头像表情"，或给一张人脸照片并想要一组不同表情（微笑/大笑/哭/惊讶/比心/点赞等）的卡通贴纸时，使用本技能——即使用户没明确说"Memoji"这个词，只要意图是"照片→一套人物表情贴纸"，也应触发。也支持只生成单张 Memoji 风格头像。不用于：视频/动态表情、OCR、给已有图做裁剪压缩水印等非生成式编辑。
---

# memoji-sticker-pack

## 这个技能做什么

输入**一张人物照片**，产出一套 **Apple Memoji 风格**的表情贴纸包：先把照片转成一张「基准 Memoji」头像锁定长相，再以它为参考逐个生成多个表情（默认 16 个），最后给出透明底 PNG + 可浏览的 `index.html` 画廊。

本技能是**编排器**：自己不调图像 API，而是循环调用已安装的 **image-2 (gpt-image-2)** 技能里的 `create_task.sh`，复用它的 key 链、轮询、下载、401 兜底。所有图片由 `gpt-image-2` 图生图生成。

## 何时使用

- "把这张照片/自拍做成 Memoji 表情包 / 拟我表情包 / 表情贴纸包"
- "用我这张照片生成一组不同表情的卡通贴纸"
- "做个 Q 版头像表情 / nimoji"
- 只要一张 Memoji 风格头像（用 `--mode single`）

## 何时不要用

- 视频 / 动态 Memoji / GIF
- OCR、文档解析
- 对已有图做裁剪、压缩、加水印等非生成式编辑

## 依赖

- 已安装 **image-2** 技能（`~/.claude/skills/image-2*/scripts/create_task.sh`）。没有则先安装它。
- 配好 **foxapi.cc 的 key**（与 image-2 共用，环境变量 `X_API_KEY`，或工作目录下 `.env` / `.env.local`，或 `~/.config/image-2/.env` 配合 `--use-local-key`）。
- macOS 自带 `sips`（用于缩图；缺失时回退 `ffmpeg`）。

## ⚠️ 成本与确认（重要）

每张贴纸都是一次 `gpt-image-2` 调用、**会消耗 foxapi 积分**：

- 一套 pack = **1（基准）+ N（表情）** 次调用（默认 N=16 → 17 次）。
- 失败重试开启时，**最坏情况 = 1 + 2N**（每个表情各重试一次）。
- `single` 模式 = 1 次。

**因此运行真正生成前，必须：**

1. 先跑 `--plan` 拿到准确的调用次数。
2. 把"将生成什么 + 预计调用次数 + 会消耗积分"摘要给用户，**等用户明确确认后**再真正运行。
3. 失败重试默认开启（用户在设计时已授权）；若用户不希望重试，加 `--no-retry`。

## 使用流程（Agent 按此执行）

> 下面命令里的 `$SKILL_DIR` 指**本技能自身所在目录**（含本 SKILL.md 的目录）。Claude Code 触发技能时会告知它的 base directory；执行前先 `SKILL_DIR="<该目录>"`，或直接把 `$SKILL_DIR` 换成绝对路径。脚本内部对 `cutout.py`/`build_gallery.py` 的引用是自定位的（`dirname "$0"`），无需另配。

### 1. 收集输入

- 必须拿到一张人物照片：本地路径 / 公网 URL / data URI 都行（本地路径最常见；脚本会自动缩图编码）。
- 可选：人物名/包名（`--name`）、输出目录（`--outdir`）、只要单张（`--mode single`）、自定义/裁剪表情数（`--count` / `--expressions`）。

### 2. 预览成本，等确认

```bash
bash "$SKILL_DIR/scripts/gen_pack.sh" \
  --image "<照片路径>" --name "<名字>" --plan
```

把输出里的调用次数、输出目录、表情清单转述给用户，明确"会消耗积分"，**等用户确认**。

### 3. 真正生成

```bash
bash "$SKILL_DIR/scripts/gen_pack.sh" \
  --image "<照片路径>" --name "<名字>"
```

脚本会：预处理照片 → 生成 `base.png` → 逐个生成 `NN-<slug>.png`（透明底）→ 写 `manifest.json` + `index.html`。每个表情失败自动重试一次再跳过，结束时汇总失败项。

### 4. 展示结果

- 生成完用 `as_open_url` 打开 `<outdir>/index.html` 给用户看整套（画廊用棋盘格背景显示透明区域）。
- 转述成功/失败数；若有失败项，告诉用户可用 `--expressions "<slug>:<描述>"` 单独补跑。

## 关键参数

| 参数 | 说明 |
|---|---|
| `--image PATH` | 必填。本地路径 / 公网 URL / data URI |
| `--name NAME` | 人物名/包名，影响输出目录 `./memoji-<name>/` 与画廊标题 |
| `--outdir DIR` | 自定义输出目录 |
| `--mode pack\|single` | `pack`=整套(默认)，`single`=只出基准头像 |
| `--count N` | 只取前 N 个表情 |
| `--expressions "slug:描述;..."` | 覆盖默认表情（英文描述效果最好） |
| `--resolution WxH` | 贴纸分辨率，默认 `1024x1024` |
| `--no-retry` | 关闭失败重试 |
| `--use-local-key` | 允许读 `~/.config/image-2/.env` 里的 key |
| `--plan` | 只打印计划与调用次数，不生成、不消耗积分 |

## 默认 16 表情

微笑、大笑、狂笑、大哭、流泪、惊讶、比心、点赞、爱心眼、生气、瞪眼、思考、眨眼、翻白眼、捂脸、OK 手势。
（完整 slug 与英文描述见 `scripts/gen_pack.sh` 顶部的 `DEFAULT_EXPRESSIONS`，那是表情集的唯一真源。）

## 一致性是怎么保证的

16 个表情**不是各自从原始照片重画**（那样每张脸会漂移），而是都以**同一张基准 Memoji**为参考、只改表情/动作。基准图由脚本缩到 ≤640px 编码成 data URI 传给每次调用，所以全套是同一张脸。

## 输出结构

```
memoji-<name>/
  base.png              # 基准头像
  01-smile.png … NN-*.png   # 各表情，透明底 PNG
  manifest.json         # 名称、基准图、表情列表映射
  index.html            # 画廊（浏览器/as_open_url 打开）
  .log-*.txt            # 每次调用的日志（排错用）
```

## 排错

- **"未找到 image-2 的 create_task.sh"**：先装 image-2 技能。
- **基准生成就失败**：多半是 key/积分问题，看 `.log-base.txt`，按 image-2 的报错处理（401 key 无效 / 402 余额不足 / 429 限流）。
- **个别表情总失败**：手势类（OK/点赞/比心）偶尔不稳，可改 `--expressions` 换个描述单独补跑。
- **照片太大/argv 报错**：脚本已缩到 ≤768px；若仍异常，先手动把照片缩小再传。
