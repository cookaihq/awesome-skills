# Scenario 4 — 本地大文件软警告

**目标**：本地媒体 > 20MB 时，提交前给文字软警告，但**不阻断**，且声明非 API 硬限制。

## User Turn
> 用 gemini-3.5-flash 看这个 50MB 的视频 big.mp4。

## Expected (with skill)
- 摘要中出现「约 XX MB，超过 ~20MB 经验阈值，可能失败……非 API 硬限制」
- 用户确认后仍可继续（仅提醒）

## Red flags
- 把 20MB 当成 API 硬上限、直接拒绝
- 编造"最大 20MB"为接口规定
