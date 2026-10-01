from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest

from earliest.sources.wayback import CDX_ENDPOINT, WaybackSource

HEADER = ["timestamp", "original", "statuscode"]


def cdx_rows(*rows):
    return [HEADER, *rows]


@pytest.fixture
def source():
    return WaybackSource()


def test_trailing_slash_gives_different_cdx_key(source, respx_mock):
    """Documents the problem: the two forms are sent as different CDX keys."""
    calls = []

    def capture(request):
        calls.append(request.url.params["url"])
        return httpx.Response(200, json=cdx_rows())

    respx_mock.get(CDX_ENDPOINT).mock(side_effect=capture)
    source.find_earliest("https://example.com/", timeout=5)
    source.find_earliest("https://example.com", timeout=5)

    assert calls[0] == "https://example.com/"
    assert calls[1] == "https://example.com"
    assert calls[0] != calls[1]


# --- FAILING TESTS -----------------------------------------------------------
# These specify the desired fix: when one form finds nothing, retry with the
# alternate trailing-slash form. They currently fail because find_earliest
# makes only one CDX request. Remove this comment when the fix is in.


def test_trailing_slash_retries_without_slash(source, respx_mock):
    """Slashed form finds nothing → should retry without the slash and return the result."""
    def respond(request):
        if request.url.params["url"].endswith("/"):
            return httpx.Response(200, json=cdx_rows())
        return httpx.Response(
            200,
            json=cdx_rows(["20240325195322", "https://bloggingduringlunch.com/", "200"]),
        )

    respx_mock.get(CDX_ENDPOINT).mock(side_effect=respond)
    result = source.find_earliest("https://bloggingduringlunch.com/", timeout=5)

    assert result.finding is not None
    assert result.finding.date == datetime(2024, 3, 25, 19, 53, 22, tzinfo=timezone.utc)


def test_no_trailing_slash_retries_with_slash(source, respx_mock):
    """No-slash form finds nothing → should retry with the slash and return the result."""
    def respond(request):
        if not request.url.params["url"].endswith("/"):
            return httpx.Response(200, json=cdx_rows())
        return httpx.Response(
            200,
            json=cdx_rows(["20240325195322", "https://example.com/", "200"]),
        )

    respx_mock.get(CDX_ENDPOINT).mock(side_effect=respond)
    result = source.find_earliest("https://example.com", timeout=5)

    assert result.finding is not None
    assert result.finding.date == datetime(2024, 3, 25, 19, 53, 22, tzinfo=timezone.utc)
