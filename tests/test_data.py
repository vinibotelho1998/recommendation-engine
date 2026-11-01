import pandas as pd
import pytest

from recommendation_engine.data import generate_demo, load_dataset


def write_dataset(dataset, tmp_path):
    dataset.movies.to_csv(tmp_path / "movies.csv", index=False)
    dataset.ratings.to_csv(tmp_path / "ratings.csv", index=False)


def test_demo_generator_is_reproducible_and_declares_synthetic_data(tmp_path):
    import json

    first, second = tmp_path / "first", tmp_path / "second"
    generate_demo(first)
    generate_demo(second)
    assert load_dataset(first).fingerprint == load_dataset(second).fingerprint
    provenance = json.loads((first / "provenance.json").read_text())
    assert provenance["synthetic"] is True
    assert len(load_dataset(first).ratings) == 1440


def test_duplicate_user_movie_pairs_are_rejected(dataset, tmp_path):
    dataset.ratings = pd.concat([dataset.ratings, dataset.ratings.iloc[:1]], ignore_index=True)
    write_dataset(dataset, tmp_path)
    with pytest.raises(ValueError, match="Duplicate"):
        load_dataset(tmp_path)


def test_ratings_cannot_reference_missing_movies(dataset, tmp_path):
    dataset.ratings.loc[0, "movieId"] = 999
    write_dataset(dataset, tmp_path)
    with pytest.raises(ValueError, match="missing from the catalog"):
        load_dataset(tmp_path)


@pytest.mark.parametrize("value", [0.0, 5.5, 4.2, float("nan")])
def test_rating_contract_is_enforced(dataset, tmp_path, value):
    dataset.ratings.loc[0, "rating"] = value
    write_dataset(dataset, tmp_path)
    with pytest.raises(ValueError, match="Ratings must"):
        load_dataset(tmp_path)


def test_empty_title_is_rejected(dataset, tmp_path):
    dataset.movies.loc[0, "title"] = " "
    write_dataset(dataset, tmp_path)
    with pytest.raises(ValueError, match="non-empty titles"):
        load_dataset(tmp_path)


def test_numeric_movie_titles_are_read_as_text(dataset, tmp_path):
    dataset.movies["title"] = range(2001, 2007)
    write_dataset(dataset, tmp_path)
    restored = load_dataset(tmp_path)
    assert restored.movies.iloc[0]["title"] == "2001"


def test_fractional_user_id_is_rejected(dataset, tmp_path):
    dataset.ratings["userId"] = dataset.ratings["userId"].astype(float)
    dataset.ratings.loc[0, "userId"] = 1.5
    write_dataset(dataset, tmp_path)
    with pytest.raises(ValueError, match="positive integers"):
        load_dataset(tmp_path)
