"""HTTP serving; training is an explicit offline command."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Header, HTTPException, Query, Response
from fastapi import Path as ApiPath
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .model import Recommender
from .store import FeedbackStore, IdempotencyConflict

logger = logging.getLogger(__name__)
MAX_SQLITE_ID = 2**63 - 1


class FeedbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: int = Field(gt=0, le=MAX_SQLITE_ID, strict=True)
    movie_id: int = Field(gt=0, le=MAX_SQLITE_ID, strict=True)
    rating: float = Field(ge=0.5, le=5, strict=True)

    @field_validator("rating")
    @classmethod
    def half_star_rating(cls, value: float) -> float:
        if value * 2 % 1:
            raise ValueError("Use ratings in steps of 0.5")
        return value


class RecommendationItem(BaseModel):
    movie_id: int
    title: str
    score: float
    source: str
    explanation: str


class RecommendationsResponse(BaseModel):
    user_id: int
    cold_start: bool
    model_version: str
    recommendations: list[RecommendationItem]


class FeedbackResponse(BaseModel):
    id: int
    user_id: int
    movie_id: int
    rating: float
    created_at: str
    created: bool


def create_app(
    model: Recommender | None = None,
    model_path: str | Path | None = None,
    db_path: str | Path | None = None,
) -> FastAPI:
    artifact_path = Path(model_path or os.getenv("RECSYS_MODEL_PATH", "var/model.joblib"))
    feedback_path = Path(db_path or os.getenv("RECSYS_DB_PATH", "var/feedback.sqlite3"))

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        application.state.model = model
        if model is None and artifact_path.is_file():
            try:
                application.state.model = Recommender.load(artifact_path)
            except (OSError, ValueError, EOFError, ImportError):
                logger.exception("Could not load recommendation artifact")
        application.state.feedback = FeedbackStore(feedback_path)
        yield

    application = FastAPI(
        title="Recommendation Engine", version="0.1.0",
        description="Item-item recommendations with persistent feedback and cold-start fallback.",
        lifespan=lifespan,
    )

    def ready_model() -> Recommender:
        current = application.state.model
        if current is None:
            raise HTTPException(503, "No trained model loaded; run python -m recommendation_engine demo")
        return current

    @application.get("/health")
    def health():
        current = application.state.model
        if current is None:
            return JSONResponse(status_code=503, content={"status": "not_ready", "model_loaded": False})
        return {"status": "ready", "model_loaded": True, "model": current.metadata}

    @application.get("/recommendations/{user_id}", response_model=RecommendationsResponse)
    def recommendations(
        user_id: Annotated[int, ApiPath(gt=0, le=MAX_SQLITE_ID)],
        k: Annotated[int, Query(ge=1, le=50)] = 10,
    ):
        current = ready_model()
        feedback = application.state.feedback.latest_for_user(user_id)
        return current.recommend(user_id, k, feedback)

    @application.post("/feedback", status_code=201, response_model=FeedbackResponse)
    def feedback(
        body: FeedbackRequest, response: Response,
        idempotency_key: Annotated[str, Header(min_length=8, max_length=128)],
    ):
        current = ready_model()
        if body.movie_id not in current.titles:
            raise HTTPException(404, "Movie is not in the loaded model catalog")
        if not idempotency_key.strip():
            raise HTTPException(422, "Idempotency-Key must not be blank")
        try:
            saved, created = application.state.feedback.record(
                idempotency_key, body.user_id, body.movie_id, body.rating,
            )
        except IdempotencyConflict as exc:
            raise HTTPException(409, str(exc)) from exc
        response.status_code = 201 if created else 200
        return {**saved, "created": created}

    return application


app = create_app()
