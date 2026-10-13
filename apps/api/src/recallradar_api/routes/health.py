import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from recallradar_api import __version__
from recallradar_core.db.session import get_engine
from recallradar_core.settings import Environment, get_settings

logger = logging.getLogger("recallradar.api")

router = APIRouter(tags=["health"])


class Liveness(BaseModel):
    status: Literal["ok"]


class Readiness(BaseModel):
    status: Literal["ok", "unavailable"]
    database: bool


class Meta(BaseModel):
    version: str
    environment: Environment


def database_is_reachable() -> bool:
    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        logger.warning("database ping failed", exc_info=True)
        return False
    return True


@router.get("/healthz")
def liveness() -> Liveness:
    """The process is up. Never touches the database, so it stays cheap to poll."""
    return Liveness(status="ok")


@router.get(
    "/readyz",
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": Readiness}},
)
def readiness(
    response: Response, database_ok: Annotated[bool, Depends(database_is_reachable)]
) -> Readiness:
    if not database_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return Readiness(status="unavailable", database=False)
    return Readiness(status="ok", database=True)


@router.get("/v1/meta")
def meta() -> Meta:
    return Meta(version=__version__, environment=get_settings().environment)
