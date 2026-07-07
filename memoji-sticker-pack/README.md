# memoji-sticker-pack

从**一张人物照片**生成一套 **Apple Memoji 风格（拟我表情）** 的表情贴纸包：先把照片转成一张「基准 Memoji」头像锁定长相，再以它为参考并发生成多个表情（默认 16 个），输出**透明底 PNG** + 可浏览的 `index.html` 画廊。

这是一个**编排型 skill**——自己不调图像 API，而是循环调用同仓库的 [`image-2`](../image-2/)（`gpt-image-2`）的 `create_task.sh`，复用它的 key 链、轮询、下载、401 兜底。

## 效果

| | |
|---|---|
| 输入 | 一张人脸照片（本地路径 / 公网 URL / data URI，`.heic` 亦可） |
| 输出 | `base.png` + `01-smile.png … 16-*.png`（透明底）+ `manifest.json` + `index.html` |
| 默认表情 | 微笑 · 大笑 · 狂笑 · 大哭 · 流泪 · 惊讶 · 比心 · 点赞 · 爱心眼 · 生气 · 瞪眼 · 思考 · 眨眼 · 翻白眼 · 捂脸 · OK手势 |

## 工作原理

1. **预处理**：本地照片用 `sips`（缺失回退 `ffmpeg`）缩到 ≤768px → data URI（规避命令行 ARG_MAX）。
2. **基准 Memoji**：`gpt-image-2` 图生图 → `base.png`，锁定人物长相与风格。
3. **逐表情（并发）**：以基准图为参考、只改表情/动作，**并发提交** N 张（墙钟≈单张耗时，而非 N×）。每张失败自动重试一次再跳过。
4. **抠图**：`gpt-image-2` 渠道不支持透明背景（见下方「实现说明」），故让模型出**纯绿幕底**，再用 `cutout.py`（PIL + numpy）按到角落色的距离键控成真透明，并去绿边。
5. **画廊**：`build_gallery.py` 生成 `manifest.json` + `index.html`（棋盘格背景显示透明区域）。

## 依赖

- 同平台已安装 [`image-2`](../image-2/) skill（脚本按 `~/.claude/skills/image-2*/scripts/create_task.sh` 定位）。
- foxapi.cc 的 key（与 image-2 共用 `X_API_KEY`）。
- Python3 + `Pillow` + `numpy`（用于抠图）；macOS `sips`（或 `ffmpeg`）用于缩图。

## 用法

```bash
# 先看计划 + 预计调用次数（不消耗积分）
bash scripts/gen_pack.sh --image "./me.jpg" --name "小赵" --plan

# 出整套（默认 16 表情）
bash scripts/gen_pack.sh --image "./me.jpg" --name "小赵"

# 只出一张基准头像
bash scripts/gen_pack.sh --image "./me.jpg" --mode single

# 自定义表情（英文描述效果最好）
bash scripts/gen_pack.sh --image "./me.jpg" \
  --expressions "wink:playful wink;peace:peace sign;shy:shy and blushing"
```

### 参数

| 参数 | 说明 |
|---|---|
| `--image PATH` | 必填。本地路径 / 公网 URL / data URI |
| `--name NAME` | 人物名/包名，影响输出目录 `./memoji-<name>/` 与画廊标题 |
| `--outdir DIR` | 自定义输出目录 |
| `--mode pack\|single` | `pack`=整套(默认)，`single`=只出基准头像 |
| `--count N` | 只取前 N 个表情 |
| `--expressions "slug:描述;..."` | 覆盖默认表情 |
| `--resolution WxH` | 贴纸分辨率，默认 `1024x1024` |
| `--no-retry` | 关闭失败重试 |
| `--base-url URL` | 复用已有基准图 URL（跳过基准生成、省一次积分、可断点续跑） |
| `--use-local-key` | 允许读 `~/.config/image-2/.env` 里的 key |
| `--plan` | 只打印计划与调用次数，不生成、不消耗积分 |

## 成本

一套 pack = **1（基准）+ N（表情）** 次 `gpt-image-2` 调用（默认 17 次）；开启失败重试时最坏 `1 + 2N`。`single` 模式 1 次。运行前请务必用 `--plan` 预览并向用户确认——**会消耗 foxapi 积分**。

## 输出结构

```
memoji-<name>/
  base.png                  # 基准头像（透明底）
  01-smile.png … NN-*.png   # 各表情，透明底 PNG
  manifest.json             # 名称、基准图、表情列表映射
  index.html                # 画廊
  .log-*.txt                # 每次调用日志（排错用）
```

## 实现说明（踩过的坑）

- **`background` 参数不被渠道支持**：`gpt-image-2` 渠道对 `background=auto` 返回 422，故不传该参数。
- **别要 "transparent background"**：模型会把透明棋盘格纹理**画进图里**。改为要**纯绿幕底** + 事后抠图。主体是暖色系时绿幕不撞色，抠得干净。
- **图生图很慢**：单张约 2–4 分钟，故多张**并发**提交而非顺序。
- 已知小瑕疵：个别发丝边缘可能有极轻微绿残留（绿幕抠图通病），可按需调 `cutout.py` 的 `--hard/--soft` 阈值。
