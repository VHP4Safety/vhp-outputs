# About

A weekly, automatic inventory of the software and data resources the Department of
Translational Genomics at Maastricht University builds. Everything on it comes from
public APIs; nothing is entered by hand, and no person is queried or stored.

It is not a bibliometric dashboard and not an assessment of individuals. The
department's publication record lives in Pure and is reported from there.

## The code

- **Source:** [github.com/TGX-UM/tgx-outputs](https://github.com/TGX-UM/tgx-outputs)
- **Report a wrong number:** [open an issue](https://github.com/TGX-UM/tgx-outputs/issues/new/choose)
- **Add a project, or have one removed:** a row in a table - see
  [CONTRIBUTING.md](https://github.com/TGX-UM/tgx-outputs/blob/main/CONTRIBUTING.md)

The whole site builds offline from recorded fixtures, with no network and no
credential, so anyone can fork it and check what it does.

## Acknowledgements

The shape of this page follows
[RECETOX/specdatri_reporting](https://github.com/RECETOX/specdatri_reporting), the reporting
tool RECETOX built to track its own research software. The grid of per-source totals over a
per-project table is theirs, and several of the checks that keep a wrong number off this page
exist because that project met the failure first.

It is MIT licensed. This is an independent implementation rather than a fork: no code was
taken, only the shape of the problem and some hard-won lessons about it.

## Licence

The code is **MIT**. The figures are derived aggregates of public data, never a
verbatim copy of anyone's dataset; where a source sets terms, those terms travel with
it, and each is credited in the [attribution table](methods.md#sources).

The project logos on the overview belong to the projects that made them and appear
only to identify the tool whose figures sit beneath them.

## Download the data

Every figure links to the CSV behind it, and they are all here. Long format:
`metric, entity, period, value, partial, collected_on`. One row per observation.

- [Everything, one file](data/all_metrics.csv)

Individual metrics are at `data/<metric>.csv`; the names are in the
[source sections on Methods](methods.md#sources).

### Raw snapshots

Each run writes a full snapshot and a manifest to the `data` branch:

- `snapshots/<date>.json` holds everything true that day
- `manifests/<date>.json`, per-source status, errors, quarantined records, calls made

Whole state per run rather than a chain of diffs, so one file can be read on its own.

### Reuse

Code is MIT. Figures are derived aggregates of public data; see the
[attribution table](methods.md#sources). Where a source sets terms, those terms
travel with it.

## Citing this

Cite the tools themselves rather than this page - each project's own papers are linked
from its tile. If you need to cite the inventory, the repository carries a
[`CITATION.cff`](https://github.com/TGX-UM/tgx-outputs/blob/main/CITATION.cff).
