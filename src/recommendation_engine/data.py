"""CSV contracts shared by synthetic and MovieLens datasets."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass
class Dataset:
    movies: pd.DataFrame
    ratings: pd.DataFrame
    fingerprint: str


def _positive_integer_column(frame: pd.DataFrame, name: str) -> None:
    values = pd.to_numeric(frame[name], errors="coerce")
    if values.isna().any() or ((values % 1) != 0).any() or (values <= 0).any():
        raise ValueError(f"{name} must contain positive integers")
    frame[name] = values.astype("int64")


def load_dataset(directory: str | Path) -> Dataset:
    directory = Path(directory)
    movies_path, ratings_path = directory / "movies.csv", directory / "ratings.csv"
    movies = pd.read_csv(movies_path, dtype={"title": "string"})
    ratings = pd.read_csv(ratings_path)
    if not {"movieId", "title"}.issubset(movies.columns):
        raise ValueError("movies.csv needs movieId and title")
    if not {"userId", "movieId", "rating", "timestamp"}.issubset(ratings.columns):
        raise ValueError("ratings.csv needs userId, movieId, rating and timestamp")
    if movies.empty or ratings.empty:
        raise ValueError("The catalog and ratings cannot be empty")
    movies = movies.copy()
    ratings = ratings[["userId", "movieId", "rating", "timestamp"]].copy()
    _positive_integer_column(movies, "movieId")
    for column in ["userId", "movieId", "timestamp"]:
        _positive_integer_column(ratings, column)
    if movies["movieId"].duplicated().any():
        raise ValueError("movieId must be unique in movies.csv")
    if movies["title"].isna().any() or movies["title"].str.strip().eq("").any():
        raise ValueError("Movies need non-empty titles")
    if ratings.duplicated(["userId", "movieId"]).any():
        raise ValueError("Duplicate user/movie pairs; resolve updates before importing")
    rating_values = pd.to_numeric(ratings["rating"], errors="coerce")
    if (
        rating_values.isna().any()
        or not rating_values.between(0.5, 5.0).all()
        or ((rating_values * 2) % 1 != 0).any()
    ):
        raise ValueError("Ratings must be 0.5 to 5.0 in steps of 0.5")
    ratings["rating"] = rating_values.astype(float)
    if not ratings["movieId"].isin(movies["movieId"]).all():
        raise ValueError("Ratings reference movies missing from the catalog")
    digest = hashlib.sha256()
    for path in [movies_path, ratings_path]:
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return Dataset(
        movies.sort_values("movieId").reset_index(drop=True),
        ratings.sort_values(["timestamp", "userId", "movieId"]).reset_index(drop=True),
        digest.hexdigest(),
    )


def generate_demo(directory: str | Path, seed: int = 42) -> None:
    """Create reproducible taste groups, not a benchmark for real users."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)
    genres = ["Ficcao", "Comedia", "Drama", "Animacao", "Suspense", "Documentario"]
    movies = [
        {"movieId": group * 12 + number + 1,
         "title": f"{genre} — filme ficticio {number + 1:02d}", "genres": genre}
        for group, genre in enumerate(genres)
        for number in range(12)
    ]
    ratings = []
    for user_id in range(1, 121):
        favorite = (user_id - 1) % len(genres)
        primary = rng.choice(np.arange(favorite * 12 + 1, favorite * 12 + 13), 9, replace=False)
        outsiders = np.setdiff1d(np.arange(1, 73), np.arange(favorite * 12 + 1, favorite * 12 + 13))
        sampled_outsiders = rng.choice(outsiders, 3, replace=False)
        events = [(int(movie), float(rng.choice([4.0, 4.5, 5.0]))) for movie in primary]
        events += [(int(movie), float(rng.choice([1.5, 2.5, 3.0]))) for movie in sampled_outsiders]
        rng.shuffle(events)
        for index, (movie, rating) in enumerate(events):
            ratings.append({
                "userId": user_id, "movieId": movie, "rating": rating,
                "timestamp": 1700000000 + index * 86400 + user_id * 61,
            })
    pd.DataFrame(movies).to_csv(directory / "movies.csv", index=False)
    pd.DataFrame(ratings).to_csv(directory / "ratings.csv", index=False)
    (directory / "provenance.json").write_text(json.dumps({
        "synthetic": True, "seed": seed, "users": 120, "movies": 72,
        "generator": "recommendation_engine.data.generate_demo",
        "purpose": "Exercise the pipeline; taste groups are intentionally easy to recover.",
        "license": "CC0-1.0 for this generated fixture only",
    }, indent=2) + "\n", encoding="utf-8")
