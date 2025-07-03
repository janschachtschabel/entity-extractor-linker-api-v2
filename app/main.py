"""Main FastAPI application entrypoint.

Provides a minimal health endpoint and registers versioned API routers.
Lifespan handler prepares global resources (e.g. OpenAI client) in future.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime
import os
import sys

from fastapi import APIRouter, FastAPI, Request, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from loguru import logger
import json

from app.core.settings import settings

# ---------------------------------------------------------------------------
# API Routers
# ---------------------------------------------------------------------------

api_router = APIRouter(prefix="/api")


# ---------------------------------------------------------------------------
# FastAPI application factory
# ---------------------------------------------------------------------------


def create_app() -> FastAPI:
    """Instantiate FastAPI app and include routers."""

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
        logger.info("Backend started and ready to accept requests")
        yield
        logger.info("Shutting down backend")

    # --- LOGGING CONFIG ---
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs")
    os.makedirs(log_dir, exist_ok=True)
    current_date = datetime.now().strftime("%Y-%m-%d")
    log_file = os.path.join(log_dir, f"backend_api_{current_date}.log")
    logger.remove()
    log_level = "DEBUG"
    logger.add(
        sys.stdout,
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    )
    logger.add(
        log_file,
        level="DEBUG",
        rotation="10 MB",
        retention="30 days",
        compression="zip",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    )
    logger.info(f"Backend logging configured: {log_file} (level={log_level})")

    app = FastAPI(
        title="Entity Extraction & Knowledge API",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )
    
    # Add global exception handler for JSON parsing errors
    @app.exception_handler(json.JSONDecodeError)
    async def json_decode_error_handler(request: Request, exc: json.JSONDecodeError):
        """Handle JSON decode errors caused by invalid control characters."""
        logger.error(f"JSON decode error: {exc} for request {request.url}")
        return JSONResponse(
            status_code=422,
            content={
                "detail": [
                    {
                        "type": "json_invalid",
                        "loc": ["body"],
                        "msg": "Invalid JSON: Contains invalid control characters or malformed JSON",
                        "input": "<request body contains invalid characters>"
                    }
                ]
            }
        )
    
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Enhanced validation error handler with better JSON error messages."""
        # Check if this is a JSON decode error
        for error in exc.errors():
            if error.get('type') == 'json_invalid':
                logger.error(f"JSON validation error: {error} for request {request.url}")
                return JSONResponse(
                    status_code=422,
                    content={
                        "detail": [
                            {
                                "type": "json_invalid",
                                "loc": error.get('loc', ['body']),
                                "msg": "Invalid JSON: Request contains invalid control characters. Please ensure your text contains only printable characters.",
                                "input": "<request body contains invalid characters>",
                                "ctx": {
                                    "error": "Invalid control character detected",
                                    "suggestion": "Remove or replace control characters (\x00-\x1F except \t, \n, \r) from your input text"
                                }
                            }
                        ]
                    }
                )
        
        # Default validation error handling
        return JSONResponse(
            status_code=422,
            content={"detail": exc.errors()}
        )

    # Mount v1 routers
    from app.api.v1 import compendium as compendium_v1
    from app.api.v1 import linker as linker_v1
    from app.api.v1 import pipeline as pipeline_v1
    from app.api.v1 import qa as qa_v1
    from app.api.v1 import utils as utils_v1

    api_router.include_router(linker_v1.router)
    api_router.include_router(compendium_v1.router)
    api_router.include_router(qa_v1.router)
    api_router.include_router(utils_v1.router)
    api_router.include_router(pipeline_v1.router)

    # Add rate limiter middleware
    from app.middleware.ratelimiter import RateLimitMiddleware

    app.add_middleware(
        RateLimitMiddleware,
        limit=settings.RATE_LIMIT,
        window=settings.RATE_WINDOW,
    )

    # Health check endpoint
    @app.get("/health")
    async def health_check() -> dict[str, str]:
        """Health check endpoint for monitoring and Docker health checks."""
        from datetime import datetime
        try:
            from zoneinfo import ZoneInfo  # Python 3.9+
            berlin_now = datetime.now(ZoneInfo("Europe/Berlin"))
        except ImportError:
            import pytz
            berlin_now = datetime.now(pytz.timezone("Europe/Berlin"))
        return {
            "status": "healthy",
            "service": "entityextractorbatch",
            "version": "0.1.0",
            "timestamp": berlin_now.isoformat()
        }

    # Register top-level api router
    app.include_router(api_router)

    return app


app = create_app()

# For `uvicorn backend.app.main:app --reload`
__all__ = ["app"]
