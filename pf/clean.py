"""Merge raw sources and keep only real, recent, relevant complaints."""
from collections import Counter

from .common import COMPLAINT_WORDS, cutoff_date, has_any, log, norm_for_dedupe, parse_iso

RATED_SOURCES = {"playstore", "appstore"}
# Every post on these sites is a complaint, so no complaint-word filter is needed.
COMPLAINT_SITES = {"consumercomplaints"}


def clean(items, months=12, max_rating=3, segment_keywords=None, exclude_keywords=None,
          max_per_source=600, min_chars=25):
    cutoff = cutoff_date(months)
    stats = Counter()
    seen, kept = set(), []
    for it in items:
        stats["raw"] += 1
        text = it["text"]
        if len(text) < min_chars:
            stats["too_short"] += 1
            continue
        dt = parse_iso(it["date"])
        if dt and dt < cutoff:
            stats["too_old"] += 1
            continue
        if it["source"] in RATED_SOURCES:
            if it["rating"] is not None and it["rating"] > max_rating:
                stats["positive_rating"] += 1
                continue
        elif it["source"] not in COMPLAINT_SITES and not has_any(text, COMPLAINT_WORDS):
            stats["not_a_complaint"] += 1
            continue
        if segment_keywords and not has_any(text, segment_keywords):
            stats["off_segment"] += 1
            continue
        if exclude_keywords and has_any(text, exclude_keywords):
            stats["excluded_keyword"] += 1
            continue
        key = norm_for_dedupe(text)
        if key in seen:
            stats["duplicate"] += 1
            continue
        seen.add(key)
        kept.append(it)

    # Cap each source so one site can't dominate. Pick evenly across the date range
    # (not just the newest) so older complaints keep their place.
    by_source = {}
    for it in sorted(kept, key=lambda x: x["date"] or ""):
        by_source.setdefault(it["source"], []).append(it)
    final = []
    for src, lst in by_source.items():
        if len(lst) > max_per_source:
            stats["capped"] += len(lst) - max_per_source
            step = len(lst) / max_per_source
            lst = [lst[int(i * step)] for i in range(max_per_source)]
        final.extend(lst)

    stats["kept"] = len(final)
    log("  Cleaning: " + ", ".join(f"{k}={v}" for k, v in stats.items()))
    return final, dict(stats)
