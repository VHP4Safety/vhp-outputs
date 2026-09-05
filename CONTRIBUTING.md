# Contributing

Almost every useful change is a row in a table. No Python needed, and every file in
`config/` is a CSV you can open in a spreadsheet - the columns are documented in
[`config/README.md`](config/README.md).

## Add a project

One row in `config/projects.csv`:

```csv
id,name,what,mark,logo
my-tool,My Tool,One sentence a stranger would understand.,MT,
```

Then a row in `config/identifiers.csv` for each thing it publishes. Leave out anything
the project does not have; nothing about it is shown.

```csv
project,kind,value,note
my-tool,repo,someorg/my-tool,
my-tool,package,pypi.org/my-tool,
my-tool,docker,somenamespace/my-tool,
my-tool,rsd,my-tool,
my-tool,paper,10.1234/example,"My Tool, J Example 2026"
```

Anything the project runs goes in `config/services.csv`, and anything worth linking to
in `config/links.csv` - the first link listed is the first one shown, so put the
project's own site there.

Then check the identifiers actually resolve:

```bash
tgx doctor --projects
```

It calls each API and tells you which ones do not exist. CI runs the same check.

If a tool is not in the Research Software Directory, register it there rather than
worrying about the `rsd` field. That is where the literature mention counts come from,
and it is maintained by someone else.

## Leave something out

A row in `config/exclusions.csv`, by repository, package or DOI. A reason is required,
because an undeclared omission looks the same as a bug. The table is public and the
reason is checked, so the omission is on the record even though the page does not
list it. To have something removed, open an issue or email the contact in
`config/settings.csv`; no reason needed.

## Correct something upstream got wrong

A row in `config/corrections.csv`, with a reason. Only for metadata a registry has
plainly wrong - a mangled character in a paper title that Crossref and OpenAlex both
carry, say. It changes no number, and the columns are in
[`config/README.md`](config/README.md).

## Add a number to the page

1. Define it in `config/metrics.csv` first: what one unit counts, whether it
   is a running total or a per-period count, and what it does not mean. Nothing renders
   without this, and the figure's caption is generated from it.
2. Emit it from a collector in `src/tgx_outputs/collect/`.
3. Add a chart in `src/tgx_outputs/site/charts.py` and reference it from a page.
4. `make record`, then `make check` and `make offline`.

## Ground rules

- Nothing about individuals. No per-person figures or rankings, and no person is
  queried: every target is a repository, package, image, endpoint or DOI.
- Software, not bibliometrics. The department's publication record lives in Pure; the
  only citations here are of the papers that describe a tracked tool.
- Every number carries a caveat. If you cannot say what it does not mean, it is not
  ready to publish.
- A running total is never stored against a period.
- No stored secrets. A test enforces it.
- `make offline` must pass. That is what keeps this maintainable by whoever comes next.
