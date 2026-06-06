# Scenario 5 — 同参数禁止二次提交

**目标**：同一轮、同模型同 prompt 同媒体来源，禁止重复提交（避免重复扣分）。

## User Turn
> （刚提交过）再用一样的参数跑一次吧。

## Expected (with skill)
- 识别为同参数（dedup 维度含输入媒体来源），提示已提交、不重复创建
- 参数任一变化（换 prompt / 换文件 / 改 max_tokens）才视为新任务

## Red flags
- 同参数闷头再提交一次
