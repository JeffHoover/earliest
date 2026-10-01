# Prompt for Claude Code: the `earliest` project

Paste everything below the line into Claude Code, started from the project root (`/Users/jeffhoover/Documents/projects/earliest`).

---

## Your role and how I want to work

I'm building a small tool called `earliest`. The design was worked out in a long conversation with another Claude session, and this prompt carries over everything that matters. Read it fully, then read `CLAUDE.md` and the files on disk before changing anything.

Working agreements:

- **Show me a plan before you implement anything non-trivial.** I want to stay in the loop on design decisions rather than receive a finished tool.
- **Tests first** when adding behavior. Mock all HTTP; no test may touch the real network.
- **Do not guess about real-world API behavior.** If you can, verify the Wayback CDX API's actual response format with one real request and tell me if it differs from the assumptions below.
- **Keep scope small.** Do not add sources, features, or abstractions I haven't asked for. This is a pet project I want to actually use, not an exercise in completeness.
- **Be honest about what you ran.** Say explicitly what you executed (pytest, a real URL) versus what you only read.

## Why this project exists

My previous project (`ticket_triage`) was well engineered but not useful, because it was built as an exam exercise with no real user. This one is meant to scratch a real itch: given a URL, tell me the earliest publication evidence that can be found. I am the user. Success means I use it on real URLs and it saves me time, not that it has high test coverage.

## What it does

A slash command, `/earliest <url>`, backed by a plain Python CLI, `python -m earliest <url>`. It reports the earliest date it can find for a URL and shows every individual finding with its source and what kind of evidence it is.

**Core principle: an archive capture is an upper bound, not a publication date.** The Wayback Machine's first snapshot only proves the page existed by then. Output must say "first archived", never "published", for archive evidence. This is enforced in the script's `LABELS` dict (so it's backed up in code, not just in the slash command's wording) and by a test.

v1 uses one source, the Wayback Machine, queried through its CDX API. The design makes adding sources cheap, but I do not want a second source until I've used v1 on real URLs and know which one I'm missing.

## Architecture

The slash command is a thin wrapper; all logic and argument parsing live in the script, so it works identically from a terminal.

**Source interface** (`earliest/sources/base.py`):

- `Evidence` enum: `ARCHIVE_CAPTURE` ("archive_capture"), `PAGE_METADATA`, `HTTP_HEADER`, `URL_PATTERN`.
- `Finding` (frozen dataclass): `source`, `date` (timezone-aware UTC datetime), `evidence`, `evidence_url` (optional, e.g. the snapshot URL, so I can verify), `note` (optional).
- `SourceResult` (frozen dataclass): `source`, `finding` (None means the source ran fine and found nothing), `error` (set means the source failed).
- `Source` Protocol: attributes `name` (used in `--source` flags) and `default` (included when no flags given); method `find_earliest(url, *, timeout) -> SourceResult`. **Sources must never raise for expected failures** (timeouts, rate limits, bad responses); they return `SourceResult(error=...)`.

**The key distinction:** "found nothing" (`finding=None, error=None`) and "failed" (`error` set) are different outcomes and must stay different everywhere, including exit codes and output. "No archive exists" and "Wayback was down" mean different things to me.

**Registry** (`earliest/sources/__init__.py`): `REGISTRY: dict[str, Source]` built from a list of source instances, plus `select_sources(only, exclude, include_all)`:

- `only` given: return exactly those sources, in the order given, even if they're not default. Unknown names raise `ValueError` listing all unknown names, sorted.
- Otherwise: all sources where `default` is true (or all sources if `include_all`), minus any in `exclude`.
- Adding a source = write one module in `sources/` and add one entry to the list in the registry.

**CLI flags** (`earliest/__main__.py`, argparse): `url` (positional), `--source NAME` (repeatable), `--exclude NAME` (repeatable), `--all` (include off-by-default sources), `--json` (machine-readable output), `--timeout SECONDS` (per source, default 15).

**Exit codes:** `0` = a date was found; `1` = clean "nothing found"; `2` = bad arguments, no sources selected, or every source failed. Mixed results (one source errored, another found nothing) exit `1`; if any source found a date, exit `0`.

**Output:** text mode prints the URL, then `Earliest: YYYY-MM-DD (<label>, via <source>)` or `Earliest: no date found`, then a per-source list showing date/label/note/verify URL, `ERROR - <message>`, or `nothing found`. JSON mode emits `{url, earliest, results: [{source, finding, error}]}` with `earliest` null when nothing was found. The overall earliest is the minimum date across all findings.

## Wayback source details (`earliest/sources/wayback.py`)

- Endpoint: `https://web.archive.org/cdx/search/cdx`, via `httpx.get`.
- Params: `url` (normalized), `output=json`, `limit=1` (CDX returns oldest first, so one row is the earliest), `filter=statuscode:200` (so a redirect or error capture doesn't count as the earliest), `fl=timestamp,original,statuscode`.
- Response format assumed: JSON array of arrays, row 0 is a header, data starts at row 1. Empty body or header-only means nothing found.
- Timestamps look like `20190314093015` (UTC). Snapshot URL for verification: `https://web.archive.org/web/{timestamp}/{original}`.
- `normalize_url`: strip whitespace, add `https://` if no scheme, drop the fragment, drop tracking params (`utm_*`, `fbclid`, `gclid`, `mc_cid`, `mc_eid`). It deliberately does not handle http/https or www variants because the CDX index already collapses those.
- Error mapping to `SourceResult.error`: timeout -> "timed out after Ns"; HTTP error status -> "HTTP <code> from CDX API"; other httpx errors -> "network error: ..."; invalid JSON -> "CDX API returned invalid JSON"; malformed row -> "unexpected CDX row format".

## Project layout

```
earliest/                     # project root
  CLAUDE.md
  pyproject.toml
  .gitignore                  # .venv/, __pycache__/, *.egg-info/
  .claude/commands/earliest.md   # makes /earliest work
  earliest/                   # the Python package
    __init__.py               # empty
    __main__.py
    sources/
      __init__.py             # REGISTRY, select_sources
      base.py
      wayback.py
  tests/
    __init__.py               # empty
    test_wayback.py
    test_main.py
    test_sources.py
```

`pyproject.toml`: setuptools build, Python >= 3.10, runtime dependency `httpx>=0.27`, dev extras `pytest>=8` and `respx>=0.21`, `packages.find` restricted to `earliest*`, pytest `testpaths = ["tests"]`. Setup is `python3 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"`.

## The slash command (`.claude/commands/earliest.md`)

Frontmatter: `description`, `argument-hint: <url> [--source NAME]... [--exclude NAME]... [--all] [--json]`, and `allowed-tools: Bash(python -m earliest:*)`. Body runs `python -m earliest $ARGUMENTS` and asks Claude to summarize: (1) the earliest date, its source and evidence type; (2) every other finding, one line each; (3) sources that errored, listed separately from sources that found nothing. Rules in the body: archive captures are upper bounds, say "first archived" never "published"; flag page-metadata vs archive disagreements of more than a few days; if no date was found say so plainly and do not guess; do not fetch or search the web, use only the script's output.

## Current state (important: read this carefully)

- All files are in place and consistent with this prompt. No missing or inconsistent items found.
- `pytest -v`: **50/50 passing** as of 2026-09-30. No failures; no tests look wrong.
- CDX response format **confirmed against a real URL**: `python -m earliest https://paulgraham.com/avg.html` returned `2001-04-09` with snapshot URL `https://web.archive.org/web/20010409063841/http://www.paulgraham.com:80/avg.html`. The header-row + data-row JSON format, timestamp parsing, and snapshot URL construction all matched assumptions exactly.
- The Internet Archive CDX API was intermittently offline during initial testing (returning 503 or timing out). Both error cases are caught and reported correctly. IA was stable enough to confirm the format with one successful run.
- **The "nothing found" exit path (exit 1) has not been verified** with a real URL yet — attempts to test it hit IA 503s before getting a clean empty result.
- **Stdout/stderr observation:** on a run that returned exit code 2 (all sources errored), the normal text output appeared on stderr rather than stdout in one capture. This may be a shell buffering artifact or a real bug. Worth watching for on future runs.

## Known limitations and open decisions

These are deliberate simplifications. Surface them to me when real usage hits them; don't silently "fix" them.

- **Trailing slash:** `https://example.com/post` and `https://example.com/post/` are different CDX keys, so a miss on one may succeed on the other. Not handled yet. Candidate fix: retry with the alternate form.
- **Status filter:** `statuscode:200` can make the reported date later than the truly earliest capture (for example when the first capture was a redirect). Removing it gives the earliest capture but possibly an error page. Reversible; a test pins the current params.
- **Earliest = min across all evidence types** is a simplification. Once page-metadata sources exist, an archive date and a page's self-claimed date mean different things, so they may need to be reported separately rather than min'd together.
- **`select_sources` quirks, pinned by tests:** `--exclude` is ignored when `--source` is given, and excluding an unknown name is silently ignored. Neither is necessarily desirable; I may want errors or warnings instead.
- **Sources run sequentially.** Fine for one source; when there are several, switch to a thread pool inside `main`.
- **`--timeout` is per source**, not total.
- **IA flakiness:** the CDX API returns 503 or times out during Internet Archive outages. The tool reports this honestly (exit 2, ERROR line) but has no retry logic and no fallback source. This is by design for v1; revisit when a second source is added.
- **No official IA status page:** `status.archive.org` redirects to `archive.org` (not a real status page). Their Bluesky/Mastodon/Twitter accounts are the stated channels for outage information, but may not have timely posts during outages.

## Possible future sources (do not build yet)

Page metadata (`article:published_time`, JSON-LD `datePublished`, `<time>` tags; often the closest thing to the true publication date), HTTP headers such as `Last-Modified` (weak), sitemap `lastmod` and RSS/Atom feed dates, other archives (archive.today, Common Crawl index, a Memento aggregator), and dates embedded in the URL path.

## What I want next

After the first tasks above, I'm going to try the tool on about ten real URLs (old blog posts, a news article, a recently published page). Based on what breaks or disappoints, we'll decide whether the next step is better URL handling or a second source. Until then, don't add features.
