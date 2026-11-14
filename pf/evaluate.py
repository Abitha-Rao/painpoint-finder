"""Accuracy check: does each complaint land in the right pain point?

1. sample: draw a random sample and write a BLIND sheet (complaint text + the list of
   pain points, but NOT which one the tool chose). The tool's answers go to a hidden key file.
2. A labeller (Claude or a person) picks the right pain point for each complaint.
3. score: compare the labeller's answers with the tool's and report agreement.
"""
import random
import re
import string
from collections import Counter

from .common import read_json, write_json
from .report import build_pain_points

NONE_CODE = "X"


def _pain_point_codes(items, groups, labels, keep_codes=None):
    """Letter per pain point. keep_codes ({letter: name}) keeps letters stable when re-keying
    an existing sheet, so earlier answers still mean the same pain point."""
    specific, vague, _ = build_pain_points(items, groups, labels)
    codes = {}
    if keep_codes:
        by_name = {pp["name"]: pp for pp in specific}
        for code, name in keep_codes.items():
            if name in by_name:
                codes[code] = by_name.pop(name)
        free = [c for c in string.ascii_uppercase if c not in codes and c != NONE_CODE]
        for code, pp in zip(free, by_name.values()):
            codes[code] = pp
    else:
        for code, pp in zip(string.ascii_uppercase, specific):
            codes[code] = pp
    assign = {}
    for code, pp in codes.items():
        for i in pp["ordered_ids"]:
            assign[i] = code
    for pp in vague:
        for i in pp["ordered_ids"]:
            assign[i] = NONE_CODE
    return codes, assign


def make_sample(items, groups, labels, out_dir, n=50, seed=7, max_chars=350, exclude_ids=()):
    old = read_json(out_dir / "answer_key_HIDDEN.json")
    codes, assign = _pain_point_codes(items, groups, labels, keep_codes=old["codes"] if old else None)
    rng = random.Random(seed)
    pool = [it for it in items if it["id"] not in set(exclude_ids)]
    pick = rng.sample(pool, min(n, len(pool)))
    lines = ["# Accuracy check: blind labelling sheet", "",
             "For each complaint, choose the ONE pain point that best describes its main problem.",
             f"Use {NONE_CODE} if it is too vague or fits none of them.", "", "## Pain points"]
    for code, pp in codes.items():
        lines.append(f"- **{code}** {pp['name']}: {pp['definition']}")
    lines.append(f"- **{NONE_CODE}** Too vague / none of these")
    lines.append("- **N:<short name>** A specific, recurring problem none of the above covers "
                 "(use the same name each time)")
    lines += ["", "## Complaints", ""]
    key = {}
    for num, it in enumerate(pick, 1):
        t = re.sub(r"\s+", " ", it["text"])
        t = t if len(t) <= max_chars else t[:max_chars] + "…"
        lines.append(f"{num}. {t}")
        key[str(num)] = {"id": it["id"], "tool": assign.get(it["id"], NONE_CODE)}
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "sheet.md").write_text("\n".join(lines), encoding="utf-8")
    write_json(out_dir / "answer_key_HIDDEN.json",
               {"codes": {c: p["name"] for c, p in codes.items()}, "key": key})
    template = {str(k): "" for k in range(1, len(pick) + 1)}
    if not (out_dir / "labels_human.json").exists():
        write_json(out_dir / "labels_human.json", template)
    return out_dir / "sheet.md"


def score(out_dir, labeller="Claude"):
    keyf = read_json(out_dir / "answer_key_HIDDEN.json")
    human = read_json(out_dir / "labels_human.json")
    names = dict(keyf["codes"], **{NONE_CODE: "Too vague / none"})
    pairs = []
    for num, k in keyf["key"].items():
        raw = (human.get(num) or "").strip()
        # A new theme the tool has no group for counts as "none of these" when scoring.
        h = NONE_CODE if raw.upper().startswith("N:") else raw.upper()[:1]
        if h:
            pairs.append((k["tool"], h))
    if not pairs:
        raise SystemExit("labels_human.json has no answers yet.")
    n = len(pairs)
    agree = sum(t == h for t, h in pairs)
    # Among complaints the labeller says are specific, did the tool find the same pain point?
    spec = [(t, h) for t, h in pairs if h != NONE_CODE]
    spec_agree = sum(t == h for t, h in spec)

    per = {}
    for code in names:
        tool_said = [h for t, h in pairs if t == code]
        human_said = [t for t, h in pairs if h == code]
        if not tool_said and not human_said:
            continue
        per[code] = {
            "name": names[code],
            "tool_count": len(tool_said),
            "human_count": len(human_said),
            # precision: of complaints the tool put here, share the labeller agreed with
            "precision": (sum(1 for h in tool_said if h == code) / len(tool_said)) if tool_said else None,
            # recall: of complaints the labeller put here, share the tool also put here
            "recall": (sum(1 for t in human_said if t == code) / len(human_said)) if human_said else None,
        }
    confusions = Counter((t, h) for t, h in pairs if t != h).most_common(5)
    res = {
        "labeller": labeller, "n": n, "agree": agree, "accuracy": agree / n,
        "n_specific": len(spec), "specific_accuracy": (spec_agree / len(spec)) if spec else None,
        "per_pain_point": per,
        "top_confusions": [{"tool": names[t], "labeller": names[h], "count": c} for (t, h), c in confusions],
    }
    write_json(out_dir / "results.json", res)
    return res


def format_results(res):
    lines = [f"Accuracy check — {res['n']} random complaints labelled blind by {res['labeller']}",
             f"  Overall agreement: {res['agree']}/{res['n']} = {res['accuracy']*100:.0f}%"]
    if res["specific_accuracy"] is not None:
        lines.append(f"  On complaints with a specific problem: {res['specific_accuracy']*100:.0f}% "
                     f"({res['n_specific']} complaints)")
    lines.append("  Per pain point (precision = tool's picks the labeller agreed with; "
                 "recall = labeller's picks the tool also found):")
    for code, p in res["per_pain_point"].items():
        pr = f"{p['precision']*100:.0f}%" if p["precision"] is not None else "–"
        rc = f"{p['recall']*100:.0f}%" if p["recall"] is not None else "–"
        lines.append(f"    {code} {p['name'][:55]:<55} precision {pr:>4} ({p['tool_count']}), "
                     f"recall {rc:>4} ({p['human_count']})")
    if res["top_confusions"]:
        lines.append("  Most common disagreements (tool → labeller):")
        for c in res["top_confusions"]:
            lines.append(f"    {c['count']}× {c['tool']} → {c['labeller']}")
    return "\n".join(lines)
