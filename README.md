# earliest

Given a URL, report the earliest publication evidence that can be found for it.

```
$ python -m earliest https://paulgraham.com/avg.html

URL: https://paulgraham.com/avg.html

Earliest: 2001-04-09 (first archived, via wayback)

All sources:
  wayback: 2001-04-09 (first archived; first HTTP 200 capture)
    verify: https://web.archive.org/web/20010409063841/http://www.paulgraham.com:80/avg.html
```

**Important:** an archive capture is an upper bound, not a publication date. A Wayback
snapshot proves the page existed by that date — not that it was published then. The tool
says "first archived", never "published".

## Setup

```
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Requires Python 3.10+. Runtime dependency: `httpx`. Dev extras: `pytest`, `respx`.

## Usage

```
python -m earliest <url> [options]
```

Or, in Claude Code:

```
/earliest <url> [options]
```

### Options

| Flag | Description |
|------|-------------|
| `--source NAME` | Use only this source (repeatable) |
| `--exclude NAME` | Skip this source (repeatable) |
| `--all` | Include sources that are off by default |
| `--json` | Machine-readable output |
| `--timeout SECONDS` | Per-source timeout (default: 15) |

### Exit codes

| Code | Meaning |
|------|---------|
| `0` | A date was found |
| `1` | Ran fine, no date found |
| `2` | Bad arguments, no sources selected, or every source errored |

"No archive exists" (exit 1) and "Wayback was down" (exit 2) are distinct and reported
differently.

### JSON output

```
$ python -m earliest https://paulgraham.com/avg.html --json
{
  "url": "...",
  "earliest": {
    "source": "wayback",
    "date": "2001-04-09T06:38:41+00:00",
    "evidence": "archive_capture",
    "evidence_url": "https://web.archive.org/web/...",
    "note": "first HTTP 200 capture"
  },
  "results": [...]
}
```

`earliest` is `null` when nothing was found.

## Sources

**v1 has one source: the Wayback Machine** (via the CDX API). It returns the oldest
HTTP 200 capture for the URL.

URL variants are normalized before querying: scheme is added if missing, fragment and
common tracking parameters (`utm_*`, `fbclid`, `gclid`, `mc_cid`, `mc_eid`) are dropped.
The CDX index already collapses `http`/`https` and `www` variants.

Adding a source means writing one module in `earliest/sources/` and registering it in
`earliest/sources/__init__.py`. A second source will be added after v1 has been used on
real URLs.

## Known limitations

- **Trailing slash:** `https://example.com/post` and `https://example.com/post/` are
  separate CDX keys. A miss on one might succeed on the other. Not handled yet.
- **Status filter:** `statuscode:200` may push the reported date later than the absolute
  earliest capture (e.g. when the first snapshot was a redirect).
- **IA flakiness:** the CDX API returns 503 or times out during Internet Archive outages.
  The tool reports this as an error (exit 2) rather than "nothing found" (exit 1).

## Running tests

```
pytest -v
```

All tests mock HTTP; none touch the real network.

### Mutation testing

```
mutmut run
mutmut results
mutmut show <id>
```

To clear results and rerun from scratch:

```
rm -rf mutants/ mutmut-results.db && mutmut run
```

### Continuing the mutation triage

As of 2026-09-30, 27 mutants survive. The gaps found so far are documented in
`mutation_testing_notes.md`. The following mutants have not been examined and are
theorised to be trivial (error-message string wrapping, formatting, or equivalent
mutants) — but show them to Claude to confirm before closing them off:

```
mutmut show earliest.sources.wayback.xǁWaybackSourceǁfind_earliest__mutmut_32
mutmut show earliest.sources.wayback.xǁWaybackSourceǁfind_earliest__mutmut_37
mutmut show earliest.sources.wayback.xǁWaybackSourceǁfind_earliest__mutmut_42
mutmut show earliest.sources.wayback.xǁWaybackSourceǁfind_earliest__mutmut_47
mutmut show earliest.sources.wayback.xǁWaybackSourceǁfind_earliest__mutmut_52
mutmut show earliest.sources.wayback.xǁWaybackSourceǁfind_earliest__mutmut_57
mutmut show earliest.sources.wayback.xǁWaybackSourceǁfind_earliest__mutmut_69
mutmut show earliest.sources.wayback.xǁWaybackSourceǁfind_earliest__mutmut_85
mutmut show earliest.sources.wayback.xǁWaybackSourceǁfind_earliest__mutmut_91
mutmut show earliest.sources.wayback.xǁWaybackSourceǁfind_earliest__mutmut_92
mutmut show earliest.__main__.x_render_json__mutmut_18
mutmut show earliest.__main__.x_render_json__mutmut_23
mutmut show earliest.__main__.x_render_text__mutmut_9
mutmut show earliest.__main__.x_render_text__mutmut_19
mutmut show earliest.__main__.x_render_text__mutmut_23
mutmut show earliest.sources.wayback.x_normalize_url__mutmut_14
mutmut show earliest.sources.wayback.x_normalize_url__mutmut_15
```
