"""Strict Pydantic models for the three-file configuration snapshot."""

from __future__ import annotations

from typing import Literal

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    PositiveFloat,
    PositiveInt,
    model_validator,
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class QueueConfig(StrictModel):
    ingest_maxsize: PositiveInt = 100
    publish_maxsize: PositiveInt = 20
    processor_workers: PositiveInt = 1
    publisher_workers: PositiveInt = 1


class StatusConfig(StrictModel):
    host: Literal["127.0.0.1"] = "127.0.0.1"
    port: int = Field(default=17654, ge=1024, le=65535)


class WebsiteConfig(StrictModel):
    enabled: bool = False
    host: str = "0.0.0.0"
    port: int = Field(default=8080, ge=1024, le=65535)


class AgentsConfig(StrictModel):
    enabled: bool = False
    endpoint: str = ""
    token_file: str = "../runtime/secrets/agents-collector.token"
    poll_seconds: PositiveFloat = 5


class AgentsTarget(StrictModel):
    collectFiles: bool = False
    sourceId: str = Field(min_length=1)
    targetId: str = Field(min_length=1)
    plugin: Literal["telegram", "x", "youtube"]
    locator: str = Field(min_length=1)
    name: str = Field(min_length=1)
    enabled: bool
    pollSeconds: PositiveFloat


class SQLiteConfig(StrictModel):
    busy_timeout_seconds: PositiveFloat = 30
    max_database_bytes: PositiveInt = 1_073_741_824


class RetentionConfig(StrictModel):
    enabled: bool = False
    batch_size: PositiveInt = 500
    media_days: PositiveInt = 3650
    generated_days: PositiveInt = 30
    diagnostics_days: PositiveInt = 30
    logs_days: PositiveInt = 30


class BackupConfig(StrictModel):
    automatic: bool = False
    keep: PositiveInt = 7


class AppConfig(StrictModel):
    version: Literal[1]
    runtime_root: str
    database_path: str
    timezone: Literal["Asia/Shanghai"] = "Asia/Shanghai"
    queues: QueueConfig
    status: StatusConfig
    website: WebsiteConfig = Field(default_factory=WebsiteConfig)
    agents: AgentsConfig = Field(default_factory=AgentsConfig)
    sqlite: SQLiteConfig
    retention: RetentionConfig
    backup: BackupConfig


ConfigScalar = str | int | float | bool


class TargetConfig(StrictModel):
    poll_seconds: PositiveFloat | None = None
    id: str = Field(min_length=1)
    locator: str = Field(min_length=1)
    name: str = Field(min_length=1)
    enabled: bool = True
    options: dict[str, ConfigScalar] = Field(default_factory=dict)


class SourceConfig(StrictModel):
    id: str = Field(min_length=1)
    plugin: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    enabled: bool = True
    poll_seconds: PositiveFloat
    options: dict[str, ConfigScalar] = Field(default_factory=dict)
    targets: tuple[TargetConfig, ...] = ()


class SourcesConfig(StrictModel):
    version: Literal[1]
    sources: tuple[SourceConfig, ...]

    @model_validator(mode="after")
    def unique_ids(self) -> SourcesConfig:
        source_ids = [source.id for source in self.sources]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("source IDs must be unique")
        target_ids: list[str] = []
        for source in self.sources:
            target_ids.extend(target.id for target in source.targets)
        if len(target_ids) != len(set(target_ids)):
            raise ValueError("target IDs must be unique")
        return self


class NewsPublishConfig(StrictModel):
    publish_interval_minutes: PositiveFloat
    restart_resume_minutes: PositiveFloat = 20
    startup_collection_timeout_seconds: PositiveFloat = 180
    # Accepted for older config snapshots; restart behavior now uses downtime and per-platform caps.
    startup_lookback_minutes: PositiveFloat = 30
    backlog_publish_interval_minutes: PositiveFloat = 5
    backlog_max_five_star_rounds: PositiveInt = 3
    previous_day_keep_minutes: int = Field(default=20, ge=0, le=60)
    source_publish_interval_minutes: dict[str, PositiveFloat] = Field(default_factory=dict)
    source_publish_modes: dict[str, Literal["interval", "capacity", "scheduled_only"]] = Field(
        default_factory=dict
    )
    source_batch_sizes: dict[str, PositiveInt] = Field(default_factory=dict)
    source_immediate_five_star: dict[str, bool] = Field(
        default_factory=dict,
        validation_alias=AliasChoices("source_immediate_five_star", "source_breaking_news"),
    )
    source_presentations: dict[
        str,
        Literal["editorial", "original_with_chinese_translation"],
    ] = Field(default_factory=dict)
    source_card_templates: dict[str, Literal["x_post.html"]] = Field(default_factory=dict)
    night_publish_interval_minutes: float = Field(ge=30, le=60)
    night_start_hour: int = Field(ge=0, le=23)
    night_end_hour: int = Field(ge=0, le=23)
    new_post_threshold: PositiveInt
    max_news_per_note: int = Field(ge=1, le=18)
    first_review_model: Literal["deepseek-v4-pro", "deepseek-v4-flash", "deepseek-flash"] = Field(
        validation_alias=AliasChoices("first_review_model", "compliance_model")
    )
    second_review_model: Literal["deepseek-v4-pro", "deepseek-v4-flash", "deepseek-flash"] = Field(
        validation_alias=AliasChoices("second_review_model", "quality_model")
    )
    image_review_model: Literal["deepseek-flash"] = "deepseek-flash"
    deepseek_key_path: str
    codex_fallback_enabled: bool = True
    codex_fallback_executable: str = Field(
        default="/Users/djf/.npm-global/bin/codex",
        min_length=1,
    )
    codex_fallback_model: str = Field(default="gpt-5.6-luna", min_length=1)
    codex_fallback_timeout_seconds: PositiveFloat = 60

    @model_validator(mode="after")
    def distinct_night_hours(self) -> NewsPublishConfig:
        if self.night_start_hour == self.night_end_hour:
            raise ValueError("night_start_hour and night_end_hour must differ")
        if self.first_review_model == self.second_review_model:
            raise ValueError("first_review_model and second_review_model must differ")
        oversized = {
            source: size
            for source, size in self.source_batch_sizes.items()
            if size > self.max_news_per_note
        }
        if oversized:
            raise ValueError("source batch size cannot exceed max_news_per_note")
        return self


class XiaohongshuSinkConfig(StrictModel):
    enabled: bool
    account_id: str = Field(min_length=1)
    mode: Literal["mac_safari"]
    background: bool = True
    keep_window_open: bool = False


class SinksConfig(StrictModel):
    xiaohongshu: XiaohongshuSinkConfig


class RetryConfig(StrictModel):
    editorial_attempts: PositiveInt
    editorial_base_delay_seconds: PositiveFloat
    transient_attempts: PositiveInt
    transient_base_delay_seconds: PositiveFloat


class ContentFilterConfig(StrictModel):
    enabled: bool = True
    minimum_text_characters: PositiveInt = 1


class RouteConfig(StrictModel):
    id: str = Field(min_length=1)
    enabled: bool = True
    content_type: str = Field(min_length=1)
    source_plugins: tuple[str, ...] = Field(min_length=1)
    processor: str = Field(min_length=1)
    sinks: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_references(self) -> RouteConfig:
        if len(self.source_plugins) != len(set(self.source_plugins)):
            raise ValueError("route source_plugins must be unique")
        if len(self.sinks) != len(set(self.sinks)):
            raise ValueError("route sinks must be unique")
        return self


class VideoProcessingConfig(StrictModel):
    transcription_key_path: str = "../runtime/secrets/dashscope-api-key"
    transcription_base_url: str = "https://dashscope.aliyuncs.com/api/v1"
    transcription_model: Literal["paraformer-v2"] = "paraformer-v2"
    workers: int = Field(default=2, ge=1, le=4)


class PublishingConfig(StrictModel):
    version: Literal[1]
    filters: dict[str, ContentFilterConfig]
    routes: tuple[RouteConfig, ...]
    news: NewsPublishConfig
    sinks: SinksConfig
    retry: RetryConfig
    videos: VideoProcessingConfig = Field(default_factory=VideoProcessingConfig)

    @model_validator(mode="after")
    def valid_routes(self) -> PublishingConfig:
        route_ids = [route.id for route in self.routes]
        if len(route_ids) != len(set(route_ids)):
            raise ValueError("route IDs must be unique")
        sink_ids = set(type(self.sinks).model_fields)
        for route in self.routes:
            if route.content_type not in self.filters:
                raise ValueError(f"route {route.id} references an unknown filter")
            unknown_sinks = set(route.sinks) - sink_ids
            if unknown_sinks:
                raise ValueError(
                    f"route {route.id} references unknown sinks: {', '.join(sorted(unknown_sinks))}"
                )
        return self
