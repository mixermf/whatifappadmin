from __future__ import annotations

from sqlalchemy import BigInteger, Column, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSONB

from admin_db import Base


class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    install_id_hash = Column(String, nullable=True)
    google_sub = Column(String, nullable=True)
    credits_balance = Column(Integer, nullable=False, default=0)
    merged_into_user_id = Column(BigInteger, nullable=True)
    last_seen_at = Column(DateTime(timezone=True), nullable=True)


class CreditLedger(Base):
    __tablename__ = "credit_ledger"

    id = Column(BigInteger, primary_key=True)
    user_id = Column(BigInteger, index=True, nullable=False)
    type = Column(String, nullable=False)
    delta = Column(Integer, nullable=False)
    ref_type = Column(String, nullable=True)
    ref_id = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)


class IapTransaction(Base):
    __tablename__ = "iap_transactions"

    id = Column(BigInteger, primary_key=True)
    user_id = Column(BigInteger, index=True, nullable=False)
    store = Column(String, nullable=False)
    product_id = Column(String, nullable=True)
    purchase_token = Column(String, nullable=True)
    status = Column(String, nullable=False)
    raw_payload = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    verified_at = Column(DateTime(timezone=True), nullable=True)


class EventLog(Base):
    __tablename__ = "event_log"

    id = Column(BigInteger, primary_key=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    trace_id = Column(String, index=True, nullable=True)
    user_id = Column(BigInteger, index=True, nullable=True)
    job_id = Column(String, index=True, nullable=True)
    event = Column(String, index=True, nullable=False)
    payload = Column(JSONB, nullable=True)
