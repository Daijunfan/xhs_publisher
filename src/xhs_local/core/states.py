"""Persisted work and plugin states."""

from enum import StrEnum


class WorkTopic(StrEnum):
    RECORD_COLLECTED = "record_collected"
    VIDEO_PREPARE = "video_prepare"
    NEWS_PUBLISH = "news_publish"
    RESOURCE_PUBLISH = "resource_publish"  # Decode historical work only; no active handler/queue.


class WorkState(StrEnum):
    READY = "READY"
    RUNNING = "RUNNING"
    SUBMITTING = "SUBMITTING"
    RETRY_WAIT = "RETRY_WAIT"
    RECONCILE_ONLY = "RECONCILE_ONLY"
    WAITING_OPERATOR = "WAITING_OPERATOR"
    SUCCEEDED = "SUCCEEDED"
    REJECTED = "REJECTED"
    DEAD_LETTER = "DEAD_LETTER"


TERMINAL_WORK_STATES = frozenset({WorkState.SUCCEEDED, WorkState.REJECTED, WorkState.DEAD_LETTER})
