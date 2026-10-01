# earliest

A slash command (`/earliest <url>`) that reports the earliest publication
evidence it can find for a URL. Also runs as `python -m earliest`.

## Design decisions

- Archive captures are upper bounds, not publication dates. Output must say
  "first archived", never "published".
- Each source implements `find_earliest(url, timeout) -> SourceResult`
  (see sources/base.py). Sources never raise for expected failures; they
  return SourceResult(error=...). "Found nothing" and "failed" are distinct.
- Sources register in sources/**init**.py REGISTRY. Flags: --source (repeatable),
  --exclude (repeatable), --all, --json.
- v1 is Wayback only (CDX API, oldest-first, limit=1, filter to status 200,
  normalize URL variants). Add a second source only after using v1 on real URLs.
- The slash command is a thin wrapper; all logic and arg parsing lives in
  the script so it works from a terminal too.

## Planned future sources

Page metadata (og/JSON-LD/<time>), HTTP headers, sitemap/RSS dates,
other archives (archive.today, Common Crawl, Memento), URL-path dates.

## Status

v1 complete and verified (2026-09-30). 50/50 tests passing. CDX response format confirmed
against a real URL: `https://paulgraham.com/avg.html` returned 2001-04-09, matching all
assumptions (header-row + data-row JSON, timestamp parsing, snapshot URL construction).

Known open items:
- "Nothing found" exit path (exit 1) not yet exercised against a real URL — IA was flaky
  during testing. Try a URL with no known captures when IA is stable.
- One run showed normal output on stderr instead of stdout (exit code 2 case). May be a
  shell buffering artifact; watch for it on future runs.
- IA flakiness: CDX API returns 503 or times out during outages. No retry or fallback by
  design; revisit when a second source is added.
