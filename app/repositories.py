"""Database queries isolated from HTTP handlers."""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models import Meter, Reading


def list_meters(session: Session, *, status: str | None, node_id: str | None, limit: int, offset: int):
    query = select(Meter)
    count_query = select(func.count()).select_from(Meter)
    if status is not None:
        query = query.where(Meter.status == status)
        count_query = count_query.where(Meter.status == status)
    if node_id is not None:
        query = query.where(Meter.network_node_id == node_id)
        count_query = count_query.where(Meter.network_node_id == node_id)
    items = session.scalars(query.order_by(Meter.id).limit(limit).offset(offset)).all()
    total = session.scalar(count_query) or 0
    return items, total


def get_meter(session: Session, meter_id: str) -> Meter | None:
    return session.scalar(select(Meter).options(joinedload(Meter.network_node)).where(Meter.id == meter_id))


def get_readings(session: Session, meter_id: str, start: datetime | None, end: datetime | None, limit: int):
    query = select(Reading).where(Reading.meter_id == meter_id)
    if start:
        query = query.where(Reading.recorded_at >= start)
    if end:
        query = query.where(Reading.recorded_at <= end)
    return session.scalars(query.order_by(Reading.recorded_at.desc()).limit(limit)).all()
