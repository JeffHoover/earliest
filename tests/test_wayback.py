from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import httpx
import pytest

from earliest.sources.base import Evidence
from earliest.sources.wayback import (
    CDX_ENDPOINT,
    WaybackSource,
    normalize_url,
    parse_timestamp,
)

HEADER = ["timestamp", "original", "statuscode"]


def cdx_rows(*rows):
    """Build a CDX JSON response: header row followed by data rows."""
    return [HEADER, *rows]


@pytest.fixture
def source():
    return WaybackSource()


# --- normalize_url -----------------------------------------------------------

@pytest.mark.parametrize(
    "raw, expected",
    [
        ("https://example.com/post", "https://example.com/post"),
        ("example.com/post", "https://example.com/post"),
        ("  https://example.com/post  ", "https://example.com/post"),
        ("https://example.com/post#section", "https://example.com/post"),
        (
            "https://example.com/post?utm_source=x&utm_medium=y",
            "https://example.com/post",
        ),
        (
            "https://example.com/post?id=7&fbclid=abc",
            "https://example.com/post?id=7",
        ),
        (
            "https://example.com/post?id=7&gclid=abc&page=2",
            "https://example.com/post?id=7&page=2",
        ),
    ],
)
def test_normalize_url(raw, expected):
    assert normalize_url(raw) == expected


def test_parse_timestamp_is_utc():
    assert parse_timestamp("20190314093015") == datetime(
        2019, 3, 14, 9, 30, 15, tzinfo=timezone.utc
    )


# --- found -------------------------------------------------------------------

def test_found_returns_finding(source, respx_mock):
    respx_mock.get(CDX_ENDPOINT).mock(
        return_value=httpx.Response(
            200,
            json=cdx_rows(["20190314093015", "https://example.com/post", "200"]),
        )
    )
    result = source.find_earliest("https://example.com/post", timeout=5)

    assert result.error is None
    assert result.finding is not None
    f = result.finding
    assert f.source == "wayback"
    assert f.date == datetime(2019, 3, 14, 9, 30, 15, tzinfo=timezone.utc)
    assert f.evidence is Evidence.ARCHIVE_CAPTURE
    assert f.evidence_url == (
        "https://web.archive.org/web/20190314093015/https://example.com/post"
    )


def test_timeout_forwarded_to_httpx(source):
    request = httpx.Request("GET", CDX_ENDPOINT)
    response = httpx.Response(200, json=cdx_rows(), request=request)
    with patch("earliest.sources.wayback.httpx.get") as mock_get:
        mock_get.return_value = response
        source.find_earliest("https://example.com", timeout=7.5)
    assert mock_get.call_args.kwargs["timeout"] == 7.5


def test_request_params(source, respx_mock):
    route = respx_mock.get(CDX_ENDPOINT).mock(
        return_value=httpx.Response(200, json=cdx_rows())
    )
    source.find_earliest("example.com/post?utm_source=x#top", timeout=5)

    params = route.calls[0].request.url.params
    assert params["url"] == "https://example.com/post"  # normalized
    assert params["limit"] == "1"
    assert params["filter"] == "statuscode:200"
    assert params["output"] == "json"
    assert params["fl"] == "timestamp,original,statuscode"


# --- nothing found (not an error) --------------------------------------------

def test_header_only_means_nothing_found(source, respx_mock):
    respx_mock.get(CDX_ENDPOINT).mock(
        return_value=httpx.Response(200, json=cdx_rows())
    )
    result = source.find_earliest("https://example.com", timeout=5)
    assert result.finding is None
    assert result.error is None


def test_empty_body_means_nothing_found(source, respx_mock):
    respx_mock.get(CDX_ENDPOINT).mock(return_value=httpx.Response(200, text=""))
    result = source.find_earliest("https://example.com", timeout=5)
    assert result.finding is None
    assert result.error is None


# --- failures (must be errors, not "nothing found") --------------------------

def test_timeout_is_error(source, respx_mock):
    respx_mock.get(CDX_ENDPOINT).mock(side_effect=httpx.ConnectTimeout("slow"))
    result = source.find_earliest("https://example.com", timeout=5)
    assert result.finding is None
    assert "timed out" in result.error


def test_network_error_is_error(source, respx_mock):
    respx_mock.get(CDX_ENDPOINT).mock(side_effect=httpx.ConnectError("refused"))
    result = source.find_earliest("https://example.com", timeout=5)
    assert result.finding is None
    assert "network error" in result.error


@pytest.mark.parametrize("status", [429, 500, 503])
def test_http_error_status_is_error(source, respx_mock, status):
    respx_mock.get(CDX_ENDPOINT).mock(return_value=httpx.Response(status))
    result = source.find_earliest("https://example.com", timeout=5)
    assert result.finding is None
    assert str(status) in result.error


def test_invalid_json_is_error(source, respx_mock):
    respx_mock.get(CDX_ENDPOINT).mock(
        return_value=httpx.Response(200, text="<html>not json</html>")
    )
    result = source.find_earliest("https://example.com", timeout=5)
    assert result.finding is None
    assert "invalid JSON" in result.error


@pytest.mark.parametrize(
    "bad_row",
    [
        ["not-a-timestamp", "https://example.com", "200"],  # bad date
        ["20190314093015", "https://example.com"],          # too few fields
    ],
)
def test_malformed_row_is_error(source, respx_mock, bad_row):
    respx_mock.get(CDX_ENDPOINT).mock(
        return_value=httpx.Response(200, json=cdx_rows(bad_row))
    )
    result = source.find_earliest("https://example.com", timeout=5)
    assert result.source == "wayback"
    assert result.finding is None
    assert "unexpected CDX row format" in result.error


