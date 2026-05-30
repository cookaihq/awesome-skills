# template-preview

把一个文件夹的图片 + 文案渲染成「指定模板风格」的自包含展示页。v1 提供**小红书个人主页**模板。

## 它做什么

- 输入：一组封面图 + 文案（卡片标题/点赞），以及可选人设（昵称/简介/头像/数据）。
- 输出：一个自包含文件夹 —— `index.html`（套模板渲染）+ `content.json`（本次数据，便于手改重渲）+ `assets/`（所有图片，相对引用）。
- 本地双击 `index.html` 即可看效果；可交给 [preview-share](../preview-share/) 上传得到在线预览链接。

## 用法

```bash
# 1) 准备 content.json（通常由 Claude 按 SKILL.md 工作流生成）
#    { "label": "iot", "notes": [ { "cover": "封面.jpg", "title": "标题", "likes": 1234 } ] }

# 2) 先看计划（不写盘）
python3 scripts/generate.py --template xiaohongshu --content content.json --label iot --dry-run

# 3) 正式生成
python3 scripts/generate.py --template xiaohongshu --content content.json --label iot
# stdout 打印生成的 index.html 绝对路径
```

## 配置

人设与输出位置通过环境变量 / `.env` / `.env.local` 覆盖（不配则用内置默认）。完整变量表见 [SKILL.md](SKILL.md)。例如临时换昵称：

```bash
TPL_XHS_NICKNAME='我的昵称' TPL_XHS_BIO='我的简介' \
python3 scripts/generate.py --template xiaohongshu --content content.json --label demo
```

## 模板可插拔

每个模板在 `templates/<名字>/` 下自带：`template.html`（固定版式 + CSS）、`defaults.env`（默认人设）、`assets/`（默认头像 + 填充卡 + `titles.json`）。新增平台模板只需多一个目录，核心脚本不变。

## 故障排查

- **图在本地能看、线上裂图**：`assets/` 没传全 —— 用 `preview-share` 上传（它会扫描 `index.html` 的相对引用整体上传），别只传 `index.html`。
- **`[error] 输出目录已存在，拒绝覆盖`**：你自定义的 `TPL_SUBDIR_PATTERN` 去掉了 `{time}`，换个 `--label` 或保留 `{time}`。
- **填充卡太多/太少**：调 `TPL_XHS_MIN_CARDS`。
- **想换填充卡**：把 `TPL_XHS_FILLER_CARDS` 指向自己的目录（内含图片 + `titles.json`）。

## 开发 / 测试

```bash
python3 -m pytest tests/test_generate.py -q
```

纯 Python 标准库，无运行时第三方依赖（测试用 pytest）。
