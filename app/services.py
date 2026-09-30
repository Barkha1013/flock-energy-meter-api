"""Use cases and transaction boundaries."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Meter, NetworkNode, Reading
from app.schemas import ImportBatch


def import_batch(session: Session, batch: ImportBatch) -> dict[str, int]:
    """Upsert a normalized snapshot in one transaction; repeated imports are safe."""
    nodes_count = meters_count = readings_count = 0
    try:
        # Insert parent nodes before children, even when an import is unordered.
        node_items = {item.id: item for item in batch.network_nodes}
        if len(node_items) != len(batch.network_nodes):
            raise ValueError("network node IDs must be unique within an import")
        pending = dict(node_items)
        inserted: set[str] = set()
        while pending:
            ready = [
                item for item in pending.values()
                if item.parent_id is None or item.parent_id in inserted or session.get(NetworkNode, item.parent_id) is not None
            ]
            if not ready:
                raise ValueError("network nodes contain a missing parent or a cycle")
            for item in ready:
                node = session.get(NetworkNode, item.id)
                if node is None:
                    node = NetworkNode(id=item.id)
                    session.add(node)
                node.name, node.node_type, node.parent_id = item.name, item.node_type, item.parent_id
                nodes_count += 1
                inserted.add(item.id)
                pending.pop(item.id)
            session.flush()
        # Catch cycles that involve a previously stored node as well as this batch.
        for node_id in inserted:
            seen: set[str] = set()
            current_id: str | None = node_id
            while current_id is not None:
                if current_id in seen:
                    raise ValueError("network nodes contain a cycle")
                seen.add(current_id)
                current = session.get(NetworkNode, current_id)
                current_id = current.parent_id if current else None

        for item in batch.meters:
            meter = session.get(Meter, item.id)
            if meter is None:
                meter = Meter(id=item.id)
                session.add(meter)
            meter.serial_number = item.serial_number
            meter.status = item.status
            meter.meter_type = item.meter_type
            meter.latitude = item.latitude
            meter.longitude = item.longitude
            meter.installed_on = item.installed_on
            meter.network_node_id = item.network_node_id
            meter.updated_at = datetime.now(timezone.utc)
            meters_count += 1
            for item_reading in item.readings:
                reading = session.scalar(select(Reading).where(
                    Reading.meter_id == item.id,
                    Reading.recorded_at == item_reading.recorded_at,
                ))
                if reading is None:
                    reading = Reading(meter_id=item.id, recorded_at=item_reading.recorded_at)
                    session.add(reading)
                reading.consumption_kwh = item_reading.consumption_kwh
                readings_count += 1
        session.commit()
    except Exception:
        session.rollback()
        raise
    return {"nodes_upserted": nodes_count, "meters_upserted": meters_count, "readings_upserted": readings_count}
