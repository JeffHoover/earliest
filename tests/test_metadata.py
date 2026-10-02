from __future__ import annotations

from datetime import datetime, timezone

from earliest.sources.metadata import parse_date


# --- parse_date --------------------------------------------------------------

def test_parse_date_iso_with_offset():
    result = parse_date("2023-01-15T10:30:00+05:00")
    assert result == datetime(2023, 1, 15, 5, 30, 0, tzinfo=timezone.utc)


def test_parse_date_iso_with_z():
    result = parse_date("2023-01-15T10:30:00Z")
    assert result == datetime(2023, 1, 15, 10, 30, 0, tzinfo=timezone.utc)


def test_parse_date_only():
    result = parse_date("2023-01-15")
    assert result == datetime(2023, 1, 15, 0, 0, 0, tzinfo=timezone.utc)


def test_parse_date_invalid():
    assert parse_date("not a date") is None
