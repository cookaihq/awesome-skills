# Scenario 4 — Invalid resolution tier (it's a quality tier, not pixels)

**测试目标**：banana-2 的 `resolution` 是画质档（`512`/`0.5K`/`1K`/`2K`/`4K`），不是像素。用户给像素或越界档位时，skill 必须拦截并解释清楚。

## User Turn

> 用 banana-2 生成「极简产品图」，分辨率 1920x1080。

## Expected (with skill)

- 识别出 banana-2 的 `resolution` 不接受像素值，只接受画质档 `512` / `0.5K` / `1K` / `2K` / `4K`
- 向用户解释：尺寸由 `aspect_ratio`（宽高比）+ `resolution`（画质档）共同决定；`1920x1080` 这种横屏意图应表达为 `--aspect-ratio 16:9` + 一个画质档（如 `--resolution 2K`）
- 让用户确认比例 + 画质档再继续
- **不**直接把 `1920x1080` 塞进 `resolution` 调用 API

## Anti-pattern to catch

- 把 `1920x1080` 原样当 `resolution` 提交，等 422
- 误用 image-2 的像素 resolution 心智模型（gpt-image-2 才支持像素/自定义对象）
- 未经确认擅自决定 `16:9 + 2K`

## Red flags

- payload 里出现 `"resolution": "1920x1080"` 或 `{"width":...,"height":...}`
- 出现 HTTP 422 但本可在客户端拦截
