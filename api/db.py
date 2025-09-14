from __future__ import annotations

import os
from datetime import date
from typing import Optional

from dotenv import load_dotenv
from sqlalchemy import (
    JSON,
    Date,
    Integer,
    String,
    Column,
    create_engine,
    DateTime,
    Float,
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session


# Load .env early
load_dotenv()

# Prefer Supabase/Postgres via DATABASE_URL; fallback to local SQLite for dev
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./local.db")

# Ensure SSL for Supabase Postgres
connect_args = {}
if DATABASE_URL.startswith("postgresql") and "sslmode=" not in DATABASE_URL:
    sep = "&" if "?" in DATABASE_URL else "?"
    DATABASE_URL = f"{DATABASE_URL}{sep}sslmode=require"
    connect_args = {"sslmode": "require"}

engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)

Base = declarative_base()


class UserDaily(Base):
    __tablename__ = "user_daily"

    user_id: str = Column(String, primary_key=True)
    date: date = Column(Date, primary_key=True)

    previous_state_probs: Optional[dict] = Column(JSON, nullable=True)
    training_load: Optional[str] = Column(String, nullable=True)

    journal: Optional[dict] = Column(JSON, nullable=True)
    objective: Optional[dict] = Column(JSON, nullable=True)
    hooper: Optional[dict] = Column(JSON, nullable=True)
    cycle: Optional[dict] = Column(JSON, nullable=True)

    final_readiness_score: Optional[int] = Column(Integer, nullable=True)
    final_diagnosis: Optional[str] = Column(String, nullable=True)
    final_posterior_probs: Optional[dict] = Column(JSON, nullable=True)
    next_previous_state_probs: Optional[dict] = Column(JSON, nullable=True)

    daily_au: Optional[int] = Column(Integer, nullable=True)


class UserModel(Base):
    __tablename__ = "user_models"

    user_id: str = Column(String, primary_key=True)
    model_type: str = Column(String, primary_key=True, default="EMISSION_CPT")
    payload_json: Optional[dict] = Column(JSON, nullable=True)
    version: Optional[str] = Column(String, nullable=True)
    created_at: Optional[DateTime] = Column(DateTime, nullable=True)


class UserBaseline(Base):
    __tablename__ = "user_baselines"

    user_id: str = Column(String, primary_key=True)
    sleep_baseline_hours: Optional[float] = Column(Float, nullable=True)
    sleep_baseline_eff: Optional[float] = Column(Float, nullable=True)
    rest_baseline_ratio: Optional[float] = Column(Float, nullable=True)
    hrv_baseline_mu: Optional[float] = Column(Float, nullable=True)
    hrv_baseline_sd: Optional[float] = Column(Float, nullable=True)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def get_session() -> Session:
    return SessionLocal()
