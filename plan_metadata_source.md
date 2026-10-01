# Plan: Page Metadata Source

Second source for `earliest`. Fetches the live page and extracts self-reported
publication dates. Evidence type: `PAGE_METADATA` — the closest thing to a true
publication date, but only as trustworthy as the page itself.

**Do not begin until this plan is approved.**

---

## Decisions needed before writing any code

These are open questions where I need your input:

1. **HTML parsing library.** Three options:
   - `html.parser` (stdlib) — no new dep, but fragile on messy HTML
   - `beautifulsoup4` with `html.parser` backend — clean API, one pure-Python dep, no binaries
   - `lxml` — fastest, but binary dep, harder to install on some platforms
   - **Recommendation: `beautifulsoup4` with `html.parser`**

2. **Date parsing for Python 3.10 compatibility.** `datetime.fromisoformat` in 3.10
   does not handle the `Z` suffix (`2023-01-15T10:30:00Z`), which is common in
   `article:published_time` values. Two options:
   - Handle `Z` → `+00:00` substitution manually (one line, no new dep)
   - Add `python-dateutil` as a runtime dep (handles all ISO 8601 variants)
   - **Recommendation: manual Z substitution** — keeps deps minimal

3. **Which signals to support in v1.** In priority order:
   - `<meta property="article:published_time">` (Open Graph, most reliable)
   - `<meta property="og:published_time">` (alternative OG property)
   - JSON-LD `datePublished` (used by many CMS/blogs, e.g. WordPress)
   - `<time datetime="...">` (fallback, common in article markup)
   - **Recommendation: all four in v1** — they're all simple to extract and
     collectively cover most publishing platforms

4. **`default = True` or `False`?** This source makes a live HTTP request to
   the target URL, which is a side effect the user might not always want.
   - `True`: included in every run by default, makes the tool more useful immediately
   - `False`: opt-in with `--source metadata`, safer/quieter default
   - **Recommendation: `True`** — the tool exists to find dates; this is the
     best source for that

5. **Fetch the live URL or an IA snapshot?** The live page reflects its current
   state; an IA snapshot reflects a historical state but requires knowing which
   snapshot to fetch.
   - **Recommendation: live URL for v1** — simpler, and page metadata on static
     blog posts is stable. Revisit if a use-case appears where the live page has
     been edited.

---

## TDD steps (do not execute yet)

### Step 1 — write `tests/test_metadata.py` (all tests failing)

Tests to write, in this order:

**Date parsing helper**
- `test_parse_date_iso_with_offset` — `2023-01-15T10:30:00+05:00` → UTC datetime
- `test_parse_date_iso_with_z` — `2023-01-15T10:30:00Z` → UTC datetime (the 3.10 edge case)
- `test_parse_date_only` — `2023-01-15` → UTC midnight datetime
- `test_parse_date_invalid` — garbage string → returns None, does not raise

**Signal extraction (mock the HTTP call; pass raw HTML)**
- `test_finds_article_published_time` — `<meta property="article:published_time" content="...">`
- `test_finds_og_published_time` — `<meta property="og:published_time" content="...">`
- `test_finds_json_ld_date_published` — `<script type="application/ld+json">{"datePublished": "..."}</script>`
- `test_finds_time_element` — `<time datetime="2023-01-15">...`
- `test_prefers_earliest_when_signals_disagree` — multiple signals with different dates → pick earliest
- `test_nothing_found_when_no_metadata` — valid HTML, no date signals → finding=None, error=None

**Error handling**
- `test_timeout_is_error`
- `test_http_error_status_is_error` (parametrize: 404, 429, 500)
- `test_network_error_is_error`

**Integration (matches test_wayback.py style)**
- `test_found_returns_finding` — check source name, date, evidence type, evidence_url is the page URL
- `test_evidence_type_is_page_metadata` — assert `f.evidence is Evidence.PAGE_METADATA`
- `test_date_is_timezone_aware`
- `test_timeout_forwarded_to_httpx`
- `test_request_uses_given_url`

### Step 2 — implement `earliest/sources/metadata.py`

- `parse_date(s: str) -> datetime | None` module-level helper
- `MetadataSource` class: `name = "metadata"`, `default = True`
- `find_earliest(url, *, timeout) -> SourceResult`
  - `httpx.get(url, timeout=timeout, follow_redirects=True)`
  - Extract all signals, parse each date, pick the earliest valid one
  - `evidence_url` = the page URL itself (so it can be verified)
  - `note` = which signal it came from (e.g. `"article:published_time"`)
  - Never raise; return `SourceResult(error=...)` for all failure modes

### Step 3 — register in `earliest/sources/__init__.py`

Add `MetadataSource()` to the registry list alongside `WaybackSource()`. Order
determines default display order in output: Wayback first, then metadata.

### Step 4 — verify with a real URL

Run both sources against a known old post and check:
- Do the dates agree? If they disagree by more than a few days, flag it.
- Does the `/earliest` slash command output correctly say "first archived" vs
  "page claims published" for the two sources?

### Step 5 — update docs

- `CLAUDE.md` status section
- `earliest_claude_code_prompt.md` current state and known limitations
- Remove the metadata source from "Planned future sources" and "do not build yet"

---

## What this does NOT include

- Fetching IA snapshot HTML (deferred)
- `Last-Modified` HTTP header source (separate, weaker source)
- Sitemap/RSS date source (separate)
- Concurrent source execution (deferred until there are several sources)
- Any change to how the overall earliest date is computed — min across all
  findings still applies for now, per the known limitation in the design doc

---

## Open question to surface when real usage hits it

Once both sources exist, archive date and page metadata date mean different things.
The design doc already flags that `min` across evidence types may eventually need
to be replaced with separate reporting. Watch for cases where the two disagree
significantly — that's the signal to revisit.
