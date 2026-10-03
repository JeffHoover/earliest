from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest

from earliest.sources.metadata import MetadataSource, parse_date


@pytest.fixture
def source():
    return MetadataSource()


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


# --- signal extraction -------------------------------------------------------

def test_finds_article_published_time(source, respx_mock):
    html = '<meta property="article:published_time" content="2023-01-15T10:30:00Z">'
    respx_mock.get("https://example.com/post").mock(
        return_value=httpx.Response(200, text=html)
    )
    result = source.find_earliest("https://example.com/post", timeout=5)
    assert result.error is None
    assert result.finding is not None
    assert result.finding.date == datetime(2023, 1, 15, 10, 30, 0, tzinfo=timezone.utc)


def test_finds_og_published_time(source, respx_mock):
    html = '<meta property="og:published_time" content="2023-03-20T08:00:00Z">'
    respx_mock.get("https://example.com/post").mock(
        return_value=httpx.Response(200, text=html)
    )
    result = source.find_earliest("https://example.com/post", timeout=5)
    assert result.error is None
    assert result.finding is not None
    assert result.finding.date == datetime(2023, 3, 20, 8, 0, 0, tzinfo=timezone.utc)


def test_finds_json_ld_date_published(source, respx_mock):
    html = '<script type="application/ld+json">{"datePublished": "2022-06-01T00:00:00Z"}</script>'
    respx_mock.get("https://example.com/post").mock(
        return_value=httpx.Response(200, text=html)
    )
    result = source.find_earliest("https://example.com/post", timeout=5)
    assert result.error is None
    assert result.finding is not None
    assert result.finding.date == datetime(2022, 6, 1, 0, 0, 0, tzinfo=timezone.utc)


def test_finds_time_element(source, respx_mock):
    html = '<time datetime="2021-11-05">November 5, 2021</time>'
    respx_mock.get("https://example.com/post").mock(
        return_value=httpx.Response(200, text=html)
    )
    result = source.find_earliest("https://example.com/post", timeout=5)
    assert result.error is None
    assert result.finding is not None
    assert result.finding.date == datetime(2021, 11, 5, 0, 0, 0, tzinfo=timezone.utc)


def test_prefers_earliest_when_signals_disagree(source, respx_mock):
    html = """
    <meta property="article:published_time" content="2023-06-01T00:00:00Z">
    <time datetime="2021-01-10">January 10, 2021</time>
    """
    respx_mock.get("https://example.com/post").mock(
        return_value=httpx.Response(200, text=html)
    )
    result = source.find_earliest("https://example.com/post", timeout=5)
    assert result.error is None
    assert result.finding is not None
    assert result.finding.date == datetime(2021, 1, 10, 0, 0, 0, tzinfo=timezone.utc)


def test_nothing_found_when_no_metadata(source, respx_mock):
    html = "<html><body><p>No dates here.</p></body></html>"
    respx_mock.get("https://example.com/post").mock(
        return_value=httpx.Response(200, text=html)
    )
    result = source.find_earliest("https://example.com/post", timeout=5)
    assert result.finding is None
    assert result.error is None


# --- error handling ----------------------------------------------------------

def test_timeout_is_error(source, respx_mock):
    respx_mock.get("https://example.com/post").mock(
        side_effect=httpx.ConnectTimeout("slow")
    )
    result = source.find_earliest("https://example.com/post", timeout=5)
    assert result.finding is None
    assert "timed out" in result.error


def test_network_error_is_error(source, respx_mock):
    respx_mock.get("https://example.com/post").mock(
        side_effect=httpx.ConnectError("refused")
    )
    result = source.find_earliest("https://example.com/post", timeout=5)
    assert result.finding is None
    assert "network error" in result.error


@pytest.mark.parametrize("status", [404, 429, 500])
def test_http_error_status_is_error(source, respx_mock, status):
    respx_mock.get("https://example.com/post").mock(
        return_value=httpx.Response(status)
    )
    result = source.find_earliest("https://example.com/post", timeout=5)
    assert result.finding is None
    assert result.error == f"HTTP {status}"
