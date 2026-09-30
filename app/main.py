"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import router
from app.database import Base, engine
from app import models  # noqa: F401 - register model metadata before create_all
from app.config import portal_credentials_configured
from app.portal_client import PortalClient


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    app.state.portal_client = PortalClient() if portal_credentials_configured() else None
    yield
    if app.state.portal_client is not None:
        app.state.portal_client.close()


app = FastAPI(
    title="Flock Meter Data API",
    description=(
        "A read API for Urja Meter Ops meter, transformer, network-hierarchy, and energy data. "
        "Run `python -m app.sync` to refresh meter and transformer data from the portal."
    ),
    version="1.0.0",
    lifespan=lifespan,
)
app.include_router(router)


@app.get("/health", tags=["operations"], summary="Check service availability")
def health():
    return {"status": "ok"}
