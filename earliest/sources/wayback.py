from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

from .base import Evidence, Finding, SourceResult

CDX_ENDPOINT = "https://web.archive.org/cdx/search/cdx"
SNAPSHOT_URL = "https://web.archive.org/web/{timestamp}/{original}"

TRACKING_PREFIXES = ("utm_",)
TRACKING_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid"}


def normalize_url(url: str) -> str:
    """Drop the fragment and common tracking params; add a scheme if missing.

    The CDX index already collapses http/https and www variants, so those
    need no handling here.
    """
    url = url.strip()
    if "://" not in url:
        url = "https://" + url
    parts = urlsplit(url)
    query = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not k.lower().startswith(TRACKING_PREFIXES)
        and k.lower() not in TRACKING_KEYS
    ]
    return urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(query), "")
    )


def _toggle_slash(url: str) -> str:
    """Return the URL with the path's trailing slash toggled."""
    parts = urlsplit(url)
    if parts.path.endswith("/"):
        new_path = parts.path.rstrip("/") or ""
    else:
        new_path = parts.path + "/"
    return urlunsplit((parts.scheme, parts.netloc, new_path, parts.query, ""))


def parse_timestamp(ts: str) -> datetime:
    """CDX timestamps look like 20190314093015 (UTC)."""
    return datetime.strptime(ts, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)


class WaybackSource:
    name = "wayback"
    default = True

    def _query_cdx(self, target: str, timeout: float) -> SourceResult:
        params = {
            "url": target,
            "output": "json",
            "limit": 1,                      # CDX sorts oldest first
            "filter": "statuscode:200",      # skip redirects and errors
            "fl": "timestamp,original,statuscode",
        }
        try:
            resp = httpx.get(CDX_ENDPOINT, params=params, timeout=timeout)
            resp.raise_for_status()
            body = resp.text.strip()
            rows = resp.json() if body else []
        except httpx.TimeoutException:
            return SourceResult(self.name, None, error=f"timed out after {timeout}s")
        except httpx.HTTPStatusError as e:
            return SourceResult(
                self.name, None, error=f"HTTP {e.response.status_code} from CDX API"
            )
        except httpx.HTTPError as e:
            return SourceResult(self.name, None, error=f"network error: {e}")
        except ValueError:
            return SourceResult(self.name, None, error="CDX API returned invalid JSON")

        # rows[0] is the header row; data starts at rows[1]
        if len(rows) < 2:
            return SourceResult(self.name, None)

        try:
            timestamp, original, _status = rows[1]
            date = parse_timestamp(timestamp)
        except (ValueError, TypeError):
            return SourceResult(self.name, None, error="unexpected CDX row format")

        return SourceResult(
            self.name,
            Finding(
                source=self.name,
                date=date,
                evidence=Evidence.ARCHIVE_CAPTURE,
                evidence_url=SNAPSHOT_URL.format(timestamp=timestamp, original=original),
                note="first HTTP 200 capture",
            ),
        )

    def find_earliest(self, url: str, *, timeout: float) -> SourceResult:
        target = normalize_url(url)
        result = self._query_cdx(target, timeout)
        if result.finding is None and result.error is None:
            alt_result = self._query_cdx(_toggle_slash(target), timeout)
            if alt_result.finding is not None:
                return alt_result
        return result
