from __future__ import annotations

import argparse
import json
import sys

from .sources import REGISTRY, select_sources
from .sources.base import Evidence, Finding, SourceResult

LABELS = {
    Evidence.ARCHIVE_CAPTURE: "first archived",
    Evidence.PAGE_METADATA: "page claims published",
    Evidence.HTTP_HEADER: "last-modified header",
    Evidence.URL_PATTERN: "date in URL",
}


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="earliest",
        description="Find the earliest publication evidence for a URL.",
    )
    p.add_argument("url")
    p.add_argument(
        "--source", action="append", metavar="NAME",
        help=f"use only this source (repeatable). Available: {', '.join(REGISTRY)}",
    )
    p.add_argument(
        "--exclude", action="append", metavar="NAME",
        help="skip this source (repeatable)",
    )
    p.add_argument(
        "--all", action="store_true", dest="include_all",
        help="include sources that are off by default",
    )
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.add_argument(
        "--timeout", type=float, default=15.0,
        help="per-source timeout in seconds (default: 15)",
    )
    return p


def earliest_finding(results: list[SourceResult]) -> Finding | None:
    findings = [r.finding for r in results if r.finding]
    return min(findings, key=lambda f: f.date) if findings else None


def finding_to_dict(f: Finding) -> dict:
    return {
        "source": f.source,
        "date": f.date.isoformat(),
        "evidence": f.evidence.value,
        "evidence_url": f.evidence_url,
        "note": f.note,
    }


def render_json(url: str, results: list[SourceResult], best: Finding | None) -> str:
    return json.dumps(
        {
            "url": url,
            "earliest": finding_to_dict(best) if best else None,
            "results": [
                {
                    "source": r.source,
                    "finding": finding_to_dict(r.finding) if r.finding else None,
                    "error": r.error,
                }
                for r in results
            ],
        },
        indent=2,
    )


def render_text(url: str, results: list[SourceResult], best: Finding | None) -> str:
    lines = [f"URL: {url}", ""]
    if best:
        lines.append(
            f"Earliest: {best.date:%Y-%m-%d} "
            f"({LABELS[best.evidence]}, via {best.source})"
        )
    else:
        lines.append("Earliest: no date found")
    lines.append("")
    lines.append("All sources:")
    for r in results:
        if r.error:
            lines.append(f"  {r.source}: ERROR - {r.error}")
        elif r.finding:
            f = r.finding
            lines.append(
                f"  {r.source}: {f.date:%Y-%m-%d} "
                f"({LABELS[f.evidence]}; {f.note or 'no note'})"
            )
            if f.evidence_url:
                lines.append(f"    verify: {f.evidence_url}")
        else:
            lines.append(f"  {r.source}: nothing found")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        sources = select_sources(args.source, args.exclude, args.include_all)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if not sources:
        print("error: no sources selected", file=sys.stderr)
        return 2

    results = [s.find_earliest(args.url, timeout=args.timeout) for s in sources]
    best = earliest_finding(results)

    render = render_json if args.json else render_text
    print(render(args.url, results, best))

    if best:
        return 0
    # nothing found: distinguish "all sources failed" from "genuinely no data"
    return 2 if all(r.error for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())

