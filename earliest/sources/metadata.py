from __future__ import annotations

import json
from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup

from earliest.sources.base import Evidence, Finding, SourceResult


class MetadataSource:
    name = "metadata"
    default = True

    def find_earliest(self, url: str, *, timeout: float) -> SourceResult:
        try:
            response = httpx.get(url, timeout=timeout, follow_redirects=True)
        except httpx.TimeoutException:
            return SourceResult(source=self.name, finding=None, error="timed out")
        except httpx.NetworkError:
            return SourceResult(source=self.name, finding=None, error="network error")
        except Exception as exc:
            return SourceResult(source=self.name, finding=None, error=str(exc))

        if response.status_code != 200:
            return SourceResult(source=self.name, finding=None, error=f"HTTP {response.status_code}")

        soup = BeautifulSoup(response.text, "html.parser")

        candidates = []

        for signal_name in ("article:published_time", "og:published_time"):
            tag = soup.find("meta", property=signal_name)
            if tag and tag.get("content"):
                date = parse_date(tag["content"])
                if date is not None:
                    candidates.append((date, signal_name))

        for time_tag in soup.find_all("time", datetime=True):
            date = parse_date(time_tag["datetime"])
            if date is not None:
                candidates.append((date, "time[datetime]"))

        for script_tag in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script_tag.string or "")
                raw_date = data.get("datePublished")
                if raw_date:
                    date = parse_date(raw_date)
                    if date is not None:
                        candidates.append((date, "datePublished"))
            except (json.JSONDecodeError, AttributeError):
                pass

        if candidates:
            earliest_date, signal_name = min(candidates, key=lambda pair: pair[0])
            finding = Finding(
                source=self.name,
                date=earliest_date,
                evidence=Evidence.PAGE_METADATA,
                evidence_url=url,
                note=signal_name,
            )
            return SourceResult(source=self.name, finding=finding)

        return SourceResult(source=self.name, finding=None)


def parse_date(date_str: str) -> datetime | None:
    if not date_str[:4].isdigit():
        return None
    if "T" not in date_str and " " not in date_str:
        try:
            return datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    if date_str.endswith("Z"):
        date_str = date_str[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(date_str)
        if parsed.tzinfo is not None:
            return parsed.astimezone(timezone.utc)
        return parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None
