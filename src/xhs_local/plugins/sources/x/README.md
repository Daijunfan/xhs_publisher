# X source

`XSourcePlugin` reads the public FxTwitter v2 JSON timeline at
`https://api.fxtwitter.com/2/profile/<handle>/statuses`. It uses no Cookie,
account session, API key, Bearer Token, or plugin-owned checkpoint. Every bounded
collection call emits only posts inside the configured 24-hour window; the shared
record repository deduplicates immutable post IDs and publication marks exclude
delivered posts.

The plugin downloads public `pbs.twimg.com` images and video thumbnails without
converting them. Polling, review, ranking, publication scheduling, persistence,
and Xiaohongshu delivery remain in the existing platform-neutral pipeline.
