"""Every collector, against recorded responses, with no network.

This is the test that keeps the project maintainable. A collector that only works
against the live internet cannot be changed with any confidence: you cannot tell a code
regression from an upstream outage, and CI fails for reasons nobody controls.
"""

import os

import pytest

from tgx_outputs import config as _cfg
from tgx_outputs import config as cfg
from tgx_outputs import guards
from tgx_outputs.collect import COLLECTORS
from tgx_outputs.collect.base import run_one
from tgx_outputs.http import HttpClient

# Disabled collectors have no fixtures by design: `tgx collect --record` skips them.
OFFLINE = sorted(n for n in COLLECTORS if _cfg.collector_enabled(n))


@pytest.fixture(scope="module")
def http():
    with HttpClient(mode="replay") as client:
        yield client


@pytest.mark.parametrize("name", OFFLINE)
def test_collector_runs_and_produces_defined_metrics(name, http):
    env = run_one(COLLECTORS[name], http)
    assert env.status in {"ok", "degraded"}, f"{name} failed: {env.errors[:2]}"
    if name == "github" and not env.records and cfg.project_field("repos"):
        has_token = bool(os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN"))
        assert has_token, (
            "config has GitHub repositories but no GITHUB_TOKEN (or GH_TOKEN) is set "
            "in the environment -- fixtures cannot be recorded without one; see "
            "CONTRIBUTING.md")
    assert env.records, f"{name} produced no records"

    semantics = cfg.semantics()
    for rec in env.records:
        assert rec.metric in semantics, (
            f"{name} emits {rec.metric!r}, which has no entry in metrics.csv")


@pytest.mark.parametrize("name", OFFLINE)
def test_collector_output_survives_the_guards(name, http):
    """Whatever a collector emits must be publishable, or explain why it is not."""
    env = run_one(COLLECTORS[name], http)
    promoted, dropped = guards.check_records(env, cfg.semantics(), {})
    # A little quarantine is legitimate -- upstream genuinely ships the odd future
    # period -- but a collector that mostly produces unusable records is a bug.
    assert len(promoted) >= len(env.records) * 0.9, (
        f"{name}: {len(dropped)} of {len(env.records)} records quarantined: {dropped[:3]}")


def test_no_collector_reaches_the_network_in_replay_mode(http):
    """The offline guarantee, asserted rather than assumed."""
    assert http.mode == "replay"
    assert http._client is None, "replay mode must never open a real HTTP client"


def test_download_windows_are_never_mixed(http):
    """The bug this split fixes: a 30-day figure published as a lifetime total.

    npm and PyPI publish no lifetime counter, so ecosyste.ms answers with a rolling
    window and says so in `downloads_period`. Filing that under the all-time metric put
    "downloads, all time" under a number that was last month's, and let the project
    table add it to a genuine lifetime total.
    """
    env = run_one(COLLECTORS["ecosystems"], http)
    windows = {"package_downloads_total": "total",
               "package_downloads_recent": "last-month"}
    seen = set()
    for rec in env.records:
        if rec.metric not in windows:
            continue
        assert rec.extra["period_label"] == windows[rec.metric], (
            f"{rec.entity} reports {rec.extra['period_label']!r} but was filed under "
            f"{rec.metric}")
        assert rec.entity not in seen, f"{rec.entity} filed under two windows"
        seen.add(rec.entity)
    assert seen, "no package reported downloads at all"


def test_a_rolling_window_is_not_declared_cumulative():
    """`monotonic` guards cumulative metrics, and a rolling window legitimately falls.

    Declaring it cumulative means a quiet month is quarantined as a counter running
    backwards, and the tile silently reads "not collected" with nothing wrong upstream.
    """
    assert cfg.semantics()["package_downloads_recent"]["cumulative"] is False
    assert cfg.semantics()["package_downloads_total"]["cumulative"] is True


def test_citations_asks_in_batches_not_once_per_doi(http):
    """The failure of 2026-08-26: twenty-five requests, five of them 429s.

    OpenAlex takes an OR filter, so every DOI fits in one request. Going back to a
    request per DOI would not fail a build -- it would quietly lose whichever papers
    happened to be throttled that morning, which reads on the page as a tool losing
    citations overnight.
    """
    env = run_one(COLLECTORS["citations"], http)
    papers = cfg.project_field("papers")
    assert len(papers) > 10, "this test is only meaningful with a real paper list"
    assert len(env.calls) <= (len(papers) // 20) + 1, (
        f"{len(env.calls)} calls for {len(papers)} DOIs: the batch filter is not being used")
    # and every paper OpenAlex knows about still gets its own record. A DOI it does not
    # index yields none by necessity -- Figshare and Zenodo deposits routinely are not
    # indexed -- but the collector has to say so out loud. That is the whole difference
    # between a disclosed gap and a quietly smaller number, which is the same failure
    # this test was written to catch.
    from tgx_outputs.collect.citations import _bare

    tracked = {_bare(doi) for _project, doi in papers} - cfg.excluded_dois()
    by_doi = {r.entity for r in env.records if r.metric == "paper_citations_by_doi"}
    assert by_doi <= tracked, f"records for DOIs nothing tracks: {by_doi - tracked}"
    unindexed = tracked - by_doi
    if unindexed:
        assert any("no record" in err for err in env.errors), (
            f"{len(unindexed)} DOI(s) produced no record and the collector said nothing: "
            f"{sorted(unindexed)}")


def test_citations_identifies_a_doi_however_it_is_written():
    """OpenAlex answers with a full https://doi.org/ URL; the tables hold bare DOIs.

    Matching the response back to what was asked for is what decides whether a paper
    counts or is reported as unresolved, so the two forms have to compare equal.
    """
    from tgx_outputs.collect.citations import _bare

    assert _bare("https://doi.org/10.1021/CI025584Y") == "10.1021/ci025584y"
    assert _bare("doi:10.1021/ci025584y") == "10.1021/ci025584y"
    assert _bare("  10.1021/ci025584y ") == "10.1021/ci025584y"


def test_a_moved_repo_is_reported_rather_than_silently_followed(tmp_path, monkeypatch):
    """The pybacting bug, in the one place code could have caught it.

    GitHub serves a renamed or transferred repository under its new name and never
    errors, so a config row naming the old path keeps collecting and every check stays
    green -- which is exactly how one project spent a year reading a fork.
    """
    from tgx_outputs import config as cfg
    from tgx_outputs.collect.github_graphql import GitHub

    for name, cols in cfg.COLUMNS.items():
        (tmp_path / name).write_text(",".join(cols) + "\n")
    (tmp_path / "projects.csv").write_text(
        "id,name,what,mark,logo\np,P,A sentence.,P,\n")
    (tmp_path / "identifiers.csv").write_text(
        "project,kind,value,note\np,repo,olduser/thing,\n")
    monkeypatch.setattr(cfg, "CONFIG_DIR", tmp_path)
    for fn in (cfg.projects, cfg.exclusions, cfg.corrections):
        fn.cache_clear()
    monkeypatch.setenv("GITHUB_TOKEN", "x")

    node = {"nameWithOwner": "neworg/thing", "pushedAt": "2026-01-01T00:00:00Z",
            "isArchived": False, "releases": {"nodes": []}, "refs": {"nodes": []}}

    class Http:
        mode = "live"
        def post_json(self, *a, **k):
            return {"data": {"r0": node}}

    env = GitHub(Http()).collect()
    for fn in (cfg.projects, cfg.exclusions, cfg.corrections):
        fn.cache_clear()

    assert env.status == "degraded"
    assert any("moved" in e and "neworg/thing" in e for e in env.errors), env.errors
