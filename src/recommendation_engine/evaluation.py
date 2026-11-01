"""Ranking metrics against one withheld positive per eligible user."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from .data import Dataset
from .model import leave_last_positive_out, train


def evaluate(dataset: Dataset, ks: tuple[int, ...] = (5, 10), neighbors: int = 30) -> dict:
    if not ks or any(not 1 <= k <= 50 for k in ks):
        raise ValueError("All k values must be between 1 and 50")
    training, test = leave_last_positive_out(dataset.ratings)
    if test.empty:
        raise ValueError("Evaluation needs users with at least two positive ratings")
    training_hash = hashlib.sha256(training.to_csv(index=False).encode()).hexdigest()
    model = train(Dataset(dataset.movies, training, training_hash), neighbors)
    results = []
    for name, popularity_only in [("item_similarity", False), ("popularity", True)]:
        for k in ks:
            hits, reciprocal_ranks, unique_items, returned = [], [], set(), []
            for row in test.itertuples():
                items = model.recommend(int(row.userId), k, popularity_only=popularity_only)
                ids = [item["movie_id"] for item in items["recommendations"]]
                hit = int(row.movieId in ids)
                hits.append(hit)
                reciprocal_ranks.append(1 / (ids.index(row.movieId) + 1) if hit else 0.0)
                unique_items.update(ids)
                returned.append(len(ids))
            count = len(hits)
            results.append({
                "method": name, "k": k, "users_evaluated": count,
                "precision_at_k": round(sum(hits) / (count * k), 6),
                "recall_at_k": round(sum(hits) / count, 6),
                "mrr_at_k": round(sum(reciprocal_ranks) / count, 6),
                "catalog_coverage": round(len(unique_items) / len(dataset.movies), 6),
                "mean_list_length": round(sum(returned) / count, 6),
            })
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "data_sha256": dataset.fingerprint,
        "protocol": "leave-last-positive-out; same-user events at/after cutoff excluded",
        "global_time_caveat": "Other users may have later events; not a global temporal simulation.",
        "train_ratings": len(training), "test_ratings": len(test),
        "positive_threshold": 4.0, "neighbors": neighbors, "results": results,
        "definitions": {
            "precision_at_k": "hits / (users * k), with at most one hit per user",
            "recall_at_k": "hits / eligible users; equal to hit rate with one held-out item",
            "mrr_at_k": "mean reciprocal rank of held-out item, zero when absent",
            "catalog_coverage": "unique recommended movies / total catalog movies",
        },
    }
