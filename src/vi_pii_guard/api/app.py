"""HTTP API and OpenAI-compatible proxy.

Run with ``vi-pii-guard serve`` or
``uvicorn vi_pii_guard.api.app:create_app --factory``.

Raw message content is never logged: logs only carry counts and status codes.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from starlette.concurrency import run_in_threadpool

from vi_pii_guard import __version__
from vi_pii_guard.api.schemas import (
    DetectRequest,
    DetectResponse,
    HealthResponse,
    RedactedEntityOut,
    RedactRequest,
    RedactResponse,
    RestoreRequest,
    RestoreResponse,
    SpanOut,
)
from vi_pii_guard.api.settings import Settings
from vi_pii_guard.guard import Guard
from vi_pii_guard.vault import InMemoryVault

logger = logging.getLogger("vi_pii_guard.api")

SESSION_HEADER = "X-PII-Session"
COUNT_HEADER = "X-PII-Redacted"


def _openai_error(status: int, message: str, code: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"message": message, "type": "invalid_request_error", "code": code}},
    )


def create_app(
    settings: Settings | None = None,
    *,
    guard: Guard | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> FastAPI:
    """Build the app. ``guard`` and ``transport`` are injectable for tests."""
    settings = settings or Settings()
    guard = guard or Guard.default(
        ner_model=settings.ner_model,
        min_score=settings.min_score,
        vault=InMemoryVault(
            ttl_seconds=settings.session_ttl_seconds, max_sessions=settings.max_sessions
        ),
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with httpx.AsyncClient(
            base_url=settings.upstream_base_url,
            timeout=settings.upstream_timeout_seconds,
            transport=transport,
        ) as client:
            app.state.http = client
            yield

    app = FastAPI(
        title="vi-pii-guard",
        version=__version__,
        summary="Vietnamese PII detection, redaction and an OpenAI-compatible privacy proxy",
        lifespan=lifespan,
    )
    app.state.guard = guard
    app.state.settings = settings

    @app.get("/healthz", response_model=HealthResponse)
    def healthz() -> HealthResponse:
        return HealthResponse(
            status="ok", version=__version__, recognizers=list(guard.recognizer_names)
        )

    @app.post("/v1/detect", response_model=DetectResponse)
    def detect(body: DetectRequest) -> DetectResponse:
        spans = guard.detect(body.text)
        return DetectResponse(
            spans=[
                SpanOut(
                    start=s.start,
                    end=s.end,
                    entity_type=s.entity_type,
                    text=s.text,
                    score=s.score,
                    source=s.source,
                )
                for s in spans
            ]
        )

    @app.post("/v1/redact", response_model=RedactResponse)
    def redact(body: RedactRequest) -> RedactResponse:
        result = guard.redact(body.text, session_id=body.session_id, strategy=body.strategy)
        return RedactResponse(
            text=result.text,
            session_id=result.session_id,
            entities=[
                RedactedEntityOut(
                    replacement=item.replacement,
                    entity_type=item.span.entity_type,
                    start=item.span.start,
                    end=item.span.end,
                )
                for item in result.items
            ],
        )

    @app.post("/v1/restore", response_model=RestoreResponse)
    def restore(body: RestoreRequest) -> RestoreResponse:
        return RestoreResponse(text=guard.restore(body.text, body.session_id))

    @app.delete("/v1/sessions/{session_id}", status_code=204)
    def forget(session_id: str) -> Response:
        guard.forget(session_id)
        return Response(status_code=204)

    @app.post("/v1/chat/completions")
    async def chat_completions(request: Request) -> Response:
        """Redact every message, forward upstream, restore the answer."""
        try:
            body: Any = await request.json()
        except ValueError:
            return _openai_error(400, "Request body must be JSON.", "invalid_json")
        if not isinstance(body, dict) or not isinstance(body.get("messages"), list):
            return _openai_error(400, "`messages` must be a list.", "invalid_messages")
        if body.get("stream"):
            return _openai_error(
                400,
                "stream=true is not supported yet (see docs/adr/0003-non-streaming-proxy.md).",
                "stream_not_supported",
            )

        session_id = request.headers.get(SESSION_HEADER)
        redacted = 0
        for message in body["messages"]:
            if not isinstance(message, dict):
                continue
            content = message.get("content")
            if isinstance(content, str):
                result = await run_in_threadpool(guard.redact, content, session_id=session_id)
                message["content"], session_id = result.text, result.session_id
                redacted += len(result.items)
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("type") == "text":
                        text = part.get("text")
                        if isinstance(text, str):
                            result = await run_in_threadpool(
                                guard.redact, text, session_id=session_id
                            )
                            part["text"], session_id = result.text, result.session_id
                            redacted += len(result.items)

        headers = {"content-type": "application/json"}
        if settings.upstream_api_key is not None:
            headers["authorization"] = f"Bearer {settings.upstream_api_key.get_secret_value()}"
        elif "authorization" in request.headers:
            headers["authorization"] = request.headers["authorization"]

        client: httpx.AsyncClient = request.app.state.http
        try:
            upstream = await client.post("chat/completions", json=body, headers=headers)
        except httpx.HTTPError as exc:
            logger.warning("upstream request failed: %s", type(exc).__name__)
            return _openai_error(502, "Upstream LLM request failed.", "upstream_unavailable")

        logger.info(
            "proxied chat completion: redacted=%d status=%d", redacted, upstream.status_code
        )
        if upstream.status_code >= 400:
            return Response(
                content=upstream.content,
                status_code=upstream.status_code,
                media_type=upstream.headers.get("content-type", "application/json"),
            )

        data = upstream.json()
        if session_id:
            for choice in data.get("choices", []) if isinstance(data, dict) else []:
                message = choice.get("message") if isinstance(choice, dict) else None
                if isinstance(message, dict) and isinstance(message.get("content"), str):
                    message["content"] = guard.restore(message["content"], session_id)
        return JSONResponse(
            content=data,
            headers={SESSION_HEADER: session_id or "", COUNT_HEADER: str(redacted)},
        )

    return app
