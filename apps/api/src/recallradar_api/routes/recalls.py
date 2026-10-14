from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from recallradar_api import schemas
from recallradar_api.checking import coverage_out, product_out, recall_summary
from recallradar_api.state import DbSession, State
from recallradar_core.db import Recall, RecallProduct

router = APIRouter(prefix="/v1", tags=["recalls"])

MAX_PRODUCTS = 50


@router.get("/recalls/{recall_id}", responses={status.HTTP_404_NOT_FOUND: {}})
def get_recall(recall_id: int, session: DbSession) -> schemas.RecallDetail:
    recall = session.get(Recall, recall_id)
    if recall is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Recall not found.")
    products = session.scalars(
        select(RecallProduct)
        .where(RecallProduct.recall_id == recall_id)
        .order_by(RecallProduct.id)
        .limit(MAX_PRODUCTS)
    ).all()
    return schemas.RecallDetail(
        recall=recall_summary(recall),
        description=recall.description,
        distribution=recall.distribution,
        products=[product_out(p) for p in products],
    )


@router.get("/stats")
def stats(state: State, session: DbSession) -> schemas.Stats:
    """What we check against: "Checked against 31,482 recalls from CPSC and FDA"."""
    sources = state.coverage.get(session)
    coverage = coverage_out(sources, [])
    products = session.scalar(select(func.count()).select_from(RecallProduct)) or 0
    return schemas.Stats(
        recalls=coverage.recalls_checked,
        products=products,
        sources=sources,
        updated_at=coverage.updated_at,
    )
