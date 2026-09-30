"""SQLite read model mapped from the fields returned by Urja Meter Ops."""

from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class NetworkNode(Base):
    __tablename__ = "network_nodes"
    __table_args__ = (Index("ix_network_type_code", "node_type", "code"),)

    id: Mapped[str] = mapped_column(String(512), primary_key=True)
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    node_type: Mapped[str] = mapped_column(String(50), nullable=False)
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("network_nodes.id"), nullable=True)
    parent: Mapped["NetworkNode | None"] = relationship(remote_side="NetworkNode.id")


class Transformer(Base):
    __tablename__ = "transformers"

    code: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    feeder_code: Mapped[str] = mapped_column(String(100), primary_key=True, index=True)
    capacity_kva: Mapped[float | None] = mapped_column(Float, nullable=True)


class Meter(Base):
    __tablename__ = "meters"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    serial_number: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    make: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    phase_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    install_status: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    install_type: Mapped[str] = mapped_column(String(100), nullable=False)
    build: Mapped[str] = mapped_column(String(100), nullable=False)
    dt_code: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    network_node_id: Mapped[str] = mapped_column(ForeignKey("network_nodes.id"), nullable=False, index=True)
    network_node: Mapped[NetworkNode] = relationship()
    readings: Mapped[list["Reading"]] = relationship(back_populates="meter", cascade="all, delete-orphan")
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class Reading(Base):
    """Half-hourly register observations; kWh/kVAh are cumulative meter registers."""

    __tablename__ = "readings"
    __table_args__ = (
        UniqueConstraint("meter_id", "recorded_at", name="uq_reading_meter_timestamp"),
        Index("ix_readings_meter_recorded", "meter_id", "recorded_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    meter_id: Mapped[str] = mapped_column(ForeignKey("meters.id", ondelete="CASCADE"), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    kwh: Mapped[float | None] = mapped_column(Float, nullable=True)
    kvah: Mapped[float | None] = mapped_column(Float, nullable=True)
    volt_r: Mapped[float | None] = mapped_column(Float, nullable=True)
    meter: Mapped[Meter] = relationship(back_populates="readings")
