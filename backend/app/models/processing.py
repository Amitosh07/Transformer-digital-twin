"""Durable SQL receipts and H01 checkpoint envelopes; no mutable defaults."""
from datetime import datetime
from typing import Any
from sqlalchemy import String, DateTime, BigInteger, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class IngestionReceipt(Base):
    __tablename__ = 'ingestion_receipts'
    snapshot_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    payload_hash: Mapped[str] = mapped_column(String(64))
    transformer_id: Mapped[str] = mapped_column(String(128), ForeignKey('transformers.id'))
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    telemetry_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey('telemetry.id'))
    status: Mapped[str] = mapped_column(String(32))
    ingestion_outcome: Mapped[str] = mapped_column(String(32))
    ml_status: Mapped[str | None] = mapped_column(String(64))
    committed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    reason: Mapped[str | None] = mapped_column(String(128))
    accepted_payload_hash: Mapped[str] = mapped_column(String(64))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MLCheckpoint(Base):
    __tablename__ = 'ml_checkpoints'
    transformer_id: Mapped[str] = mapped_column(String(128), ForeignKey('transformers.id'), primary_key=True)
    checkpoint: Mapped[dict[str, Any]] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
