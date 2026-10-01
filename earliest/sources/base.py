# earliest/sources/base.py
from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Protocol


class Evidence(str, Enum):
    ARCHIVE_CAPTURE = "archive_capture"  # upper bound: page existed by this date
    PAGE_METADATA = "page_metadata"      # date the page claims for itself
    HTTP_HEADER = "http_header"          # weak: often reflects last modification
    URL_PATTERN = "url_pattern"          # date parsed from the URL path


@dataclass(frozen=True)
class Finding:
    source: str            # "wayback"
    date: datetime         # timezone-aware, UTC
    evidence: Evidence
    evidence_url: str | None = None   # e.g. the snapshot URL, so you can verify
    note: str | None = None           # e.g. "first HTTP 200 capture"


@dataclass(frozen=True)
class SourceResult:
    source: str
    finding: Finding | None   # None = ran fine, found nothing
    error: str | None = None  # set = source failed (timeout, rate limit, bad response)


class Source(Protocol):
    name: str            # used in --source flags
    default: bool        # included when no flags are given

    def find_earliest(self, url: str, *, timeout: float) -> SourceResult:
        """Never raise for expected failures; return SourceResult(error=...)."""
        ...