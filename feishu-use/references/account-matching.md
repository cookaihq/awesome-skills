# Account Matching

## 数据来源

当前账户只从 `lark-cli auth status --json` 获取；旧版输出缺少账户字段时，回退到 `lark-cli auth list --json`。不要直接读取或改写 Keychain、Token 文件或 `config.json` 来判断账户。

## 匹配等级

### 强匹配

用户提供 `ou_...` Open ID，且与当前 `openId/userOpenId` 完全相同：

```text
expected_open_id == actual_open_id
```

Open ID 相同但显示名不同，按强匹配处理并提示名称可能已变更。

### 弱匹配

用户只提供显示名，且与当前 `userName` 相同。显示名可能重名，因此必须展示：

```text
账户名称：Alice
Open ID：ou_expe...1234
```

用户明确确认后，才可在本次预检中使用 `--accept-name-match`。

### 不匹配

- 用户提供的 Open ID 与当前 Open ID 不同。
- 用户只提供显示名，且与当前名称不同。
- 飞书/Lark brand 或用户指定 Profile 不一致。

不要用邮箱、手机号或另一个系统的用户 ID 与 Open ID 做字符串比较。若有可靠通讯录能力，可先解析成 Open ID；否则让用户确认登录后显示的账户。

## 未指定账户

用户没有指定账户时，使用当前 Profile 唯一可用的用户身份，并在执行前或结果摘要中说明账户名称和脱敏 Open ID。若用户随后指出账户不对，停止并进入账户替换流程。

## 账户替换

当前官方 `lark-cli auth login` 登录成功后，会把当前 Profile 的用户列表替换为新用户，并删除旧用户 Token。账户不匹配时应展示：

1. 用户期望的账户。
2. 当前账户名称和脱敏 Open ID。
3. 登录新账户会替换当前 Profile 登录状态的影响。
4. 选择：登录目标账户、明确改用当前账户、取消。

只有用户明确同意后才发起 Device Flow。用户原请求明确要求特定账户时，“改用当前账户”不能作为默认选项。

需要长期保留多个账户时，应让用户明确创建独立 Profile；不得自动复制 App Secret、创建 Profile 或切换默认 Profile。
