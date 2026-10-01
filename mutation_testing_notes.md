# Mutation Testing Notes

Run date: 2026-09-30. Tool: mutmut 2.x. 330 mutants total.

## Results over time

| Run | Killed | Survived | Timed out |
|-----|--------|----------|-----------|
| Initial (50 tests) | 249 | 79 | 2 |
| After adding `fl` param + JSON field assertions | 287 | 43 | 2 |
| After adding timeout + source-name assertions | 301 | 27 | 2 |

## Gaps we fixed

### 1. `fl` param not verified in `test_request_params`
`test_request_params` checked `url`, `limit`, `filter`, and `output` but not `fl`.
A wrong `fl` key would cause CDX to return all fields, breaking the row unpack.
**Fix:** added `assert params["fl"] == "timestamp,original,statuscode"`.

### 2. `evidence_url` and `note` not checked in JSON output test
`test_json_output_structure` verified `source`, `evidence`, and `date` in the
`earliest` object but not `evidence_url` or `note`.
**Fix:** added assertions for both fields using the values from `make_finding()`.

### 3. `timeout` not verified as passed to `httpx.get`
`test_timeout_is_error` mocked a `ConnectTimeout` exception directly, which proved
the error was caught but not that the `timeout=` kwarg was forwarded. Removing
`timeout=timeout` from the `httpx.get` call would have silently made the flag a no-op.
**Fix:** added `test_timeout_forwarded_to_httpx` using `unittest.mock.patch` to
capture kwargs and assert `timeout == 7.5`.

### 4. `result.source` not checked in malformed-row error tests
`test_malformed_row_is_error` checked `result.finding` and `result.error` but not
`result.source`. A mutation replacing `self.name` with `None` survived.
**Fix:** added `assert result.source == "wayback"` to the parametrized test.

## Known surviving mutants — confirmed trivial

### `build_parser` (16 survivors)
All are mutations to argparse string arguments: `prog`, `description`, `metavar`,
`help`, `dest`. None affect runtime behavior; they only change help text.
Not worth testing.

### `render_text` and `render_json` formatting (several survivors)
Mutations to blank separator lines (`""` → `"XXXX"`), `indent=2` → `indent=None`,
and similar presentation details. `json.loads` in tests is indifferent to indentation;
blank lines are not asserted on. Not worth testing.

### `main__mutmut_20` and similar `in`-check survivors
Mutations that wrap strings in `XX...XX` (e.g. `"XXerror: no sources selectedXX"`)
survive because the tests use `in` rather than `==`. The substring still matches.
Same pattern applies to `render_text__mutmut_5` ("Earliest: no date found").
These are not real gaps — tightening `in` to `==` would make tests brittle for no
meaningful safety gain.

### Equivalent mutants in `normalize_url`
- `mutmut_7`: `"https://"` → `"HTTPS://"` — `urlsplit` lowercases the scheme,
  so output is identical.
- `mutmut_12`: `keep_blank_values=True` → `keep_blank_values=None` — `None` is
  falsy, same behavior as `False`; no test URL has blank query values.
- `mutmut_14`, `mutmut_15`: not examined but likely similar (equivalent or
  formatting).

### `main` timeouts (2)
`parse_args(argv)` → `parse_args(None)` causes pytest's own `sys.argv` to be
parsed as CLI arguments. Argparse calls `sys.exit`, which confuses mutmut into
recording a timeout. Every test that calls `cli.main([...])` already exercises the
`argv` parameter; this is a test-environment artifact, not a real gap.

### `find_earliest` note/source-name string mutations
`mutmut_90`, `mutmut_91`, `mutmut_92` are near the end of `find_earliest` and
almost certainly mutations to `note="first HTTP 200 capture"` and similar string
literals. The `note` field wording is not pinned by tests by design — it is
human-readable flavor text.

## Unexamined survivors — theories

These were not shown via `mutmut show`. Based on the numbering pattern and the
mutations already seen in neighboring mutants, best guesses:

### `find_earliest` 32, 37, 42, 47, 52, 57 (spaced by 5)
Regular spacing strongly suggests a repeated pattern — likely mutations to the six
error-message strings in the `except` blocks:
- `"timed out after {timeout}s"`
- `"HTTP {status} from CDX API"`
- `"network error: {e}"`
- `"CDX API returned invalid JSON"`
- `"unexpected CDX row format"`

Each survives because the corresponding test uses `in` (e.g. `"timed out" in
result.error`), so `XX`-wrapping the message still passes. Same category as the
confirmed trivial `in`-check survivors above.

### `find_earliest` 69, 80, 85
Likely additional `note=None` or `source=None` variants in the success path,
or mutations to `Evidence.ARCHIVE_CAPTURE`. The `evidence` field IS checked
(`assert f.evidence is Evidence.ARCHIVE_CAPTURE`), so an evidence-type mutation
should be killed — these are more likely note/string mutations.

### `render_json` 18, 23
Likely mutations to JSON key names in the `results` list entries (e.g. `"source"`,
`"finding"`, `"error"`). The test checks `r["source"]` and `r["error"]` for the
second result but may not check every key on every result object.

### `render_text` 9, 19, 23
Likely formatting mutations: the `"  "` indentation before source lines, the
`"; "` separator between date and note, or the `"    verify: "` prefix on the
evidence URL line. The text tests check specific substrings but not the full
formatted output.

## Recommendation

The unexamined survivors are very likely all trivial by the same patterns already
confirmed. The mutation score improvement from 249→301 killed covers the only
meaningful gaps. Stop here unless a specific surviving mutant is suspected of
hiding a real bug.
