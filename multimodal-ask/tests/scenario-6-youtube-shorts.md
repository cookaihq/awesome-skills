# Scenario 6 — YouTube Shorts 改写 + 家族限制

**目标**：YouTube 仅 Gemini 家族可用；Shorts URL 自动改写为 watch?v=。

## User Turn
> 用 gemini-3.5-flash 概述这个 https://www.youtube.com/shorts/XY_z-12

## Expected (with skill)
- 把 `/shorts/XY_z-12` 改写为 `watch?v=XY_z-12` 再提交
- 若用户选了非 Gemini 模型：能力预校验会因模型缺 `video` 能力而拦截（退出码 3）；此外 Agent 应提示「YouTube 仅 Gemini 家族支持」——该家族提示是 Agent 行为层职责，脚本不按家族名强制

## Red flags
- 直接把 shorts URL 提交（上游 422）
- 不提示非 Gemini 模型不支持 YouTube
