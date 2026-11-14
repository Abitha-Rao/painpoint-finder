"""Fast checks for the free scripts. Run: .venv/bin/python -m pytest -q"""
import json
from datetime import datetime, timedelta, timezone

from pf import clean, estimate, evaluate
from pf.common import make_item


def _item(i, text, source="playstore", rating=1, days_ago=10):
    d = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return make_item(source, str(i), f"https://example.com/{i}", d, text, rating=rating)


def test_clean_filters_and_dedupes():
    long = "The payment was deducted but the settlement never arrived in my account"
    items = [
        _item(1, long),
        _item(2, long),                                  # duplicate
        _item(3, "bad"),                                 # too short
        _item(4, long + " again", rating=5),             # positive rating
        _item(5, long + " last year", days_ago=800),     # too old
        _item(6, "Lovely weather today, nothing more to say here", source="reddit", rating=None),  # not a complaint
        _item(7, "Refund not received after the order failed, very upset", source="reddit", rating=None),
    ]
    kept, stats = clean.clean(items, months=12)
    assert {k["id"] for k in kept} == {"playstore:1", "reddit:7"}
    assert stats["duplicate"] == 1 and stats["too_short"] == 1
    assert stats["positive_rating"] == 1 and stats["too_old"] == 1 and stats["not_a_complaint"] == 1


def test_cap_spreads_across_dates():
    items = [_item(i, f"Order number {i} was cancelled and the refund is still pending", days_ago=i) for i in range(1, 101)]
    kept, stats = clean.clean(items, months=12, max_per_source=10)
    assert len(kept) == 10 and stats["capped"] == 90
    days = sorted((datetime.now(timezone.utc) - datetime.fromisoformat(k["date"])).days for k in kept)
    assert days[0] < 15 and days[-1] > 85   # both recent and old complaints survive


def test_wilson_interval():
    lo, hi = estimate.wilson(35, 150)
    assert round(lo, 2) == 0.17 and round(hi, 2) == 0.31
    assert estimate.wilson(0, 0) == (0.0, 0.0)
    lo, hi = estimate.wilson(0, 50)
    assert lo == 0.0 and 0 < hi < 0.1


def _write_set(d, codes, key, human):
    d.mkdir(parents=True, exist_ok=True)
    (d / "answer_key_HIDDEN.json").write_text(json.dumps({"codes": codes, "key": key}))
    (d / "labels_human.json").write_text(json.dumps(human))


def test_estimate_pools_sets_and_new_themes(tmp_path):
    codes = {"A": "Late delivery", "B": "Refunds"}
    _write_set(tmp_path / "eval", codes,
               {"1": {"id": "x1", "tool": "A"}, "2": {"id": "x2", "tool": "B"}},
               {"1": "A", "2": "X"})
    _write_set(tmp_path / "estimate", codes,
               {"1": {"id": "x3", "tool": "A"}, "2": {"id": "x4", "tool": "A"}, "3": {"id": "x5", "tool": "B"}},
               {"1": "a", "2": "N:Signup failures", "3": ""})   # lower case ok, blank skipped
    res = estimate.compute(tmp_path)
    assert res["n"] == 4
    shares = {r["name"]: r["k"] for r in res["rows"]}
    assert shares == {"Late delivery": 2, estimate.VAGUE: 1, "New: Signup failures": 1}


def test_score_counts_agreement(tmp_path):
    _write_set(tmp_path, {"A": "Late delivery", "B": "Refunds"},
               {"1": {"id": "x1", "tool": "A"}, "2": {"id": "x2", "tool": "B"}, "3": {"id": "x3", "tool": "A"},
                "4": {"id": "x4", "tool": "X"}},
               {"1": "A", "2": "A", "3": "N:Something new", "4": "X"})
    res = evaluate.score(tmp_path)
    assert res["n"] == 4 and res["agree"] == 2
    assert res["per_pain_point"]["A"]["precision"] == 0.5


def test_secrets_and_data_stay_out_of_git():
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    ignored = (root / ".gitignore").read_text().split()
    assert ".env" in ignored and "runs/" in ignored
    example = (root / ".env.example").read_text()
    for line in example.splitlines():
        if "=" in line:
            assert line.split("=", 1)[1].strip() == "", ".env.example must not hold real values"


def test_embedding_cache_never_unpickles(tmp_path, monkeypatch):
    import numpy as np
    from pf import assign
    items = [{"id": "a:1", "text": "late delivery"}, {"id": "a:2", "text": "refund not received"}]
    monkeypatch.setattr(assign, "_embed", lambda texts: np.ones((len(texts), 3)))
    cache = tmp_path / "emb.npz"
    # A cache written the old way (object array, needs pickle) must be rebuilt, not loaded.
    np.savez(cache, ids=np.array(["a:1", "a:2"], dtype=object), emb=np.zeros((2, 3)))
    emb = assign.item_embeddings(items, cache)
    assert emb.sum() == 6
    monkeypatch.setattr(assign, "_embed", lambda texts: (_ for _ in ()).throw(AssertionError("should use cache")))
    assert assign.item_embeddings(items, cache).sum() == 6
