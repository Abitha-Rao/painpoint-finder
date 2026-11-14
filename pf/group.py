"""Group similar complaints for free, on this Mac (no AI tokens).

A small local model turns each complaint into numbers that capture its meaning,
then similar complaints are grouped together. Each group gets an automatic label
from its most distinctive words.
"""
import os
import re

import numpy as np

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

from sklearn.cluster import KMeans  # noqa: E402
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer  # noqa: E402
from sklearn.metrics import silhouette_score  # noqa: E402

from .common import log  # noqa: E402

# Multilingual so Hindi / mixed-language reviews still group sensibly.
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

GENERIC_WORDS = {
    "worst", "bad", "app", "application", "good", "useless", "pathetic", "service",
    "experience", "poor", "fraud", "scam", "don", "dont", "use", "very", "ever",
    "rating", "star", "stars", "waste", "time", "please", "people", "company",
    "terrible", "horrible", "nice", "best", "ok", "okay", "really", "just",
}


def _embed(texts):
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(MODEL_NAME)
    return model.encode(texts, batch_size=64, show_progress_bar=False, normalize_embeddings=True)


def _pick_k(emb, k_min, k_max):
    n = len(emb)
    k_max = max(k_min, min(k_max, n // 15))
    if n < k_min * 5:
        return max(2, n // 5)
    best_k, best_s = k_min, -1
    for k in range(k_min, k_max + 1):
        labels = KMeans(n_clusters=k, n_init=10, random_state=42).fit_predict(emb)
        s = silhouette_score(emb, labels)
        if s > best_s:
            best_k, best_s = k, s
    return best_k


def _auto_labels(texts, labels, k, extra_stop):
    """Most distinctive words per group (class-based TF-IDF)."""
    stop = set(ENGLISH_STOP_WORDS) | {w.lower() for w in extra_stop}
    docs = [" ".join(t for t, l in zip(texts, labels) if l == c) for c in range(k)]
    vec = TfidfVectorizer(stop_words=list(stop), ngram_range=(1, 2), min_df=1,
                          max_features=5000, token_pattern=r"(?u)\b[a-zA-Z][a-zA-Z]+\b")
    m = vec.fit_transform(docs)
    vocab = np.array(vec.get_feature_names_out())
    out = []
    for c in range(k):
        row = m[c].toarray().ravel()
        top = [w for w in vocab[row.argsort()[::-1]] if row[vocab.tolist().index(w)] > 0][:8]
        out.append(top)
    return out


def group(items, product_terms=(), k_min=6, k_max=14, samples_per_group=6):
    texts = [it["text"][:1000] for it in items]
    log(f"  Grouping {len(texts)} complaints on this Mac (first run downloads a ~470 MB model)...")
    emb = _embed(texts)
    # Bigger datasets deserve finer groups (silhouette alone tends to pick the minimum).
    k_min = max(k_min, min(10, len(texts) // 80))
    k = _pick_k(emb, k_min, k_max)
    km = KMeans(n_clusters=k, n_init=10, random_state=42).fit(emb)
    labels = km.labels_

    extra_stop = set()
    for t in product_terms:
        extra_stop.update(re.findall(r"[a-zA-Z]+", t.lower()))
    keywords = _auto_labels(texts, labels, k, extra_stop)

    clusters = []
    for c in range(k):
        idx = np.where(labels == c)[0]
        dists = np.linalg.norm(emb[idx] - km.cluster_centers_[c], axis=1)
        order = idx[np.argsort(dists)]
        kw = keywords[c]
        specific = [w for w in kw if not set(w.split()) <= GENERIC_WORDS]
        vague = len(specific) <= 2
        clusters.append({
            "id": int(c),
            "size": int(len(idx)),
            "keywords": kw,
            "auto_label": " / ".join((specific or kw)[:3]),
            "looks_vague": bool(vague),
            # closest-to-centre first: the most typical complaints in the group
            "ordered_ids": [items[i]["id"] for i in order],
            "sample_ids": [items[i]["id"] for i in order[:samples_per_group]],
        })
    clusters.sort(key=lambda c: c["size"], reverse=True)
    assignments = {items[i]["id"]: int(labels[i]) for i in range(len(items))}
    log(f"  Found {k} groups: " + "; ".join(f"[{c['id']}] {c['auto_label']} ({c['size']})" for c in clusters))
    return {"k": int(k), "model": MODEL_NAME, "clusters": clusters, "assignments": assignments}


def write_brief_for_claude(groups, items_by_id, path, max_chars=280):
    """Compact file Claude reads in lean mode: a few typical complaints per group."""
    lines = ["# Groups to name", "",
             "For each group, read the samples and write a clear pain-point name, a one-line",
             "definition, a severity (money / blocked / annoyance), and whether it is too vague",
             "to be a real pain point. Groups that describe the same problem can share a name",
             "(they will be merged).", ""]
    for c in groups["clusters"]:
        lines.append(f"## Group {c['id']} — {c['size']} complaints — auto label: {c['auto_label']}")
        lines.append(f"keywords: {', '.join(c['keywords'])}")
        for sid in c["sample_ids"]:
            it = items_by_id[sid]
            t = re.sub(r"\s+", " ", it["text"])[:max_chars]
            r = f"{it['rating']}★ " if it.get("rating") else ""
            lines.append(f"- ({it['source']}, {r}{(it['date'] or '')[:7]}) {t}")
        lines.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
