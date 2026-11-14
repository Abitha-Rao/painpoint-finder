"""Sample-based estimates: how common is each pain point, with an error margin.

Every labelled sample under runs/<case>/ (eval_dev, eval, estimate, ...) is a random draw
from the same complaints, taken without overlap, so together they form one random
sample. A labeller read each complaint and picked its main problem. The share of the
sample per pain point estimates its share of all complaints; the Wilson interval gives
the 95% range.
"""
import math
from collections import Counter

from .common import read_json, write_json

VAGUE = "Too vague / none of these"


def wilson(k, n, z=1.96):
    if n == 0:
        return 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def labelled_items(run_dir):
    """{item id: pain point name or VAGUE} from every fully or partly labelled set."""
    out, sets = {}, []
    for d in sorted(p for p in run_dir.iterdir() if p.is_dir()):
        key = read_json(d / "answer_key_HIDDEN.json")
        human = read_json(d / "labels_human.json")
        if not key or not human:
            continue
        codes = key["codes"]
        used = 0
        for num, k in key["key"].items():
            raw = (human.get(num) or "").strip()
            if not raw:
                continue
            if raw.upper().startswith("N:"):
                # A theme the tool's groups missed, named by the labeller.
                out[k["id"]] = "New: " + raw[2:].strip()
                used += 1
                continue
            ans = raw.upper()[:1]
            out[k["id"]] = codes.get(ans, VAGUE) if ans != "X" else VAGUE
            used += 1
        if used:
            sets.append({"set": d.name, "labelled": used, "labeller": None})
    return out, sets


def compute(run_dir, labeller="Claude"):
    lab, sets = labelled_items(run_dir)
    n = len(lab)
    if n == 0:
        raise SystemExit("No labelled samples found.")
    counts = Counter(lab.values())
    n_specific = n - counts.get(VAGUE, 0)
    rows = []
    for name, k in counts.most_common():
        lo, hi = wilson(k, n)
        rows.append({"name": name, "k": k, "share": k / n, "lo": lo, "hi": hi,
                     "share_specific": (k / n_specific) if name != VAGUE and n_specific else None})
    res = {"n": n, "n_specific": n_specific, "labeller": labeller, "sets": sets,
           "rows": rows, "item_labels": lab}
    write_json(run_dir / "estimate.json", res)
    return res


def format_estimate(res):
    lines = [f"Sample-based estimate — {res['n']} random complaints labelled by {res['labeller']} "
             f"(sets: {', '.join(s['set'] for s in res['sets'])})"]
    for r in res["rows"]:
        lines.append(f"  {r['share']*100:4.0f}%  (95% range {r['lo']*100:.0f}–{r['hi']*100:.0f}%)  "
                     f"{r['k']:>3}/{res['n']}  {r['name']}")
    return "\n".join(lines)
