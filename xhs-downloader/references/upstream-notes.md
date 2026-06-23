# XHS-Downloader 上游笔记

来源：JoeanAmier/XHS-Downloader（本仓 clone 于 forked-repos/XHS-Downloader）。

## 入口
- `from source import XHS`（async context manager）。
- `await xhs.extract(url, download=False, index=None) -> list[dict]`。
  - `url`：支持 `explore/`、`discovery/item/`、`user/profile/`、`xhslink.com/`，空格分隔多条；内部 `extract_links` 过滤。
  - `download=True` 写盘；`index=[1,2,5]` 相册选图。
  - 失败返回 `[]` 或空 dict。
- ⚠️ 这套调用契约（构造 kwargs + `extract` 签名）被 `scripts/smoke_check.py` 的 `REQUIRED_INIT_PARAMS` / `REQUIRED_EXTRACT_PARAMS` 编码，自动更新后会据此自检、不符则回滚。**有意改变本 skill 对上游的调用方式时，必须同步改那两个常量**，否则自检会把新版误判为「使用方式已变」而回滚。

## 返回 dict 关键字段（中文键）
`作品标题 / 作品描述 / 作品类型 / 作者昵称 / 作者ID / 作品链接 / 下载地址(下载直链) / 动图地址(livephoto)`。

## 落盘结构
`<work_path>/<folder_name>/` 为根；`author_archive=True` 再加 `/<nickname>`；
`folder_mode=True` 再加 `/<work-name>`。本 skill 固定 `author_archive=False, folder_mode=True`，
saved_dir 报告 `<work_path>/<folder_name>`，文件用 rglob 扫描确认，不复刻命名规则。

## Cookie
- 必须以字符串传入 `XHS(cookie=...)`；本版「读浏览器 Cookie」功能已注释，不可用。
- 登录态判定：`source/module/manager.py` 用正则识别 `web_session=...`。
- 无 Cookie：视频只能下低清；提取私密/受限内容可能返回空。
