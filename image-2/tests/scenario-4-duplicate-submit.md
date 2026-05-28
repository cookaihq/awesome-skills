# Scenario 4 — Same-params duplicate submission

**测试目标**：同一轮对话里用户因为没耐心连续按了两次"再创建一次"，skill 必须挡掉同参数的二次提交。

## Conversation

第一轮（已成功创建 task_id=`task-unified-aaa`，状态在 `processing` 中）：

> 用户：再帮我创建一次，参数都一样。

## Expected (with skill)

- 识别"参数都一样" → 触发 Dedup Rule
- 输出：已有同参数任务 `task-unified-aaa` 正在执行，二次提交会再次扣积分
- 不再调用 create 接口
- 给出建议：
  - 等待第一个任务完成
  - 如要再来一张，请改 `num_outputs` 或 `prompt` 或 `resolution` 中任一项

## Anti-pattern to catch

- 直接再调用一次 create，扣双倍积分
- 用"用户说了再来一次所以我必须执行"为借口绕过 Dedup Rule

## Red flags

- 一轮对话里 create 接口被调用 ≥ 2 次但参数完全相同
- 没有提示积分消耗
