import pytest
from fastapi.testclient import TestClient

from recommendation_engine.api import create_app


@pytest.fixture
def client(model, tmp_path):
    with TestClient(create_app(model=model, db_path=tmp_path / "feedback.sqlite3")) as instance:
        yield instance


def test_ready_health_and_recommendations(client):
    assert client.get("/health").json()["status"] == "ready"
    response = client.get("/recommendations/1?k=3")
    assert response.status_code == 200
    assert response.json()["recommendations"][0]["movie_id"] == 3


def test_feedback_retry_conflict_and_immediate_seen_exclusion(client):
    payload = {"user_id": 1, "movie_id": 3, "rating": 5.0}
    headers = {"Idempotency-Key": "rating-request-001"}
    first = client.post("/feedback", json=payload, headers=headers)
    repeated = client.post("/feedback", json=payload, headers=headers)
    assert first.status_code == 201
    assert repeated.status_code == 200
    assert first.json()["id"] == repeated.json()["id"]
    assert not repeated.json()["created"]
    conflict = client.post("/feedback", json={**payload, "rating": 4.0}, headers=headers)
    assert conflict.status_code == 409
    result = client.get("/recommendations/1").json()
    assert 3 not in [item["movie_id"] for item in result["recommendations"]]


@pytest.mark.parametrize("payload", [
    {"user_id": 0, "movie_id": 3, "rating": 5.0},
    {"user_id": 1, "movie_id": 3, "rating": 4.2},
    {"user_id": 1, "movie_id": 3, "rating": 5.5},
    {"user_id": 1, "movie_id": 3, "rating": True},
    {"user_id": 1, "movie_id": 3, "rating": 5, "extra": "unexpected"},
])
def test_invalid_feedback_is_rejected(client, payload):
    assert client.post("/feedback", json=payload, headers={"Idempotency-Key": "rating-001"}).status_code == 422


def test_missing_idempotency_key_is_rejected(client):
    assert client.post("/feedback", json={"user_id": 1, "movie_id": 3, "rating": 5}).status_code == 422


def test_unknown_movie_is_rejected(client):
    response = client.post(
        "/feedback", json={"user_id": 1, "movie_id": 999, "rating": 5},
        headers={"Idempotency-Key": "rating-001"},
    )
    assert response.status_code == 404


@pytest.mark.parametrize("path", ["/recommendations/0", "/recommendations/1?k=0", "/recommendations/1?k=51"])
def test_query_validation(client, path):
    assert client.get(path).status_code == 422


def test_ids_must_fit_sqlite_integers(client):
    too_large = 2**63
    assert client.get(f"/recommendations/{too_large}").status_code == 422
    assert client.get(f"/recommendations/{too_large - 1}").status_code == 200
    headers = {"Idempotency-Key": "rating-large-id"}
    assert client.post(
        "/feedback", json={"user_id": too_large, "movie_id": 3, "rating": 5}, headers=headers,
    ).status_code == 422
    assert client.post(
        "/feedback", json={"user_id": 1, "movie_id": too_large, "rating": 5}, headers=headers,
    ).status_code == 422


def test_no_artifact_returns_readiness_503_without_training_at_startup(tmp_path):
    with TestClient(create_app(model_path=tmp_path / "missing.joblib", db_path=tmp_path / "f.db")) as client:
        assert client.get("/health").status_code == 503
        assert client.get("/recommendations/1").status_code == 503
