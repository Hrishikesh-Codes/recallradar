from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from recallradar_api import schemas
from recallradar_api.checking import run_check
from recallradar_api.ratelimit import client_key, enforce
from recallradar_api.state import DbSession, State
from recallradar_core.db import Feedback, Recall

router = APIRouter(prefix="/v1", tags=["check"])

_TOO_MANY: dict[int | str, dict[str, Any]] = {
    status.HTTP_429_TOO_MANY_REQUESTS: {"description": "Rate limited; see Retry-After."}
}


@router.post("/check", responses=_TOO_MANY)
def check_product(
    body: schemas.CheckRequest, request: Request, state: State, session: DbSession
) -> schemas.CheckResponse:
    """Check one product (description, product link, barcode, or VIN) against every recall.

    No account needed. Nothing about the product is stored, only that a check happened.
    """
    enforce(state.check_limits, client_key(request))
    return run_check(
        session,
        body,
        embedder=state.embedder,
        barcodes=state.barcodes,
        coverage=state.coverage,
        vins=state.vins,
    )


@router.post(
    "/feedback",
    status_code=status.HTTP_202_ACCEPTED,
    responses={**_TOO_MANY, status.HTTP_404_NOT_FOUND: {"description": "Unknown recall."}},
)
def feedback(
    body: schemas.FeedbackRequest, request: Request, state: State, session: DbSession
) -> schemas.Accepted:
    """Record "This is mine", "Not my product", or "Already handled" for one match."""
    enforce(state.feedback_limits, client_key(request))
    if session.scalar(select(Recall.id).where(Recall.id == body.recall_id)) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Unknown recall.")
    values = {
        "check_id": str(body.check_id),
        "recall_id": body.recall_id,
        "label": body.label,
        "tier_shown": body.tier_shown.value if body.tier_shown else None,
        "query": body.query.model_dump(mode="json") if body.query else {},
    }
    statement = insert(Feedback).values(**values)
    session.execute(
        statement.on_conflict_do_update(
            constraint="uq_feedback_check_id_recall_id",
            set_={"label": statement.excluded.label, "query": statement.excluded.query},
        )
    )
    return schemas.Accepted()
