"""Find Play Store / App Store ids for a product (free, no tokens beyond reading the output).

  .venv/bin/python find_apps.py "razorpay"
"""
import sys

from google_play_scraper import app as play_app
from google_play_scraper import search

from pf.collect_appstore import find_app_ids
from pf.collect_consumercomplaints import find_company

term = " ".join(sys.argv[1:])
print("Play Store (India):")
for r in search(term, lang="en", country="in", n_hits=6):
    app_id = r.get("appId")
    if not app_id:
        # Known library quirk: the top "featured" result sometimes has no id.
        print(f"  (id not shown)  |  {r['title']}  |  {r.get('developer', '')}  "
              f"-> find it in the app's play.google.com link after 'id='")
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
