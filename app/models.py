"""Relational representation of meters, network placement, and readings."""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class NetworkNode(Base):
    __tablename__ = "network_nodes"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    node_type: Mapped[str] = mapped_column(String(50), nullable=False)
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("network_nodes.id"), nullable=True)
    parent: Mapped["NetworkNode | None"] = relationship(remote_side="NetworkNode.id")
    meters: Mapped[list["Meter"]] = relationship(back_populates="network_node")


class Meter(Base):
    __tablename__ = "meters"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    serial_number: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    status: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    meter_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    installed_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    network_node_id: Mapped[str | None] = mapped_column(ForeignKey("network_nodes.id"), nullable=True, index=True)
    network_node: Mapped[NetworkNode | None] = relationship(back_populates="meters")
    readings: Mapped[list["Reading"]] = relationship(back_populates="meter", cascade="all, delete-orphan")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class Reading(Base):
    __tablename__ = "readings"
    __table_args__ = (
        UniqueConstraint("meter_id", "recorded_at", name="uq_reading_meter_timestamp"),
        Index("ix_readings_meter_recorded", "meter_id", "recorded_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    meter_id: Mapped[str] = mapped_column(ForeignKey("meters.id", ondelete="CASCADE"), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumption_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    meter: Mapped[Meter] = relationship(back_populates="readings")
