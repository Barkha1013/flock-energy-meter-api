"""Synchronize the portal's meter export and transformer inventory into SQLite."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.database import Base, SessionLocal, engine
from app.models import Meter, NetworkNode, Transformer
from app.portal_client import PortalClient

HIERARCHY_LEVELS = ("zone", "circle", "division", "subdivision", "substation", "feeder", "dt")


def _required_text(record: dict, key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"portal export record is missing {key}")
    return value


def sync_portal(session: Session, portal: PortalClient) -> dict[str, object]:
    """Fetch a complete source snapshot before applying it in one local transaction."""
    meter_rows = portal.export_meters()
    transformer_rows = portal.list_transformers()
    now = datetime.now(timezone.utc)

    try:
        node_cache: dict[str, NetworkNode] = {}
        for row in meter_rows:
            hierarchy = row.get("hierarchy")
            if not isinstance(hierarchy, dict):
                raise ValueError("portal meter record is missing hierarchy")
            parent_id: str | None = None
            for level in HIERARCHY_LEVELS:
                source_node = hierarchy.get(level)
                if not isinstance(source_node, dict):
                    raise ValueError(f"portal meter record is missing hierarchy level {level}")
                code = _required_text(source_node, "code")
                name = _required_text(source_node, "name")
                node_id = f"{parent_id or 'root'}/{level}:{code}"
                node = session.get(NetworkNode, node_id)
                if node is None:
                    node = NetworkNode(id=node_id, code=code, name=name, node_type=level, parent_id=parent_id)
                    session.add(node)
                else:
                    node.code, node.name, node.node_type, node.parent_id = code, name, level, parent_id
                node_cache[node_id] = node
                parent_id = node_id

            geo = row.get("geo")
            if not isinstance(geo, dict) or geo.get("lat") is None or geo.get("lng") is None:
                raise ValueError("portal meter record is missing coordinates")
            meter_id = _required_text(row, "meterId")
            meter = session.get(Meter, meter_id)
            if meter is None:
                meter = Meter(id=meter_id)
                session.add(meter)
            meter.serial_number = _required_text(row, "serialNo")
            meter.make = _required_text(row, "make")
            meter.phase_type = _required_text(row, "phaseType")
            meter.install_status = _required_text(row, "installStatus")
            meter.install_type = _required_text(row, "installType")
            meter.build = _required_text(row, "build")
            meter.dt_code = _required_text(row, "dtCode")
            meter.latitude = float(geo["lat"])
            meter.longitude = float(geo["lng"])
            meter.network_node_id = parent_id
            meter.synced_at = now

        for row in transformer_rows:
            code = _required_text(row, "code")
            feeder_code = _required_text(row, "feederCode")
            transformer = session.get(Transformer, (code, feeder_code))
            if transformer is None:
                transformer = Transformer(code=code, feeder_code=feeder_code)
                session.add(transformer)
            transformer.name = _required_text(row, "name")
            transformer.feeder_code = feeder_code
            capacity = row.get("capacityKva")
            transformer.capacity_kva = float(capacity) if capacity is not None else None

        session.commit()
    except Exception:
        session.rollback()
        raise

    return {
        "meters_synced": len(meter_rows),
        "network_nodes_synced": len(node_cache),
        "transformers_synced": len(transformer_rows),
        "synced_at": now,
    }


def main() -> None:
    """Command-line entry point: python -m app.sync"""
    Base.metadata.create_all(bind=engine)
    portal = PortalClient()
    session = SessionLocal()
    try:
        result = sync_portal(session, portal)
        print(
            "Synced {meters_synced} meters, {network_nodes_synced} network nodes, "
            "and {transformers_synced} transformers at {synced_at}.".format(**result)
        )
    finally:
        session.close()
        portal.close()


if __name__ == "__main__":
    main()
