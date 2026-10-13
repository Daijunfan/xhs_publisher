# xhs_publisher

Telegram、X、YouTube 采集器与小红书发布接口。采集结果直接存入本地 SQLite/网页，视频用 GPU Whisper 转写；原文、收藏、图片、视频音频和转写最多保留最近 48 小时，每 5 分钟清理。

**AI Agent 全程托管运营**：Agent 自行审核、撰写、按相关主题汇总跨平台信息，再明确调用小红书发布接口。程序不调用 DeepSeek，不自动审核、撰写或发帖。小红书仍使用已验证的 Chromium/Safari 浏览器发布接口，并在作品列表确认结果。

- [云主机部署.md](云主机部署.md)：拉取仓库、恢复 Sensitive data、安装和启动。
- [AI_AGENT_GUIDE.md](AI_AGENT_GUIDE.md)：运营流程与完整保留的原提示词。
- [发布接口.md](发布接口.md)：Agent 的选稿、提交、去重和结果查询。

`config/sources.yaml` 保留 Telegram 14、X 300、YouTube 172 个目标，480 个启用。敏感信息单独在 Mac 根目录 `Sensitive data/`，不随 GitHub 分发；网页默认监听 `127.0.0.1:8080`，发布 API 需要运营 token。

```bash
uv sync --frozen --extra dev --python 3.12
.venv/bin/python tools/restore_sensitive_data.py
ops/run_cloud.sh migrate
ops/install_cloud_service.sh
ops/run_cloud.sh status
```

```bash
.venv/bin/pytest -q
.venv/bin/ruff check src tests tools
```

默认测试不向小红书发送内容。更新代码保留 `runtime/` 中的凭据、模型与运行状态。
