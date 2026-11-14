"""Accuracy check for a case that already has a report.

  .venv/bin/python eval.py cases/<case>.json sample [--n 50]   # writes runs/<case>/eval/sheet.md
  (fill in runs/<case>/eval/labels_human.json: {"1": "A", "2": "X", ...})
  .venv/bin/python eval.py cases/<case>.json score [--labeller "Claude"]
  .venv/bin/python run.py cases/<case>.json --stage report     # report now includes the result

--set NAME keeps several samples apart (default "eval"; the report shows "eval").
--exclude-set NAME draws a fresh sample that avoids the complaints in another set.
Running `sample` again on an existing set re-checks the same complaints against the
current tool (your answers are kept).

Never open answer_key_HIDDEN.json before labelling; that would spoil the blind check.
"""
import argparse

from pf import assign, estimate, evaluate
from pf.common import RUNS, read_json, read_jsonl


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("case")
    ap.add_argument("action", choices=["sample", "score", "estimate"])
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--labeller", default="Claude")
    ap.add_argument("--set", default="eval")
    ap.add_argument("--exclude-set")
    a = ap.parse_args()
    case = read_json(a.case)
    out = RUNS / case["slug"]
    ev = out / a.set
    if a.action == "sample":
        items = read_jsonl(out / "clean.jsonl")
        groups = read_json(out / "groups.json")
        labels = read_json(out / "labels.json")
        if not items or not groups:
            raise SystemExit("Run the case first (run.py --stage prepare).")
        groups, labels = assign.effective_groups(out, items, groups, labels)
        exclude = []
        for s in (a.exclude_set or "").split(","):
            if s.strip():
                k = read_json(out / s.strip() / "answer_key_HIDDEN.json")
                exclude += [v["id"] for v in k["key"].values()]
        path = evaluate.make_sample(items, groups, labels, ev, n=a.n, seed=a.seed, exclude_ids=exclude)
        print(f"Blind sheet: {path}\nAnswers go in: {ev / 'labels_human.json'}")
    elif a.action == "score":
        res = evaluate.score(ev, labeller=a.labeller)
        print(evaluate.format_results(res))
    else:
        res = estimate.compute(out, labeller=a.labeller)
        print(estimate.format_estimate(res))


if __name__ == "__main__":
    main()
