"""Config invariants that a reviewer cannot be expected to hold in their head."""

import pytest

from tgx_outputs import config as cfg
from tgx_outputs.collect import COLLECTORS
from tgx_outputs.site.charts import CHARTS

REQUIRED = {"label", "counts", "source", "cumulative", "granularity", "caveat"}


def test_every_metric_is_fully_defined():
    for name, spec in cfg.semantics().items():
        assert REQUIRED <= set(spec), f"{name} is missing {sorted(REQUIRED - set(spec))}"
        assert spec["caveat"].strip(), f"{name} has an empty caveat"


def test_cumulative_metrics_declare_no_granularity():
    """A level cannot belong to a period. Enforced in config, not only at runtime."""
    for name, spec in cfg.semantics().items():
        if spec["cumulative"]:
            assert spec["granularity"] == "none", (
                f"{name} is cumulative but declares granularity {spec['granularity']!r}")


def test_every_chart_renders_a_defined_metric():
    semantics = cfg.semantics()
    for chart, (_builder, metric) in CHARTS.items():
        assert metric in semantics, f"chart {chart!r} renders undefined metric {metric!r}"


def test_every_collector_is_configured_and_vice_versa():
    configured = set(cfg.sources().get("collectors", {}))
    assert configured == set(COLLECTORS), (
        f"configured but missing: {sorted(configured - set(COLLECTORS))}; "
        f"implemented but unconfigured: {sorted(set(COLLECTORS) - configured)}")


def test_exclusions_always_carry_a_reason():
    for kind, entries in cfg.exclusions().items():
        for entry in entries or []:
            assert entry.get("reason"), f"{kind}: {entry} has no reason"


def test_no_config_file_names_a_person():
    """The privacy promise, as a test rather than a paragraph in a README.

    Every target is a repository, package, image, endpoint or DOI. Nothing here is
    queried by person, so an ORCID appearing in config would be a change of scope
    rather than a typo.
    """
    for path in sorted(cfg.CONFIG_DIR.glob("*.csv")):
        text = path.read_text()
        assert "orcid" not in text.lower(), (
            f"{path.name} mentions ORCID; this dashboard queries software, not people")


def test_the_shipped_tables_validate():
    """`tgx doctor` runs this; so does CI. A green suite should mean a green doctor."""
    assert cfg.validate() == []


def test_every_table_has_the_columns_the_loader_expects():
    """A renamed or reordered column is the likeliest way a spreadsheet edit breaks.

    Caught here with a clear message rather than as a KeyError three layers down.
    """
    for name in cfg.COLUMNS:
        assert (cfg.CONFIG_DIR / name).exists(), f"{name} is missing"
        cfg._read(name)  # raises ConfigError if the header does not match


def test_a_row_pointing_at_no_project_is_an_error(tmp_path, monkeypatch):
    """The foreign key a JSON schema could never check.

    Every row in identifiers, services and links names a project. A typo there used to
    mean the identifier was silently attached to nothing and never collected.
    """
    for name, header, row in (
        ("identifiers.csv", "project,kind,value,note", "nosuch,repo,a/b,"),
        ("services.csv", "project,name,url,what", "nosuch,S,https://x,y."),
        ("links.csv", "project,label,url", "nosuch,site,https://x"),
    ):
        for other, cols in cfg.COLUMNS.items():
            (tmp_path / other).write_text(",".join(cols) + "\n")
        (tmp_path / "projects.csv").write_text(
            "id,name,what,mark,logo\nreal,Real,A sentence.,RE,\n")
        (tmp_path / name).write_text(f"{header}\n{row}\n")

        monkeypatch.setattr(cfg, "CONFIG_DIR", tmp_path)
        cfg.projects.cache_clear()
        with pytest.raises(cfg.ConfigError, match="nosuch"):
            cfg.projects()
    cfg.projects.cache_clear()


def test_an_unknown_identifier_kind_is_an_error(tmp_path, monkeypatch):
    """`kind` is an enumeration. A misspelling must not read as "collect nothing"."""
    for other, cols in cfg.COLUMNS.items():
        (tmp_path / other).write_text(",".join(cols) + "\n")
    (tmp_path / "projects.csv").write_text(
        "id,name,what,mark,logo\nreal,Real,A sentence.,RE,\n")
    (tmp_path / "identifiers.csv").write_text(
        "project,kind,value,note\nreal,repoo,a/b,\n")

    monkeypatch.setattr(cfg, "CONFIG_DIR", tmp_path)
    cfg.projects.cache_clear()
    with pytest.raises(cfg.ConfigError, match="repoo"):
        cfg.projects()
    cfg.projects.cache_clear()


def test_blank_spreadsheet_rows_are_not_data(tmp_path, monkeypatch):
    """Editing a CSV in a spreadsheet leaves trailing empty rows behind."""
    for other, cols in cfg.COLUMNS.items():
        (tmp_path / other).write_text(",".join(cols) + "\n")
    (tmp_path / "projects.csv").write_text(
        "id,name,what,mark,logo\nreal,Real,A sentence.,RE,\n,,,,\n,,,,\n")

    monkeypatch.setattr(cfg, "CONFIG_DIR", tmp_path)
    cfg.projects.cache_clear()
    assert cfg.project_ids() == ["real"]
    cfg.projects.cache_clear()


def test_corrections_carry_a_reason_and_name_a_tracked_doi():
    """A correction is an override of what a registry says, so it has to justify
    itself and has to still apply to something the page renders."""
    dois = {d.lower() for _, d in cfg.project_field("papers")}
    for row in cfg._read("corrections.csv"):
        assert row["reason"], f"{row['value']} corrects without a reason"
        assert row["to"], f"{row['value']} has nothing to correct it to"
        assert row["field"] in cfg.CORRECTABLE[row["kind"]]
        if row["kind"] == "paper":
            assert row["value"].lower() in dois, f"{row['value']} is not tracked"


def test_an_uncorrected_value_passes_straight_through():
    assert cfg.corrected("paper", "10.0000/nothing", "title", "As upstream had it") == \
        "As upstream had it"
