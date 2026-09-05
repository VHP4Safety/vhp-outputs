# When something breaks

A collector failing is normal - these are eight third-party APIs and roughly one of them
changes something every few months. The pipeline is built so that this degrades
one section of one page rather than taking the site down, and so that a broken source
is *visible* rather than quietly serving last month's number.

## First: is anything actually wrong?

Open the [collection status page](https://tgx-um.github.io/tgx-outputs/status/). It
shows every source, its last successful collection and its error text. The banner at the
top of every page goes amber past twice a source's cadence and red past five times.

Then read the latest `manifests/<date>.json` on the `data` branch. It records, per
source: status, the calls made, the errors, and every record that was quarantined and
by which rule.

## The decision tree

**A source is `degraded`.** It returned something, but not enough, or it hit a rate
limit. Usually transient. Re-run `Refresh and publish` manually from the Actions tab. If
it degrades twice in a row, treat it as failed.

**A source is `failed`.** Reproduce locally:

```bash
tgx collect --only <source>
```

The traceback is in the manifest. Common causes, in the order they actually happen:

1. *An upstream response shape changed.* A field was renamed or nested one level
   deeper. Fix the collector, re-record its fixture (`make record`), commit both.
2. *An endpoint moved or was retired.* Update the URL in the collector, or disable the
   collector in `config/settings.csv` - that is a one-line change and an honest one. The
   page will say the source is absent rather than pretending.
3. *A rate limit tightened.* Reduce what the collector asks for, or lengthen its
   `cadence_days`.

**Records are being quarantined.** Look at the rule name in the manifest:

| Rule | What it means | What to do |
|---|---|---|
| `semantics_gate` | A collector emits a metric with no definition | Add it to `config/metrics.csv`, or stop emitting it |
| `period_class` | A cumulative counter was given a period | Store it as a level; derive deltas at query time |
| `future_period` | Upstream shipped placeholder rows for future months | Usually correct behaviour; check the collector filters them at source too |
| `no_silent_zero` | A value collapsed to zero | Almost always an upstream problem. Do **not** override it without understanding why |
| `monotonic` | A lifetime counter went backwards | Upstream recalculated. If it is legitimate, note it and let it through once |
| `volume_drop` | A source returned far less than usual | Nothing was published from it. Investigate before overriding |

**The site is stale but the workflow is green.** Check whether the schedule was
disabled: GitHub turns off scheduled workflows in public repositories after 60 days
with no repository activity, and bot commits may not count. The Actions tab says so at
the top of the workflow page. Re-enable it and push something.

**Everything is fine but a number looks wrong.** That is the most valuable kind of
report. Every figure links to its CSV and names its source and collection date; the
[Methods page](https://tgx-um.github.io/tgx-outputs/methods/) gives the exact
query. If the number is genuinely wrong, the fix is usually either a definition that
does not say what people assume, or an entry for `config/exclusions.csv`.

## What never to do

- **Do not disable a guard to make a number appear.** The guards exist because a
  confidently wrong number does more damage than a missing one. If a guard is wrong,
  change the guard deliberately and add a test for the new behaviour.
- **Do not hand-edit files on the `data` branch.** They are the record of what the
  APIs returned. If a value is wrong, fix the collector and let the next run correct it.
- **Do not add a stored secret to make a collector work.** `make offline` and
  `tests/test_no_secrets_required.py` both assume there are none, and the moment one
  exists forks can no longer run CI. If a source genuinely needs a credential, that is
  a decision to take in the open, with those tests updated in the same pull request.
