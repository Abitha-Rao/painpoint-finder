# Pain point finder (v0)

Finds the top real pain points for a product from public complaints and writes a Word report
with estimated shares, ranges, quotes and source links. Built for PM case prep on Indian
products: "improve Razorpay for merchants" becomes "about 18% of public complaints are login
failures (95% range 12–27%), here are the quotes".

It runs on your own machine. With [Claude Code](https://claude.com/claude-code) it uses your
subscription for the small amount of reading that needs judgment; no API key is needed. It
also runs with no AI at all (free mode).

## Install

Needs Python 3.10+ and about 1.5 GB of disk (a local language model downloads on first run).

```
git clone https://github.com/Abitha-Rao/painpoint-finder.git && cd painpoint-finder
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q        # optional: 5 quick checks
```

Tested on macOS (Apple Silicon). On Windows use `.venv\Scripts\python` in place of
`.venv/bin/python`.

## Know the limits before you quote numbers

- The automatic grouping is rough: in blind checks it agreed with a careful reader on about
  half of complaints. That is why reports lead with **sample-based estimates** (see below)
  and show the tool's own counts only as "rough".
- Public complaints come from vocal, unhappy users. They show what people complain about,
  not how many users are affected.
- The two cases in `cases/` are examples. Results change as new reviews are posted.

## Use responsibly

This collects public reviews for personal research. It respects each site's robots.txt,
spaces out requests, stores no author names, and leaves out sites that block crawlers.
Keep it that way: don't raise request rates, don't republish collected reviews in bulk, and
check a site's terms before adding it as a source.

## Use it

Open this folder in Claude Code and type:

```
/painpoints Swiggy delivery partners, last 12 months
```

Add "free mode" to use no Claude tokens at all (labels are automatic and rougher).

Reports land in `runs/<case>/<case>-pain-points.docx`.

## How tokens are used

| Step | Who | Tokens |
|---|---|---|
| Collect reviews, Reddit, news | scripts | 0 |
| Clean, remove duplicates, filter | scripts | 0 |
| Group similar complaints | local model on your machine | 0 |
| Name the groups (lean mode) | Claude reads ~40–60 sample complaints | small |
| Estimate shares (lean mode) | Claude labels a random sample of ~100 | small–medium |
| Count, rank, charts, Word report | scripts | 0 |

## Sources in v0

- Google Play reviews (India)
- App Store reviews (India, Apple's official feed, max ~500 per app)
- Reddit, via the official API (needs keys, see below)
- ConsumerComplaints.in (company page listings; strong for consumer brands, thin for B2B)
- Google News headlines (India), as context

Not collected, on purpose: MouthShut (its robots.txt blocks Claude/Anthropic bots),
Trustpilot (blocks all crawlers), Voxya (company pages only load through a private API).

## Reddit setup (one time, free)

1. Log in to Reddit and open https://www.reddit.com/prefs/apps
2. "Create another app" → type **script** → any name → redirect uri `http://localhost:8080`
3. Copy `.env.example` to `.env` and paste the client id (under the app name) and secret.

## Accuracy check

Ask Claude for "an accuracy check" after a run, or do it yourself (zero tokens):

```
.venv/bin/python eval.py cases/<case>.json sample --n 50
# open runs/<case>/eval/sheet.md, fill runs/<case>/eval/labels_human.json with letters
.venv/bin/python eval.py cases/<case>.json score --labeller "Me"
.venv/bin/python run.py cases/<case>.json --stage report
```

Don't open `answer_key_HIDDEN.json` until you've labelled.

### What the checks showed (Swiggy, Nov 2026)

| Method | Fresh blind sample (50) | Specific complaints only |
|---|---|---|
| Free grouping only | 21/50 (42%) | 14/33 |
| Free grouping + assign to closest definition (current) | 23/50 (46%) | 14/33 |

Distinct topics (late delivery) are reliable (100% of the tool's picks confirmed). Overlapping
ones (refunds vs support vs missing items) are not. Tuning on one sample looked like 62%
but didn't hold on a fresh one, so always check on a sample you didn't tune on.
Stronger free models (multilingual-e5-small/base) gave no clear gain.

## Sample-based estimates (what the report leads with)

The tool's counts are rough, so in lean mode the headline numbers come from a random sample
of complaints read and labelled one by one (blind to the tool's grouping). All labelled sets
for a case (`eval_dev`, `eval`, `estimate`, …) are pooled, since each is a random draw
without overlap. Shares get a 95% Wilson range, e.g. "~23% of complaints (17–31%)".

```
.venv/bin/python eval.py cases/<case>.json sample --set estimate --n 100 --exclude-set eval
# label runs/<case>/estimate/labels_human.json
.venv/bin/python eval.py cases/<case>.json estimate
.venv/bin/python run.py cases/<case>.json --stage report
```

Rough range width: ±7 points at 150 complaints, ±10 at 100, ±13 at 50.

## Other outputs

- `runs/<case>/findings.md`: a short summary (ranked pain points, numbers, quotes, links) to
  hand to a deck-building skill.
- Official figures: add `official_stats` to the case file (`stat`, `source`, `url`) and the
  report gets an "Official and regulator context" section.

## Tests

```
.venv/bin/python -m pytest -q
```

## Running without Claude

```
.venv/bin/python find_apps.py "zomato"
.venv/bin/python run.py cases/<case>.json            # free mode, end to end
```
