---
name: painpoints
description: Find the top real customer pain points for a product (e.g. "Razorpay merchants") from public reviews, Reddit and news, and produce a Word report with estimated shares, ranges and quotes. Use when the user says /painpoints, or asks for pain points / secondary research / data backing for a PM case.
---

# Pain point finder

Turns a PM case prompt ("improve Razorpay for merchants") into a data-backed Word report.
Scripts do almost everything for free on the user's machine. **Keep token use small**: the
user may be on a limited subscription and need their quota for other work.

## Token rules (important)
- Never read `runs/*/raw/*.jsonl`, `clean.jsonl`, `groups.json`, the answer keys or the .docx.
  They are large, or reading them spoils a blind check.
- The only files you read under `runs/<slug>/` are `brief_for_claude.md`, the `sheet.md` of a
  labelling step, and `findings.md` (short; use it for the final numbers).
- Web search: only for the official-figures step, and only when the user asks for official or
  regulator figures. Otherwise don't search.
- Keep replies short: the report has the detail.

## Steps

Run everything from the project folder with `.venv/bin/python`.

1. **Understand the ask.** Product, which users (merchants, customers, drivers…), period
   (default 12 months), mode: **lean** (default) or **free** (if the user says "free",
   "no tokens" or "save tokens").

2. **Make the case file.** Find app ids:
   `.venv/bin/python find_apps.py "<product>"`
   Pick the apps this user type actually uses. Skip unrelated apps, apps with almost no
   reviews, and sibling apps for a different user type or product (for a "customers" case,
   leave out the merchant app and separate products such as an investing app). Say which you
   left out. If an id shows as "(id not found)", ask the user for the app's Play Store link;
   don't fill it in from memory.
   Copy `cases/_template.json` to `cases/<slug>.json` and fill in:
   - `name`, `slug`, `segment_label` ("public" unless every source is one user type)
   - `playstore`, `appstore` ids
   - `consumercomplaints`: the company page path(s) `find_apps.py` printed, e.g. `["/swiggy-b115762"]`
     (leave `[]` if none was found)
   - `reddit.query` and 3–5 likely Indian subreddits
   - `news_query`
   - `product_terms`: product/brand words to ignore when labelling groups
   - `official_stats`: leave `[]` unless the user asked for official figures. If they did, do
     one web search for 1–2 sector-wide figures from a regulator or government body (RBI
     Ombudsman for fintech, National Consumer Helpline for e-commerce and food, TRAI for
     telecom), each as `{"stat": "...", "source": "...", "url": "..."}`. Only add figures you
     opened and checked, and say in the stat what they do not cover.
   - Leave these at their defaults unless the user asks: `months` (period), `max_rating` (3 =
     keep 1–3★ reviews), `max_per_source` (cap so one source can't dominate),
     `exclude_keywords` (drop complaints containing these words), `segment_keywords` (keep
     only complaints containing these words; use only when sources mix user types).
   Show the user the apps and subreddits in one or two lines and carry on unless they object.

3. **Collect, clean, group (free):**
   `.venv/bin/python run.py cases/<slug>.json --stage prepare`
   (add `--reuse` to skip re-downloading). If few complaints come back (< 80), tell the user
   the numbers will be thin.

4. **Name the groups.**
   - **Lean mode:** read `runs/<slug>/brief_for_claude.md` and write `runs/<slug>/labels.json`:
     ```json
     {"<group id>": {"name": "...", "definition": "one line", "severity": "money|blocked|annoyance", "vague": false}}
     ```
     - Names are specific and neutral ("Settlement delays", not "Bad payouts").
     - The definition describes the **problem**, never the group ("Support is hard to reach",
       not "this group also holds mixed complaints"). It is shown to the labeller later.
     - Optionally add `"examples": ["short phrase", ...]` (3–4 typical wordings).
     - Give two groups the same name if they are the same problem (they merge).
     - `vague: true` for groups that are only rants ("worst app"), mixed topics, or grouped by
       language rather than topic (e.g. a Hindi/Hinglish group covering many issues).
     - Flag it in the definition if a group comes from a different user type than the case
       (e.g. end customers in a merchant case).
   - **Free mode:** skip this step; the report uses automatic labels.

5. **Estimate shares from a labelled sample (lean mode only).** The tool's own counts are
   rough (blind checks: about half agree with a careful reader), so the report leads with
   sample estimates:
   - `.venv/bin/python eval.py cases/<slug>.json sample --set estimate --n 100 --seed 23`
     (add `--exclude-set eval,eval_dev` for any sets that already exist; they get pooled in)
   - Read ONLY `runs/<slug>/estimate/sheet.md` and write `runs/<slug>/estimate/labels_human.json`
     with one letter per complaint (main problem; `X` if vague / none).
     If a specific problem keeps recurring that no letter covers, write `"N:<short name>"`
     (same name every time) instead of `X`; the report lists it as a new theme.
   - `.venv/bin/python eval.py cases/<slug>.json estimate`
   - If the user wants to save tokens, use `--n 50` and say the ranges will be wider.

6. **Write the report (free):**
   `.venv/bin/python run.py cases/<slug>.json --stage report`
   It prints the ranked list (estimates with ranges in lean mode, rough counts in free mode)
   and writes `runs/<slug>/findings.md`, a short summary with numbers, quotes and links.
   Tell the user the report path, the top 3–4 pain points with their share and range, which
   ones can't be ranked against each other (overlapping ranges), and anything that limits the
   data (missing sources, short date coverage, small sample).
   If the user then wants slides, give `findings.md` (not the .docx) to a deck-building skill
   as the problem-and-data input.

## Accuracy check (when the user asks for evals / an accuracy check)
1. `.venv/bin/python eval.py cases/<slug>.json sample --n 50`
2. Read ONLY `runs/<slug>/eval/sheet.md`.
3. For each complaint pick the one letter for its main problem (`X` if vague / none fits) and
   write `runs/<slug>/eval/labels_human.json` (`{"1": "A", ...}`). If the user labels instead,
   tell them to fill that file and pass `--labeller "<their name>"` when scoring.
4. `.venv/bin/python eval.py cases/<slug>.json score`, then re-run `--stage report`
   (the report gains an "Accuracy check" section).
5. Tell the user the overall agreement and which pain points have low confirmation.

## Sources we don't collect
- **Reddit** needs free API keys (the user runs `.venv/bin/python setup_reddit.py`). Without
  them it is skipped and the report says which sources were used. Don't try other ways to get
  Reddit data, and never ask the user to paste keys into the chat.
- **MouthShut** (blocks Claude/Anthropic bots), **Trustpilot** (blocks all crawlers) and
  **Voxya** (no public company listing) are deliberately left out. Don't scrape them. If
  the user wants them, suggest they read a few pages themselves and paste quotes in.
