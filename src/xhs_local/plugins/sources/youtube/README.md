# YouTube 来源

`plugin.py` 实现标准 `SourcePlugin`，复用 `video/plugin.py`；`client.py` 按上传标签惰性读取，只做发现与元数据读取，不触发发布。`session.py` 复用用户明确选择的 Chrome 配置，仅保留 YouTube cookies。

配置：`poll_seconds: 1800`；`chrome_profile` 或 `cookie_file` 二选一，`node_path` 指定 yt-dlp JS 解析器。首次启用边界由主调度器持久化后传入 `CollectRequest.checkpoint`；没有边界时拒绝采集。返回 `video_pending` 记录及 `video_prepare` 任务，由独立 worker 下载、转写和总结。

不读取其他平台账号、不修改 VPN、不启动浏览器窗口。登录状态、网页改版或平台访问限制会导致失败并保留进度，不会制造空摘要绕过审核。
