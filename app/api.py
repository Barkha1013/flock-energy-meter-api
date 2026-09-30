"""Versioned HTTP routes."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import Meter
from app.repositories import get_meter, get_readings, list_meters
from app.schemas import ImportBatch, ImportResult, MeterDetail, MeterPage, ReadingOut
from app.services import import_batch

router = APIRouter(prefix="/api/v1", tags=["meter data"])


@router.get("/meters", response_model=MeterPage, summary="List meters")
def meters(
    status_filter: str | None = Query(default=None, alias="status", description="Exact status match"),
    network_node_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
):
    items, total = list_meters(session, status=status_filter, node_id=network_node_id, limit=limit, offset=offset)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/meters/{meter_id}", response_model=MeterDetail, summary="Get a meter")
def meter(meter_id: str, session: Session = Depends(get_session)):
    item = get_meter(session, meter_id)
    if item is None:
        raise HTTPException(status_code=404, detail={"code": "meter_not_found", "message": "Meter was not found"})
    return item


@router.get("/meters/{meter_id}/readings", response_model=list[ReadingOut], summary="Get meter consumption readings")
def readings(
    meter_id: str,
    start: datetime | None = Query(default=None, description="Inclusive ISO 8601 start timestamp"),
    end: datetime | None = Query(default=None, description="Inclusive ISO 8601 end timestamp"),
    limit: int = Query(default=100, ge=1, le=1000),
    session: Session = Depends(get_session),
):
    if (start is not None and start.tzinfo is None) or (end is not None and end.tzinfo is None):
        raise HTTPException(status_code=422, detail={"code": "timezone_required", "message": "start and end must include a timezone offset"})
    if start and end and start > end:
        raise HTTPException(status_code=422, detail={"code": "invalid_range", "message": "start must be before or equal to end"})
    if session.get(Meter, meter_id) is None:
        raise HTTPException(status_code=404, detail={"code": "meter_not_found", "message": "Meter was not found"})
    start_utc = start.astimezone(timezone.utc).replace(tzinfo=None) if start and start.tzinfo else start
    end_utc = end.astimezone(timezone.utc).replace(tzinfo=None) if end and end.tzinfo else end
    return get_readings(session, meter_id, start_utc, end_utc, limit)


@router.post("/imports", response_model=ImportResult, status_code=status.HTTP_200_OK,
             summary="Import a normalized data snapshot", tags=["data ingestion"])
def imports(batch: ImportBatch, session: Session = Depends(get_session)):
    """Local ingestion seam for a future portal-specific adapter; not portal write access."""
    try:
        return import_batch(session, batch)
    except ValueError as error:
        raise HTTPException(status_code=422, detail={"code": "invalid_import", "message": str(error)}) from error
