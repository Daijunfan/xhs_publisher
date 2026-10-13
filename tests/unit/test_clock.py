from datetime import UTC, datetime

from xhs_local.core.clock import utc_iso


def test_utc_iso_preserves_legacy_millisecond_z_format() -> None:
    assert utc_iso(datetime(2026, 8, 19, 12, 34, 56, 123456, tzinfo=UTC)) == (
        "2026-08-19T12:34:56.123Z"
    )
