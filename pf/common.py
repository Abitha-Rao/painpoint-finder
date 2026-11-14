"""Shared helpers: item format, file I/O, settings."""
import json
import os
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "runs"
USER_AGENT = "painpoint-finder/0.1 (personal PM research script)"

# Words that suggest someone is complaining. Used to filter sources that have
# no star rating (Reddit, complaint sites).
COMPLAINT_WORDS = [
    "issue", "problem", "worst", "bad", "scam", "fraud", "stuck", "not received",
    "not credited", "delay", "delayed", "blocked", "frozen", "hold", "on hold",
    "support", "no response", "refund", "charge", "charged", "fee", "fees",
    "fail", "failed", "failure", "error", "bug", "crash", "down", "outage",
    "kyc", "rejected", "deactivated", "suspended", "terrible", "pathetic",
    "useless", "frustrat", "complain", "disappoint", "waste", "hidden",
    "deducted", "pending", "cheat", "harass", "unable", "can't", "cannot",
    "doesn't work", "not working", "never", "avoid", "horrible", "awful",
]


def now_utc():
    return datetime.now(timezone.utc)


def cutoff_date(months):
    return now_utc() - timedelta(days=int(months * 30.4))


def to_iso(dt):
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def parse_iso(s):
    if not s:
        return None
    return datetime.fromisoformat(s)


def make_item(source, id, url, date, text, rating=None, title=None, meta=None):
    """Every collector returns items in this one shape."""
    return {
        "id": f"{source}:{id}",
        "source": source,
        "url": url,
        "date": to_iso(date) if isinstance(date, datetime) else date,
        "rating": rating,
        "title": title or "",
        "text": (text or "").strip(),
        "meta": meta or {},
    }


def write_jsonl(path, items):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")


def read_jsonl(path):
    path = Path(path)
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def read_json(path, default=None):
    path = Path(path)
    if not path.exists():
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_env():
    """Read KEY=VALUE lines from .env in the project root (no extra library)."""
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def has_any(text, words):
    t = text.lower()
    return any(w.lower() in t for w in words)


def norm_for_dedupe(text):
    return re.sub(r"[^a-z0-9]+", "", text.lower())[:200]


def log(msg):
    print(msg, flush=True)
