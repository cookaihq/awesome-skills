# Scenario 2 — Image-editing intent implies reference image

**测试目标**：用户描述里暗示「基于某张图改」，skill 必须识别为图像编辑/图生图模式，先确认参考图 URL，而不是当成纯文生图。

## User Turn

> 用 banana-2 把这张产品图的背景换成热带海滩，比例就按原图来。

（用户提到「这张产品图」「按原图比例」，但还没给出图片 URL。）

## Expected (with skill)

- 识别出这是图像编辑（需要 `image_urls`），主动向用户索要参考图 URL（公开可访问）
- 「按原图比例」→ 计划传 `--aspect-ratio match_input_image`
- 拿到 URL 后输出请求摘要（model、mode=img2img/editing、aspect_ratio、resolution），等用户确认再调用
- **不**在没有参考图的情况下退化成纯文生图凭空画一张

## Anti-pattern to catch (baseline likely behavior)

- 忽略「这张图」，直接文生图生成一张全新的海滩产品图
- 自己编一个图片 URL
- 把 `match_input_image` 用在没有 `image_urls` 的纯文生图里

## Red flags during review

- payload 里没有 `image_urls` 却号称在"编辑用户的图"
- 传了 `aspect_ratio=match_input_image` 但没有任何 `--image-url`
