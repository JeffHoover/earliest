from __future__ import annotations

from .base import Source
from .wayback import WaybackSource

REGISTRY: dict[str, Source] = {s.name: s for s in [WaybackSource()]}


def select_sources(
    only: list[str] | None,
    exclude: list[str] | None,
    include_all: bool,
) -> list[Source]:
    if only:
        unknown = set(only) - REGISTRY.keys()
        if unknown:
            raise ValueError(f"Unknown source(s): {', '.join(sorted(unknown))}")
        return [REGISTRY[n] for n in only]
    chosen = [s for s in REGISTRY.values() if include_all or s.default]
    return [s for s in chosen if s.name not in (exclude or [])]


