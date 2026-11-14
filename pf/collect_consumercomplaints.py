"""ConsumerComplaints.in — public complaints listed on a company's page.

Respects the site's robots.txt (its search pages are off-limits, so companies are found
via the A–Z company list) and its terms: no author names or locations are stored.
Requests are spaced out to keep load low.
"""
import re
import time
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from .common import USER_AGENT, cutoff_date, log, make_item

BASE = "https://www.consumercomplaints.in"
DELAY = 2.0  # seconds between requests


def _get(url):
    r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
    r.raise_for_status()
    return r.text


def _parse_date(s):
    s = (s or "").strip()
    for fmt in ("%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass
    return None


def _parse_page(html):
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for box in soup.select("div.complaint-box"):
        cid = (box.get("id") or "").lstrip("c")
        link = box.select_one("a.complaint-box__link")
        body = box.select_one("div.complaint-box__more-txt")
        if not cid or not link or not body:
            continue
        for t in body.select("table.custom-fields"):  # address / website fields
            t.decompose()
        text = body.get_text(" ").replace("[protected]", "")  # site masks phone/order numbers
        text = re.sub(r"\s+", " ", text).strip()
        date_el = box.select_one(".author-box__date")
        out.append({
            "id": cid,
            "title": link.get_text(" ", strip=True),
            "url": BASE + link["href"],
            "date": _parse_date(date_el.get_text() if date_el else ""),
            "text": text,
            "resolved": bool(box.select_one(".complaint-box__resolved")),
        })
    return out


def collect(company_paths, months=12, max_pages=15):
    """company_paths: e.g. ["/razorpay-b115695"] (find with find_apps.py)."""
    cutoff = cutoff_date(months).replace(tzinfo=None)
    out = []
    for path in company_paths:
        kept = 0
        for page in range(1, max_pages + 1):
            url = BASE + path + ("" if page == 1 else f"/page/{page}")
            try:
                rows = _parse_page(_get(url))
            except Exception as e:
                log(f"  ConsumerComplaints.in {path} page {page}: stopped ({e})")
                break
            if not rows:
                break
            for r in rows:
                if r["date"] and r["date"] < cutoff:
                    continue
                out.append(make_item(
                    source="consumercomplaints", id=r["id"], url=r["url"], date=r["date"],
                    text=f"{r['title']}. {r['text']}", title=r["title"],
                    meta={"company": path, "resolved": r["resolved"]},
                ))
                kept += 1
            dated = [r["date"] for r in rows if r["date"]]
            if dated and max(dated) < cutoff:
                break  # whole page is older than the window
            time.sleep(DELAY)
        log(f"  ConsumerComplaints.in {path}: {kept} complaints in window")
    return out


def find_company(term, max_list_pages=40):
    """Look up a company's page via the A–Z company list (the site's search is off-limits)."""
    term_l = term.lower().strip()
    letter = term_l[0] if term_l[0].isalpha() else "0"
    found = []
    for page in range(1, max_list_pages + 1):
        url = f"{BASE}/company-list/{letter}" + ("" if page == 1 else f"/page/{page}")
        try:
            html = _get(url)
        except Exception:
            break
        soup = BeautifulSoup(html, "html.parser")
        links = soup.select("a[href]")
        hits = [(a["href"], a.get_text(" ", strip=True)) for a in links
                if re.fullmatch(r"/[a-z0-9-]+-b\d+", a["href"]) and term_l in a.get_text(" ", strip=True).lower()]
        found.extend(h for h in hits if h not in found)
        if found:
            break
        if f"/company-list/{letter}/page/{page + 1}" not in html:
            break
        time.sleep(1.0)
    return found
