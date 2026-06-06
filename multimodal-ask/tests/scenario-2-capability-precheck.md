# Scenario 2 — 能力预校验

**目标**：所选模型不支持该媒体类型时，预校验拦截、荐可用模型，不浪费上传+提交。

## User Turn
> 用 gpt-5.5 分析这段视频 ./clip.mp4。（gpt-5.5 无 video 能力）

## Expected (with skill)
- 预校验发现 gpt-5.5 缺 `video` → 退出码 3，stderr 给出原因 + 支持 video 的模型（如 gemini-3.5-flash）
- **不**上传文件、**不**提交任务

## Red flags
- 直接上传+提交，等 422 才报错（浪费一次上传）
