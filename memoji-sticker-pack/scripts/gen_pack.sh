#!/usr/bin/env bash
# memoji-sticker-pack — 从一张人物照片生成一套 Apple Memoji 风格表情贴纸包。
#
# 本脚本是「编排器」：不自己调 API，而是循环调用已安装的 image-2 (gpt-image-2)
# 技能里的 create_task.sh，复用它的 key 链、轮询、下载、401 兜底。
#
# 流程：
#   1. 预处理输入照片（缩到 ≤768px → data URI，规避命令行 ARG_MAX）。
#   2. 生成 1 张「基准 Memoji」(base.png)，锁定人物长相与风格。
#   3. 以基准图为参考，逐个生成各表情（透明底 PNG）。每个失败自动重试一次再跳过。
#   4. 写 manifest.json + index.html 画廊。
#
# 成功判定：create_task.sh 退出码 0 且产物文件确实存在（双重判断）。
set -uo pipefail

VERSION="1.0.0"

# ---------------- 默认参数 ----------------
IMAGE=""
NAME="memoji"
OUTDIR=""
MODE="pack"            # pack | single
COUNT=0                # 0 = 全部
RESOLUTION="1024x1024"
EXPRESSIONS_OVERRIDE=""
USE_LOCAL_KEY=0
PLAN_ONLY=0
RETRY=1                # 每个失败的表情重试次数（用户已授权；0 可关闭）
BASE_URL_REUSE=""      # --base-url：复用已有基准图 URL（跳过基准生成、省一次积分）
STAGGER=0.6            # 并行提交每张之间的间隔秒，避免 429 限流
PER_CALL_POLL=6        # 传给 create_task.sh 的轮询间隔
PER_CALL_MAXATT=75     # 传给 create_task.sh 的最大轮询次数（6s×75≈450s 单张上限）

# 输入预处理尺寸
PHOTO_MAXPX=768        # 原始照片缩放上限
REF_MAXPX=640          # 基准图作为参考时的缩放上限

# ---------------- 默认 16 表情 ----------------
# 格式： slug|中文标签|英文表情/动作描述
DEFAULT_EXPRESSIONS=(
  "smile|微笑|a warm gentle closed-mouth smile, friendly eyes"
  "grin|大笑|a big happy open smile showing teeth, cheerful"
  "laugh|狂笑|laughing hard, eyes squeezed shut, head tilted back, one hand near the face"
  "cry|大哭|crying loudly, mouth wide open, streams of cartoon tears"
  "tear|流泪|sad and teary-eyed, pouting lips, a single tear rolling down"
  "surprised|惊讶|shocked and surprised, very wide eyes, open mouth, eyebrows raised high"
  "love|比心|making a finger-heart gesture with the hands, affectionate warm smile"
  "thumbsup|点赞|giving a clear thumbs-up with one hand, confident happy smile"
  "heart-eyes|爱心眼|big heart-shaped eyes, in love, hands near the cheeks, blushing"
  "angry|生气|angry, furrowed eyebrows, frowning mouth, tense and grumpy"
  "glare|瞪眼|annoyed unimpressed flat stare, side-eye, deadpan"
  "think|思考|thinking, one hand resting on the chin, looking up pensively"
  "wink|眨眼|playful wink with one eye, tongue slightly out, cheeky smile"
  "eyeroll|翻白眼|rolling the eyes upward, exasperated and done"
  "facepalm|捂脸|facepalming, one hand covering the forehead, embarrassed"
  "ok|OK手势|making an OK hand sign near the face, cheerful relaxed smile"
)

# ---------------- 风格 prompt 片段 ----------------
# 注意：本渠道无法输出真透明，且对"transparent background"会画出假棋盘格纹理。
# 因此统一要求纯绿幕底，再由 cutout.py 抠成透明 PNG。绝不能要 transparent/checkerboard。
STYLE_FRAGMENT="Rendered as an Apple Memoji-style 3D avatar: a smooth rounded cartoon character, glossy soft 3D shading, large expressive eyes, soft studio lighting, head-and-shoulders portrait, centered, facing the camera. Place the character on a SOLID FLAT UNIFORM CHROMA-KEY GREEN background (pure bright green screen, RGB约 0,200,0) — absolutely NO checkerboard, NO transparency pattern, NO gradient, NO scenery, NO cast shadow on the background. No text, no watermark, no border, no extra characters."

usage() {
  cat <<EOF
gen_pack.sh v${VERSION} — Memoji 表情包生成器（编排 image-2）

用法：
  gen_pack.sh --image <路径|URL|dataURI> [选项]

必填：
  --image PATH        人物照片：本地路径 / 公网 URL / data URI

选项：
  --name NAME         人物名/包名（影响输出目录与标题），默认 memoji
  --outdir DIR        输出目录，默认 ./memoji-<name>/
  --mode pack|single  pack=整套表情(默认)；single=只出 1 张基准头像
  --count N           只取前 N 个表情（默认全部）
  --resolution WxH    贴纸分辨率，默认 1024x1024
  --expressions STR   覆盖默认表情，格式 "slug:描述;slug:描述;..."（英文描述）
  --no-retry          关闭失败重试（默认每个失败表情重试 1 次）
  --use-local-key     允许 create_task.sh 读取 ~/.config/image-2/.env 里的 key
  --plan              只打印将要做什么 + 预计调用次数，不真正生成（不消耗积分）
  -h, --help          显示帮助

成本：pack = 1(基准) + N(表情) 次 image-2 调用；最坏(每个表情重试一次) = 1 + 2N。
EOF
}

# ---------------- 参数解析 ----------------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --image)        IMAGE="${2:-}"; shift 2 ;;
    --name)         NAME="${2:-}"; shift 2 ;;
    --outdir)       OUTDIR="${2:-}"; shift 2 ;;
    --mode)         MODE="${2:-}"; shift 2 ;;
    --count)        COUNT="${2:-}"; shift 2 ;;
    --resolution)   RESOLUTION="${2:-}"; shift 2 ;;
    --expressions)  EXPRESSIONS_OVERRIDE="${2:-}"; shift 2 ;;
    --no-retry)     RETRY=0; shift ;;
    --base-url)     BASE_URL_REUSE="${2:-}"; shift 2 ;;
    --use-local-key) USE_LOCAL_KEY=1; shift ;;
    --plan)         PLAN_ONLY=1; shift ;;
    -h|--help)      usage; exit 0 ;;
    *) echo "未知参数: $1" >&2; usage; exit 1 ;;
  esac
done

# ---------------- 校验 ----------------
[[ -z "$IMAGE" ]] && { echo "错误：--image 必填" >&2; usage; exit 1; }
case "$MODE" in pack|single) ;; *) echo "错误：--mode 只能是 pack 或 single" >&2; exit 1 ;; esac
[[ "$COUNT" =~ ^[0-9]+$ ]] || { echo "错误：--count 必须是非负整数" >&2; exit 1; }

# 安全化 name 用于路径
NAME_SLUG="$(printf '%s' "$NAME" | tr -d '/\\:*?"<>|' | tr ' ' '_')"
[[ -z "$NAME_SLUG" ]] && NAME_SLUG="memoji"
[[ -z "$OUTDIR" ]] && OUTDIR="./memoji-${NAME_SLUG}"

# ---------------- 组装表情列表 ----------------
EXPR_LIST=()  # 每项： slug|label|desc
if [[ -n "$EXPRESSIONS_OVERRIDE" ]]; then
  # 解析 "slug:desc;slug:desc"
  IFS=';' read -ra _parts <<< "$EXPRESSIONS_OVERRIDE"
  for p in "${_parts[@]}"; do
    [[ -z "${p// }" ]] && continue
    slug="${p%%:*}"; desc="${p#*:}"
    slug="$(printf '%s' "$slug" | tr -d ' ')"
    [[ -z "$slug" ]] && continue
    EXPR_LIST+=("${slug}|${slug}|${desc}")
  done
else
  EXPR_LIST=("${DEFAULT_EXPRESSIONS[@]}")
fi
# 应用 count
if [[ "$COUNT" -gt 0 && "$COUNT" -lt "${#EXPR_LIST[@]}" ]]; then
  EXPR_LIST=("${EXPR_LIST[@]:0:$COUNT}")
fi

EXPR_N=${#EXPR_LIST[@]}

# ---------------- 定位 image-2 的 create_task.sh ----------------
find_image2() {
  local c
  for c in "$HOME"/.claude/skills/image-2*/scripts/create_task.sh; do
    [[ -f "$c" ]] && { printf '%s' "$c"; return 0; }
  done
  return 1
}

# ---------------- 计划模式（不消耗积分） ----------------
if [[ $PLAN_ONLY -eq 1 ]]; then
  if [[ "$MODE" == "single" ]]; then
    total=1; worst=1
  else
    total=$((1 + EXPR_N)); worst=$((1 + 2*EXPR_N))
  fi
  echo "PLAN（不消耗积分）："
  echo "- 模式: $MODE"
  echo "- 人物/包名: $NAME"
  echo "- 输出目录: $OUTDIR"
  echo "- 分辨率: $RESOLUTION"
  echo "- 基准 Memoji 调用: 1 次"
  if [[ "$MODE" == "pack" ]]; then
    echo "- 表情数: $EXPR_N"
    printf '    '; for e in "${EXPR_LIST[@]}"; do lbl="${e#*|}"; printf '%s ' "${lbl%%|*}"; done; echo
  fi
  echo "- image-2 调用总数（无重试）: $total 次"
  [[ "$MODE" == "pack" ]] && echo "- 最坏情况（每个表情各重试 1 次）: $worst 次"
  if CREATE_SH="$(find_image2)"; then
    echo "- 复用脚本: $CREATE_SH"
  else
    echo "- ⚠️ 未找到 image-2 的 create_task.sh（请确认 image-2 技能已安装）"
  fi
  echo "- ⚠️ 实际运行会消耗 foxapi 积分。"
  exit 0
fi

# 真正运行：先确认 image-2 存在
if ! CREATE_SH="$(find_image2)"; then
  echo "错误：未找到 image-2 的 create_task.sh。" >&2
  echo "本技能依赖 image-2 (gpt-image-2) 技能，请先安装它。" >&2
  exit 1
fi

mkdir -p "$OUTDIR"

# ---------------- 工具函数 ----------------

# 把本地图缩放并编码成 data URI。 $1=文件 $2=最大边 $3=jpg|png
to_data_uri() {
  local src="$1" maxpx="$2" fmt="$3"
  local tmp out mime
  tmp="$(mktemp -t memoji.XXXXXX)"
  out="${tmp}.${fmt}"
  if command -v sips >/dev/null 2>&1; then
    if [[ "$fmt" == "png" ]]; then
      sips -s format png -Z "$maxpx" "$src" --out "$out" >/dev/null 2>&1
    else
      sips -s format jpeg -s formatOptions 85 -Z "$maxpx" "$src" --out "$out" >/dev/null 2>&1
    fi
  elif command -v ffmpeg >/dev/null 2>&1; then
    ffmpeg -y -i "$src" -vf "scale='min(${maxpx},iw)':-2" "$out" >/dev/null 2>&1
  else
    cp "$src" "$out"
  fi
  [[ -f "$out" ]] || out="$src"   # 缩放失败则用原图兜底
  mime="image/jpeg"; [[ "$fmt" == "png" ]] && mime="image/png"
  printf 'data:%s;base64,%s' "$mime" "$(base64 < "$out" | tr -d '\n')"
  rm -f "$tmp" "$out" 2>/dev/null || true
}

# 把 --image 解析成可传给 --image-url 的值。 $1=输入 $2=最大边 $3=fmt
resolve_image() {
  local in="$1" maxpx="$2" fmt="$3"
  case "$in" in
    http://*|https://*|data:*) printf '%s' "$in" ;;
    *)
      [[ -f "$in" ]] || { echo "错误：找不到图片文件: $in" >&2; return 1; }
      to_data_uri "$in" "$maxpx" "$fmt"
      ;;
  esac
}

# 查找某个 stem 实际生成的产物文件
produced_file() {
  local stem="$1" f
  for f in "$OUTDIR/$stem".png "$OUTDIR/$stem".webp "$OUTDIR/$stem".jpg "$OUTDIR/$stem".jpeg; do
    [[ -f "$f" ]] && { printf '%s' "$f"; return 0; }
  done
  return 1
}

# 调一次 create_task.sh。 $1=image_url $2=prompt $3=stem $4=logfile
run_one() {
  local img="$1" prompt="$2" stem="$3" log="$4"
  # 注：本账号的 gpt-image-2 渠道不支持 background 参数（返回 422
  # unsupported_advanced_options），故不传 --background；透明/纯净底靠 prompt 表达。
  local args=(
    --prompt "$prompt"
    --image-url "$img"
    --resolution "$RESOLUTION"
    --output-dir "$OUTDIR"
    --filename "$stem"
    --poll-interval "$PER_CALL_POLL"
    --max-attempts "$PER_CALL_MAXATT"
  )
  [[ $USE_LOCAL_KEY -eq 1 ]] && args+=(--use-local-key)
  bash "$CREATE_SH" "${args[@]}" >"$log" 2>&1
}

# 生成一张：成功把路径写入全局 PRODUCED 并返回 0。 $1=img $2=prompt $3=stem
PRODUCED=""
generate() {
  local img="$1" prompt="$2" stem="$3"
  local log="$OUTDIR/.log-${stem}.txt"
  local attempt=0 max=$((1 + RETRY))
  PRODUCED=""
  # 删除可能存在的旧产物，避免误判成功
  rm -f "$OUTDIR/$stem".png "$OUTDIR/$stem".webp "$OUTDIR/$stem".jpg "$OUTDIR/$stem".jpeg 2>/dev/null || true
  while (( attempt < max )); do
    attempt=$((attempt + 1))
    if run_one "$img" "$prompt" "$stem" "$log" && produced_file "$stem" >/dev/null 2>&1; then
      PRODUCED="$(produced_file "$stem")"
      return 0
    fi
    echo "    ! ${stem} 第 ${attempt} 次失败（日志见 ${log}）" >&2
  done
  return 1
}

# 对刚生成的原图（绿幕底）抠图成透明 PNG。 $1=stem，使用全局 PRODUCED。
# 成功后把最终透明 PNG 路径写入全局 FINAL_PNG。
FINAL_PNG=""
cutout_file() {
  local stem="$1"
  local out="$OUTDIR/${stem}.png"
  local log="$OUTDIR/.log-${stem}.txt"
  if python3 "$(dirname "$0")/cutout.py" --in "$PRODUCED" --out "$out" >>"$log" 2>&1; then
    [[ "$PRODUCED" != "$out" ]] && rm -f "$PRODUCED" 2>/dev/null || true
    FINAL_PNG="$out"
  else
    echo "    ! ${stem} 抠图失败，保留原图（带绿底）" >&2
    FINAL_PNG="$PRODUCED"
  fi
}

# ---------------- 第 1 步：基准 Memoji ----------------
echo "=== Memoji 表情包：${NAME} ==="
echo "[1/$([[ "$MODE" == single ]] && echo 1 || echo $((1+EXPR_N)))] 预处理照片 + 生成基准 Memoji…"

INPUT_REF="$(resolve_image "$IMAGE" "$PHOTO_MAXPX" jpg)" || exit 1

BASE_PROMPT="Turn the person in the reference photo into a friendly Memoji-style avatar. Preserve their key identifying traits: hairstyle, hair color, skin tone, facial hair, glasses or accessories, and overall vibe. Neutral friendly expression. ${STYLE_FRAGMENT}"

if [[ -n "$BASE_URL_REUSE" ]]; then
  echo "    复用已有基准图 URL（不消耗积分）"
  if ! curl -s -L -o "$OUTDIR/base_raw" "$BASE_URL_REUSE" || [[ ! -s "$OUTDIR/base_raw" ]]; then
    echo "错误：下载复用基准图失败：$BASE_URL_REUSE" >&2; exit 2
  fi
  PRODUCED="$OUTDIR/base_raw"
else
  if ! generate "$INPUT_REF" "$BASE_PROMPT" "base"; then
    echo "错误：基准 Memoji 生成失败，无法继续。日志：$OUTDIR/.log-base.txt" >&2
    exit 2
  fi
fi
cutout_file "base"
BASE_FILE="$FINAL_PNG"
echo "    ✓ 基准头像：$BASE_FILE"

# single 模式到此结束
if [[ "$MODE" == "single" ]]; then
  python3 "$(dirname "$0")/build_gallery.py" \
    --outdir "$OUTDIR" --name "$NAME" \
    --base "$(basename "$BASE_FILE")" || true
  echo "=== 完成（single 模式）：$OUTDIR ==="
  exit 0
fi

# ---------------- 第 2 步：逐个表情（并行提交） ----------------
# 用基准图（缩小版）作为所有表情的参考，保证同一张脸。
# 单张 gpt-image-2 图生图很慢（分钟级），故并发提交、墙钟≈单张耗时。
BASE_REF="$(to_data_uri "$BASE_FILE" "$REF_MAXPX" png)"

# 组装每个表情的 stem / prompt / label / slug（按索引对齐）
STEMS=(); PROMPTS=(); LABELS=(); SLUGS=()
idx=1
for entry in "${EXPR_LIST[@]}"; do
  IFS='|' read -r e_slug e_label e_desc <<< "$entry"
  STEMS+=("$(printf '%02d-%s' "$idx" "$e_slug")")
  SLUGS+=("$e_slug"); LABELS+=("$e_label")
  PROMPTS+=("Keep the EXACT same character as in the reference image — identical face shape, hairstyle, hair color, skin tone, facial hair, glasses/accessories and art style. Change ONLY the facial expression and pose to: ${e_desc}. ${STYLE_FRAGMENT}")
  idx=$((idx + 1))
done

# 后台并发提交一批索引，wait 等全部结束
launch_round() {
  local i stem prompt log
  for i in "$@"; do
    stem="${STEMS[$i]}"; prompt="${PROMPTS[$i]}"; log="$OUTDIR/.log-${stem}.txt"
    rm -f "$OUTDIR/$stem".png "$OUTDIR/$stem".webp "$OUTDIR/$stem".jpg "$OUTDIR/$stem".jpeg 2>/dev/null || true
    ( run_one "$BASE_REF" "$prompt" "$stem" "$log" ) &
    sleep "$STAGGER"
  done
  wait
}

collect_failures() {
  FAIL_IDX=()
  local i
  for i in "${!STEMS[@]}"; do
    produced_file "${STEMS[$i]}" >/dev/null 2>&1 || FAIL_IDX+=("$i")
  done
}

# 第 1 轮：全部
ALL_IDX=()
for i in "${!STEMS[@]}"; do ALL_IDX+=("$i"); done
echo "[并行] 提交 ${#STEMS[@]} 个表情（每张间隔 ${STAGGER}s，单张最长约 $((PER_CALL_POLL*PER_CALL_MAXATT))s）…"
launch_round "${ALL_IDX[@]}"

# 重试一轮失败项（用户已授权）
collect_failures
if [[ $RETRY -gt 0 && ${#FAIL_IDX[@]} -gt 0 ]]; then
  echo "[并行] 重试 ${#FAIL_IDX[@]} 个失败表情…"
  launch_round "${FAIL_IDX[@]}"
  collect_failures
fi

# 抠图 + 汇总
OK_ROWS=()      # slug|label|filename
FAIL_ROWS=()    # slug|label
for i in "${!STEMS[@]}"; do
  if produced_file "${STEMS[$i]}" >/dev/null 2>&1; then
    PRODUCED="$(produced_file "${STEMS[$i]}")"
    cutout_file "${STEMS[$i]}"
    OK_ROWS+=("${SLUGS[$i]}|${LABELS[$i]}|$(basename "$FINAL_PNG")")
    echo "    ✓ ${LABELS[$i]} → $(basename "$FINAL_PNG")"
  else
    FAIL_ROWS+=("${SLUGS[$i]}|${LABELS[$i]}")
    echo "    ✗ ${LABELS[$i]} 跳过"
  fi
done

# ---------------- 第 3 步：画廊 + manifest ----------------
# 把成功项写入临时 TSV 交给 python 生成
ITEMS_TSV="$(mktemp -t memoji-items.XXXXXX)"
if [[ ${#OK_ROWS[@]} -gt 0 ]]; then
  for row in "${OK_ROWS[@]}"; do
    IFS='|' read -r r_slug r_label r_file <<< "$row"
    printf '%s\t%s\t%s\n' "$r_slug" "$r_label" "$r_file" >> "$ITEMS_TSV"
  done
fi

python3 "$(dirname "$0")/build_gallery.py" \
  --outdir "$OUTDIR" --name "$NAME" \
  --base "$(basename "$BASE_FILE")" \
  --items "$ITEMS_TSV" || true
rm -f "$ITEMS_TSV" 2>/dev/null || true

# ---------------- 汇总 ----------------
echo ""
echo "=== 完成：$OUTDIR ==="
echo "成功 ${#OK_ROWS[@]}/${EXPR_N} 个表情 + 1 张基准头像"
if [[ ${#FAIL_ROWS[@]} -gt 0 ]]; then
  echo "失败（已跳过）："
  for row in "${FAIL_ROWS[@]}"; do
    IFS='|' read -r slug label <<< "$row"
    echo "  - ${label} (${slug})"
  done
  echo "可针对单个表情单独重跑，例如："
  echo "  bash $0 --image '$IMAGE' --name '$NAME' --outdir '$OUTDIR' --expressions '<slug>:<描述>'"
fi
echo "画廊：$OUTDIR/index.html"
exit 0
