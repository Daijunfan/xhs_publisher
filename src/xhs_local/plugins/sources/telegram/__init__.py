"""Telegram SourcePlugin implementation."""

from .client import activate_session, authorize_telegram_session
from .plugin import TelegramSourcePlugin

__all__ = ["TelegramSourcePlugin", "activate_session", "authorize_telegram_session"]
