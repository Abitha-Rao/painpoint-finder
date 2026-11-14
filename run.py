"""Pain point finder — run a case.

  .venv/bin/python run.py cases/<case>.json                 # free mode: everything, 0 tokens
  .venv/bin/python run.py cases/<case>.json --stage prepare # collect + clean + group (lean mode step 1)
  .venv/bin/python run.py cases/<case>.json --stage report  # write the report (uses labels.json if present)

Add --reuse to skip re-downloading when raw data already exists for this case.
"""
import argparse
import sys
from collections import Counter

from pf import assign
from pf import clean as cleaner
from pf import collect_appstore, collect_consumercomplaints, collect_news, collect_playstore, collect_reddit
from pf import group as grouper
from pf import report as reporter
from pf.common import RUNS, log, read_json, read_jsonl, write_json, write_jsonl


def collect(case, raw_dir):
    m = case.get("months", 12)
    if case.get("playstore"):
        write_jsonl(raw_dir / "playstore.jsonl", collect_playstore.collect(case["playstore"], months=m))
    if case.get("appstore"):
        write_jsonl(raw_dir / "appstore.jsonl", collect_appstore.collect(case["appstore"], months=m))
    if case.get("reddit"):
        r = case["reddit"]
        write_jsonl(raw_dir / "reddit.jsonl",
                    collect_reddit.collect(r["query"], r.get("subreddits"), months=m))
    if case.get("consumercomplaints"):
        write_jsonl(raw_dir / "consumercomplaints.jsonl",
                    collect_consumercomplaints.collect(case["consumercomplaints"], months=m))
    if case.get("news_query"):
        write_jsonl(raw_dir / "news.jsonl", collect_news.collect(case["news_query"], months=m))


def prepare(case, out, reuse):
    raw_dir = out / "raw"
    if not (reuse and raw_dir.exists()):
        log("1/3 Collecting...")
        collect(case, raw_dir)
    else:
        log("1/3 Reusing raw data already downloaded")
    items = []
    for f in sorted(raw_dir.glob("*.jsonl")):
        if f.stem != "news":
            items.extend(read_jsonl(f))
    if not items:
        sys.exit("No complaints collected — check the app ids / queries in the case file.")
    log("2/3 Cleaning...")
    kept, stats = cleaner.clean(
        items, months=case.get("months", 12), max_rating=case.get("max_rating", 3),
        segment_keywords=case.get("segment_keywords"), exclude_keywords=case.get("exclude_keywords"),
        max_per_source=case.get("max_per_source", 600))
    write_jsonl(out / "clean.jsonl", kept)
    write_json(out / "clean_stats.json", {"stats": stats, "raw_counts": dict(Counter(i["source"] for i in items))})
    log("3/3 Grouping (free, on this Mac)...")
    groups = grouper.group(kept, product_terms=case.get("product_terms", []))
    write_json(out / "groups.json", groups)
    grouper.write_brief_for_claude(groups, {i["id"]: i for i in kept}, out / "brief_for_claude.md")
    # Group numbers change when the data changes, so old names no longer fit.
    if (out / "labels.json").exists():
        (out / "labels.json").replace(out / "labels.old.json")
        log("  Old group names moved to labels.old.json (groups have changed)")
    log(f"Prepared. Groups to name: {out / 'brief_for_claude.md'}")


def report(case, out):
    items = read_jsonl(out / "clean.jsonl")
    groups = read_json(out / "groups.json")
    if not items or not groups:
        sys.exit("Run --stage prepare first.")
    meta = read_json(out / "clean_stats.json", {})
    labels = read_json(out / "labels.json")
    news = read_jsonl(out / "raw" / "news.jsonl")
    if labels:
        log("Assigning each complaint to its closest pain point (free, on this Mac)...")
    groups, labels = assign.effective_groups(out, items, groups, labels)
    log("Writing report...")
    path, ranked = reporter.write_report(case, items, meta.get("raw_counts", {}), meta.get("stats", {}),
                                         groups, labels, news, out)
    for i, p in enumerate(ranked[:8], 1):
        e = p.get("est")
        if e:
            log(f"  {i}. {p['name']}: ~{e['share']*100:.0f}% (95% range {e['lo']*100:.0f}–{e['hi']*100:.0f}%, "
                f"{e['k']} of the sample)")
        else:
            log(f"  {i}. {p['name']}: {p['count']} ({p['share']*100:.0f}%, rough count), "
                f"{p['n_sources']} source(s), {p['trend']}")
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("case")
    ap.add_argument("--stage", choices=["all", "prepare", "report"], default="all")
    ap.add_argument("--reuse", action="store_true")
    a = ap.parse_args()
    case = read_json(a.case)
    out = RUNS / case["slug"]
    out.mkdir(parents=True, exist_ok=True)
    if a.stage in ("all", "prepare"):
        prepare(case, out, a.reuse)
    if a.stage in ("all", "report"):
        report(case, out)


if __name__ == "__main__":
    main()
