from __future__ import annotations

import os
from datetime import date
from typing import Optional

from dotenv import load_dotenv
from sqlalchemy import JSON, Date, Integer, String, Column, create_engine, DateTime, Float, func, Text, Index
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


class User(Base):
    __tablename__ = "users"

    user_id: str = Column(String, primary_key=True)
    email: str = Column(String, unique=True, nullable=False, index=True)
    password_hash: str = Column(String, nullable=False)
    display_name: Optional[str] = Column(String, nullable=True)
    gender: Optional[str] = Column(String, nullable=True)
    auth_provider: Optional[str] = Column(String, nullable=True)  # local/google/apple
    oauth_sub: Optional[str] = Column(String, nullable=True)
    metadata_json: Optional[dict] = Column(JSON, nullable=True)
    created_at: DateTime = Column(DateTime, nullable=False, server_default=func.now())
    updated_at: DateTime = Column(DateTime, nullable=False, server_default=func.now())


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    user_id: str = Column(String, nullable=False, index=True)
    token_hash: str = Column(String, nullable=False, index=True)
    expires_at: DateTime = Column(DateTime, nullable=False)
    revoked: bool = Column(Integer, nullable=False, default=0)
    created_at: DateTime = Column(DateTime, nullable=False, server_default=func.now())

Index("ix_refresh_user_token", RefreshToken.user_id, RefreshToken.token_hash)


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
    device_metrics: Optional[dict] = Column(JSON, nullable=True)

    final_readiness_score: Optional[int] = Column(Integer, nullable=True)
    # 展示用的“当前剩余准备度”，由 /readiness/consumption 动态更新；
    # 每日由 /readiness/from-healthkit 初始化为 final_readiness_score。
    current_readiness_score: Optional[int] = Column(Integer, nullable=True)
    final_diagnosis: Optional[str] = Column(String, nullable=True)
    final_posterior_probs: Optional[dict] = Column(JSON, nullable=True)
    next_previous_state_probs: Optional[dict] = Column(JSON, nullable=True)

    daily_au: Optional[int] = Column(Integer, nullable=True)
    report_notes: Optional[str] = Column(Text, nullable=True)


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


class WeeklyReportRecord(Base):
    __tablename__ = "weekly_reports"

    user_id: str = Column(String, primary_key=True)
    week_start: date = Column(Date, primary_key=True)
    week_end: date = Column(Date, nullable=False)
    report_version: Optional[str] = Column(String, nullable=True)
    report_payload: dict = Column(JSON, nullable=False)
    markdown_report: str = Column(Text, nullable=False)
    created_at: DateTime = Column(DateTime, nullable=False, server_default=func.now())


# ---------------- New training/strength tables ---------------- #


class UserTrainingSession(Base):
    __tablename__ = "user_training_sessions"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    user_id: str = Column(String, nullable=False, index=True)
    date: date = Column(Date, nullable=False, index=True)
    # Array of machine-readable tags, e.g., ["strength:chest", "strength:push"],
    # ["cardio:rower"], ["sport:tennis"]. Stored as JSON array for portability.
    type_tags: Optional[dict] | Optional[list] = Column(JSON, nullable=True)
    rpe: Optional[int] = Column(Integer, nullable=True)
    duration_minutes: Optional[int] = Column(Integer, nullable=True)
    au: Optional[float] = Column(Float, nullable=True)
    notes: Optional[str] = Column(Text, nullable=True)
    created_at: DateTime = Column(DateTime, nullable=False, server_default=func.now())


Index("ix_user_training_sessions_user_date", UserTrainingSession.user_id, UserTrainingSession.date)


class UserStrengthRecord(Base):
    __tablename__ = "user_strength_records"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    user_id: str = Column(String, nullable=False, index=True)
    exercise_name: str = Column(String, nullable=False, index=True)
    record_date: date = Column(Date, nullable=False, index=True)
    weight_kg: float = Column(Float, nullable=False)
    reps: int = Column(Integer, nullable=False)
    one_rm_est: Optional[float] = Column(Float, nullable=True)
    notes: Optional[str] = Column(Text, nullable=True)
    created_at: DateTime = Column(DateTime, nullable=False, server_default=func.now())


Index(
    "ix_user_strength_latest",
    UserStrengthRecord.user_id,
    UserStrengthRecord.exercise_name,
    UserStrengthRecord.record_date,
)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    # 轻量级列迁移：为已存在的 user_daily 表添加 current_readiness_score 列
    try:
        with engine.begin() as conn:
            dialect = engine.dialect.name
            if dialect == "postgresql":
                conn.exec_driver_sql(
                    "ALTER TABLE user_daily ADD COLUMN IF NOT EXISTS current_readiness_score INTEGER"
                )
            elif dialect == "sqlite":
                # SQLite 不支持 IF NOT EXISTS；用 PRAGMA 检查
                res = conn.exec_driver_sql("PRAGMA table_info('user_daily')")
                cols = [row[1] for row in res]
                if "current_readiness_score" not in cols:
                    conn.exec_driver_sql(
                        "ALTER TABLE user_daily ADD COLUMN current_readiness_score INTEGER"
                    )
    except Exception:
        # 迁移失败不影响 API 启动；后续由 DBA 修复
        pass


def get_session() -> Session:
    return SessionLocal()
