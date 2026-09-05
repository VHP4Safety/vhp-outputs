#!/usr/bin/env python3
"""Pull newly department-built services from vhp4safety/cloud into config/.

`vhp4safety/cloud` keeps one JSON file per service in `docs/service/*.json`, for its
own service catalog. Some of those services are software this department built and
belongs in this repository's `config/` tables too, but nothing pulls them over on its
own -- this automates the procedure documented in `VHP_CLOUD_INPUT.md`. Run it via
`make cloud-sync`. Set `GITHUB_TOKEN` (or `GH_TOKEN`) for a much higher API rate
limit, same as `make record` -- a fine-grained PAT that the org rejects on lifetime
policy is dropped and retried unauthenticated automatically.

What counts as a candidate (VHP_CLOUD_INPUT.md Step 1): `developed-by-VHP` is
`"true"`, and the file names a GitHub repository -- almost always `instance.source`,
occasionally only elsewhere in the file, so a whole-file scan for `github.com` is used
as a fallback rather than trusting `instance.source` alone.

A candidate already in `identifiers.csv` is left untouched, *including* one that was
renamed on GitHub since it was added: the GitHub API is asked to resolve both the
tracked value and the candidate to a repository id, not just compared as strings, and
a tracked row whose name has gone stale is rewritten in place to the current name.

For a repo that is genuinely new, which project it belongs to (Step 2) is decided
without guessing at anything the doc says needs a person's judgement:
- the service JSON's own `id` matching an existing `projects.csv` id is the strongest
  signal, and is used first;
- otherwise, if every repository already tracked with this candidate's owner belongs
  to one and the same project, it goes there;
- otherwise a new `projects.csv` row is created.

A new row's `what` (first sentence of the JSON `description`) and `mark` (initials of
`service`) are mechanical drafts, not a paraphrase or a considered abbreviation --
VHP_CLOUD_INPUT.md Step 3 is explicit that those need a person's read. They are
printed at the end precisely so that person's glance is easy to find.

Ambiguous cases -- more than one project sharing an owner, more than one plausible
repo mentioned in a file with no `instance.source` to prefer -- are never guessed at
either: they are skipped and printed so a person can resolve them by hand.
"""

from __future__ import annotations

import csv
import io
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from tgx_outputs import config as cfg  # noqa: E402
from tgx_outputs.http import USER_AGENT  # noqa: E402

LISTING_URL = "https://api.github.com/repos/vhp4safety/cloud/contents/docs/service"
RAW_URL = "https://raw.githubusercontent.com/VHP4Safety/cloud/main/docs/service/{name}"
GITHUB_REPO_URL = "https://api.github.com/repos/{repo}"
CROSSREF_URL = "https://api.crossref.org/works/{doi}"

LOGOS_DIR = ROOT / "docs" / "assets" / "images" / "logos"
PROJECTS_CSV = cfg.CONFIG_DIR / "projects.csv"
IDENTIFIERS_CSV = cfg.CONFIG_DIR / "identifiers.csv"

GITHUB_RE = re.compile(r"github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)", re.IGNORECASE)
STOPWORDS = {"a", "an", "the", "of", "for", "and", "to", "in", "on"}


def http_client() -> httpx.Client:
    headers = {"User-Agent": USER_AGENT}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return httpx.Client(headers=headers, timeout=30.0, follow_redirects=True)


def get_json(client: httpx.Client, url: str) -> Any | None:
    """GET and decode JSON, dropping a token that GitHub's org policy rejected.

    VHP_CLOUD_INPUT.md: a fine-grained PAT can be refused for the whole org on a
    lifetime policy, which looks like an auth error, not a missing-repo one. Retry
    unauthenticated before treating the resource as absent.
    """
    resp = client.get(url)
    if resp.status_code in (401, 403) and "Authorization" in client.headers:
        headers = {k: v for k, v in client.headers.items() if k != "Authorization"}
        resp = httpx.get(url, headers=headers, timeout=30.0, follow_redirects=True)
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.json()


def deep_find(obj: Any, key: str) -> str | None:
    """First non-empty value of `key` anywhere in a nested dict/list, or None."""
    if isinstance(obj, dict):
        if key in obj and str(obj[key]).strip():
            return str(obj[key]).strip()
        for value in obj.values():
            found = deep_find(value, key)
            if found:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = deep_find(item, key)
            if found:
                return found
    return None


def normalize_repo(owner: str, name: str) -> str:
    name = re.sub(r"\.git$", "", name)
    return f"{owner}/{name}"


def find_repo(service: dict[str, Any], raw_text: str) -> tuple[str | None, list[str]]:
    """The repo this service names, plus every other distinct one mentioned.

    Trusts `instance.source` when it names one; only falls back to a whole-file scan
    when it doesn't, per VHP_CLOUD_INPUT.md Step 1 -- a deployment-docs link or an
    unrelated tool's own repo elsewhere in the file is not this service's repo, and
    both `aopwikiapi.json` (links `CLARIAH/grlc`'s deployment docs) and
    `qsprpred.json` (links `VHP4Safety/vhp4safety-docs`) would be mis-tracked by
    trusting the scan over a present `instance.source`.
    """
    source = (service.get("instance") or {}).get("source", "")
    source_match = GITHUB_RE.search(source) if source else None
    primary = normalize_repo(*source_match.groups()) if source_match else None

    all_matches = {normalize_repo(o, n) for o, n in GITHUB_RE.findall(raw_text)}
    if primary is None:
        if len(all_matches) == 1:
            primary = next(iter(all_matches))
        elif len(all_matches) > 1:
            return None, sorted(all_matches)

    others = sorted(r for r in all_matches if r.lower() != (primary or "").lower())
    return primary, others


def resolve_canonical(client: httpx.Client, repo: str) -> tuple[str, int] | None:
    """(current owner/name, numeric id) a repo resolves to, following any rename.

    Best-effort: a network error or an exhausted unauthenticated rate limit degrades
    to "resolution unavailable" rather than aborting the run -- the repo is then
    treated as new under its as-given name, which a person can still fix by hand.
    """
    try:
        data = get_json(client, GITHUB_REPO_URL.format(repo=repo))
    except httpx.HTTPError:
        return None
    if data is None:
        return None
    return data["full_name"], data["id"]


def load_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        return list(reader.fieldnames or []), list(reader)


def append_rows(path: Path, header: list[str], rows: list[dict[str, str]]) -> None:
    if not rows:
        return
    with path.open("a", newline="", encoding="utf-8") as fh:
        csv.DictWriter(fh, fieldnames=header).writerows(rows)


def update_repo_value(path: Path, old_value: str, new_value: str) -> None:
    """Rewrite one repo identifier's value in place, byte-for-byte elsewhere.

    Re-serialising every row through `csv.writer` would also normalise whichever
    rows happen to carry quoting `csv.QUOTE_MINIMAL` wouldn't have chosen itself,
    turning a one-repo rename into a diff a reviewer has to read past.
    """
    with path.open(newline="", encoding="utf-8") as fh:
        lines = fh.readlines()
    for i, row in enumerate(csv.reader(lines[1:]), start=1):
        if len(row) >= 3 and row[1] == "repo" and row[2] == old_value:
            row[2] = new_value
            buf = io.StringIO()
            csv.writer(buf).writerow(row)
            lines[i] = buf.getvalue()
            break
    with path.open("w", newline="", encoding="utf-8") as fh:
        fh.writelines(lines)


def crossref_note(client: httpx.Client, doi: str) -> str:
    try:
        data = get_json(client, CROSSREF_URL.format(doi=doi))
    except httpx.HTTPError:
        return ""
    if not data:
        return ""
    message = data.get("message", {})
    titles = message.get("title") or []
    if not titles:
        return ""
    fragment = titles[0].split(":")[0].strip()
    year = None
    for field in ("published", "published-print", "published-online", "issued"):
        parts = (message.get(field) or {}).get("date-parts")
        if parts and parts[0]:
            year = parts[0][0]
            break
    container = (message.get("container-title") or [None])[0]
    if container:
        venue = f"{container} {year}" if year else container
    else:
        venue = f"preprint {year}" if year else "preprint"
    return f"{fragment}, {venue}"


def docker_identifier(instance: dict[str, Any]) -> str | None:
    match = re.search(r"hub\.docker\.com/r/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)",
                       instance.get("docker", ""))
    return f"{match.group(1)}/{match.group(2)}" if match else None


PACKAGE_PATTERNS = [
    ("pypi.org", re.compile(r"pypi\.org/project/([A-Za-z0-9_.-]+)")),
    ("npmjs.org", re.compile(r"npmjs\.(?:org|com)/package/(@?[A-Za-z0-9_./-]+)")),
    ("bioconductor.org",
     re.compile(r"bioconductor\.org/packages/(?:release/\w+/\w+/)?([A-Za-z0-9_.-]+)")),
    ("cran.r-project.org",
     re.compile(r"cran\.r-project\.org/(?:web/packages/|package=)([A-Za-z0-9_.-]+)")),
    ("conda-forge.org", re.compile(r"anaconda\.org/conda-forge/([A-Za-z0-9_.-]+)")),
]


def package_identifier(raw_text: str) -> str | None:
    for registry, pattern in PACKAGE_PATTERNS:
        match = pattern.search(raw_text)
        if match:
            return f"{registry}/{match.group(1).rstrip('/')}"
    return None


def derive_what(description: str) -> str:
    first = re.split(r"(?<=[.!?])\s", description.strip(), maxsplit=1)[0].strip()
    if not first:
        return "No description given upstream -- needs a person to write one."
    if not first.endswith((".", "!", "?")):
        first += "."
    return first


WORD_RE = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z][a-z0-9]*|[a-z0-9]+")


def derive_mark(name: str) -> str:
    """Initials of up to three words, splitting camelCase as well as punctuation.

    A plain punctuation split turns "PathVisio" into one word and a one-letter mark;
    splitting internal capitals too recovers the initials a person picked by hand for
    the names already in projects.csv (PathVisio -> PV, BridgeDb -> BD, WikiPathways
    -> WP, ToxTempAssistant -> TTA), which is the best evidence available for what a
    reader expects here.
    """
    words = [w for w in WORD_RE.findall(name) if len(w) > 1 and w.lower() not in STOPWORDS]
    words = words or WORD_RE.findall(name)
    letters = "".join(w[0] for w in words[:3]).upper()
    if len(letters) >= 2:
        return letters
    return re.sub(r"[^A-Za-z0-9]", "", name)[:2].upper() or name[:3].upper()


def derive_id(service: dict[str, Any], existing_ids: set[str]) -> str:
    seed = str(service.get("id") or service.get("service") or "service").strip().lower()
    candidate = re.sub(r"[^a-z0-9-]+", "-", seed).strip("-") or "service"
    if candidate not in existing_ids:
        return candidate
    for n in range(2, 100):
        if f"{candidate}-{n}" not in existing_ids:
            return f"{candidate}-{n}"
    raise RuntimeError(f"could not derive a free project id from {candidate!r}")


def find_unreferenced_logo(project_id: str, referenced: set[str]) -> str | None:
    if not LOGOS_DIR.exists():
        return None
    for path in sorted(LOGOS_DIR.iterdir()):
        if path.stem.lower() == project_id.lower() and path.name not in referenced:
            return path.name
    return None


def main() -> int:
    client = http_client()

    try:
        listing = get_json(client, LISTING_URL) or []
    except httpx.HTTPError as exc:
        print(f"cloud-sync: could not list vhp4safety/cloud's docs/service/: {exc}")
        return 1
    names = sorted(entry["name"] for entry in listing
                    if entry["name"].endswith(".json") and entry["name"] != "template.json")
    print(f"cloud-sync: {len(names)} service files in vhp4safety/cloud")

    proj_header, proj_rows = load_rows(PROJECTS_CSV)
    ident_header, ident_rows = load_rows(IDENTIFIERS_CSV)
    existing_project_ids = {row["id"] for row in proj_rows}
    referenced_logos = {row["logo"] for row in proj_rows if row["logo"]}
    repo_rows = [row for row in ident_rows if row["kind"] == "repo"]

    canonical_cache: dict[str, tuple[str, int] | None] = {}

    def canonical(repo: str) -> tuple[str, int] | None:
        if repo not in canonical_cache:
            canonical_cache[repo] = resolve_canonical(client, repo)
        return canonical_cache[repo]

    new_projects: list[dict[str, str]] = []
    new_identifiers: list[dict[str, str]] = []
    skipped_ambiguous: list[str] = []
    review_needed: list[str] = []
    renamed = False

    for name in names:
        try:
            service = get_json(client, RAW_URL.format(name=name))
        except httpx.HTTPError as exc:
            print(f"  ! {name}: fetch failed ({exc}), skipping")
            continue
        if service is None:
            print(f"  ! {name}: not found, skipping")
            continue
        if str(service.get("developed-by-VHP", "")).strip().lower() != "true":
            continue

        raw_text = json.dumps(service)
        repo, others = find_repo(service, raw_text)
        if repo is None:
            if others:
                skipped_ambiguous.append(
                    f"{name}: no instance.source, and more than one github.com "
                    f"link is mentioned: {others}")
            continue
        if others:
            print(f"  ? {name}: also mentions {others} besides {repo}; "
                  "using instance.source, others ignored")

        resolved = canonical(repo)
        canonical_repo, canonical_id = resolved if resolved else (repo, None)

        if any(r["value"].lower() == canonical_repo.lower() for r in repo_rows):
            continue

        owner = canonical_repo.split("/")[0].lower()
        same_owner_rows = [r for r in repo_rows
                            if r["value"].split("/")[0].lower() == owner]

        stale_row = None
        if canonical_id is not None:
            for row in same_owner_rows:
                tracked = canonical(row["value"])
                if tracked and tracked[1] == canonical_id:
                    stale_row = row
                    break
        if stale_row is not None:
            print(f"  = {name}: {stale_row['value']} renamed on GitHub to "
                  f"{canonical_repo}; updating {stale_row['project']}'s row")
            update_repo_value(IDENTIFIERS_CSV, stale_row["value"], canonical_repo)
            stale_row["value"] = canonical_repo
            renamed = True
            continue

        json_id = re.sub(r"[^a-z0-9-]+", "-",
                          str(service.get("id") or "").strip().lower()).strip("-")
        project_id = json_id if json_id in existing_project_ids else None
        if project_id is None:
            owning_projects = {r["project"] for r in same_owner_rows}
            if len(owning_projects) == 1:
                project_id = next(iter(owning_projects))
            elif len(owning_projects) > 1:
                skipped_ambiguous.append(
                    f"{name}: owner {owner!r} is used by more than one existing "
                    f"project ({sorted(owning_projects)}); not guessing which one")
                continue

        if project_id is None:
            project_id = derive_id(service, existing_project_ids)
            what = derive_what(service.get("description", ""))
            mark = derive_mark(service.get("service", project_id))
            logo = find_unreferenced_logo(project_id, referenced_logos)
            new_projects.append({"id": project_id, "name": service.get("service", project_id),
                                  "what": what, "mark": mark, "logo": logo or ""})
            existing_project_ids.add(project_id)
            review_needed.append(
                f"{project_id}: what={what!r} mark={mark!r}"
                + (f" logo={logo!r}" if logo else ""))
            print(f"  + {name}: new project {project_id!r} for {canonical_repo}")
        else:
            print(f"  + {name}: {canonical_repo} -> existing project {project_id!r}")

        new_repo_row = {"project": project_id, "kind": "repo", "value": canonical_repo, "note": ""}
        new_identifiers.append(new_repo_row)
        repo_rows.append(new_repo_row)

        instance = service.get("instance") or {}
        doi = service.get("doi", "").strip()
        already_has_doi = any(
            r["kind"] == "paper" and r["value"].lower() == doi.lower()
            for r in ident_rows + new_identifiers)
        if doi and not already_has_doi:
            new_identifiers.append({"project": project_id, "kind": "paper",
                                     "value": doi, "note": crossref_note(client, doi)})

        rsd = deep_find(service.get("Other") or {}, "rsd")
        if rsd:
            new_identifiers.append({"project": project_id, "kind": "rsd",
                                     "value": rsd, "note": ""})

        docker = docker_identifier(instance)
        if docker:
            new_identifiers.append({"project": project_id, "kind": "docker",
                                     "value": docker, "note": ""})

        package = package_identifier(raw_text)
        if package:
            new_identifiers.append({"project": project_id, "kind": "package",
                                     "value": package, "note": ""})

    append_rows(PROJECTS_CSV, proj_header, new_projects)
    append_rows(IDENTIFIERS_CSV, ident_header, new_identifiers)

    print(f"\ncloud-sync: {len(new_projects)} new project(s), "
          f"{len(new_identifiers)} new identifier row(s)"
          + (", some renamed repos updated in place" if renamed else ""))
    if review_needed:
        print("\nmechanical drafts worth a human glance (VHP_CLOUD_INPUT.md Step 3):")
        for line in review_needed:
            print(f"  - {line}")
    if skipped_ambiguous:
        print("\nskipped -- needs a person's judgement (VHP_CLOUD_INPUT.md Step 2.4):")
        for line in skipped_ambiguous:
            print(f"  - {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
