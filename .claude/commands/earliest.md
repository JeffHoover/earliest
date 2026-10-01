---
description: Find the earliest publication evidence for a URL
argument-hint: <url> [--source NAME]... [--exclude NAME]... [--all] [--json]
allowed-tools: Bash(python -m earliest:*)
---

Run this and report the result:

`python -m earliest $ARGUMENTS`

Then summarize for me:

1. The earliest date found, and which source and evidence type it came from.
2. Every other finding, one line each (source, date, evidence type).
3. Any source that errored, listed separately from sources that found nothing.

Rules:

- Archive captures are upper bounds, not publication dates. Say "first
  archived" for those, never "published."
- If page-metadata and archive dates disagree by more than a few days,
  point that out.
- If no date was found, say so plainly. Do not guess or estimate.
- Do not fetch or search the web yourself. Use only the script's output.
