# Scenario 4 — 远程 URL 转存

**目标**：用户给一个远程 URL，希望转存成 foxapi 72h 短链。

## User Turn
> 把 https://example.com/a.pdf 转存成你们的链接给我。

## Expected (with skill)
- 调 `python3 scripts/upload.py --url 'https://example.com/a.pdf'`
- 返回新的 foxapi URL，并说明 72 小时过期

## Anti-pattern (baseline)
- 直接把原始 URL 还给用户（没转存）
