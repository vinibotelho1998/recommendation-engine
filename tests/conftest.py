import pandas as pd
import pytest

from recommendation_engine.data import Dataset
from recommendation_engine.model import train


@pytest.fixture
def dataset():
    movies = pd.DataFrame({"movieId": range(1, 7), "title": [f"Movie {i}" for i in range(1, 7)]})
    events = [
        (1, 1, 5.0, 10), (1, 2, 4.0, 20),
        (2, 1, 4.0, 10), (2, 2, 4.5, 20), (2, 3, 5.0, 30),
        (3, 4, 4.0, 10), (3, 5, 4.5, 20), (3, 6, 5.0, 30),
        (4, 4, 4.5, 10), (4, 5, 4.0, 20), (4, 6, 4.0, 30),
    ]
    ratings = pd.DataFrame(events, columns=["userId", "movieId", "rating", "timestamp"])
    return Dataset(movies, ratings, "test-data")


@pytest.fixture
def model(dataset):
    return train(dataset, neighbors=5)
