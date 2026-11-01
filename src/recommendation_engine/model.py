"""Sparse collaborative filtering with an explicit popularity fallback."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from sklearn.neighbors import NearestNeighbors

from .data import Dataset


@dataclass(frozen=True)
class Recommendation:
    movie_id: int
    title: str
    score: float
    source: str
    explanation: str


@dataclass
class Recommender:
    titles: dict[int, str]
    profiles: dict[int, dict[int, float]]
    neighbors: dict[int, list[tuple[int, float]]]
    popularity: list[int]
    popularity_scores: dict[int, float]
    metadata: dict
    positive_threshold: float = 4.0

    def recommend(
        self, user_id: int, k: int = 10,
        feedback: dict[int, float] | None = None, popularity_only: bool = False,
    ) -> dict:
        if user_id <= 0 or not 1 <= k <= 50:
            raise ValueError("user_id must be positive and k must be between 1 and 50")
        profile = dict(self.profiles.get(user_id, {}))
        profile.update(feedback or {})
        seen = set(profile)
        positives = {movie for movie, rating in profile.items() if rating >= self.positive_threshold}
        scores: dict[int, float] = {}
        reasons: dict[int, tuple[int, float]] = {}
        if not popularity_only:
            for movie in sorted(positives):
                for candidate, similarity in self.neighbors.get(movie, []):
                    if candidate in seen:
                        continue
                    scores[candidate] = scores.get(candidate, 0.0) + similarity
                    if candidate not in reasons or similarity > reasons[candidate][1]:
                        reasons[candidate] = (movie, similarity)
        ranked = sorted(scores, key=lambda movie: (-scores[movie], movie))[:k]
        recommendations = []
        for movie in ranked:
            neighbor, _ = reasons[movie]
            recommendations.append(Recommendation(
                movie, self.titles[movie], round(scores[movie] / len(positives), 6),
                "item_similarity", f"Similar a um filme que voce avaliou bem: {self.titles[neighbor]}",
            ))
        picked = set(ranked)
        for movie in self.popularity:
            if len(recommendations) >= k:
                break
            if movie in seen or movie in picked:
                continue
            recommendations.append(Recommendation(
                movie, self.titles[movie], round(self.popularity_scores.get(movie, 0.0), 6),
                "popularity", "Popular entre os usuarios do conjunto de treinamento",
            ))
        return {
            "user_id": user_id,
            "cold_start": not bool(positives),
            "model_version": self.metadata["version"],
            "recommendations": [asdict(item) for item in recommendations],
        }

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        joblib.dump(self, temporary)
        temporary.replace(path)

    @staticmethod
    def load(path: str | Path) -> Recommender:
        model = joblib.load(path)
        if not isinstance(model, Recommender):
            raise ValueError("Artifact is not a recommendation model")
        return model


def train(dataset: Dataset, neighbors: int = 30, positive_threshold: float = 4.0) -> Recommender:
    if neighbors < 1:
        raise ValueError("neighbors must be at least 1")
    if not 0.5 <= positive_threshold <= 5:
        raise ValueError("positive_threshold must be between 0.5 and 5")
    ratings = dataset.ratings
    if ratings.empty:
        raise ValueError("Training needs at least one rating")
    titles = dict(zip(dataset.movies["movieId"].astype(int), dataset.movies["title"], strict=True))
    profiles = {
        int(user): {int(row.movieId): float(row.rating) for row in group.itertuples()}
        for user, group in ratings.groupby("userId")
    }
    positive = ratings[ratings["rating"] >= positive_threshold]
    user_ids = sorted(ratings["userId"].unique())
    active_movies = sorted(positive["movieId"].unique())
    user_index = {int(user): index for index, user in enumerate(user_ids)}
    item_index = {int(movie): index for index, movie in enumerate(active_movies)}
    item_neighbors: dict[int, list[tuple[int, float]]] = {}
    if active_movies:
        row_indices = positive["movieId"].map(item_index).to_numpy()
        column_indices = positive["userId"].map(user_index).to_numpy()
        matrix = csr_matrix(
            (np.ones(len(positive), dtype=np.float32), (row_indices, column_indices)),
            shape=(len(active_movies), len(user_ids)),
        )
        # Sparse input avoids a dense users x movies array. Only top neighbors are retained.
        search = NearestNeighbors(metric="cosine", algorithm="brute", n_jobs=1).fit(matrix)
        distances, indices = search.kneighbors(
            matrix, n_neighbors=min(neighbors + 1, len(active_movies)),
        )
        for position, movie in enumerate(active_movies):
            candidates = [
                (int(active_movies[index]), float(np.clip(1 - distance, 0, 1)))
                for distance, index in zip(distances[position], indices[position], strict=True)
                if index != position and distance < 1 - 1e-7
            ]
            item_neighbors[int(movie)] = sorted(
                candidates, key=lambda item: (-item[1], item[0]),
            )[:neighbors]
    positive_counts = positive.groupby("movieId")["userId"].nunique().to_dict()
    all_counts = ratings.groupby("movieId")["userId"].nunique().to_dict()
    popularity = sorted(titles, key=lambda movie: (
        -positive_counts.get(movie, 0), -all_counts.get(movie, 0), movie,
    ))
    metadata = {
        "version": f"itemknn-{dataset.fingerprint[:12]}-n{neighbors}-p{positive_threshold:g}",
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "data_sha256": dataset.fingerprint,
        "ratings": len(ratings), "users": len(user_ids), "movies": len(titles),
        "positive_ratings": len(positive), "neighbors": neighbors,
        "positive_threshold": positive_threshold,
        "algorithm": "cosine item-item on binary positive feedback",
    }
    return Recommender(
        titles, profiles, item_neighbors, popularity,
        {int(movie): count / len(user_ids) for movie, count in positive_counts.items()},
        metadata, positive_threshold,
    )


def leave_last_positive_out(
    ratings: pd.DataFrame, positive_threshold: float = 4.0,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Hold out one positive per user who has at least two positive interactions."""
    ordered = ratings.sort_values(["timestamp", "movieId"])
    positive = ordered[ordered["rating"] >= positive_threshold]
    counts = positive.groupby("userId")["movieId"].transform("size")
    candidates = positive[counts >= 2].groupby("userId", sort=True).tail(1)
    first_timestamp = positive.groupby("userId")["timestamp"].min()
    test = candidates[
        candidates["timestamp"] > candidates["userId"].map(first_timestamp)
    ]
    # Later events from the same user must not enter that user's training profile.
    cutoff = test.set_index("userId")["timestamp"].to_dict()
    train_mask = ratings.apply(
        lambda row: row["userId"] not in cutoff or row["timestamp"] < cutoff[row["userId"]],
        axis=1,
    )
    return ratings[train_mask].copy(), test.copy()
