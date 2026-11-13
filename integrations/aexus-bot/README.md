# Linux channel collector

`frontier.py` runs the existing Frontier collectors and video processor on Linux.
The Mac runs Aexus Bot's Core, receives articles and displays the channels. The
worker uses the existing source credentials and checkpoints; it does not start
coding employees or publish to social platforms.

The integration reuses `FrontierScheduler`, `FrontierCollector`,
`WebsiteSubscriptions`, `WebsiteVideos` and `AgentsPublisher` from the existing
`<collector-root>` checkout. `frontier-summary-only.patch` records the small
changes required there. Apply it only against the matching existing Frontier
source; preserve unrelated working-tree edits and private configuration.

YouTube produces DeepSeek Chinese summaries and video links. It skips full
translation and removes completed jobs' original audio and transcription files.
Discovery defers full video metadata until already-seen IDs have been filtered.
`frontier-youtube-throughput.patch` additionally keeps discovery flat, rotates
undated entries through durable pending metadata, commits partial progress before
the collection deadline, and staggers dynamically added targets. Exact publication
timestamps still come from video metadata. Run `test_youtube_collection.py` against
the matching Frontier source before deployment; the patch follows the existing
summary-only changes and must not overwrite unrelated source edits.
Transcription uses one CPU worker with eight threads; this service reserves no GPU.
YouTube audio processing requires both `ffmpeg` and `ffprobe` in the service PATH.
The unit also searches `~/AgentsCompany/collectors/bin` for a scoped installation;
verify these executables from the service environment, not only an interactive shell.

The worker authenticates using a dedicated Core collector token. It cannot call
employee, Team or general Core APIs. Tokens and the DeepSeek key are private files
with mode `0600`; command lines and logs contain only their paths. The key is the
same official DeepSeek key used by the Mac's Claude Code route, not the local
router's placeholder token.

```sh
systemctl --user status aexus-bot-collector.service
systemctl --user restart aexus-bot-collector.service
systemctl --user stop aexus-bot-collector.service
journalctl --user -u aexus-bot-collector.service -n 30 --no-pager
```

Deploy the entry point under `~/AgentsCompany/collectors/`, install the accompanying
user service, then enable it with `systemctl --user enable --now
aexus-bot-collector.service`. The existing Mac LaunchAgent
`com.agentscompany.news-bridge` forwards the server's loopback port `5152` to the
Core's loopback collector listener. No collector port is exposed publicly.

Core's `channel.source-*` API owns the worker's runtime subscription projection.
It retains disabled subscriptions and stable source identities. It does not
overwrite Frontier's separate source configuration. A disconnected Mac does not
stop Linux collection: the publisher uses its last confirmed configuration and
retries pending deliveries when the receiver returns.

Status is written to `Xhs/runtime/aexus-bot/status.json`. Check `ready`,
`execution_host`, `agents.connected` and per-source results separately. An active
service does not establish that every social account is reachable or has new posts.

## Subscription application receipts

Deploy `subscription_sync.py` beside `frontier.py`. The Mac app owns subscription edits; the Linux collector receives the latest scoped snapshot and acknowledges it only after `apply_agents_targets` completes. Its independent watcher keeps management updates responsive during news and image delivery. A failed acknowledgment is retried without silently claiming synchronization; cached confirmed targets still support temporary Mac outages. The App shows pending, server-applied and disconnected states through `channel.subscription-status`.

The user's standalone Frontier `sources.yaml` remains separate and is never overwritten. Subscription changes affect this Bot collector's runtime projection and checkpoint only. Unfollowed identities and saved news remain available; the default management list shows followed subscriptions.

## Memory-only Mac content and document retrieval

Deploy `channel_content.py`, `channel_documents.py`, and `channel_avatars.py` beside
`frontier.py` and `subscription_sync.py`. The independent storage worker uses the
same dedicated reverse connection; no extra port or operator token is needed.
Core `channel.storage` binds this all-source collector, the registered collector SSH
host, and `<collector-root>/runtime/aexus-bot/channel-content`.

The server content store owns unsaved news/discussion and original image bytes
with independent 1 TB platform budgets and no age TTL. Explicit saves and
user-requested document caches are protected from oldest-first capacity eviction. The Mac runs content queries in RAM and acknowledges changes after
server durability. Legacy local messages/images are hash-verified on the server
before local removal.

`telegram-lazy.patch` adds the `document_metadata_only` source option and the
existing transport's single-message fetch. Bot applies that option to Telegram
runtime targets without modifying the user's source YAML. Collection lists
filenames, sizes and IDs only. A Mac download click starts a bounded server job,
then the existing SSH transfer; completed file hashes prevent repeated retrieval.
There is no automatic full-magazine download or generated PDF preview.

The avatar worker uses original X record attachments or the platform client and
public YouTube channel images. Its platform HTTP session has no Core token.
Platform failures remain retryable and do not fabricate profile pictures.

Deploy `channel_queries.py` and `channel_capacity.py` with the other collector
modules. Existing Pillow (verified 12.3.0) provides bounded WebP previews. SQLite
FTS5/trigram and relational indexes keep reads independent of payload history;
source count/read-watermark and platform byte ledgers avoid repeated whole-store
scans. Only the migration builds indexes once. The existing filesystem has ample
space; budgets do not preallocate 3 TB or alter partitions.

The own publisher uses `channel.media-register` after server-side image validation.
Original images remain on Linux; Mac browsing requests previews and explicit
original reads/downloads keep the previous checksum path. Eight scoped workers
serve requests without an additional public listener or operator token.

## Opt-in magazine prefetch

Set `options.prefetch_documents: true` on the selected Telegram target in the existing collector `config/sources.yaml`. The plugin manifest validates this boolean. Other targets and listing remain metadata-only. The opted-in target downloads new originals during Linux collection, before Core publication, so a temporarily disconnected Mac does not postpone those new files. A separate background loop backfills existing archive metadata through the same `ChannelDocumentRequests` path used by explicit downloads. Core subscription refresh preserves the target option.

The loop handles newest publications first, resumes pending work after restart and retries failures after a five-minute cooldown. Only one background job is queued at a time, leaving the second transfer slot for user requests. Completed size/SHA-256 verified originals are stored under `channel-content/documents/`; user requests reuse or join that exact cache entry. Automatic prefetch does not bookmark or pin a post, alter its text, or download anything onto the Mac. Explicit user requests retain their normal server pin. Capacity limits still apply.

Run `test_channel_content.py` and `test_document_prefetch.py` with the collector source on `PYTHONPATH` before deployment. For a staged test directory, set `AEXUS_XHS_ROOT` to that source root.
