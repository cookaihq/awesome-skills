# Scenario 5 — Iteration: same prompt, different resolution

**测试目标**：用户在同一轮里做参数迭代（同 prompt 但换比例），skill 必须允许新建而不是被 Dedup Rule 卡住。

## Conversation

第一轮已创建并轮询完成 task A：`prompt="科技风产品海报"`，`resolution=1920x1080`，`num_outputs=1`。

第二轮：

> 用户：刚那张挺好，再来一张 9:16 竖屏的，prompt 不用改。

## Expected (with skill)

- 把"9:16 竖屏"映射到完整版预设 `1080x1920`（如果用户没指定具体像素值，要么用 `1080x1920`，要么主动确认）
- 识别这是**参数变化**（resolution 不同）→ Dedup Rule 不触发
- 走正常流程：输出请求摘要 → 等待用户确认 → 调用脚本
- 创建后获得一个**新的** `task_id`，并轮询到终态

## Anti-pattern to catch

- 因为 prompt 没变就直接搬第一次的 task 结果，不再调用 create
- 错误地按 Dedup Rule 拒绝
- 把"9:16"当作比例字符串塞进 API（旧版接口才接受比例，新版只接受像素）

## Red flags

- 没有真的发起新的 create 请求
- 请求 body 中 `resolution` 仍是 `1920x1080`
- 请求 body 中 `resolution` 是 `"9:16"`（非法）
