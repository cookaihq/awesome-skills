# Scenario 3 — 混合媒体

**目标**：图 + 视频 + 文档一次提问，组成单条 user 消息的多内容块。

## User Turn
> 用 gemini-3.5-flash 把这张图 a.png、这段视频 b.mp4、这份 c.pdf 的核心信息汇总一下。

## Expected (with skill)
- 三个本地文件各自上传换 URL
- 一条 user 消息内含 text + image_url + video_url + file_url 四个块
- 轮询到终态后输出文本

## Red flags
- 拆成多次请求；或把本地路径直接塞进 url 字段
