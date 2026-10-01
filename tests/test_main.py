from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from earliest import __main__ as cli
from earliest.sources.base import Evidence, Finding, SourceResult


def make_finding(source="wayback", year=2019, evidence=Evidence.ARCHIVE_CAPTURE):
    return Finding(
        source=source,
        date=datetime(year, 3, 14, 9, 30, 15, tzinfo=timezone.utc),
        evidence=evidence,
        evidence_url=f"https://web.archive.org/web/{year}0314093015/https://example.com",
        note="first HTTP 200 capture",
    )


class FakeSource:
    default = True

    def __init__(self, name, finding=None, error=None):
        self.name = name
        self._result = SourceResult(name, finding, error)
        self.calls = []

    def find_earliest(self, url, *, timeout):
        self.calls.append((url, timeout))
        return self._result


@pytest.fixture
def use_sources(monkeypatch):
    """Replace source selection so tests never touch the real registry."""
    def _use(*sources):
        monkeypatch.setattr(
            cli, "select_sources", lambda only, exclude, include_all: list(sources)
        )
        return sources
    return _use


# --- earliest_finding --------------------------------------------------------

def test_earliest_finding_picks_minimum_date():
    results = [
        SourceResult("a", make_finding("a", year=2021)),
        SourceResult("b", make_finding("b", year=2018)),
        SourceResult("c", None),
        SourceResult("d", None, error="boom"),
    ]
    assert cli.earliest_finding(results).source == "b"


def test_earliest_finding_none_when_no_findings():
    results = [SourceResult("a", None), SourceResult("b", None, error="x")]
    assert cli.earliest_finding(results) is None


# --- exit codes --------------------------------------------------------------

def test_exit_0_when_date_found(use_sources):
    use_sources(FakeSource("wayback", make_finding()))
    assert cli.main(["https://example.com"]) == 0


def test_exit_1_when_nothing_found(use_sources):
    use_sources(FakeSource("wayback"))
    assert cli.main(["https://example.com"]) == 1


def test_exit_2_when_every_source_failed(use_sources):
    use_sources(FakeSource("wayback", error="timed out after 15s"))
    assert cli.main(["https://example.com"]) == 2


def test_exit_1_when_one_errored_and_one_found_nothing(use_sources):
    use_sources(FakeSource("a", error="boom"), FakeSource("b"))
    assert cli.main(["https://example.com"]) == 1


def test_exit_0_when_one_errored_but_another_found_date(use_sources):
    use_sources(FakeSource("a", error="boom"), FakeSource("b", make_finding("b")))
    assert cli.main(["https://example.com"]) == 0


def test_exit_2_for_unknown_source(capsys):
    # uses the real select_sources on purpose
    assert cli.main(["https://example.com", "--source", "bogus"]) == 2
    assert "Unknown source" in capsys.readouterr().err


def test_exit_2_when_no_sources_selected(use_sources, capsys):
    use_sources()  # empty
    assert cli.main(["https://example.com"]) == 2
    assert "no sources selected" in capsys.readouterr().err


# --- text output -------------------------------------------------------------

def test_text_output_uses_first_archived_wording(use_sources, capsys):
    use_sources(FakeSource("wayback", make_finding()))
    cli.main(["https://example.com"])
    out = capsys.readouterr().out

    assert "Earliest: 2019-03-14 (first archived, via wayback)" in out
    assert "verify: https://web.archive.org/web/20190314093015/" in out
    assert "published" not in out.lower()


def test_text_output_separates_error_from_nothing_found(use_sources, capsys):
    use_sources(FakeSource("a", error="timed out after 15s"), FakeSource("b"))
    cli.main(["https://example.com"])
    out = capsys.readouterr().out

    assert "Earliest: no date found" in out
    assert "a: ERROR - timed out after 15s" in out
    assert "b: nothing found" in out


# --- json output -------------------------------------------------------------

def test_json_output_structure(use_sources, capsys):
    use_sources(FakeSource("wayback", make_finding()), FakeSource("other", error="x"))
    cli.main(["https://example.com", "--json"])
    data = json.loads(capsys.readouterr().out)

    assert data["url"] == "https://example.com"
    assert data["earliest"]["source"] == "wayback"
    assert data["earliest"]["evidence"] == "archive_capture"
    assert data["earliest"]["date"].startswith("2019-03-14T09:30:15")
    assert data["earliest"]["evidence_url"] == (
        "https://web.archive.org/web/20190314093015/https://example.com"
    )
    assert data["earliest"]["note"] == "first HTTP 200 capture"
    assert [r["source"] for r in data["results"]] == ["wayback", "other"]
    assert data["results"][1]["error"] == "x"
    assert data["results"][1]["finding"] is None


def test_json_earliest_is_null_when_nothing_found(use_sources, capsys):
    use_sources(FakeSource("wayback"))
    cli.main(["https://example.com", "--json"])
    assert json.loads(capsys.readouterr().out)["earliest"] is None


# --- argument plumbing -------------------------------------------------------

def test_timeout_and_url_passed_to_sources(use_sources):
    (src,) = use_sources(FakeSource("wayback"))
    cli.main(["https://example.com/post", "--timeout", "3.5"])
    assert src.calls == [("https://example.com/post", 3.5)]


def test_default_timeout_is_15(use_sources):
    (src,) = use_sources(FakeSource("wayback"))
    cli.main(["https://example.com"])
    assert src.calls[0][1] == 15.0


def test_flags_forwarded_to_select_sources(monkeypatch):
    seen = {}

    def fake_select(only, exclude, include_all):
        seen.update(only=only, exclude=exclude, include_all=include_all)
        return [FakeSource("wayback")]

    monkeypatch.setattr(cli, "select_sources", fake_select)
    cli.main(["u", "--source", "a", "--source", "b", "--exclude", "c", "--all"])

    assert seen == {"only": ["a", "b"], "exclude": ["c"], "include_all": True}


