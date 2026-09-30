"""Database queries isolated from HTTP handlers."""

from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models import Meter, NetworkNode, Reading, Transformer


def list_meters(
    session: Session,
    *,
    install_status: str | None,
    make: str | None,
    phase_type: str | None,
    dt_code: str | None,
    search: str | None,
    limit: int,
    offset: int,
):
    query = select(Meter)
    count_query = select(func.count()).select_from(Meter)
    for column, value in (
        (Meter.install_status, install_status),
        (Meter.make, make),
        (Meter.phase_type, phase_type),
        (Meter.dt_code, dt_code),
    ):
        if value is not None:
            query = query.where(column == value)
            count_query = count_query.where(column == value)
    if search:
        pattern = f"%{search}%"
        match = or_(Meter.id.ilike(pattern), Meter.serial_number.ilike(pattern))
        query = query.where(match)
        count_query = count_query.where(match)
    items = session.scalars(query.order_by(Meter.id).limit(limit).offset(offset)).all()
    total = session.scalar(count_query) or 0
    return items, total


def get_meter(session: Session, meter_id: str) -> Meter | None:
    return session.scalar(select(Meter).where(Meter.id == meter_id))


def get_network_path(session: Session, node_id: str) -> list[NetworkNode]:
    path: list[NetworkNode] = []
    current_id: str | None = node_id
    while current_id:
        node = session.get(NetworkNode, current_id)
        if node is None:
            break
        path.append(node)
        current_id = node.parent_id
    return list(reversed(path))


def list_transformers(session: Session, *, feeder_code: str | None, limit: int, offset: int):
    query = select(Transformer)
    count_query = select(func.count()).select_from(Transformer)
    if feeder_code is not None:
        query = query.where(Transformer.feeder_code == feeder_code)
        count_query = count_query.where(Transformer.feeder_code == feeder_code)
    items = session.scalars(query.order_by(Transformer.code, Transformer.feeder_code).limit(limit).offset(offset)).all()
    return items, session.scalar(count_query) or 0


def get_readings(session: Session, meter_id: str, start: datetime | None, end: datetime | None, limit: int):
    query = select(Reading).where(Reading.meter_id == meter_id)
    if start:
        query = query.where(Reading.recorded_at >= start)
    if end:
        query = query.where(Reading.recorded_at <= end)
    return session.scalars(query.order_by(Reading.recorded_at.desc()).limit(limit)).all()
