"""Reddit posts + comments via Reddit's official API.

Needs free API keys in .env (see README):
    REDDIT_CLIENT_ID=...
    REDDIT_CLIENT_SECRET=...
Without them, this source is skipped.
"""
import os
import time
from datetime import datetime, timezone

import requests

from .common import COMPLAINT_WORDS, USER_AGENT, cutoff_date, has_any, load_env, log, make_item


def _token():
    load_env()
    cid, secret = os.environ.get("REDDIT_CLIENT_ID"), os.environ.get("REDDIT_CLIENT_SECRET")
    if not cid or not secret:
        return None
    r = requests.post("https://www.reddit.com/api/v1/access_token",
                      auth=(cid, secret), data={"grant_type": "client_credentials"},
                      headers={"User-Agent": USER_AGENT}, timeout=20)
    r.raise_for_status()
    return r.json()["access_token"]


def collect(query, subreddits=None, months=12, max_posts=150, comments_per_post=40):
    token = _token()
    if not token:
        log("  Reddit: skipped (no REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET in .env)")
        return []
    h = {"Authorization": f"bearer {token}", "User-Agent": USER_AGENT}
    cutoff = cutoff_date(months)
    t = "year" if months <= 12 else "all"

    searches = [("https://oauth.reddit.com/search", {})]
    for sub in subreddits or []:
        searches.append((f"https://oauth.reddit.com/r/{sub}/search", {"restrict_sr": 1}))

    posts = {}
    for url, extra in searches:
        params = {"q": query, "t": t, "limit": 100, "sort": "relevance", **extra}
        try:
            r = requests.get(url, headers=h, params=params, timeout=20)
            r.raise_for_status()
        except Exception as e:
            log(f"  Reddit search {url}: failed ({e})")
            continue
        for c in r.json()["data"]["children"]:
            p = c["data"]
            if p["id"] not in posts:
                posts[p["id"]] = p
        time.sleep(1)

    out = []
    ranked = sorted(posts.values(), key=lambda p: p.get("num_comments", 0), reverse=True)[:max_posts]
    q = query.lower()
    for p in ranked:
        dt = datetime.fromtimestamp(p["created_utc"], tz=timezone.utc)
        if dt < cutoff:
            continue
        text = f"{p.get('title', '')}. {p.get('selftext', '')}"
        if q not in text.lower():
            continue  # search can return loosely related posts
        link = "https://www.reddit.com" + p["permalink"]
        if has_any(text, COMPLAINT_WORDS):
            out.append(make_item("reddit", p["id"], link, dt, text, title=p.get("title"),
                                 meta={"subreddit": p.get("subreddit"), "score": p.get("score"), "kind": "post"}))
        # Comments in a thread about the product are usually about the product.
        if p.get("num_comments", 0) > 0:
            try:
                r = requests.get(f"https://oauth.reddit.com/comments/{p['id']}",
                                 headers=h, params={"limit": comments_per_post, "depth": 2}, timeout=20)
                r.raise_for_status()
                for c in r.json()[1]["data"]["children"]:
                    d = c.get("data", {})
                    body = d.get("body", "")
                    if c.get("kind") != "t1" or not body or not has_any(body, COMPLAINT_WORDS):
                        continue
                    cdt = datetime.fromtimestamp(d["created_utc"], tz=timezone.utc)
                    out.append(make_item("reddit", d["id"], "https://www.reddit.com" + d["permalink"], cdt, body,
                                         meta={"subreddit": d.get("subreddit"), "score": d.get("score"), "kind": "comment"}))
            except Exception as e:
                log(f"  Reddit comments {p['id']}: failed ({e})")
            time.sleep(1)
    log(f"  Reddit: {len(out)} complaint posts/comments")
    return out
