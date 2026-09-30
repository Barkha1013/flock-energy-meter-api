"""Versioned read-only HTTP routes for meter and transformer data."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.orm import Session

from app.database import get_session
from app.models import Meter
from app.portal_client import PortalClient, PortalError
from app.repositories import get_meter, get_network_path, get_readings, list_meters, list_transformers
from app.schemas import MeterDetail, MeterPage, ReadingOut, TransformerPage
from app.services import cache_energy

router = APIRouter(prefix="/api/v1", tags=["meter data"])


def optional_portal_client(request: Request) -> PortalClient | None:
    return getattr(request.app.state, "portal_client", None)


@router.get("/meters", response_model=MeterPage, summary="List synchronized meters")
def meters(
    search: str | None = Query(default=None, min_length=1, max_length=100, description="Substring match for meter ID or serial number"),
    install_status: str | None = Query(default=None, description="Exact portal installation status"),
    make: str | None = Query(default=None, description="Exact manufacturer match"),
    phase_type: str | None = Query(default=None, description="Exact phase type: single or three"),
    dt_code: str | None = Query(default=None, description="Distribution-transformer code"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
):
    items, total = list_meters(
        session,
        install_status=install_status,
        make=make,
        phase_type=phase_type,
        dt_code=dt_code,
        search=search,
        limit=limit,
        offset=offset,
    )
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/meters/{meter_id}", response_model=MeterDetail, summary="Get a meter and its network path")
def meter(meter_id: str, session: Session = Depends(get_session)):
    item = get_meter(session, meter_id)
    if item is None:
        raise HTTPException(status_code=404, detail={"code": "meter_not_found", "message": "Meter was not found"})
    return {
        "id": item.id,
        "serial_number": item.serial_number,
        "make": item.make,
        "phase_type": item.phase_type,
        "install_status": item.install_status,
        "install_type": item.install_type,
        "build": item.build,
        "dt_code": item.dt_code,
        "latitude": item.latitude,
        "longitude": item.longitude,
        "network_hierarchy": get_network_path(session, item.network_node_id),
    }


@router.get("/transformers", response_model=TransformerPage, summary="List distribution transformers")
def transformers(
    feeder_code: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session),
):
    items, total = list_transformers(session, feeder_code=feeder_code, limit=limit, offset=offset)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/meters/{meter_id}/readings", response_model=list[ReadingOut], summary="Get recent meter energy readings")
def readings(
    meter_id: str,
    response: Response,
    start: datetime | None = Query(default=None, description="Inclusive ISO 8601 timestamp"),
    end: datetime | None = Query(default=None, description="Inclusive ISO 8601 timestamp"),
    limit: int = Query(default=100, ge=1, le=1000),
    portal: PortalClient | None = Depends(optional_portal_client),
    session: Session = Depends(get_session),
):
    if (start is not None and start.tzinfo is None) or (end is not None and end.tzinfo is None):
        raise HTTPException(status_code=422, detail={"code": "timezone_required", "message": "start and end must include a timezone offset"})
    if start and end and start > end:
        raise HTTPException(status_code=422, detail={"code": "invalid_range", "message": "start must be before or equal to end"})
    if session.get(Meter, meter_id) is None:
        raise HTTPException(status_code=404, detail={"code": "meter_not_found", "message": "Meter was not found; run a portal sync first"})

    start_utc = start.astimezone(timezone.utc).replace(tzinfo=None) if start else None
    end_utc = end.astimezone(timezone.utc).replace(tzinfo=None) if end else None
    if portal is not None:
        try:
            cache_energy(session, meter_id, portal.meter_energy(meter_id))
            response.headers["X-Data-Source"] = "portal"
        except PortalError as error:
            cached = get_readings(session, meter_id, start_utc, end_utc, limit)
            if not cached:
                raise HTTPException(status_code=502, detail={"code": "portal_unavailable", "message": str(error)}) from error
            response.headers["X-Data-Source"] = "sqlite-cache"
            response.headers["X-Data-Stale"] = "true"
    else:
        response.headers["X-Data-Source"] = "sqlite-cache"

    cached = get_readings(session, meter_id, start_utc, end_utc, limit)
    if not cached and portal is None:
        raise HTTPException(status_code=503, detail={"code": "portal_not_configured", "message": "Configure portal access or run a sync that includes readings"})
    return cached
