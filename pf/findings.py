"""Write a short findings file (Markdown) that a deck-building step can read cheaply."""
from pathlib import Path

from .common import parse_iso


def write_findings(case, specific, est, total, sources, out_dir, top_n=4):
    lines = [f"# {case['name']}: pain point findings", ""]
    if est:
        lines.append(f"Method: {total} public complaints collected ({', '.join(sources)}); a random sample of "
                     f"{est['n']} was read and labelled one by one. Shares are estimates with a 95% range.")
    else:
        lines.append(f"Method: {total} public complaints collected ({', '.join(sources)}), grouped automatically. "
                     "Counts are rough.")
    lines += ["", "## Ranked pain points", ""]
    for rank, pp in enumerate(specific, 1):
        e = pp.get("est")
        if e:
            num = f"~{e['share']*100:.0f}% (95% range {e['lo']*100:.0f}–{e['hi']*100:.0f}%, {e['k']}/{est['n']} sampled)"
        else:
            num = f"{pp['share']*100:.0f}% ({pp['count']}/{total}, rough count)"
        lines.append(f"{rank}. **{pp['name']}**: {num}")
        if pp.get("definition") and not pp.get("new"):
            lines.append(f"   - {pp['definition']}")
        if rank <= top_n:
            for q in pp["quotes"][:2]:
                d = parse_iso(q["date"])
                text = " ".join(q["text"].split())
                text = text if len(text) <= 220 else text[:220].rsplit(" ", 1)[0] + "…"
                lines.append(f"   - Quote ({q['source']}, {d.strftime('%b %Y') if d else 'undated'}): "
                             f"“{text}” [{q['url']}]")
    if case.get("official_stats"):
        lines += ["", "## Official context (sector-wide)", ""]
        lines += [f"- {o['stat']} ({o.get('source', '')}) [{o.get('url', '')}]" for o in case["official_stats"]]
    lines += ["", "## Caveats", "",
              "- Public complaints only: vocal, unhappy users; not a measure of how many users are affected.",
              "- Pain points with overlapping ranges cannot be ranked against each other."]
    path = Path(out_dir) / "findings.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
