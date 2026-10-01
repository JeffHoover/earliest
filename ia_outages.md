# Internet Archive Reliability Notes

Relevant to `earliest` because the Wayback CDX API is the only v1 source.

## Ethical posture

The CDX API is a public, documented API that IA explicitly offers for programmatic
use. A single-user tool making one request per invocation is well within intended
use and far below the 60 req/min limit.

IA is a nonprofit under real financial and infrastructure pressure. The flakiness
we've seen is partly caused by others abusing their services. Being a well-behaved
client matters: honor 429s, don't retry aggressively. The current code already
does this — it makes one request and reports errors honestly rather than retrying.

If `earliest` is ever used in a batch loop over many URLs, add deliberate rate
limiting. That's a future problem; for single-user interactive use it's not a
concern.

Note: IA's `robots.txt` applies to web crawling, not the CDX API. If a future
page-metadata source fetches pages from IA snapshot URLs rather than the live web,
revisit this.

## What we've observed

| Date | Error | Likely cause |
|------|-------|--------------|
| 2026-09-30 | HTTP 503 | IA bot-protection / infrastructure |
| 2026-09-30 | Timeout (15s) | IA infrastructure instability |
| 2026-10-01 | HTTP 429 | IA bot-detection (rate limit) |
| 2026-10-01 | HTTP 503 | IA infrastructure instability |
| 2026-10-01 | Timeout (15s) | IA infrastructure instability |

All are correctly caught and reported as exit 2 errors. None indicate a bug in `earliest`.

## Known 2026 outage history

- **July 19, 2026**: intermittent outage, reports surging around 00:27 UTC
- **August 16–17, 2026**: ~4-hour infrastructure outage, 21:00–01:00 UTC
- **August 21, 2026**: intermittent outage, reports surging around 14:07 ET
- **September 2026 onward**: ongoing instability from bot-traffic protective measures

## Why IA is flaky

IA has been under heavy automated traffic throughout 2026, attributed to AI
scraping and model training. They have deployed bot-detection that, by their own
acknowledgement, occasionally blocks legitimate users by mistake. The 503s and
timeouts we see are from that protective layer, not from their core infrastructure
being down.

Source: [An Update on Wayback Machine Access (2026-09-15)](https://blog.archive.org/2026/09/15/an-update-on-wayback-machine-access/)

## CDX API rate limits

- Limit: **60 requests per minute**
- Exceeding it: HTTP 429
- Ignoring 429s for >1 minute: IP blocked at firewall for 1 hour
- Each subsequent violation doubles the block duration

Under normal single-user usage of `earliest` (one request per invocation), the
rate limit should not be triggered. A 429 likely means IA's bot-detection
flagged the request, not that we genuinely exceeded 60 req/min.

## Status monitoring

There is no reliable IA status page. `status.archive.org` redirects to
`archive.org` and is not a status dashboard. Their Bluesky, Mastodon, and
Twitter/X accounts are the stated channels for outage announcements but are not
always updated promptly.

Third-party monitors:
- https://uptimerobot.com/is-it-down/internet-archive-wayback-machine/
- https://outagehq.com/service/archive-org
- https://isitdownchecker.com/check/archive.org

## Implications for `earliest`

**Nothing to fix now.** Error handling already distinguishes 429, 503, and
timeout correctly. If IA flakiness becomes frequent enough to matter in practice,
the right fix is a single retry with backoff on 429/503 — but that is premature
for a single-user tool making one request per invocation.

If a second source is added, IA errors will degrade more gracefully: one source
errors, another may still return a result, exit code 0 or 1 instead of always 2.
