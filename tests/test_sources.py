from __future__ import annotations

import pytest

import earliest.sources as sources_pkg
from earliest.sources import REGISTRY as REAL_REGISTRY
from earliest.sources import select_sources


class Stub:
    def __init__(self, name, default):
        self.name = name
        self.default = default


@pytest.fixture
def registry(monkeypatch):
    """Swap in a registry with two default sources and one opt-in source."""
    reg = {
        "alpha": Stub("alpha", default=True),
        "beta": Stub("beta", default=True),
        "gamma": Stub("gamma", default=False),
    }
    # select_sources reads REGISTRY from its own module's globals
    monkeypatch.setattr(sources_pkg, "REGISTRY", reg)
    return reg


def names(selected):
    return [s.name for s in selected]


# --- defaults ----------------------------------------------------------------

def test_default_selects_only_default_sources(registry):
    assert names(select_sources(None, None, False)) == ["alpha", "beta"]


def test_all_includes_opt_in_sources(registry):
    assert names(select_sources(None, None, True)) == ["alpha", "beta", "gamma"]


def test_empty_only_list_behaves_like_no_only(registry):
    assert names(select_sources([], None, False)) == ["alpha", "beta"]


# --- --source ----------------------------------------------------------------

def test_only_selects_exactly_those_sources(registry):
    assert names(select_sources(["beta"], None, False)) == ["beta"]


def test_only_can_select_opt_in_source_without_all(registry):
    assert names(select_sources(["gamma"], None, False)) == ["gamma"]


def test_only_preserves_the_order_given(registry):
    assert names(select_sources(["beta", "alpha"], None, False)) == ["beta", "alpha"]


def test_unknown_source_raises_and_names_it(registry):
    with pytest.raises(ValueError, match="bogus"):
        select_sources(["alpha", "bogus"], None, False)


def test_multiple_unknown_sources_are_all_listed_sorted(registry):
    with pytest.raises(ValueError, match=r"nope, zzz"):
        select_sources(["zzz", "nope"], None, False)


# --- --exclude ---------------------------------------------------------------

def test_exclude_removes_a_default_source(registry):
    assert names(select_sources(None, ["alpha"], False)) == ["beta"]


def test_exclude_applies_on_top_of_all(registry):
    assert names(select_sources(None, ["beta"], True)) == ["alpha", "gamma"]


def test_excluding_everything_returns_empty_list(registry):
    assert select_sources(None, ["alpha", "beta"], False) == []


# --- current behavior worth knowing about ------------------------------------
# These pin down what the code does today. If you decide a different behavior
# is better, change the code and update the test deliberately.

def test_exclude_is_ignored_when_source_is_given(registry):
    assert names(select_sources(["alpha"], ["alpha"], False)) == ["alpha"]


def test_excluding_an_unknown_name_is_silently_ignored(registry):
    assert names(select_sources(None, ["bogus"], False)) == ["alpha", "beta"]


# --- the real registry -------------------------------------------------------

def test_real_registry_contains_wayback_as_default():
    assert "wayback" in REAL_REGISTRY
    assert REAL_REGISTRY["wayback"].default is True
    assert REAL_REGISTRY["wayback"].name == "wayback"


