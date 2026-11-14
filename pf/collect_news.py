"""News headlines via Google News RSS (India edition). Used as context, not as complaints."""
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus

import feedparser

from .common import log, make_item

# Headlines with these words are flagged as "risk / negative" news.
NEWS_RISK_WORDS = [
    "outage", "down", "glitch", "rbi", "penalty", "fine", "fined", "ban", "banned",
    "fraud", "scam", "probe", "ed ", "raid", "breach", "leak", "complaint", "lawsuit",
    "court", "layoff", "layoffs", "halt", "suspend", "restrict", "action", "warning",
    "loss", "losses", "decline", "slump", "crackdown", "violation", "cyber",
]


def collect(query, months=12):
    days = int(months * 30.4)
    url = (f"https://news.google.com/rss/search?q={quote_plus(query)}+when:{days}d"
           f"&hl=en-IN&gl=IN&ceid=IN:en")
    feed = feedparser.parse(url)
    out = []
    for e in feed.entries:
        try:
            dt = parsedate_to_datetime(e.published)
        except Exception:
            dt = None
        source = getattr(getattr(e, "source", None), "title", None) or ""
        title = e.title
        low = f" {title.lower()} "
        risk = any(w in low for w in NEWS_RISK_WORDS)
        out.append(make_item("news", e.get("id", e.link), e.link, dt, title, title=title,
                             meta={"publisher": source, "risk": risk}))
    log(f"  News: {len(out)} headlines ({sum(i['meta']['risk'] for i in out)} flagged as risk)")
    return out
