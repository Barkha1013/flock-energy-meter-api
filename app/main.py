"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import router
from app.database import Base, engine
from app import models  # noqa: F401 - register model metadata before create_all


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Flock Meter Data API",
    description=(
        "A read API for normalized smart-meter, network placement, and consumption data. "
        "Portal-specific discovery and synchronization are documented in PROTOCOL.md."
    ),
    version="1.0.0",
    lifespan=lifespan,
)
app.include_router(router)


@app.get("/health", tags=["operations"], summary="Check service availability")
def health():
    return {"status": "ok"}
