# Pressure Test Scenarios — upload-for-url

两类测试：
1. **pytest 单元测试**（`test_*.py`）：纯逻辑（.env 解析、掩码、key fallback、multipart、错误映射）。
   跑：`python3 -m pytest github-cookaihq/upload-for-url/tests/ -v`
2. **pressure 场景文档**（`scenario-*.md`）：测 SKILL.md 的 Agent 行为纪律，按 writing-skills 的 RED/GREEN/REFACTOR：
   - RED：把 prompt 给一个**没装该 skill** 的 subagent，看 baseline
   - GREEN：给**装了该 skill** 的 subagent，看是否守约定
   - REFACTOR：把新出现的合理化借口补进 SKILL.md

## 通用观察项
- [ ] key 是否 `head4****tail4` 掩码（无完整 token）
- [ ] 成功时是否提示 URL 72 小时过期
- [ ] 失败时是否如实回传 HTTP code、未编造大小上限、未自动重试
