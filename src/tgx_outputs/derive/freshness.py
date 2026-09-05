"""How old is every number on this page?

The single rule: freshness is computed from the data's own ``fetched_at``, never from
the build clock. A page that renders ``datetime.now()`` in a "last updated" line is
claiming freshness it has not verified -- which is exactly how an earlier reporting
dashboard displayed two-month-old numbers under today's date for eight weeks without
anyone noticing.

A source is amber past twice its declared cadence and red past five times.

Freshness is age, and nothing else. Whether a source returned *everything* asked of it
is a separate question with a separate answer -- ``complete`` per row, and the
``incomplete`` list on the result. Collapsing the two used to make a source that had
answered ten seconds ago but was missing one row of thirty-three read as "needs
attention, 0d", which is a contradiction on its face and, worse, a warning that could
never be cleared: one paper OpenAlex will never index would have held the banner amber
for good, until nobody read it any more.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from ..config import cadence_days


def _age_days(stamp: str, now: dt.datetime) -> float:
    when = dt.datetime.fromisoformat(stamp)
    if when.tzinfo is None:
        when = when.replace(tzinfo=dt.UTC)
    return (now - when).total_seconds() / 86400.0


def assess(snapshot: dict[str, Any], now: dt.datetime | None = None) -> dict[str, Any]:
    now = now or dt.datetime.now(dt.UTC)
    rows = []
    worst = "fresh"
    for name, src in sorted(snapshot.get("sources", {}).items()):
        status = src.get("status", "unknown")
        if status == "skipped":
            continue
        age = _age_days(src["fetched_at"], now)
        cadence = cadence_days(name)
        # `failed` stays red regardless of the clock. Its `fetched_at` is when the
        # attempt was made, not when the numbers on the page were gathered -- the store
        # keeps the last good records until midnight -- so age alone would call data
        # from an unknown earlier run fresh.
        if status == "failed" or age > cadence * 5:
            level = "red"
        elif age > cadence * 2:
            level = "amber"
        else:
            level = "fresh"
        if level == "red" or (level == "amber" and worst != "red"):
            worst = level
        rows.append({
            "source": name,
            "status": status,
            "age_days": round(age, 1),
            "cadence_days": cadence,
            "level": level,
            "complete": status == "ok",
            "expected": src.get("expected"),
            "found": src.get("found"),
            "unit": src.get("unit") or "records",
            "record_count": src.get("record_count", 0),
            "fetched_at": src["fetched_at"],
        })

    # "Refreshed" means the source answered us today, which a degraded one did. Only a
    # failure means we never heard back.
    refreshed = sum(1 for r in rows if r["status"] != "failed")
    incomplete = [r for r in rows if not r["complete"]]
    return {
        "collected_on": snapshot.get("collected_on"),
        "sources": rows,
        "ok": sum(1 for r in rows if r["status"] == "ok"),
        "refreshed": refreshed,
        "incomplete": incomplete,
        "total": len(rows),
        "level": worst,
        "summary": _summary(rows, refreshed, incomplete, snapshot.get("collected_on")),
    }


def _describe(row: dict[str, Any]) -> str:
    """One incomplete source, with the fraction it managed if it counted one."""
    if row["expected"] and row["found"] is not None:
        return f"{row['source']} ({row['found']} of {row['expected']} {row['unit']} found)"
    return row["source"]


def _summary(rows: list[dict[str, Any]], refreshed: int,
             incomplete: list[dict[str, Any]], collected_on: str | None) -> str:
    """Age first, completeness second, and never the one dressed up as the other."""
    head = f"{refreshed} of {len(rows)} sources refreshed {collected_on}"
    parts = []
    stale = [r for r in rows if r["level"] != "fresh"]
    if stale:
        parts.append("needs attention: " + ", ".join(
            f"{r['source']} ({r['status']}, {r['age_days']:.0f}d)" for r in stale))
    if incomplete:
        plural = "" if len(incomplete) == 1 else "s"
        parts.append(f"{len(incomplete)} source{plural} incomplete: "
                     + ", ".join(_describe(r) for r in incomplete))
    return head + ("" if not parts else " - " + " - ".join(parts))
