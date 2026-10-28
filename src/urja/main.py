import json
import logging
import secrets
import time
from collections import deque
from contextlib import asynccontextmanager
from datetime import date
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, FastAPI, Query, Request
from fastapi import Path as PathParameter
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles

from urja.config import Settings
from urja.errors import ServiceError
from urja.models import (
    Consumption,
    ErrorResponse,
    Meter,
    MeterPage,
    NetworkNode,
    NodePage,
    Result,
)
from urja.portal import PortalClient
from urja.service import MeterService

logger = logging.getLogger("urja")
bearer = HTTPBearer(auto_error=False, description="Private demo token, not portal credentials")
MeterID = Annotated[str, PathParameter(pattern=r"^[A-Za-z0-9_-]{1,80}$")]


def create_app(settings: Settings | None = None, service: MeterService | None = None):
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app):
        if service is None:
            settings.require_credentials()
            portal = PortalClient(settings)
            app.state.service = MeterService(portal, settings)
            yield
            await portal.close()
        else:
            app.state.service = service
            yield

    app = FastAPI(
        title="Urja Meter API",
        version="1.0.0",
        lifespan=lifespan,
        description="Read-only meter catalogue, cumulative registers and network hierarchy. "
        "Data endpoints require the private demo bearer token. "
        "Decimal readings are JSON strings to preserve source precision.",
        redoc_url=None,
    )
    app.state.service = service
    requests = deque()

    async def authorize(
        credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    ):
        expected = settings.demo_api_key.get_secret_value()
        if (
            not expected
            or not credentials
            or not secrets.compare_digest(credentials.credentials, expected)
        ):
            raise ServiceError("unauthorized", "A valid demo bearer token is required.", 401)
        now = time.monotonic()
        while requests and requests[0] < now - 60:
            requests.popleft()
        if len(requests) >= 120:
            raise ServiceError(
                "rate_limit", "Demo request limit reached. Try again in a minute.", 429
            )
        requests.append(now)

    @app.middleware("http")
    async def request_metadata(request: Request, call_next):
        request.state.request_id = uuid4().hex
        start = time.monotonic()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        logger.info(
            json.dumps(
                {
                    "request_id": request.state.request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "duration_ms": round((time.monotonic() - start) * 1000),
                }
            )
        )
        return response

    def error_response(request, code, message, status):
        headers = {"WWW-Authenticate": "Bearer"} if status == 401 else {}
        if status == 429:
            headers["Retry-After"] = "60"
        return JSONResponse(
            status_code=status,
            headers=headers,
            content={
                "error": {"code": code, "message": message, "request_id": request.state.request_id}
            },
        )

    @app.exception_handler(ServiceError)
    async def service_error(request, exc):
        return error_response(request, exc.code, exc.message, exc.status)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return error_response(request, "validation_error", "Invalid request parameters.", 422)

    @app.exception_handler(Exception)
    async def unexpected_error(request, exc):
        logger.error(
            "Unexpected failure request_id=%s type=%s", request.state.request_id, type(exc).__name__
        )
        return error_response(
            request, "internal_error", "An unexpected server error occurred.", 500
        )

    @app.get("/healthz", tags=["Health"])
    async def health():
        return {"status": "ok", "version": "1.0.0"}

    def get_service(request: Request) -> MeterService:
        return request.app.state.service

    Service = Annotated[MeterService, Depends(get_service)]
    common = {status: {"model": ErrorResponse} for status in (401, 404, 422, 429, 502, 503, 504)}
    from fastapi import APIRouter

    api = APIRouter(prefix="/api/v1", dependencies=[Depends(authorize)], responses=common)

    @api.get("/meters", response_model=Result[MeterPage], tags=["Meters"])
    async def meters(
        svc: Service,
        q: str = Query("", max_length=100),
        page: int = Query(1, ge=1, le=100000),
        page_size: int = Query(20, ge=1, le=100),
        status: str | None = Query(None, max_length=80),
        node_id: str | None = Query(None, max_length=100),
    ):
        """Search IDs/serials, filter status or hierarchy path, and page a complete export."""
        return await svc.meters(q, page, page_size, status, node_id)

    @api.get("/meters/{meter_id}", response_model=Result[Meter], tags=["Meters"])
    async def meter(meter_id: MeterID, svc: Service):
        """Nameplate, source hierarchy and coordinates from the signed portal export."""
        return await svc.meter(meter_id)

    @api.get("/meters/{meter_id}/consumption", response_model=Result[Consumption], tags=["Meters"])
    async def consumption(
        meter_id: MeterID,
        svc: Service,
        from_date: date | None = Query(None, alias="from"),
        to_date: date | None = Query(None, alias="to"),
    ):
        """Cumulative registers, NOT interval usage. Inclusive dates; max 366 days if both supplied.

        Without dates, uses the portal's default window (observed: fixed June 2026 data).
        Timezone is a configurable assumption, not an offset supplied by the source.
        """
        if from_date and to_date and (to_date < from_date or (to_date - from_date).days > 366):
            raise ServiceError(
                "validation_error", "Use an ordered date window of at most 366 days.", 422
            )
        return await svc.consumption(meter_id, from_date, to_date)

    @api.get("/network/nodes", response_model=Result[NodePage], tags=["Network"])
    async def nodes(
        svc: Service,
        parent_id: str | None = Query(None, max_length=100),
        level: str | None = Query(
            None, pattern="^(zone|circle|division|subdivision|substation|feeder|dt)$"
        ),
    ):
        """Root nodes by default; immediate children with parent_id, or all nodes at a level."""
        snapshot, meta = await svc.snapshot()
        if parent_id and parent_id not in snapshot.nodes:
            raise ServiceError("not_found", "Network node not found.", 404)
        items = [
            n
            for n in snapshot.nodes.values()
            if (n.parent_id == parent_id if not level or parent_id else True)
            and (not level or n.level == level)
        ]
        items.sort(key=lambda node: (node.level, node.code or "", node.id))
        return Result(data=NodePage(items=items, total=len(items)), meta=meta)

    @api.get("/network/nodes/{node_id}", response_model=Result[NetworkNode], tags=["Network"])
    async def node(node_id: str, svc: Service):
        snapshot, meta = await svc.snapshot()
        if node_id not in snapshot.nodes:
            raise ServiceError("not_found", "Network node not found.", 404)
        return Result(data=snapshot.nodes[node_id], meta=meta)

    app.include_router(api)
    if settings.web_dist.is_dir():
        app.mount("/assets", StaticFiles(directory=settings.web_dist / "assets"), name="assets")

        @app.get("/", include_in_schema=False)
        async def dashboard():
            return FileResponse(
                settings.web_dist / "index.html", headers={"Cache-Control": "no-cache"}
            )

    return app


app = create_app()
