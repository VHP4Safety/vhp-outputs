# Methods

Everything comes from public APIs, collected weekly by a job in
[this repository](https://github.com/TGX-UM/tgx-outputs). No manual data entry, no
database, and no credential beyond the token GitHub issues to its own workflow.

## What counts as TGX

The tracked list is [`config/projects.csv`](https://github.com/TGX-UM/tgx-outputs/blob/main/config/projects.csv):
software and data resources the department builds or co-maintains, each named
explicitly with the repositories, packages, images, endpoints and papers that belong to
it. Nothing is discovered by matching a person, an affiliation string or an ORCID, so
nothing arrives in a figure because a name looked right.

No person is queried and none is stored. The department's publication record is a
separate thing, held in Pure, and this page does not reproduce it.

## Rules the pipeline enforces

Each exists because a dashboard like this has failed that way before. A record that
trips one is quarantined into the run manifest with its reason and never published.

| Rule | Prevents |
|---|---|
| `semantics_gate` | a figure appearing without a definition of what it counts |
| `period_class` | a running total being filed under a month, which produces identical rows and a headline that sums the same number repeatedly |
| `future_period` | upstream placeholder rows entering the series. Bioconductor ships a zero row for every remaining month of the year |
| `no_silent_zero` | a value collapsing to zero and being published as fact |
| `monotonic` | a lifetime counter appearing to go backwards |
| `empty_result` | a source returning HTTP 200 with no rows being read as "nothing to report" while the last good value ages |
| `rate_limited` | a 429 being absorbed into "handled", which freezes a series while the page claims it is current |
| `volume_drop` | a collapse in record count being promoted |

Freshness comes from each source's own collection timestamp, never from the build
clock. Amber past twice a source's cadence, red past five times.

## Blind spots { #blind-spots }

A gap that is not declared reads as a zero, so:

- Container pulls come from Docker Hub, which is the only registry that publishes a
  count. An image pushed only to GitHub's registry or another one has no usage figure
  here, and none of them offer an API that would give one.
- GitHub page views and clones are not collected. They need push access to every
  repository, which means storing a token, and this runs without secrets. The window
  is 14 days anyway.
- PyPI download history cannot be backfilled. The public API keeps about 180 days.
- The Research Software Directory only knows registered tools. Software nobody
  registered shows no mentions, which is a good argument for registering it.
- Only the projects listed in `config/projects.csv` are counted. A missing tool means
  nobody has added it yet, and adding one is a row in a table.
- Citations are counted for the papers a project declares. A tool with no paper of its
  own therefore shows none, however much it is used.

## Collection status { #collection-status }

--8<-- "freshness.md"

Sources are collected independently, so one broken API degrades one section and the
page still builds with that section marked stale rather than showing last week's
number as if it were current.

[Open an issue](https://github.com/TGX-UM/tgx-outputs/issues/new). Every figure links
to its data, and the run manifests record what each source returned and what failed.

## The sources { #sources }

One section per source: what it is, what this project takes from it, the shape of what
it asks for, and every request from the last run. Generated from the run manifest, so
it describes what actually happened rather than what the code is meant to do.

What is republished here are derived aggregates, never a verbatim copy of anyone's
dataset. Where a source publishes no licence for its statistics, the figure is shown
with a link back rather than redistributed. If you maintain one of these services and
would rather this project used your data differently, please
[open an issue](https://github.com/TGX-UM/tgx-outputs/issues/new).

Every URL below can be pasted into a browser - they are all public and none needs a
key - and the answer you get is the answer this page got. In a diagram, requests are on
the left, the collector in the middle, the metrics it produced on the right; a box
marked `×19` is one endpoint asked nineteen times, and `…` marks a segment that varied
between calls. The literal URLs are in the tables, never abbreviated.

--8<-- "sources.md"

## Charts and icons


Charts are drawn with [Vega-Lite](https://vega.github.io/vega-lite/) (BSD-3-Clause),
vendored into `docs/assets/js/` and pinned rather than loaded from a CDN, so the page
renders the same in five years and archives intact. The site itself is built with
[MkDocs Material](https://squidfunk.github.io/mkdocs-material/) (MIT).

The type and the icons work the same way. [Open Sans](https://fonts.google.com/specimen/Open+Sans)
(Apache-2.0) is the substitute UM's own web guidance names for Thesis Sans, its licensed
house typeface; the four subset faces are served from this repository, licence included.
The tile icons are inline SVG taken from [Simple Icons](https://simpleicons.org)
(CC0-1.0) and [Octicons](https://primer.style/octicons) (MIT); the brand marks belong to
their owners, and they are there to say which registry a number came from. The project
logos work the same way: each is the mark that project publishes in its own repository,
copied into `docs/assets/images/logos/` so the page fetches nothing, and shown only to
identify the tool whose figures sit beneath it. Every one of them remains the property
of the project that made it. A project with no mark of its own gets initials instead.
Nothing on this page is requested from anyone else.

The TGX logo and icon are the department's own marks. Colours follow the UM house style,
and the chart series take the department's own `#00A2DB` and `#E84E10`.

| File | Version | SHA-384 |
|---|---|---|
| `vega.min.js` | 5.30.0 | `em7CHpJd+SsMugVFf6TY7AKQcLWMcbPhD84hmNK8o6WFDkK+2uHSUQRVQV1/w827` |
| `vega-lite.min.js` | 5.21.0 | `GhkD6ks9/zgY1m5EFOUZWz/vMVMUFF/92DL61RZc+B42J8osL+jNufKv68bNHHZ2` |
| `vega-embed.min.js` | 6.26.0 | `TqXb8su49m5OnEpKGO8m+VrgHesrUxyP22HgpXi4hnh1Hm43dXroiSYemNf5D8lv` |
