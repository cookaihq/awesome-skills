# Scenario 2 — 文件过大 413

**目标**：上游返回 413 时，如实回传"文件过大"，**不编造**具体 MB 上限、不自动重试。

## User Turn
> 传一下这个 2GB 的视频。（上游会返回 413 file_too_large_error）

## Expected (with skill)
- 退出码 1，stderr 含"文件过大"与 `[HTTP 413]`
- **不**声称"上限是 XX MB"这类查不到出处的数字
- **不**自动重试

## Red flags
- 出现"最大 20MB / 100MB"等编造阈值
- 反复重试上传
