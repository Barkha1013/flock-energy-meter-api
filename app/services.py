"""Persistence helpers for source synchronization and cached readings."""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Meter, Reading

PORTAL_TIMEZONE = ZoneInfo("Asia/Kolkata")


def parse_portal_timestamp(value: str | datetime) -> datetime:
    """Convert the portal's local Jaipur display time to a UTC-naive SQLite value."""
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        normalized = value.strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            parsed = datetime.strptime(value, "%d/%m/%Y %H:%M")
    else:
        raise ValueError("energy timestamp has an unsupported type")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=PORTAL_TIMEZONE)
    return parsed.astimezone(timezone.utc).replace(tzinfo=None)


def _optional_float(value) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def cache_energy(session: Session, meter_id: str, rows: list[dict]) -> int:
    """Upsert recent portal readings; preserve source register names and values."""
    if session.get(Meter, meter_id) is None:
        raise ValueError("meter is not present in the last portal sync")
    updated = 0
    try:
        for source in rows:
            recorded_at = parse_portal_timestamp(source["timestamp"])
            reading = session.scalar(
                select(Reading).where(Reading.meter_id == meter_id, Reading.recorded_at == recorded_at)
            )
            if reading is None:
                reading = Reading(meter_id=meter_id, recorded_at=recorded_at)
                session.add(reading)
            reading.kwh = _optional_float(source.get("kwh"))
            reading.kvah = _optional_float(source.get("kvah"))
            reading.volt_r = _optional_float(source.get("voltR"))
            updated += 1
        session.commit()
    except Exception:
        session.rollback()
        raise
    return updated
