# awesome-skills

cookaihq 维护的 Agent Skill 集合 —— 每个 skill 是一份遵循 [agentskills.io](https://agentskills.io) 开放标准的 `SKILL.md` + 配套脚本，可在 Claude Code 等 Agent 平台即装即用。

## Skills

| Skill | 功能 | 文档 |
|---|---|---|
| [image-2](image-2/) | 通过 foxapi.cc 的 `gpt-image-2` 接口生成图片：文生图 / 图生图、11 种预设比例 + 自定义分辨率（最高 4K）、任务完成自动下载到工作区 | [README](image-2/README.md) · [SKILL.md](image-2/SKILL.md) |

## 安装

以 `image-2` 为例，三种方式任选其一。

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

待定（推荐 MIT）。
