"""Find Play Store / App Store ids for a product (free, no tokens beyond reading the output).

  .venv/bin/python find_apps.py "razorpay"
"""
import re
import sys

import requests
from google_play_scraper import app as play_app
from google_play_scraper import search

from pf.collect_appstore import find_app_ids
from pf.collect_consumercomplaints import find_company



def resolve_hidden_id(term, title, known_ids):
    """The library sometimes returns the top result without its id. Look the id up on the
    public Play Store search page and confirm it by matching the app title."""
    try:
        html = requests.get("https://play.google.com/store/search",
                            params={"q": term, "c": "apps", "hl": "en", "gl": "in"},
                            headers={"User-Agent": "Mozilla/5.0"}, timeout=20).text
    except Exception:
        return None
    seen = []
    for cand in re.findall(r"/store/apps/details\?id=([A-Za-z0-9_.]+)", html):
        if cand in known_ids or cand in seen:
            continue
        seen.append(cand)
        if len(seen) > 5:
            break
        try:
            if play_app(cand, country="in").get("title") == title:
                return cand
        except Exception:
            pass
    return None


term = " ".join(sys.argv[1:])
print("Play Store (India):")
results = search(term, lang="en", country="in", n_hits=6)
known = {r["appId"] for r in results if r.get("appId")}
for r in results:
    app_id = r.get("appId") or resolve_hidden_id(term, r["title"], known)
    if not app_id:
        print(f"  (id not found)  |  {r['title']}  |  {r.get('developer', '')}  "
              f"-> open the app on play.google.com and copy what follows 'id=' in the link")
        continue
    reviews = ""
    if app_id:
        try:
            reviews = f"{play_app(app_id, country='in').get('reviews', 0)} written reviews"
        except Exception:
            pass
    print(f"  {app_id}  |  {r['title']}  |  {r.get('developer', '')}  {reviews}")
print("App Store (India):")
for tid, name, seller in find_app_ids(term, limit=6):
    print(f"  {tid}  |  {name}  |  {seller}")
print("ConsumerComplaints.in company pages (use the path in the case file):")
hits = find_company(term)
for path, name in hits[:8]:
    print(f"  {path}  |  {name}")
if not hits:
    print("  none found")
