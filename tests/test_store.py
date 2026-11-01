from concurrent.futures import ThreadPoolExecutor

import pytest

from recommendation_engine.store import FeedbackStore, IdempotencyConflict


def test_duplicate_key_is_idempotent_and_survives_reopening(tmp_path):
    path = tmp_path / "feedback.sqlite3"
    store = FeedbackStore(path)
    first, created = store.record("request-001", 1, 2, 5.0)
    second, created_again = FeedbackStore(path).record("request-001", 1, 2, 5.0)
    assert created and not created_again
    assert first == second


def test_same_key_with_different_payload_conflicts(tmp_path):
    store = FeedbackStore(tmp_path / "feedback.sqlite3")
    store.record("request-001", 1, 2, 5.0)
    with pytest.raises(IdempotencyConflict):
        store.record("request-001", 1, 2, 4.0)


def test_latest_rating_replaces_older_feedback(tmp_path):
    store = FeedbackStore(tmp_path / "feedback.sqlite3")
    store.record("request-001", 1, 2, 5.0)
    store.record("request-002", 1, 2, 1.0)
    store.record("request-003", 2, 2, 4.0)
    assert store.latest_for_user(1) == {2: 1.0}
    assert store.latest_for_user(999) == {}


def test_concurrent_retries_create_one_event(tmp_path):
    store = FeedbackStore(tmp_path / "feedback.sqlite3")
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: store.record("request-001", 1, 2, 5.0), range(8)))
    assert sum(created for _, created in results) == 1
    assert len({item["id"] for item, _ in results}) == 1
