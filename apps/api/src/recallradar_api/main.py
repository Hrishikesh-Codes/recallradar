import logging
import time
import uuid
from collections.abc import Awaitable, Callable

import sentry_sdk
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from recallradar_api import __version__
from recallradar_api.routes import health
from recallradar_core.logs import configure_logging
from recallradar_core.settings import Settings, get_settings

logger = logging.getLogger("recallradar.api")

REQUEST_ID_HEADER = "X-Request-ID"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    if settings.sentry_dsn:
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.environment.value,
            release=__version__,
            send_default_pii=False,
        )

    app = FastAPI(title="RecallRadar API", version=__version__)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "Authorization", REQUEST_ID_HEADER],
        expose_headers=[REQUEST_ID_HEADER],
    )

    @app.middleware("http")
    async def request_context(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
        started = time.perf_counter()
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        logger.info(
            "request",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round((time.perf_counter() - started) * 1000, 1),
            },
        )
        return response

    app.include_router(health.router)
    return app
