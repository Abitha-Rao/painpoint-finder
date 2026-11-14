"""Google Play reviews (public, via the google-play-scraper library).

Only 1–3★ reviews are requested (those are the complaints). For each star level we take
the newest reviews plus Google's "most relevant" ones. For very popular apps the newest
reviews cover only days, so the "most relevant" set adds older, widely-upvoted complaints.
"""
import time

from google_play_scraper import Sort, reviews

from .common import cutoff_date, log, make_item


def _fetch(app_id, sort, score, limit, country, lang, cutoff):
    got, token = [], None
    while len(got) < limit:
        batch, token = reviews(app_id, lang=lang, country=country, sort=sort,
                               count=min(200, limit - len(got)), filter_score_with=score,
                               continuation_token=token)
        if not batch:
            break
        got.extend(batch)
        if sort == Sort.NEWEST and batch[-1]["at"] < cutoff:
            break
        if token is None:
            break
        time.sleep(0.5)
    return got


def collect(app_ids, months=12, max_per_app=1500, country="in", lang="en", max_star=3):
    cutoff = cutoff_date(months).replace(tzinfo=None)
    per_bucket = max(50, max_per_app // (max_star * 2))
    out = []
    for app_id in app_ids:
        seen, kept, spans = set(), 0, {}
        for sort, sample in ((Sort.NEWEST, "newest"), (Sort.MOST_RELEVANT, "most_relevant")):
            for score in range(1, max_star + 1):
                for r in _fetch(app_id, sort, score, per_bucket, country, lang, cutoff):
                    if r["at"] < cutoff or r["reviewId"] in seen:
                        continue
                    seen.add(r["reviewId"])
                    spans.setdefault(sample, []).append(r["at"])
                    out.append(make_item(
                        source="playstore",
                        id=r["reviewId"],
                        url=f"https://play.google.com/store/apps/details?id={app_id}&reviewId={r['reviewId']}",
                        date=r["at"],
                        text=r["content"],
                        rating=r["score"],
                        meta={"app": app_id, "thumbs_up": r.get("thumbsUpCount", 0), "sample": sample},
                    ))
                    kept += 1
        span_txt = "; ".join(f"{k}: {min(v):%d %b %Y}–{max(v):%d %b %Y}" for k, v in spans.items())
        log(f"  Play Store {app_id}: {kept} 1–{max_star}★ reviews in window ({span_txt})")
    return out
