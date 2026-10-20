"""Process-wide resources, created once at startup and shared by every request."""

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Annotated

import httpx
from fastapi import Depends, Request
from sqlalchemy.orm import Session, sessionmaker

from recallradar_api.checking import BarcodeLookups, CoverageCache, VinDecoder
from recallradar_api.ratelimit import RateLimiter
from recallradar_identify.barcode import USER_AGENT
from recallradar_matching.embed import Embedder
from recallradar_matching.vectors import VectorStore


@dataclass
class AppState:
    sessions: sessionmaker[Session]
    embedder: Embedder
    barcodes: BarcodeLookups | None
    coverage: CoverageCache
    check_limits: list[RateLimiter]
    feedback_limits: list[RateLimiter]
    vins: VinDecoder | None = None
    # Embeddings in their own database; None when the main database holds them.
    vectors: VectorStore | None = None


def default_state(
    sessions: sessionmaker[Session],
    embedder: Embedder,
    vector_sessions: sessionmaker[Session] | None = None,
) -> AppState:
    client = httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=10)
    return AppState(
        sessions=sessions,
        embedder=embedder,
        # Open Food Facts allows 15 product reads per minute per IP; stay under it.
        barcodes=BarcodeLookups(client, RateLimiter(limit=12, window_seconds=60)),
        coverage=CoverageCache(),
        check_limits=[
            RateLimiter(limit=20, window_seconds=60),
            RateLimiter(limit=300, window_seconds=86_400),
        ],
        feedback_limits=[RateLimiter(limit=30, window_seconds=3600)],
        vins=VinDecoder(client),
        vectors=VectorStore(vector_sessions) if vector_sessions else None,
    )


def get_state(request: Request) -> AppState:
    state: AppState = request.app.state.recallradar
    return state


State = Annotated[AppState, Depends(get_state)]


def get_session(state: State) -> Iterator[Session]:
    """A session per request that commits if the handler succeeds."""
    with state.sessions.begin() as session:
        yield session


DbSession = Annotated[Session, Depends(get_session)]
