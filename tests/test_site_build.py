"""The render gate and the freshness rules."""

import datetime as dt
import json

import pytest

from tgx_outputs import config as cfg
from tgx_outputs.derive import freshness
from tgx_outputs.site import build


def _snapshot(age_days: float, status: str = "ok", records=None):
    when = dt.datetime.now(dt.UTC) - dt.timedelta(days=age_days)
    if records is None:
        records = [{"metric": "releases_by_year", "entity": "bridgedb",
                    "value": 12.0, "period": "2026"}]
    return {
        "collected_on": when.date().isoformat(),
        "sources": {"github": {"status": status, "fetched_at": when.isoformat(),
                               "record_count": len(records), "records": records}},
    }


def test_a_chart_without_a_definition_refuses_to_render(monkeypatch):
    """The render gate: no number appears unless the page can say what it counts."""
    monkeypatch.setattr(cfg, "semantics", dict)
    monkeypatch.setattr(build.cfg, "semantics", dict)
    monkeypatch.setattr(build, "CHARTS", {"releases_by_year": (dict, "releases_by_year")})
    fresh = freshness.assess(_snapshot(0))
    with pytest.raises(build.MissingDefinition):
        build.figure("releases_by_year", _snapshot(0), fresh)


def test_unknown_chart_name_is_an_error_not_a_blank():
    with pytest.raises(build.MissingDefinition):
        build.figure("no_such_chart", _snapshot(0), freshness.assess(_snapshot(0)))


def test_figure_caption_carries_source_date_and_csv_link():
    snap = _snapshot(0)
    html = build.figure("releases_by_year", snap, freshness.assess(snap))
    assert "Source: `github`" in html
    assert "collected " in html
    assert "download CSV](data/releases_by_year.csv)" in html
    assert cfg.semantics()["releases_by_year"]["counts"][:40] in html


def test_every_metric_still_declares_what_it_does_not_mean():
    """The caveat is no longer rendered anywhere, which is a presentation choice.

    It is not an excuse to stop writing one. Every metric must still declare what its
    number does not mean, and that declaration ships in config/metrics.csv, which the
    site offers for download -- so the discipline survives even though the sentence is
    not printed under the chart any more.
    """
    published = (cfg.CONFIG_DIR / "metrics.csv").read_text()
    for name, spec in cfg.semantics().items():
        caveat = spec["caveat"].strip()
        assert caveat, f"{name} has no caveat"
        assert caveat in published, f"{name}'s caveat is not in the published table"


def test_freshness_is_computed_from_the_data_not_the_clock():
    assert freshness.assess(_snapshot(0))["level"] == "fresh"
    assert freshness.assess(_snapshot(20))["level"] == "amber"    # > 2x a 7-day cadence
    assert freshness.assess(_snapshot(60))["level"] == "red"      # > 5x


def test_a_degraded_source_is_current_but_never_reported_as_complete():
    """Degraded says the answer was partial, not that it was old.

    These were one signal until a Figshare DOI that OpenAlex will never index made the
    banner say "needs attention, 0d" -- a permanent warning about data gathered seconds
    earlier. Age and completeness are now asked separately, and a source that answered
    on time but short is current *and* incomplete.
    """
    fresh = freshness.assess(_snapshot(0, status="degraded"))
    assert fresh["level"] == "fresh"
    assert fresh["sources"][0]["complete"] is False
    assert [r["source"] for r in fresh["incomplete"]] == ["github"]
    assert "incomplete" in fresh["summary"]
    assert "needs attention" not in fresh["summary"]

    # A failure is still red whatever the clock says: the records on the page are then
    # whatever the last good run left behind, and their real age is unknown.
    assert freshness.assess(_snapshot(0, status="failed"))["level"] == "red"


def test_an_incomplete_source_reports_the_fraction_it_managed():
    snap = _snapshot(0, status="degraded")
    snap["sources"]["github"].update(expected=33, found=32, unit="papers")
    summary = freshness.assess(snap)["summary"]
    assert "32 of 33 papers found" in summary


def test_a_complete_and_current_run_says_so_plainly():
    fresh = freshness.assess(_snapshot(0))
    assert fresh["incomplete"] == []
    assert "needs attention" not in fresh["summary"]
    assert "incomplete" not in fresh["summary"]


def test_stale_sources_are_named_in_the_summary():
    summary = freshness.assess(_snapshot(60))["summary"]
    assert "needs attention" in summary and "github" in summary


def _snapshot_with(records, status="ok"):
    import datetime as _dt
    now = _dt.datetime.now(_dt.UTC)
    return {
        "collected_on": now.date().isoformat(),
        "sources": {"wikipathways": {"status": status, "fetched_at": now.isoformat(),
                                     "record_count": len(records), "records": records}},
    }


def test_a_failed_source_reads_as_missing_not_as_zero():
    """The failure that matters: a dead source rendering a confident 0.

    Summing the records of a source that returned nothing gives 0.0, and a tile then
    states "0 pathways" as fact. Missing must read as missing.
    """
    empty = _snapshot_with([], status="failed")
    assert build._value(empty, "rsd_mentions") is None

    html = build._cards(empty)
    assert build.MISSING in html
    # the failure mode: a dead source rendering a confident zero
    assert ">0<" not in html


def test_a_collected_zero_is_still_shown_as_zero():
    """The converse: a real measurement of zero must not be hidden."""
    snap = _snapshot_with([{"metric": "rsd_mentions", "entity": "Some Tool",
                            "value": 0.0}])
    assert build._value(snap, "rsd_mentions") == 0.0


def test_a_figure_with_no_data_is_replaced_by_an_explanation():
    empty = _snapshot_with([], status="failed")
    html = build.figure("releases_by_year", empty, freshness.assess(empty))
    assert build.MISSING in html
    assert "tgx-chart" not in html, "an empty chart must not be drawn"
    assert "collection status" in html


def test_retiring_a_metric_removes_its_csv(tmp_path):
    """A stale CSV is a number that stopped being collected with nothing to say so."""
    from tgx_outputs.derive import tables

    (tmp_path / "old_metric.csv").write_text("metric,entity,period,value\n")
    snap = _snapshot(0)
    tables.write_long(snap, tmp_path)
    assert not (tmp_path / "old_metric.csv").exists()
    assert (tmp_path / "releases_by_year.csv").exists()


def test_retiring_a_collector_removes_it_from_todays_snapshot(tmp_path, monkeypatch):
    """The counterpart to retiring a metric: the source itself has to go too.

    A partial run merges into today's snapshot, so a deleted collector would otherwise
    keep its last records -- and its row in the freshness strip -- until midnight.
    """
    from tgx_outputs import store
    from tgx_outputs.model import Envelope

    monkeypatch.setattr(store, "DATA_DIR", tmp_path)
    stamp = store._today()
    (tmp_path / "snapshots").mkdir()
    (tmp_path / "snapshots" / f"{stamp}.json").write_text(json.dumps({
        "collected_on": stamp,
        "sources": {"retired_source": {"status": "ok", "fetched_at": stamp,
                                       "record_count": 1, "records": [{}]}},
    }))

    env = Envelope(source="github")
    store.write_run({"github": env}, {}, {"github": []})

    snap = json.loads((tmp_path / "snapshots" / f"{stamp}.json").read_text())
    assert "retired_source" not in snap["sources"]
    assert "github" in snap["sources"]


def test_every_overview_card_carries_an_icon():
    """A mistyped glyph key renders nothing at all, which is invisible in review."""
    html = build._cards(_snapshot_with([]))
    assert html.count('class="tgx-card"') == 9
    assert html.count('class="tgx-icon"') == html.count('class="tgx-card"')


def test_icons_are_self_contained_markup():
    from tgx_outputs.site import icons

    for name in icons._ICONS:
        markup = icons.svg(name)
        assert markup.startswith("<svg") and markup.endswith("</svg>")
        # No external reference of any kind: the page must render with no network.
        assert "http" not in markup and "url(" not in markup
    assert icons.svg("no-such-icon") == ""


def test_endpoint_patterns_collapse_repeated_shapes():
    """Nineteen calls to one endpoint are one row marked x19, not nineteen rows."""
    from tgx_outputs.site.flow import endpoint_patterns

    same = ["https://api.github.com/graphql (a/b)"] * 19
    assert endpoint_patterns(same) == [("api.github.com/graphql", 19)]

    varied = [
        "https://packages.ecosyste.ms/api/v1/registries/npmjs.org/packages/bridgedb",
        "https://packages.ecosyste.ms/api/v1/registries/pypi.org/packages/pybacting",
    ]
    pattern, count = endpoint_patterns(varied)[0]
    assert count == 2
    assert pattern == "packages.ecosyste.ms/api/v1/registries/…/packages/…"
    assert "bridgedb" not in pattern, "a varying segment must not leak one call's value"


def test_every_request_that_was_made_is_listed(monkeypatch):
    """The explainability promise: every URL asked for is on the page, in full."""
    manifest = {"sources": {"github": {
        "status": "ok", "fetched_at": "2026-08-25T00:00:00+00:00", "record_count": 2,
        "calls": [
            {"url": "https://api.github.com/graphql (bridgedb/BridgeDb)",
             "status": 200, "ok": True, "note": "pushed 2026-08-02"},
            {"url": "https://api.github.com/graphql (cdk/cdk)",
             "status": 200, "ok": True, "note": "pushed 2026-08-18"},
        ],
        "errors": [], "quarantined": []}}}
    monkeypatch.setattr(build, "_latest_manifest", lambda: manifest)

    snap = _snapshot(0)
    snap["sources"] = {"github": {"status": "ok", "fetched_at": "2026-08-25T00:00:00+00:00",
                                  "record_count": 2, "records": [
                                      {"metric": "releases_by_year", "entity": "cdk",
                                       "value": 1.0, "period": "2026"}]}}
    html = build._sources(cfg.semantics(), snap)

    for call in manifest["sources"]["github"]["calls"]:
        assert call["url"] in html, "a call was made and not published"
    assert "releases_by_year" in html, "the metrics a source produced must be shown"
    assert "tgx-flow" in html


def test_a_disabled_source_with_nothing_to_say_is_left_out(monkeypatch):
    """A collector that is off and publishes nothing has no section to fill.

    Whether it exists and is switched off is a question about the configuration, and
    the collection status table answers it. A section saying only "made no requests"
    was noise between the sources that did.
    """
    monkeypatch.setattr(build, "_latest_manifest", lambda: {"sources": {"wikipathways": {
        "status": "skipped", "fetched_at": "2026-08-25T00:00:00+00:00",
        "record_count": 0, "calls": [], "errors": [], "quarantined": []}}})
    html = build._sources(cfg.semantics(), _snapshot(0))
    assert "wikipathways" not in html
    assert "tgx-flow" not in html, "nothing to draw when nothing was requested"


def test_every_project_gets_a_tile_even_with_nothing_collected():
    """A project with no measurable output still belongs on the page.

    It is in projects.csv because the department builds it. Dropping it from the
    grid when a collector returns nothing would quietly shorten the inventory, and
    the shortened list is the thing people would quote.
    """
    from tgx_outputs import config as _cfg

    html = build._project_tiles(_snapshot_with([]))
    assert html.count('class="tgx-project"') == len(_cfg.projects())
    for proj in _cfg.projects():
        assert proj["name"] in html


def test_a_tile_omits_a_figure_rather_than_printing_zero():
    """The missing-vs-zero rule, on the tiles this time.

    A tile builds itself from the records that exist, so an absent measurement has
    to leave no statistic behind -- never a confident 0 next to a real label.
    """
    html = build._project_tiles(_snapshot_with([]))
    assert "citations ·" not in html
    assert "tgx-stat-value" not in html
    assert "nothing measurable" in html


def test_a_tile_labels_each_download_with_its_own_window():
    """Two registries, two windows, and the tile must never merge them."""
    snap = _snapshot_with([
        {"metric": "package_downloads_total", "entity": "bioconductor.org/BridgeDbR",
         "value": 29390.0, "extra": {"project": "bridgedb", "registry": "bioconductor.org"}},
        {"metric": "package_downloads_recent", "entity": "npmjs.org/bridgedb",
         "value": 234.0, "extra": {"project": "bridgedb", "registry": "npmjs.org"}},
    ])
    html = build._project_tiles(snap)
    assert "Bioconductor downloads · all time" in html
    assert "npm downloads · last 30 days" in html
    assert "29,624" not in html, "two windows were added together"


def test_a_tile_mark_prefers_the_configured_one():
    """Initials derived from a name are wrong often enough to need an override.

    molAOP Builder and Analyser derives to "MAOPBA"; R-ODAF derives from a name with
    no useful capitals at all.
    """
    assert build._mark({"id": "molaop", "name": "molAOP Builder and Analyser",
                        "mark": "MA"}) == "MA"
    # Falls back rather than failing, so a project added without the field still
    # renders something -- just not always what a person would have picked.
    assert build._mark({"id": "r-odaf", "name": "R-ODAF"}) == "ROD"
    assert build._mark({"id": "bacting", "name": "Bacting"}) == "BA"
