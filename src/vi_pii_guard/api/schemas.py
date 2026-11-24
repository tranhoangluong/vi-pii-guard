"""Request and response models of the HTTP API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from vi_pii_guard.domain import EntityType


class DetectRequest(BaseModel):
    text: str = Field(max_length=100_000)


class SpanOut(BaseModel):
    start: int
    end: int
    entity_type: EntityType
    text: str
    score: float
    source: str


class DetectResponse(BaseModel):
    spans: list[SpanOut]


class RedactRequest(BaseModel):
    text: str = Field(max_length=100_000)
    session_id: str | None = None
    strategy: Literal["placeholder", "mask"] = "placeholder"


class RedactedEntityOut(BaseModel):
    """Original values are deliberately not echoed back."""

    replacement: str
    entity_type: EntityType
    start: int
    end: int


class RedactResponse(BaseModel):
    text: str
    session_id: str | None
    entities: list[RedactedEntityOut]


class RestoreRequest(BaseModel):
    text: str = Field(max_length=200_000)
    session_id: str


class RestoreResponse(BaseModel):
    text: str


class HealthResponse(BaseModel):
    status: Literal["ok"]
    version: str
    recognizers: list[str]
