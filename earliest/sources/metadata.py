from __future__ import annotations

from datetime import datetime, timezone



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
