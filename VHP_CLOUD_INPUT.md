# Pulling new projects from vhp4safety/cloud

`vhp4safety/cloud` keeps one JSON file per service in `docs/service/*.json`, meant
for its own service catalog. Some of those services are software the department
built, and belong in this repository's `config/` tables too, but nothing pulls
them over on its own.

**Run `make cloud-sync` first.** It automates Steps 1, 2 and 4 below: it lists and
filters the candidates, follows GitHub renames so an already-tracked repo is never
re-added under its old name, writes the `identifiers.csv` rows a JSON actually
supports, and finishes with the `tgx doctor` check from Step 5 (`make record` and
`pytest -q` there are still a person's job, same as for any other new repo or DOI).
What it deliberately does *not* decide for you is Step 3 - the wording of a new
project's `what` and the pick of its `mark` - and anything genuinely ambiguous (an
owner shared by more than one existing project, a file with more than one
plausible repo and no `instance.source` to prefer): those are printed for a person
to resolve, which is what the rest of this document walks through by hand. See
`scripts/cloud_sync.py`'s own docstring for exactly what it checks.

This is the manual procedure for what `make cloud-sync` leaves for a person, and
what was checked the last time it was done (2026-09-05).

## Where the source lives

- File list: `https://api.github.com/repos/vhp4safety/cloud/contents/docs/service`
  (unauthenticated `curl` works fine - it's a public repo)
- Each file: `https://raw.githubusercontent.com/VHP4Safety/cloud/main/docs/service/<id>.json`
- The schema for every field is documented in `template.json` itself, as a
  `_ins_<field>` sibling key next to each real key. Read that file first if a
  field's meaning is unclear - don't guess from the field name alone.

A fine-grained GitHub PAT may be unable to read this org (`VHP4Safety` and
`BiGCAT-UM` both reject fine-grained tokens whose lifetime exceeds 366 days,
org-wide). That's a token-policy error, not a missing-repo error - drop the
`Authorization` header and retry unauthenticated before concluding a repo is
private or gone.

## Step 1: which services are candidates at all

A service JSON is a candidate only if both hold:

- `"developed-by-VHP": "true"` - services the department didn't build (an
  external tool VHP just deploys or documents, e.g. BMDExpress, ASReview,
  Fairspace) are out of scope for `config/`, which tracks the department's own
  output.
- it names a GitHub repository somewhere - almost always
  `instance.source`, occasionally only in `deployment_docs`,`intro.url`, or
  buried in a `regulatory-question`-adjacent free-text field. Grep the raw
  file for `github.com` rather than trusting `instance.source` alone; a couple
  of services only mention their repo elsewhere in the file.

Everything else in the file (`stage`, `NAM-validation`, `VHP-persona`,
`regulatory-question`, ELIXIR entries, ...) describes the service's place in
the VHP4Safety catalog UI. None of it maps to anything in `config/` - ignore it
for this exercise.

## Step 2: does the repo already have a home in projects.csv

`config/identifiers.csv` rows carry a `project` id that must exist in
`config/projects.csv` (`tgx doctor` / `cfg.validate()` enforces this as a
foreign key - a typo there used to mean the identifier was silently attached to
nothing). So for each candidate repo:

1. Normalize `instance.source` to `owner/name` - drop any `/tree/<branch>` or
   `/blob/...` suffix; `identifiers.csv` only stores the repo, not a ref.
2. Search `config/identifiers.csv` for that `owner/name` (case-insensitively -
   GitHub itself is, even though this file is inconsistent about casing the
   owner segment).
3. If it's already there under some project, there's nothing to do - move on.
4. If it's not there, check whether it plausibly belongs to an *existing*
   project anyway before creating a new one. The signal that worked here: same
   author/org and same subject as repos already tracked under that project id
   (e.g. `marvinm2/aopwiki-snorql-extended` and `marvinm2/AOPWikiQueries` are
   both grlc/SPARQL front ends for the AOP-Wiki RDF endpoint that
   `aopwiki-rdf` already tracks three other `marvinm2/*` repos for - same
   maintainer, same ELIXIR bio.tools entry family, same endpoint). Don't
   attach a repo to a project on name similarity alone; check the actual
   provider/contact and description fields against the project's existing
   rows.
5. Otherwise, it needs a brand-new row in `projects.csv` (Step 3).

Also worth checking before inventing a new id: `docs/assets/images/logos/`
sometimes already has a logo file sitting unused for a repo that was never
given a project row (`pathvisio.png` and `arrayanalysis.png` were both already
there, unreferenced by any project, before this pass added PathVisio and
ArrayAnalysis) - that's a strong sign someone already meant for it to be
tracked, and the logo should be wired in rather than left orphaned.

## Step 3: writing the projects.csv row

Columns: `id,name,what,mark,logo` (see `config/README.md` for the full column
contract). Per new row:

- `id` - short, lowercase, no spaces. Prefer the service JSON's own `id` field
  when it already fits that shape; otherwise derive one from `service`.
- `name` - the JSON's `service` field, as stylized there.
- `what` - one sentence, ending in a full stop, written for a stranger (not
  VHP-internal jargon, not the case-study-specific framing the JSON's
  `description` often uses). Paraphrase `description`, don't copy it verbatim -
  the existing rows all read as plain-English capability statements ("Maps
  identifiers between biological databases...") rather than marketing copy.
- `mark` - two or three letters, used as the tile abbreviation when there's no
  logo. Pick something a reader would associate with the name.
- `logo` - only if a matching file already exists in
  `docs/assets/images/logos/`; leave blank otherwise. Don't add new logo
  files as part of this exercise - that's a design asset someone supplies
  separately.

## Step 4: writing the identifiers.csv rows

Columns: `project,kind,value,note`. For each new (or newly-homed) repo, pull
whatever of the following the service JSON actually has - don't invent rows
for fields that are empty:

- `repo` - the normalized `owner/name` from Step 2.
- `paper` - `doi` field, if set. Look the DOI up (Crossref's
  `https://api.crossref.org/works/<doi>` needs no auth) to write a `note` in
  this repo's existing style: a short title fragment, a comma, then an
  abbreviated venue and year, e.g. `"PathVisio 3, PLOS Comp Biol 2015"`. A
  preprint with no `container-title` gets `"<title fragment>, preprint <year>"`
  instead of a venue.
- `rsd` - `Other.rsd`, if set. This is a Research Software Directory slug, not
  a URL - just the slug.
- `docker` - only if `instance.docker` is an actual Docker Hub reference
  (`hub.docker.com/r/<namespace>/<image>`). A GHCR package page or a link to a
  `Dockerfile` in the repo is not a docker identifier in this schema's sense
  (`config/README.md`: "the only registry that publishes [pull counts]") -
  leave those out rather than adding a row the `dockerhub` collector can't
  use.
- `package` - only for a registry `cfg.REGISTRIES` actually recognizes
  (`bioconductor.org`, `pypi.org`, `npmjs.org`, `cran.r-project.org`,
  `repo1.maven.org`, `conda-forge.org`, plus the two OS repos). Most of these
  service JSONs don't name one.

Skip anything the JSON doesn't give you rather than filling a column with a
best guess - an empty `note` is fine, a fabricated DOI or slug is not.

## Step 5: verify before committing

```bash
tgx doctor              # config sha, project/identifier counts, "config is consistent"
make record              # re-records live fixtures for the new repos/DOIs with GITHUB_TOKEN set
pytest -q                 # full suite, including the offline fixture replay tests
```

`make record` will re-fetch citation counts and repo metadata for *every*
tracked identifier, not just the new ones - expect a handful of unrelated
fixture files to gain a new hash (harmless: the request payload changed
because the batch now includes more repos/DOIs) and check `git diff` before
committing to make sure nothing beyond timestamps moved in fixtures you didn't
mean to touch.

A `DEGRADED` collector status is not automatically a problem: `vhp4safety` and
`BiGCAT-UM` repos are frequently reported `not visible` by a restricted
fine-grained token (a pre-existing, already-committed condition - check
whether the same repos were already null in the fixture before your change),
and a brand-new preprint DOI legitimately has no OpenAlex record yet. Read the
specific reason printed rather than treating `DEGRADED` as a failure.
