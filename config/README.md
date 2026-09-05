# The config tables

Everything a person edits lives here, one row per thing, as CSV. Open them in a
spreadsheet, in a text editor, or with `csvkit`; a change shows up in review as a
one-line diff. No Python is involved in adding a project, and a test holds that.

These are normalised tables rather than one wide sheet on purpose. Most of what a
project has is a list - several repositories, several papers, several links - and a
wide sheet can only hold those as semicolon-separated cells that nothing can check.

`tgx doctor` validates all of it: column names, foreign keys, enumerations, and
whether the logo a project names is actually on disk. Run it before opening a pull
request. CI runs the same check.

---

## `projects.csv` - one row per tracked project

| column | required | what it is |
|---|---|---|
| `id` | yes | short slug, lowercase, no spaces. Used in URLs and file names |
| `name` | yes | how it is written on the page |
| `what` | yes | one sentence a stranger would understand, ending in a full stop. Shown under the name |
| `mark` | no | two or three letters for the tile when the project has no logo. Falls back to initials of `name`, which is wrong often enough to be worth setting |
| `logo` | no | a file in `docs/assets/images/logos/`. Wider than 2.5:1 is treated as a wordmark and shown on its own; anything squarer is treated as an icon and shown beside the name |

Row order is the order the tiles appear in.

## `identifiers.csv` - everything a project publishes

| column | what it is |
|---|---|
| `project` | an `id` from `projects.csv` |
| `kind` | one of `repo`, `package`, `docker`, `rsd`, `paper` |
| `value` | the identifier itself, in the form its `kind` expects |
| `note` | free text, for your own benefit. Not published |

What each kind expects:

- **`repo`** - `owner/name` on GitHub. Gives releases, tags and last activity.
- **`package`** - `registry/name`. Registries: `bioconductor.org`, `pypi.org`,
  `npmjs.org`, `cran.r-project.org`, `repo1.maven.org` (use `group:artifact`),
  `conda-forge.org`.
- **`docker`** - Docker Hub `namespace/image`. Gives pull counts. It is the only
  registry that publishes one.
- **`rsd`** - Research Software Directory slug, from the URL:
  `research-software-directory.org/software/<slug>`. Gives papers mentioning the tool.
  Not registered there? Register it - that is worth more than adding a row here.
- **`paper`** - DOI of a paper that describes the tool, the kind people cite when they
  use it. Citations come from OpenAlex. **List every update paper**: WikiPathways has
  seven, and counting only the newest understates it several-fold.

## `services.csv` - what the department runs

| column | what it is |
|---|---|
| `project` | an `id` from `projects.csv` |
| `name` | how the service is named on the tile |
| `url` | where it lives |
| `what` | one sentence. Not currently shown, but kept as the record of what it is for |

Nothing about these is measured. They are listed so a reader can reach them.

## `links.csv` - anything else worth clicking

| column | what it is |
|---|---|
| `project` | an `id` from `projects.csv` |
| `label` | any text you like |
| `url` | where it goes |

Row order is the order shown, and links come before services, so the project's own
site belongs in the first row. A link with the same URL as a service is shown once.

## `metrics.csv` - what every number counts

Nothing appears on the site without a row here, and each source's section on the
Methods page is generated from this file, so a definition cannot drift from the figure
it describes.

| column | what it is |
|---|---|
| `metric` | the name a collector emits |
| `label` | how it is titled on the page |
| `counts` | what one unit of it counts |
| `source` | which collector produces it; must be in `collectors.csv` |
| `cumulative` | `true` for a running total, `false` for a per-period count |
| `granularity` | `none`, `month` or `year`. Must be `none` when cumulative - a level does not belong to a period |
| `caveat` | what the number does **not** mean. Required, and published in this table, which the site offers for download. No longer printed under each figure |

## `collectors.csv` - which sources run

Disabling a broken source is a one-line change. `cadence_days` drives the freshness
strip: a source goes amber at twice its cadence and red at five times.

| column | what it is |
|---|---|
| `collector` | must match a collector in `src/tgx_outputs/collect/` |
| `title` | how the source is named on the Methods page |
| `url` | where that name links to |
| `terms` | the licence or terms its data comes under, shown beside the name. Markdown is allowed |
| `enabled` | `true` or `false` |
| `cadence_days` | how often it is expected to refresh |
| `note` | why, if it is switched off |

Each source gets one section on the Methods page built from this row plus what it
actually did on the last run: what it publishes, the shape of what it asked for, and
every request in order.

## `settings.csv` - the few single values

`key,value` pairs: who the department is, the contact address, and the Research
Software Directory endpoint. Keys beginning `rsd_` configure that source.

## `exclusions.csv` - what is left out, and why

| column | what it is |
|---|---|
| `kind` | `repos`, `packages` or `dois` |
| `value` | the identifier being excluded |
| `reason` | required, and published on the Methods page |

An undeclared omission looks exactly like a bug, which is why the reason is not
optional.

---

## `corrections.csv` - where upstream is wrong

| column | what it is |
|---|---|
| `kind` | what is being corrected. Only `paper` so far |
| `value` | the identifier it applies to - for `paper`, the DOI |
| `field` | the field to replace. For `paper`, only `title` |
| `to` | what it should say |
| `reason` | why, and it is required |

Registries are occasionally wrong in a way no re-fetch repairs. ACS published a
literal `?` where an em dash belongs in the 2006 Blue Obelisk title, and Crossref and
OpenAlex both carry it verbatim, so there is nowhere to fetch a correct one from.

Use this only for that: metadata upstream has plainly wrong. It is not a place to
retitle a paper you would have worded differently, and it does not change any number.
A row whose DOI is not in `identifiers.csv` fails validation rather than sitting there
after the paper it referred to has gone.

Corrections apply when the site is built, not when a source is collected, so a fix
reaches the page on the next build without waiting for a refresh.

## A note on privacy

Nothing in these tables is personal data. Every target is a repository, a package, an
image, an endpoint or a DOI; no person is queried, stored or rendered, and a test
fails if any file here so much as mentions an ORCID.
