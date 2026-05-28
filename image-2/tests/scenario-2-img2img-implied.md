# Scenario 2 — img2img implied but no `image_urls`

**测试目标**：用户措辞暗示图生图（"基于这张图"/"参考这几张"），但没有给出图片 URL，skill 必须要 URL 而不是退化成 text2img。

## User Turn

> 基于这几张参考图，帮我重绘一张极简风格的产品海报，比例 1024x1536。

（用户没贴 URL，也没附图。）

## Expected (with skill)

- 识别出意图是图生图
- 要求用户提供 `image_urls`（至少 1 张可访问 URL / Data URI / Base64）
- **不**默默改成 text2img 提交
- 在用户给出 URL 后再走「输出摘要 → 确认 → 调用脚本」流程

## Anti-pattern to catch

- 静默改用 text2img + 编造一个"极简产品海报"prompt 调接口
- 假装从对话历史里能拿到图片
- 把"几张参考图"作为字面文本写进 prompt 但不传 `image_urls`

## Red flags during review

- 创建请求 body 中没有 `image_urls` 字段
- skill 没问就直接调用了 create_task.sh
