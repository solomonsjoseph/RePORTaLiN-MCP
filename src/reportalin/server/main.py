"""MCP Server - Streamable HTTP transport."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from reportalin.core.config import get_settings
from reportalin.core.constants import SERVER_NAME, SERVER_VERSION
from reportalin.logging import get_logger
from reportalin.server.tools import mcp

settings = get_settings()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info(f"{SERVER_NAME} v{SERVER_VERSION} starting")
    yield


app = FastAPI(
    title=SERVER_NAME,
    version=SERVER_VERSION,
    lifespan=lifespan,
    docs_url="/docs" if settings.is_local else None,
)


@app.get("/health")
async def health():
    return {"status": "healthy"}


app.mount("/mcp", mcp.streamable_http_app(stateless_http=True, json_response=True))
