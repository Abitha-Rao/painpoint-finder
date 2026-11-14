"""Apple App Store reviews via Apple's official public RSS feed (max ~500 per app)."""
import time
from datetime import datetime

import requests

from .common import USER_AGENT, cutoff_date, log, make_item


def collect(app_ids, months=12, country="in"):
    cutoff = cutoff_date(months)
    out = []
    for app_id in app_ids:
        kept = 0
        for page in range(1, 11):
            url = (f"https://itunes.apple.com/{country}/rss/customerreviews/"
                   f"page={page}/id={app_id}/sortby=mostrecent/json")
            try:
                r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=20)
                r.raise_for_status()
                entries = r.json().get("feed", {}).get("entry", [])
            except Exception as e:
                log(f"  App Store {app_id} page {page}: stopped ({e})")
                break
            if isinstance(entries, dict):
                entries = [entries]
            entries = [e for e in entries if "im:rating" in e]  # skip app-info entry
            if not entries:
                break
            stop = False
            for e in entries:
                dt = datetime.fromisoformat(e["updated"]["label"])
                if dt < cutoff:
                    stop = True
                    continue
                title = e.get("title", {}).get("label", "")
                body = e.get("content", {}).get("label", "")
                out.append(make_item(
                    source="appstore",
                    id=e["id"]["label"],
                    url=f"https://apps.apple.com/{country}/app/id{app_id}?see-all=reviews",
                    date=dt,
                    text=f"{title}. {body}" if title else body,
                    rating=int(e["im:rating"]["label"]),
                    meta={"app": app_id},
                ))
                kept += 1
            if stop:
                break
            time.sleep(0.5)
        log(f"  App Store {app_id}: {kept} reviews in window")
    return out


def find_app_ids(term, country="in", limit=5):
    """Helper for setup: look up App Store ids by name (official iTunes Search API)."""
    r = requests.get("https://itunes.apple.com/search",
                     params={"term": term, "country": country, "entity": "software", "limit": limit},
                     headers={"User-Agent": USER_AGENT}, timeout=20)
    return [(a["trackId"], a["trackName"], a.get("sellerName")) for a in r.json().get("results", [])]
