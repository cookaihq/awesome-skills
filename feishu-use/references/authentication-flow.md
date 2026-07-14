# Authentication Flow

## 适用范围

用于内置凭证模式下的 `login_required`、用户账户替换和 `scope_required`。Bot 身份和外部凭证提供方管理的身份不执行 `auth login`。

## 登录前确认

1. 明确目标 Profile、目标账户和本次 scopes。
2. 如果当前 Profile 已登录其他用户，告知：登录成功会替换当前用户并清理旧用户 Token。
3. 让用户在浏览器中切换到目标飞书/Lark 账户后再授权。
4. 仅凭显示名无法强匹配；登录后仍需确认脱敏 Open ID。

## 第一轮：发起授权

使用最小 scopes：

```bash
lark-cli auth login \
  --scope "<space-separated scopes>" \
  --no-wait \
  --json
```

如果 scopes 尚不明确，可以使用对应领域而不是 `all`：

```bash
lark-cli auth login --domain base --no-wait --json
```

优先使用精确 `--scope`。解析返回的 `verification_url`、`device_code` 和 `expires_in`，然后生成相对路径二维码：

```bash
lark-cli auth qrcode "<verification_url>" --output "./feishu-auth.png"
```

必须按以下顺序向用户展示：

1. 原样的 `verification_url`，不编码、解码、拼接或加标点。
2. 实际二维码图片，不能只说文件已生成。
3. 目标账户、授权范围和过期时间。
4. “完成授权后回复已授权，我会继续验证账户和权限。”

展示后结束当前轮，不要同一轮立刻阻塞执行 `--device-code`。

`device_code` 只允许作为当前授权流程的短期对话状态；不得写入仓库、文件、日志、长期记忆或回复正文。授权完成、失败或过期后立即丢弃。

## 第二轮：完成授权

用户明确回复已完成后，由 Agent 执行：

```bash
lark-cli auth login --device-code "<current flow device_code>" --json
```

不要让用户自己执行该命令，也不要把 code 发给用户。若上下文中没有当前流程的 code，或 code 已过期，重新发起第一轮，不要猜测或复用旧值。

完成后立即验证：

```bash
lark-cli auth status --verify --json
lark-cli auth check --scope "<required scopes>" --json
```

再运行 `preflight.py`，并仅带上本次已经获得用户确认的 `--allow-outdated`、`--allow-unknown-version` 或 `--accept-name-match`。

## 登录结果核验

- Open ID 与期望一致：强匹配，可继续。
- 只有显示名一致：展示名称和脱敏 Open ID，请用户确认。
- Open ID 或名称不一致：明确报告实际账户，停止业务操作。

错误账户授权成功后，当前 Profile 原账户可能已经被替换。必须如实告知，询问是否重新登录目标账户；不能自动继续授权循环。

## 常见恢复

| 状态 | 处理 |
|---|---|
| 授权链接过期 | 重新运行 `--no-wait --json`，生成新链接和二维码 |
| 用户拒绝授权 | 停止，不降级到 Bot 或其他账户 |
| 缺少应用后台 scope | 原样展示 `console_url`，用户开通后发起新流程 |
| Keychain 不可访问 | 说明是凭证存储问题；不要误判为未登录或自动重配应用 |
| 外部凭证提供方不可用 | 回到对应提供方修复；不要运行被禁止的本地 `auth login` |
| Token 需要刷新 | `needs_refresh` 可由下一次用户 API 调用自动刷新；失败后再重新登录 |
| 品牌不一致 | 飞书与 Lark 不跨环境猜测，先确认 Profile/brand |
