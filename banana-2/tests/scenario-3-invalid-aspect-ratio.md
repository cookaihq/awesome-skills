# Scenario 3 — Invalid aspect_ratio

**测试目标**：用户给出非法 `aspect_ratio`，skill 必须基于合法清单拦截，不能盲提到 API 等 422。

## User Turn

> 用 banana-2 生成「未来城市夜景海报」，比例用 7:7，画质 1K。

## Expected (with skill)

- 识别 `7:7` 不在 15 种合法比例内：
  `1:1` `1:4` `1:8` `2:3` `3:2` `3:4` `4:1` `4:3` `4:5` `5:4` `8:1` `9:16` `16:9` `21:9` `match_input_image`
- 告知非法，并给出贴近用户意图的候选（如想要正方形用 `1:1`），让用户选一个再继续
- **不**直接调用 API 看错误

## Anti-pattern to catch

- 不查就直接调 create 接口，等 HTTP 422 才发现
- 用「我帮你换成 1:1」之类**未经用户确认**的替换
- 把 `aspect_ratio` 当像素分辨率处理（如试图解析成 7×7 像素）

## Red flags

- 出现 HTTP 422 `validation_error` 但本可在客户端拦截
- skill 没引用 SKILL.md 中的 15 值合法清单
