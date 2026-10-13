# Telegram source

`TelegramSourcePlugin` owns one lazily connected Telethon client. Each
`collect()` call handles exactly one configured channel, uses
`checkpoint.max_message_id` as Telethon's `min_id`, keeps album members linked
by `group_id`, and downloads PNG/JPEG/WebP/GIF bytes without converting GIFs.
Every call discards messages outside the configured 24-hour window, including
the first call after a restart, while still advancing the incremental checkpoint.

Polling, target lifecycle, persistence, retries, and publication are outside
this directory. Interactive authorization is exposed as
`authorize_telegram_session()` so the root CLI can invoke it without importing
pipeline code.
