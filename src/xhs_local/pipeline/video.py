"""Resumable video preparation, separate from both polling and remote publication."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from xhs_local.core.clock import utc_iso
from xhs_local.core.contracts import AttachmentInput
from xhs_local.core.errors import TransientError, ValidationFailure
from xhs_local.processing.provider import DeepSeekResponseError
from xhs_local.processing.transcription import TranscriptionTaskFailed
from xhs_local.processing.video_summary import translation_chunks
from xhs_local.storage.video_artifacts import VideoArtifacts


class VideoPreparationService:
    def __init__(
        self,
        *,
        records,
        work_items,
        runtime_root,
        client_for,
        transcription,
        summarizer,
        retry_attempts=3,
        channel_mode=False,
        commit_ready=None,
    ):
        self.records, self.work_items, self.runtime_root = records, work_items, runtime_root
        self.client_for, self.transcription = client_for, transcription
        self.summarizer = summarizer
        self.retry_attempts = retry_attempts
        self.channel_mode = channel_mode
        self.commit_ready = commit_ready or records.upsert

    async def __call__(self, work) -> None:
        stored = await asyncio.to_thread(self.records.get, work.record_id)
        if stored is None or stored.record.content_type != "video_pending":
            return
        record = stored.record
        cache = VideoArtifacts(self.runtime_root, record.plugin_id, record.external_id)
        state = cache.read("state.json") or {"stage": "discovered", "parts": []}
        state.update(record_id=record.record_id, work_id=work.work_id)
        client = self.client_for(record.source_id)
        if client is None:
            await asyncio.to_thread(
                self.work_items.schedule_retry,
                work.work_id,
                retry_at=datetime.now(UTC) + timedelta(minutes=30),
                error_class="SOURCE_DISABLED",
                error_summary="video source is disabled",
            )
            return
        metadata = cache.read("metadata.json") or record.payload.get("video_metadata")
        if metadata and any(
            part.get("live_status") in {"is_live", "is_upcoming", "post_live"}
            for part in (metadata.get("entries") or [metadata])
        ):
            metadata = None
        if metadata is None:
            metadata = await client.metadata(record.source_url)
            cache.save("metadata.json", metadata)
        parts = metadata.get("entries") or [metadata]
        if not parts or any(not isinstance(part, dict) for part in parts):
            raise ValidationFailure("video metadata is incomplete")
        timestamps = [part.get("release_timestamp") or part.get("timestamp") for part in parts]
        if not all(isinstance(value, (int, float)) for value in timestamps):
            raise ValidationFailure("video lacks an exact publication timestamp")
        published_at = (
            record.occurred_at
            if self.channel_mode
            else datetime.fromtimestamp(min(timestamps), UTC)
        )
        activated_at = datetime.fromisoformat(record.payload["activated_at"])
        if published_at < activated_at:
            if self.channel_mode:
                state["stage"] = "discarded"
                cache.save("state.json", state)
                return
            state["stage"] = "historical_ignored"
            cache.save("state.json", state)
            await asyncio.to_thread(
                self.records.upsert, replace(record, content_type="video_ignored")
            )
            return
        if any(
            part.get("live_status") in {"is_live", "is_upcoming", "post_live"} for part in parts
        ):
            raise TransientError("video is not yet complete")
        title = metadata.get("title") or parts[0].get("title") or record.title
        cache.save("metadata.json", metadata)
        if not state.get("media"):
            media = await client.images(record, parts[0], cache.root)
            state.update(media=media, stage="media_downloaded")
            cache.save("state.json", state)
        media_paths = tuple(cache.root / path for path in state["media"])
        for index, part in enumerate(parts):
            if len(state["parts"]) <= index:
                state["parts"].append({})
            part_state = state["parts"][index]
            if not part_state.get("audio"):
                directory = cache.root / f"part-{index + 1}"
                expected = part.get("duration")
                if not isinstance(expected, (int, float)) or expected <= 0:
                    raise ValidationFailure("video metadata has no complete audio duration")
                audio = await client.audio(
                    part.get("webpage_url") or record.source_url,
                    directory,
                    expected_duration=expected,
                )
                duration = await client.duration(audio)
                if not isinstance(expected, (int, float)) or abs(duration - expected) > max(
                    3, expected * 0.02
                ):
                    raise ValidationFailure("downloaded audio does not cover the complete video")
                part_state.update(audio=str(audio.relative_to(cache.root)), duration=duration)
                state["stage"] = "audio_downloaded"
                cache.save("state.json", state)
            if part_state.get("transcript"):
                continue
            if part_state.get("submitting") and not part_state.get("task_id"):
                await self.work_items_wait(
                    work,
                    "ASR submission outcome unknown; do not duplicate a potentially billed task",
                )
                return
            if not part_state.get("task_id"):
                audio_url = await self.transcription.upload(cache.root / part_state["audio"])
                if not getattr(self.transcription, "local", False):
                    part_state["submitting"] = True
                    cache.save("state.json", state)
                task_id = await self.transcription.submit(audio_url)
                part_state.update(task_id=task_id, submitting=False)
                state["stage"] = "transcribing"
                cache.save("state.json", state)
            try:
                transcript = await self.transcription.result(
                    part_state["task_id"], expected_duration=part_state["duration"]
                )
            except TranscriptionTaskFailed:
                part_state["failed_attempts"] = part_state.get("failed_attempts", 0) + 1
                part_state.pop("task_id", None)
                state["stage"] = "transcription_failed"
                cache.save("state.json", state)
                if part_state["failed_attempts"] < self.retry_attempts:
                    raise TransientError("cloud transcription failed; retry saved audio") from None
                raise
            if transcript is None:
                await asyncio.to_thread(
                    self.work_items.schedule_retry,
                    work.work_id,
                    retry_at=datetime.now(UTC) + timedelta(seconds=60),
                    error_class="ASR_PENDING",
                    error_summary="waiting for cloud transcription",
                )
                return
            name = f"transcript-{index + 1}.json"
            cache.save(name, transcript)
            part_state["transcript"] = name
            cache.save("state.json", state)
        transcript = "\n\n".join(cache.read(part["transcript"])["text"] for part in state["parts"])
        text = transcript
        if self.summarizer is not None:
            summary = cache.read("summary.json")
            if summary is None:
                state["stage"] = "summarizing"
                cache.save("state.json", state)
                try:
                    summary = {"text": await self.summarizer.summarize(title, transcript)}
                except DeepSeekResponseError as error:
                    state["summary_attempts"] = state.get("summary_attempts", 0) + 1
                    cache.save("state.json", state)
                    if state["summary_attempts"] >= self.retry_attempts:
                        raise
                    # Cloud polling is not a failed editorial attempt; keep a separate
                    # budget so a long transcription cannot consume all summary retries.
                    await asyncio.to_thread(
                        self.work_items.schedule_retry,
                        work.work_id,
                        retry_at=datetime.now(UTC) + timedelta(seconds=60),
                        error_class=error.error_class.value,
                        error_summary=str(error),
                    )
                    return
                cache.save("summary.json", summary)
            text = summary["text"]
        if self.channel_mode:
            state["stage"] = "translating"
            cache.save("state.json", state)
            translations = []
            for index, chunk in enumerate(translation_chunks(transcript)):
                name = f"translation-{index + 1}.json"
                translated = cache.read(name)
                if translated is None:
                    translated = {"text": await self.summarizer.translate_piece(title, chunk)}
                    cache.save(name, translated)
                translations.append(translated["text"])
            text = "## 视频总结\n\n" + text + "\n\n## 全文中文翻译\n\n" + "\n\n".join(translations)
        attachments = tuple(
            AttachmentInput("image/png", path.name, path.read_bytes()) for path in media_paths
        )
        platform_name = {"youtube": "YouTube"}.get(record.plugin_id, record.plugin_id)
        author = parts[0].get("uploader") or record.source_name
        creator_id = parts[0].get("uploader_id") or record.payload["creator_id"]
        ready_record = replace(
            record,
            content_type="tech_news",
            occurred_at=published_at,
            title=title,
            text=text,
            source_name=(
                author if self.channel_mode else f"{author} · {creator_id} · {platform_name}"
            ),
            attachments=attachments,
            payload={
                **record.payload,
                "avatar_attachment_index": 0,
                "video_verified": True,
                "ready_at": utc_iso(),
                "artifacts_path": str(cache.root.relative_to(self.runtime_root)),
            },
        )
        committed = await asyncio.to_thread(self.commit_ready, ready_record)
        state["stage"] = "discarded" if committed is False else "ready"
        cache.save("state.json", state)

    async def work_items_wait(self, work, message):
        await asyncio.to_thread(
            self.work_items.wait_for_operator,
            work.work_id,
            error_class="VIDEO_PREPARATION_PAUSED",
            error_summary=message,
        )
