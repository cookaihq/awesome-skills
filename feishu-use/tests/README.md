# Tests

运行：

```bash
python3 -m pytest -q feishu-use/tests/test_preflight.py
```

覆盖场景：CLI 缺失、发现更新、用户跳过更新、应用未配置、User 未登录、Bot 可用、Open ID 强匹配、名称弱匹配、账户不一致、缺少 scopes、旧版账户列表兼容和版本检查离线恢复。

测试不会调用真实 `lark-cli`、网络或本机凭证。
