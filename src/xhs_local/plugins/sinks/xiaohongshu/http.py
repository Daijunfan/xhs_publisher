"""Explicit, authenticated publishing API for the operating AI Agent."""

from __future__ import annotations

import asyncio
import hashlib
import secrets
import shutil
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from typing import Literal

from aiohttp import web
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from xhs_local.core.contracts import PublishNote
from xhs_local.core.states import WorkTopic
from xhs_local.rendering.layout import paginate_text
from xhs_local.rendering.renderer import HtmlPhotoGenerator
from xhs_local.storage.records import RecordsRepository
from xhs_local.storage.remote_operations import RemoteOperationRepository
from xhs_local.storage.work_items import WorkItemRepository

from .browser import SafariPublisher, SafariPublishError


class DraftItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    record_id: str = Field(min_length=1)
    headline: str = Field(min_length=1, max_length=28)
    text: str = Field(min_length=1)


class PublicationDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: str = Field(min_length=1, max_length=128)
    reviewed: Literal[True]
    title: str = Field(min_length=1, max_length=20)
    body: str = Field(min_length=1, max_length=1000)
    topics: tuple[str, ...] = ()
    items: tuple[DraftItem, ...] = Field(min_length=1, max_length=18)


class ManualPublicationAPI:
    def __init__(self, records: RecordsRepository, *, publisher=None, renderer=None):
        self.records = records
        self.root = records.media.runtime_root
        self.operations = RemoteOperationRepository(records.database)
        self.works = WorkItemRepository(records.database)
        self.publisher = publisher or SafariPublisher(max_images=18)
        self.renderer = renderer
        self.lock = asyncio.Lock()

    def authorize(self, request: web.Request) -> None:
        token_file = self.root / "secrets/operator-api.token"
        if not token_file.is_file():
            raise web.HTTPServiceUnavailable(text="Restore operator-api.token first")
        token = token_file.read_text().strip()
        if not token or not secrets.compare_digest(
            request.headers.get("Authorization", ""), "Bearer " + token
        ):
            raise web.HTTPUnauthorized()

    @staticmethod
    def response(operation) -> web.Response:
        return web.json_response(
            {
                "request_id": operation.idempotency_key,
                "state": operation.state,
                "result": operation.result,
                "error": operation.error_summary,
            },
            status=202 if operation.state in {"SUBMITTING", "AMBIGUOUS"} else 200,
        )

    async def post(self, request: web.Request) -> web.Response:
        self.authorize(request)
        try:
            draft = PublicationDraft.model_validate(await request.json())
        except (ValidationError, ValueError):
            raise web.HTTPBadRequest(
                text="Provide a reviewed draft with request_id and items"
            ) from None
        payload = draft.model_dump(mode="json")
        async with self.lock:
            existing = self.operations.get_by_key("xiaohongshu", "main", draft.request_id)
            if existing is not None:
                if existing.request != payload:
                    raise web.HTTPConflict(text="request_id already belongs to another draft")
                if existing.state != "NOT_SUBMITTED":
                    return self.response(existing)
            digest = hashlib.sha256(draft.request_id.encode()).hexdigest()
            directory = self.root / "generated/manual" / digest
            renderer = self.renderer or HtmlPhotoGenerator(
                output_dir=directory, runtime_root=self.root
            )
            cards = []
            for item in draft.items:
                stored = self.records.get(item.record_id)
                if stored is None or stored.record.occurred_at < datetime.now(UTC) - timedelta(
                    days=2
                ):
                    raise web.HTTPBadRequest(text="Source record is missing or older than 48 hours")
                record = stored.record
                avatar_index = record.payload.get("avatar_attachment_index")
                avatar = next((a for a in stored.attachments if a.index == avatar_index), None)
                attachments = tuple(a for a in stored.attachments if a.index != avatar_index)
                pages = paginate_text(item.text)
                cards.extend(
                    {
                        "record_id": item.record_id,
                        "headline": item.headline,
                        "text": page,
                        "source": record.source_name,
                        "occurred_at": record.occurred_at,
                        "source_platform": record.plugin_id,
                        "avatar": avatar,
                        "attachments": attachments if index == 0 else (),
                        "story_has_media": bool(attachments),
                        "story_page": index + 1,
                        "story_pages": len(pages),
                        "template_name": "x_post.html",
                    }
                    for index, page in enumerate(pages)
                )
            if len(cards) > 18:
                raise web.HTTPBadRequest(text="Complete stories exceed 18 images; split the draft")
            operation = None
            try:
                images = await renderer.generate_news_cards(cards, prefix="manual")
                work_id = (
                    existing.work_id
                    if existing
                    else self.works.create(WorkTopic.NEWS_PUBLISH, payload=payload)
                )
                if self.works.claim(work_id) is None:
                    raise web.HTTPConflict(text="Publication request is already in progress")
                operation = self.operations.begin(
                    work_id,
                    sink="xiaohongshu",
                    account_id="main",
                    operation="agent_publish",
                    idempotency_key=draft.request_id,
                    request=payload,
                )
                if operation is None:
                    raise web.HTTPConflict(text="Publication request is already in progress")
                result = await self.publisher.publish(
                    PublishNote(
                        draft.title,
                        draft.body,
                        tuple(images),
                        topics=draft.topics,
                    )
                )
                if result.ok and result.confirmed_in_note_manager:
                    self.operations.succeed(operation.operation_id, result=asdict(result))
                elif result.submission_started:
                    self.operations.ambiguous(
                        operation.operation_id, error_summary="Confirm in note manager"
                    )
                else:
                    self.operations.not_submitted(
                        operation.operation_id, error_summary="Not submitted"
                    )
                return self.response(self.operations.get(operation.operation_id))
            except Exception as error:
                if operation is not None:
                    if isinstance(error, SafariPublishError) and not error.submission_started:
                        self.operations.not_submitted(
                            operation.operation_id, error_summary=type(error).__name__
                        )
                    else:
                        self.operations.ambiguous(
                            operation.operation_id, error_summary=type(error).__name__
                        )
                    return self.response(self.operations.get(operation.operation_id))
                raise
            finally:
                await self.publisher.close()
                shutil.rmtree(directory, ignore_errors=True)

    async def get(self, request: web.Request) -> web.Response:
        self.authorize(request)
        async with self.lock:
            operation = self.operations.get_by_key(
                "xiaohongshu", "main", request.match_info["request_id"]
            )
            if operation is None:
                raise web.HTTPNotFound()
            if operation.state in {"SUBMITTING", "AMBIGUOUS"}:
                if operation.state == "SUBMITTING":
                    self.operations.ambiguous(
                        operation.operation_id, error_summary="Interrupted submission"
                    )
                try:
                    evidence = await self.publisher.probe_submission(
                        title=operation.request["title"],
                        body=operation.request["body"],
                        created_at=operation.created_at,
                    )
                    if evidence["found"] is True:
                        self.operations.succeed(
                            operation.operation_id, result={"reconciled": True, **evidence}
                        )
                    elif evidence["found"] is False:
                        self.operations.reject_absent(
                            operation.operation_id, evidence="Note manager confirms absence"
                        )
                finally:
                    await self.publisher.close()
                operation = self.operations.get(operation.operation_id)
            return self.response(operation)


def add_publish_routes(
    application: web.Application, records: RecordsRepository, *, api=None
) -> None:
    service = api or ManualPublicationAPI(records)
    application.add_routes(
        [
            web.post("/api/xiaohongshu/publish", service.post),
            web.get("/api/xiaohongshu/publications/{request_id}", service.get),
        ]
    )
