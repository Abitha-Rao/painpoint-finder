"""Assign each complaint to the pain point it is closest to (free, on this Mac).

The first grouping step finds the themes. Once those themes have names and definitions
(labels.json), every complaint is re-assigned to the pain point whose description it
matches best, or to "too vague" when it mostly matches generic rants.
"""
import numpy as np

from .group import MODEL_NAME

# Typical non-specific complaints: anything closest to these counts as "too vague".
GENERIC_RANTS = [
    "worst app ever", "very bad service", "pathetic experience", "worst service, don't use",
    "not satisfied with your service", "poor service, very poor", "this app is useless",
    "worst company, fraud", "bad experience", "service is very bad nowadays",
]

_model = None


def _embed(texts):
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(MODEL_NAME)
    return _model.encode(texts, batch_size=64, show_progress_bar=False, normalize_embeddings=True)


def item_embeddings(items, cache_path):
    """Embeddings for the cleaned complaints, cached next to the run."""
    ids = [it["id"] for it in items]
    if cache_path.exists():
        try:
            # allow_pickle stays off: a cache file from someone else must not be able to run code.
            data = np.load(cache_path, allow_pickle=False)
            if [str(i) for i in data["ids"]] == ids:
                return data["emb"]
        except (ValueError, OSError, KeyError):
            pass  # old or unreadable cache: rebuild it
    emb = _embed([it["text"][:1000] for it in items])
    np.savez(cache_path, ids=np.array(ids, dtype=str), emb=emb)
    return emb


def _unit(v):
    return v / (np.linalg.norm(v) + 1e-9)


def prototypes(items, emb, groups, labels, def_weight=0.5):
    """One vector per pain point: a blend of its written definition and its typical complaints."""
    idx = {it["id"]: i for i, it in enumerate(items)}
    names, vecs, meta = [], [], {}
    vague_vecs = [_unit(v) for v in _embed(GENERIC_RANTS)]
    by_name = {}
    for c in groups["clusters"]:
        lab = labels.get(str(c["id"]), {})
        if not lab:
            continue
        typical = [idx[i] for i in c["ordered_ids"][: max(10, len(c["ordered_ids"]) // 4)] if i in idx]
        centroid = _unit(emb[typical].mean(axis=0))
        if lab.get("vague"):
            vague_vecs.append(centroid)
            continue
        by_name.setdefault(lab["name"], {"lab": lab, "centroids": []})["centroids"].append(centroid)
    texts = [f"{n}. {d['lab'].get('definition', '')}" + " " + " ".join(d["lab"].get("examples", []))
             for n, d in by_name.items()]
    def_embs = _embed(texts) if texts else []
    for (name, d), de in zip(by_name.items(), def_embs):
        cen = _unit(np.mean(d["centroids"], axis=0))
        names.append(name)
        vecs.append(_unit(def_weight * _unit(de) + (1 - def_weight) * cen))
        meta[name] = d["lab"]
    return names, np.array(vecs), np.array(vague_vecs), meta


def assign(items, emb, groups, labels, def_weight=0.5, vague_margin=0.0):
    names, P, V, meta = prototypes(items, emb, groups, labels, def_weight)
    sims = emb @ P.T                       # similarity to each pain point
    vague_sim = (emb @ V.T).max(axis=1)    # similarity to the closest generic rant
    best = sims.argmax(axis=1)
    best_sim = sims.max(axis=1)
    out = {}
    for i, it in enumerate(items):
        if vague_sim[i] > best_sim[i] + vague_margin:
            out[it["id"]] = (None, float(best_sim[i]))
        else:
            out[it["id"]] = (names[best[i]], float(best_sim[i]))
    return out, names, meta


DEF_WEIGHT = 0.5  # chosen on the Swiggy dev sample (see README: accuracy check)


def effective_groups(out_dir, items, groups, labels):
    """Groups the report and accuracy check should use.

    With named pain points (lean mode) every complaint is re-assigned to its closest
    pain point. Without names (free mode) the raw groups are used as-is.
    """
    if not labels:
        return groups, labels
    emb = item_embeddings(items, out_dir / "emb.npz")
    return as_groups(items, emb, groups, labels, def_weight=DEF_WEIGHT)


def as_groups(items, emb, groups, labels, **kw):
    """Return (groups, labels) in the same shape the report already understands."""
    result, names, meta = assign(items, emb, groups, labels, **kw)
    clusters, new_labels = [], {}
    buckets = {n: [] for n in names}
    buckets["__vague__"] = []
    for iid, (name, s) in result.items():
        buckets[name or "__vague__"].append((s, iid))
    for cid, (name, lst) in enumerate(buckets.items()):
        lst.sort(reverse=True)  # most typical first
        ordered = [i for _, i in lst]
        clusters.append({"id": cid, "size": len(ordered), "keywords": [], "auto_label": name,
                         "looks_vague": name == "__vague__", "ordered_ids": ordered,
                         "sample_ids": ordered[:6]})
        if name == "__vague__":
            new_labels[str(cid)] = {"name": "Too vague to classify", "definition":
                                    "Non-specific complaints (e.g. 'worst service') or ones that fit no pain point.",
                                    "severity": None, "vague": True}
        else:
            new_labels[str(cid)] = dict(meta[name], name=name, vague=False)
    return {"k": len(clusters), "model": groups.get("model"), "method": "assigned", "clusters": clusters}, new_labels
