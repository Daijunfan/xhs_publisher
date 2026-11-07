# xhs_publisher

独立的 Telegram、X、YouTube 社交媒体采集服务。采集进程、原始媒体与内容索引运行在 Linux；[Aexus Bot](https://github.com/Daijunfan/Aexus-Bot) 是独立客户端，通过受控 API 管理订阅、读取、搜索和按需下载。

## Aexus Bot 集成

采集器入口、订阅同步、原生作者头像、内容检索、按平台容量管理和外刊按需下载位于 [integrations/aexus-bot](integrations/aexus-bot/README.md)。完整采集后端位于 `src/xhs_local/`。

- Telegram / X / YouTube 的采集、游标和重试在服务端执行。
- Aexus 模式只生成 YouTube 中文总结，不生成完整翻译；使用独立的 DeepSeek key 文件。
- 各平台容量分别管理，已收藏内容与用户请求下载的文件保留；外刊收到下载请求后才获取。
- 客户端不需要常驻保存未收藏的新闻或图片。
- API token、平台登录状态、DeepSeek key、SSH 配置和运行数据不提交仓库。

集成模式不会自动发帖，也不会创建 Coding Agent。原有独立阅读与小红书发布能力保留，由用户显式启用。

## 开发

```sh
uv sync --frozen --extra dev --python 3.12
```

部署与令牌配置见 [采集集成文档](integrations/aexus-bot/README.md)。请使用自己的配置和私有密钥文件，不要提交 `runtime/`、平台会话或凭据。
