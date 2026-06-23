# awesome-skills

cookaihq 维护的 Agent Skill 集合 —— 每个 skill 是一份遵循 [agentskills.io](https://agentskills.io) 开放标准的 `SKILL.md` + 配套脚本，可在 Claude Code 等 Agent 平台即装即用。

## Skills

| Skill | 功能 | 文档 |
|---|---|---|
| [image-2](image-2/) | 通过 aihubmax.com 的 `gpt-image-2` 接口生成图片：文生图 / 图生图、11 种预设比例 + 自定义分辨率（最高 4K）、任务完成自动下载到工作区 | [README](image-2/README.md) · [SKILL.md](image-2/SKILL.md) |
| [banana-2](banana-2/) | 通过 aihubmax.com 的 Nano Banana 2（`gemini-3.1-flash-image-preview`）接口生成/编辑图片：文生图 / 图生图 / 图像编辑、15 种宽高比 + `512`~`4K` 画质档、可选 `google_search` / `image_search`、任务完成自动下载到工作区 | [README](banana-2/README.md) · [SKILL.md](banana-2/SKILL.md) |

## 安装

以 `image-2` 为例，四种方式任选其一（其他 skill 如 `banana-2` 把命令里的 `image-2` 换成对应目录名即可）。

让 Agent 自己装（推荐，最省事 —— 把下面这段提示词丢给 Claude Code 或 Codex）：

```text
请把 https://github.com/cookaihq/awesome-skills 仓库里的 image-2 skill 安装给你自己用：
1. 克隆仓库到本地（已克隆则更新）
2. 把其中的 image-2 目录链接或复制到你当前平台的 skills 目录
   （Claude Code 用 ~/.claude/skills/image-2，其他平台用各自约定的位置）
3. 读 image-2/SKILL.md 确认能被识别，然后告诉我怎么触发它
```

如果你非常清楚 Skills 的安装方式，可以使用以下方法。

项目级 symlink（只在当前项目生效）：

```bash
git clone https://github.com/cookaihq/awesome-skills.git
mkdir -p ./.claude/skills
ln -s "$(pwd)/awesome-skills/image-2" ./.claude/skills/image-2
```

用户级 symlink（所有项目可触发）：

```bash
ln -s "$(pwd)/awesome-skills/image-2" ~/.claude/skills/image-2
```

skills CLI：

```bash
npx skills add cookaihq/awesome-skills --skill image-2 -a claude-code
```

> Codex / Gemini 用户把 `-a claude-code` 换成对应平台标识。

各 skill 的详细用法、配置与排错见其目录下的 README。

## License

[MIT](LICENSE)
