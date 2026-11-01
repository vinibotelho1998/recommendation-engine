import pandas as pd
import pytest

from recommendation_engine.data import Dataset
from recommendation_engine.evaluation import evaluate
from recommendation_engine.model import Recommender, leave_last_positive_out, train


def ids(result):
    return [item["movie_id"] for item in result["recommendations"]]


def test_similar_items_rank_before_popularity_and_seen_items_are_excluded(model):
    result = model.recommend(1, k=4)
    assert ids(result)[0] == 3
    assert result["recommendations"][0]["source"] == "item_similarity"
    assert not ({1, 2} & set(ids(result)))
    assert len(ids(result)) == len(set(ids(result)))
    assert not result["cold_start"]


def test_unknown_user_receives_popularity_with_explicit_cold_start(model):
    result = model.recommend(999, k=3)
    assert result["cold_start"]
    assert ids(result) == model.popularity[:3]
    assert all(item["source"] == "popularity" for item in result["recommendations"])


def test_feedback_updates_user_profile_without_retraining_global_neighbors(model):
    result = model.recommend(999, k=5, feedback={1: 5.0, 6: 1.0})
    assert not result["cold_start"]
    assert not ({1, 6} & set(ids(result)))
    assert model.profiles.get(999) is None


def test_negative_feedback_can_replace_a_previous_positive(model):
    result = model.recommend(1, k=4, feedback={1: 1.0, 2: 1.0})
    assert result["cold_start"]
    assert not ({1, 2} & set(ids(result)))


def test_all_seen_returns_empty_list(model):
    assert model.recommend(9, feedback=dict.fromkeys(range(1, 7), 5.0))["recommendations"] == []


def test_save_load_preserves_rankings(model, tmp_path):
    path = tmp_path / "model.joblib"
    model.save(path)
    restored = Recommender.load(path)
    assert restored.recommend(1) == model.recommend(1)


def test_training_without_positive_feedback_uses_popularity(dataset):
    dataset.ratings["rating"] = 1.0
    trained = train(dataset)
    assert trained.neighbors == {}
    assert trained.recommend(1)["cold_start"]


@pytest.mark.parametrize("k", [0, 51])
def test_invalid_k_is_rejected(model, k):
    with pytest.raises(ValueError):
        model.recommend(1, k)


def test_split_excludes_holdout_and_later_negative_events(dataset):
    later = pd.DataFrame([(1, 6, 1.0, 40)], columns=dataset.ratings.columns)
    training, test = leave_last_positive_out(pd.concat([dataset.ratings, later], ignore_index=True))
    for event in test.itertuples():
        user_training = training[training.userId == event.userId]
        assert (user_training.timestamp < event.timestamp).all()
        assert event.movieId not in user_training.movieId.values
    assert 6 not in training[training.userId == 1].movieId.values


def test_same_time_positives_are_not_eligible_for_a_temporal_holdout(dataset):
    same_time = dataset.ratings.copy()
    same_time["timestamp"] = 10
    _, test = leave_last_positive_out(same_time)
    assert test.empty


def test_evaluation_metric_denominators_and_baseline(dataset):
    report = evaluate(dataset, ks=(2,))
    assert {row["method"] for row in report["results"]} == {"item_similarity", "popularity"}
    assert report["test_ratings"] == 4
    for row in report["results"]:
        assert row["precision_at_k"] == pytest.approx(row["recall_at_k"] / 2, abs=1e-6)
        assert 0 <= row["mrr_at_k"] <= row["recall_at_k"] <= 1
        assert 0 < row["catalog_coverage"] <= 1


def test_empty_training_is_rejected(dataset):
    empty = Dataset(dataset.movies, dataset.ratings.iloc[:0], "empty")
    with pytest.raises(ValueError, match="at least one rating"):
        train(empty)
