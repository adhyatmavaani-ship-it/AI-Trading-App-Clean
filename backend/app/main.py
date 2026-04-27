import os

print("🔥 APP STARTED DEBUG 🔥")
print("REDIS_URL LOADED:", os.getenv("REDIS_URL"))

import asyncio
import logging
import signal
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
import uvicorn

from app.api.routes import backtests, frontend, health, meta, monitoring, public, realtime, simulation, trading
from app.core.config import get_settings
from app.core.exceptions import TradingSystemException
from app.core.logging import configure_logging
from app.middleware.auth import AuthMiddleware, get_api_key
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.request_context import RequestContextMiddleware
from app.services.signal_websocket_manager import get_signal_websocket_manager

logger = logging.getLogger(__name__)

settings = get_settings()
configure_logging(settings.log_level, settings.json_logs)


# Track shutdown signal
_shutdown_event = asyncio.Event()


def get_bind_port() -> int:
    return int(os.environ.get("PORT", 10000))


def _handle_shutdown_signal(signum, frame):
    """Handle SIGTERM/SIGINT for graceful shutdown."""
    logger.info(f"Received signal {signum}, initiating graceful shutdown...")
    _shutdown_event.set()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle - startup and shutdown."""
    # Startup
    await get_signal_websocket_manager().start()
    logger.info("Trading system startup - all services initialized")
    logger.info(f"Server started on port {get_bind_port()}")
    yield
    # Shutdown - graceful cleanup
    logger.info("Trading system shutdown - cleaning up resources...")
    await get_signal_websocket_manager().stop()
    await asyncio.sleep(0.1)  # Allow time for in-flight requests
    logger.info("Shutdown complete")


app = FastAPI(
    title="AI Crypto Trading System",
    version=settings.app_version_short,
    description="Production-oriented AI-driven crypto trading backend.",
    lifespan=lifespan,
    swagger_ui_parameters={"persistAuthorization": True},
    openapi_tags=[
        {"name": "Signals", "description": "Live trading signals produced by the central alpha and strategy engines."},
        {"name": "Virtual Order Batches", "description": "Aggregated virtual parent orders managed by the VOM execution layer."},
        {"name": "User Portfolio", "description": "Portfolio and profit-and-loss views used by the frontend dashboard."},
        {"name": "Trade Timeline", "description": "Trade lifecycle and execution timeline endpoints for auditability and UI timelines."},
        {"name": "Monitoring", "description": "System health, latency, drawdown, and platform readiness telemetry."},
        {"name": "Trading", "description": "Core trading evaluation and execution endpoints."},
        {"name": "Meta", "description": "Meta Controller audit trails and governance analytics for execution transparency."},
    ],
    contact={
        "name": "Trading Platform API",
        "url": "https://example.com/platform-api",
        "email": "api@example.com",
    },
    docs_url="/docs",
    redoc_url="/redoc",
)

try:
    signal.signal(signal.SIGTERM, _handle_shutdown_signal)
    signal.signal(signal.SIGINT, _handle_shutdown_signal)
except ValueError:
    logger.warning("Signal handlers unavailable in the current runtime")


# Exception handlers
@app.exception_handler(TradingSystemException)
async def trading_system_exception_handler(request, exc: TradingSystemException):
    """Handle custom trading system exceptions."""
    logger.warning(
        f"Trading system error",
        extra={
            "error_code": exc.error_code,
            "message": exc.message,
            "details": exc.details,
        },
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict(),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc: RequestValidationError):
    """Handle request validation errors with helpful details."""
    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(x) for x in error["loc"][1:]),
            "message": error["msg"],
            "type": error["type"],
        })
    logger.warning(f"Request validation failed: {len(errors)} errors")
    return JSONResponse(
        status_code=422,
        content={
            "error_code": "VALIDATION_ERROR",
            "message": "Request validation failed",
            "details": {"errors": errors},
        },
    )


# Middleware (order matters - last added is first executed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(AuthMiddleware)
app.add_middleware(RequestContextMiddleware)  # Added last so it executes first for every request


# Route registration
app.include_router(health.router)
app.include_router(health.router, prefix="/v1")
app.include_router(frontend.router, prefix="/v1", dependencies=[Depends(get_api_key)])
app.include_router(public.router, prefix="/v1")
app.include_router(trading.router, prefix="/v1", dependencies=[Depends(get_api_key)])
app.include_router(meta.router, prefix="/v1", dependencies=[Depends(get_api_key)])
app.include_router(backtests.router, prefix="/v1", dependencies=[Depends(get_api_key)])
app.include_router(monitoring.router, prefix="/v1", dependencies=[Depends(get_api_key)])
app.include_router(simulation.router, prefix="/v1", dependencies=[Depends(get_api_key)])
app.include_router(realtime.router)
app.include_router(realtime.router, prefix="/v1")


@app.api_route("/", methods=["GET", "HEAD"])
async def root() -> dict[str, str]:
    return {
        "service": settings.service_name,
        "status": "running",
        "version": settings.app_version_short,
        "environment": settings.environment,
    }


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=get_bind_port())
