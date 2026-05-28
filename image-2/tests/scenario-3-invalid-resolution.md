# Scenario 3 — Invalid resolution

**测试目标**：用户给出非法 `resolution`，skill 必须基于模型（完整版/精简版）给出合法清单，不能盲提。

## User Turn

> prompt = "未来城市夜景海报"，model 用 gpt-image-2-limit，resolution 我要 1920x1080。

## Expected (with skill)

- 识别出 `gpt-image-2-limit` 只支持 3 种预设：`1024x1024` / `1024x1536` / `1536x1024`
- 告知 `1920x1080` 在精简版下不支持，提供候选：
  1. 切到完整版 `gpt-image-2` 以使用 `1920x1080`
  2. 换成精简版支持的 `1536x1024`（最接近横屏）
- 让用户选一个再继续
- **不**直接调用 API 看错误

## Anti-pattern to catch

- 不查就直接调 create 接口，等 422 才发现
- 用「我帮你换成 1024x1024」之类**未经用户确认**的替换
- 忽视精简版限制，按完整版校验

## Red flags

- 出现 HTTP 422 `validation_error` 但本可在客户端拦截
- skill 没引用 SKILL.md 中精简版禁用字段列表
