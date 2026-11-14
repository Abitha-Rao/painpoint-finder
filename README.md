# Pain point finder: customer pain points from app reviews, for product managers

**Find a product's top customer pain points from public app reviews and complaints, with
numbers you can defend.** A user-research and voice-of-customer tool for product management
case studies, PM interviews and case competitions, built around Indian products.

A case prompt like "improve Razorpay for merchants" becomes: "about 18% of public complaints
are login failures (95% range 12–27%), and here are the quotes with links". The output is a
Word report with ranked pain points, estimated shares, real customer quotes and sources.

- **Review analysis without an API key.** It runs as a [Claude Code](https://claude.com/claude-code)
  skill on your existing subscription, or with no AI at all (free mode).
- **Sources:** Google Play Store reviews, Apple App Store reviews, Reddit, ConsumerComplaints.in
  and Google News (India editions).
- **Runs locally.** Scraping, cleaning and topic clustering of reviews happen on your machine
  with an open-source sentence-embedding model.
- **Honest numbers.** Shares come from a hand-labelled random sample with confidence intervals,
  and a built-in accuracy check tells you how far to trust the automatic grouping.

## What you get

For Swiggy (customers), from 1,043 complaints and a labelled sample of 150:

| Pain point | Estimated share | 95% range |
|---|---|---|
| Late delivery and inaccurate ETAs | ~23% | 17–31% |
| Cancelled or undelivered orders, refunds refused | ~17% | 12–24% |
| High delivery, platform and packaging fees | ~7% | 4–13% |

Each pain point comes with customer quotes, source links and a slide-ready one-liner, plus a
short `findings.md` you can hand to a deck-building step. Results as of November 2026; they
change as new reviews are posted.

## Who it's for

- Aspiring and working product managers doing secondary research for a case or interview.
- MBA students in case competitions who need evidence for a problem statement.
- Founders and analysts who want a quick read on what users complain about for a competitor
  or their own app (fintech, food delivery, e-commerce, quick commerce, and so on).

## Install

Needs Python 3.10+ and about 1.5 GB of disk (a local language model downloads on first run).

```
git clone https://github.com/Abitha-Rao/painpoint-finder.git && cd painpoint-finder
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q        # optional: quick checks
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
3. Run `.venv/bin/python setup_reddit.py` and paste the client id (under the app name) and
   the secret when asked. Typing is hidden; the script tests the keys and saves them to `.env`.

## Security

- Your Reddit keys live only in `.env`, which is git-ignored and readable only by you. Never
  commit it or paste keys into an issue.
- `runs/` (collected reviews and reports) is git-ignored too. Keep it that way if you fork.
- The tool makes requests only to the review sources listed above and, on first run, to
  Hugging Face to download the open-source model. It sends your data nowhere else.
- Found a security problem? Please open a GitHub issue without including any secrets.

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
