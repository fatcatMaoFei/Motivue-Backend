from __future__ import annotations

from typing import Any, Dict, Optional

import json
import os
import threading
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.readiness_engine.service import compute_readiness_from_payload
from libs.readiness_engine.mapping import map_inputs_to_states
from libs.core_domain.db import (
    init_db,
    get_session,
    UserDaily,
    UserModel,
    UserBaseline,
    UserTrainingSession,
    UserStrengthRecord,
)

app = FastAPI(title="Readiness API", version="0.3.0")

# Enable CORS for local dev; replace with your frontend domains
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class PreviousStateProbs(BaseModel):
    Peak: float = 0.1
    Well_adapted: float = Field(0.5, alias="Well-adapted")
    FOR: float = 0.3
    Acute_Fatigue: float = Field(0.1, alias="Acute Fatigue")
    NFOR: float = 0.0
    OTS: float = 0.0

    @field_validator("Peak", "Well_adapted", "FOR", "Acute_Fatigue", "NFOR", "OTS")
    @classmethod
    def _prob_range(cls, v: float) -> float:
        if not 0 <= v <= 1:
            raise ValueError("probability must be in [0,1]")
        return v

    def to_engine(self) -> Dict[str, float]:
        return {
            "Peak": self.Peak,
            "Well-adapted": self.Well_adapted,
            "FOR": self.FOR,
            "Acute Fatigue": self.Acute_Fatigue,
            "NFOR": self.NFOR,
            "OTS": self.OTS,
        }


class Journal(BaseModel):
    alcohol_consumed: Optional[bool] = None
    late_caffeine: Optional[bool] = None
    screen_before_bed: Optional[bool] = None
    late_meal: Optional[bool] = None
    is_sick: Optional[bool] = None
    is_injured: Optional[bool] = None
    high_stress_event_today: Optional[bool] = None
    meditation_done_today: Optional[bool] = None


class Hooper(BaseModel):
    fatigue: Optional[int] = Field(None, ge=1, le=7)
    soreness: Optional[int] = Field(None, ge=1, le=7)
    stress: Optional[int] = Field(None, ge=1, le=7)
    sleep: Optional[int] = Field(None, ge=1, le=7)


class Cycle(BaseModel):
    day: Optional[int] = Field(None, ge=1)
    cycle_length: Optional[int] = Field(None, ge=20, le=40)


class NightlySleepSegment(BaseModel):
    """Raw sci-sleep segment for nightly HRV aggregation (optional).

    All timestamps are seconds since epoch (UTC or consistently local across
    sleep segments and per-minute samples).
    """

    start_ts: int
    duration_minutes: int = Field(..., ge=1)
    sleep_type: int


class NightlyHRVSample(BaseModel):
    """Minute-level health sample for nightly HRV aggregation (optional)."""

    ts: int
    step: Optional[int] = Field(None, ge=0)
    dynamic_hr: Optional[int] = Field(None, ge=0)
    hrv_index: Optional[float] = Field(None, ge=0)


class FromHKRequest(BaseModel):
    # Required basics
    user_id: str
    date: str
    gender: Optional[str] = None

    # iOS / Apple score
    ios_version: Optional[int] = Field(None, ge=0)
    apple_sleep_score: Optional[float] = Field(None, ge=0, le=100)

    # HealthKit-like raw metrics (optional)
    sleep_duration_hours: Optional[float] = Field(None, ge=0)
    total_sleep_minutes: Optional[float] = Field(None, ge=0)
    sleep_efficiency: Optional[float] = Field(None, ge=0, le=100)
    sleep_baseline_hours: Optional[float] = None
    sleep_baseline_eff: Optional[float] = None

    restorative_ratio: Optional[float] = Field(None, ge=0, le=1)
    deep_sleep_ratio: Optional[float] = Field(None, ge=0, le=1)
    rem_sleep_ratio: Optional[float] = Field(None, ge=0, le=1)
    rest_baseline_ratio: Optional[float] = Field(None, ge=0, le=1)

    hrv_rmssd_today: Optional[float] = Field(None, ge=0)
    hrv_baseline_mu: Optional[float] = Field(None, ge=0)
    hrv_baseline_sd: Optional[float] = Field(None, ge=0)
    hrv_rmssd_28day_avg: Optional[float] = Field(None, ge=0)
    hrv_rmssd_28day_sd: Optional[float] = Field(None, ge=0)
    hrv_rmssd_21day_avg: Optional[float] = Field(None, ge=0)
    hrv_rmssd_21day_sd: Optional[float] = Field(None, ge=0)
    hrv_rmssd_3day_avg: Optional[float] = Field(None, ge=0)
    hrv_rmssd_7day_avg: Optional[float] = Field(None, ge=0)

    # Optional raw nightly data from device (for backend-side aggregation)
    nightly_sleep_segments: Optional[list[NightlySleepSegment]] = None
    nightly_hrv_samples: Optional[list[NightlyHRVSample]] = None

    # Journal + Hooper
    journal: Optional[Journal] = None
    hooper: Optional[Hooper] = None

    # Cycle (female, optional)
    cycle: Optional[Cycle] = None

    # Required previous state probs (first day or backfill); client must send
    previous_state_probs: PreviousStateProbs

    # Optional: persist today's AU for later ACWR aggregation
    daily_au: Optional[int] = Field(None, ge=0)


@app.on_event("startup")
async def _init() -> None:
    init_db()
    _start_mq_consumer_background()


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/readiness/{user_id}")
async def get_readiness(user_id: str, date: Optional[str] = None) -> Dict[str, Any]:
    """
    获取用户指定日期的 Readiness 数据（直接从数据库读取）
    如果没有指定日期，默认为今天
    """
    from datetime import datetime as dt
    
    if date:
        try:
            target_date = dt.strptime(date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="日期格式错误，请使用 YYYY-MM-DD")
    else:
        target_date = dt.now().date()
    
    with get_session() as session:
        daily = session.query(UserDaily).filter_by(
            user_id=user_id,
            date=target_date
        ).first()
        
        if not daily:
            raise HTTPException(status_code=404, detail=f"未找到 {user_id} 在 {target_date} 的数据")
        
        # 从 objective 字段读取 evidence_pool
        evidence_pool = daily.objective if daily.objective else {}
        
        return {
            "user_id": user_id,
            "date": str(target_date),
            "final_readiness_score": daily.final_readiness_score,
            "current_readiness_score": daily.current_readiness_score,
            "final_diagnosis": daily.final_diagnosis,
            "evidence_pool": evidence_pool,
            "device_metrics": daily.device_metrics,
            "hooper": daily.hooper,
            "final_posterior_probs": daily.final_posterior_probs
        }


def _load_or_fetch_baseline(user_id: str, refresh: bool = False) -> Dict[str, Any]:
    # 1) try local table
    if not refresh:
        try:
            with get_session() as s:
                b = s.get(UserBaseline, user_id)
                if b:
                    mu = b.hrv_baseline_mu
                    sd = b.hrv_baseline_sd
                    # Clamp sd if invalid
                    changed = False
                    try:
                        if sd is not None and sd <= 0:
                            sd = 5.0
                            changed = True
                    except Exception:
                        sd = 5.0
                        changed = True
                    if changed:
                        b.hrv_baseline_sd = sd
                        s.merge(b)
                        s.commit()
                    return {
                        "sleep_baseline_hours": b.sleep_baseline_hours,
                        "sleep_baseline_eff": b.sleep_baseline_eff,
                        "rest_baseline_ratio": b.rest_baseline_ratio,
                        "hrv_baseline_mu": mu,
                        "hrv_baseline_sd": sd,
                    }
        except Exception:
            pass
    # 2) fetch from Baseline service
    try:
        import requests
        url = os.getenv("BASELINE_SERVICE_URL", "http://localhost:8001")
        r = requests.get(f"{url}/api/baseline/user/{user_id}", timeout=2)
        if r.ok:
            d = r.json()
            # Normalize types and guard sd
            mu = d.get("hrv_baseline_mu")
            sd = d.get("hrv_baseline_sd")
            try:
                mu = float(mu) if mu is not None else None
            except Exception:
                mu = None
            try:
                sd = float(sd) if sd is not None else None
            except Exception:
                sd = None
            if sd is not None and sd <= 0:
                sd = 5.0
            payload = {
                "sleep_baseline_hours": d.get("sleep_baseline_hours"),
                "sleep_baseline_eff": d.get("sleep_baseline_eff"),
                "rest_baseline_ratio": d.get("rest_baseline_ratio"),
                "hrv_baseline_mu": mu,
                "hrv_baseline_sd": sd,
            }
            # persist locally for next time (and ensure sd>0)
            try:
                with get_session() as s:
                    row = s.get(UserBaseline, user_id) or UserBaseline(user_id=user_id)
                    row.sleep_baseline_hours = payload.get("sleep_baseline_hours")
                    row.sleep_baseline_eff = payload.get("sleep_baseline_eff")
                    row.rest_baseline_ratio = payload.get("rest_baseline_ratio")
                    row.hrv_baseline_mu = payload.get("hrv_baseline_mu")
                    row.hrv_baseline_sd = payload.get("hrv_baseline_sd")
                    s.merge(row)
                    s.commit()
            except Exception:
                pass
            return payload
    except Exception:
        pass
    return {}


def _start_mq_consumer_background() -> None:
    def _run() -> None:
        try:
            import pika
            url = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/%2f")
            params = pika.URLParameters(url)
            connection = pika.BlockingConnection(params)
            channel = connection.channel()
            queue_name = 'readiness.baseline_updated'
            channel.queue_declare(queue=queue_name, durable=False)

            def _cb(ch, method, properties, body):
                try:
                    msg = json.loads(body.decode('utf-8'))
                    user_id = msg.get('user_id')
                    baseline = msg.get('baseline') or {}
                    # 保存/更新个性化模型：优先使用消息中的 emission_cpt，否则仅存 baseline 占位
                    try:
                        from datetime import datetime
                        payload = {"baseline": baseline}
                        if isinstance(msg.get('emission_cpt'), dict):
                            payload = {"emission_cpt": msg.get('emission_cpt')}
                        with get_session() as s:
                            row = s.get(UserModel, {"user_id": user_id, "model_type": "EMISSION_CPT"})
                            if row is None:
                                row = UserModel(user_id=user_id, model_type="EMISSION_CPT")
                            row.payload_json = payload
                            row.version = "v1"
                            row.created_at = datetime.utcnow()
                            s.merge(row)
                            s.commit()
                    except Exception:
                        pass
                except Exception:
                    pass

            channel.basic_consume(queue=queue_name, on_message_callback=_cb, auto_ack=True)
            channel.start_consuming()
        except Exception:
            # MQ不可用时静默跳过，不影响API可用性
            return

    t = threading.Thread(target=_run, daemon=True)
    t.start()


def _normalize_probs(ps: Dict[str, float]) -> Dict[str, float]:
    total = sum(float(v) for v in ps.values())
    if total <= 0:
        return {
            "Peak": 0.1,
            "Well-adapted": 0.5,
            "FOR": 0.3,
            "Acute Fatigue": 0.1,
            "NFOR": 0.0,
            "OTS": 0.0,
        }
    return {k: float(v) / total for k, v in ps.items()}


@app.get("/healthkit/template")
async def get_healthkit_template() -> Dict[str, Any]:
    return {
        "user_id": "u001",
        "date": "2025-09-05",
        "gender": "男性",
        "ios_version": 26,
        "apple_sleep_score": None,
        # HealthKit-like metrics
        "sleep_duration_hours": None,
        "total_sleep_minutes": None,
        "sleep_efficiency": None,
        "sleep_baseline_hours": None,
        "sleep_baseline_eff": None,
        "restorative_ratio": None,
        "deep_sleep_ratio": None,
        "rem_sleep_ratio": None,
        "rest_baseline_ratio": None,
        "hrv_rmssd_today": None,
        "hrv_baseline_mu": None,
        "hrv_baseline_sd": None,
        "hrv_rmssd_3day_avg": None,
        "hrv_rmssd_7day_avg": None,
        # Journal (yesterday short-term; today persistent flags)
        "journal": {
            "alcohol_consumed": None,
            "late_caffeine": None,
            "screen_before_bed": None,
            "late_meal": None,
            "is_sick": None,
            "is_injured": None,
        },
        # Hooper 1..7
        "hooper": {
            "fatigue": None,
            "soreness": None,
            "stress": None,
            "sleep": None,
        },
        # Female cycle
        "cycle": {
            "day": None,
            "cycle_length": 28,
        },
        # Optional previous probs (first day default)
        "previous_state_probs": {
            "Peak": 0.1,
            "Well-adapted": 0.5,
            "FOR": 0.3,
            "Acute Fatigue": 0.1,
            "NFOR": 0.0,
            "OTS": 0.0,
        },
    }


@app.get("/baseline/{user_id}")
async def get_baseline_cached(user_id: str, refresh: Optional[int] = 0) -> Dict[str, Any]:
    data = _load_or_fetch_baseline(user_id, refresh=bool(refresh))
    if not data:
        raise HTTPException(status_code=404, detail="baseline not found")
    return {"user_id": user_id, **data}


@app.post("/readiness/from-healthkit")
async def post_readiness_from_healthkit(req: FromHKRequest, session: Session = Depends(get_session)) -> Dict[str, Any]:
    raw_dict: Dict[str, Any] = req.model_dump(exclude_none=True)

    # If the client sent raw nightly sleep + HRV samples but did not provide a
    # daily HRV index yet, aggregate one here so downstream mapping and the
    # readiness engine can work with a stable day-level metric.
    if raw_dict.get("hrv_rmssd_today") is None and raw_dict.get("nightly_sleep_segments") and raw_dict.get("nightly_hrv_samples"):
        try:
            from libs.core_domain.utils.hrv import compute_nightly_hrv_metric

            hrv_result = compute_nightly_hrv_metric(
                sleep_segments=raw_dict.get("nightly_sleep_segments") or [],
                hrv_samples=raw_dict.get("nightly_hrv_samples") or [],
            )
            if hrv_result.get("hrv_rmssd_today") is not None:
                raw_dict["hrv_rmssd_today"] = hrv_result["hrv_rmssd_today"]
                # Optionally expose a simple quality flag for analytics
                raw_dict.setdefault("hrv_quality", hrv_result.get("quality_band"))
        except Exception:
            # Aggregation failure should never break readiness computation;
            # fallback to whatever daily HRV the client may have provided.
            pass

    # Inject baseline BEFORE mapping so mapping can use mu/sd & thresholds
    if not any(k in raw_dict for k in [
        "sleep_baseline_hours", "sleep_baseline_eff", "rest_baseline_ratio",
        "hrv_baseline_mu", "hrv_baseline_sd"
    ]):
        base_prefill = _load_or_fetch_baseline(req.user_id)
        for k, v in base_prefill.items():
            if v is not None and k not in raw_dict:
                raw_dict[k] = v
    mapped = map_inputs_to_states(raw_dict)

    # Build payload to engine
    payload: Dict[str, Any] = {
        "user_id": req.user_id,
        "date": req.date,
        "gender": req.gender or "男性",
        # Objective from mapping
        "objective": {
            "sleep_performance_state": mapped.get("sleep_performance"),
            "restorative_sleep": mapped.get("restorative_sleep"),
            "hrv_trend": mapped.get("hrv_trend"),
        },
        # Journal (persistent flags from mapping + any unified journal booleans)
        "journal": (raw_dict.get("journal") or {}),
        # Hooper passthrough
        "hooper": (raw_dict.get("hooper") or {}),
    }

    # Apple score evidence with iOS gating handled in mapping/service
    if raw_dict.get("apple_sleep_score") is not None:
        payload["apple_sleep_score"] = raw_dict.get("apple_sleep_score")
    if raw_dict.get("ios_version") is not None:
        payload["ios_version"] = raw_dict.get("ios_version")

    # Cycle unify
    if isinstance(raw_dict.get("cycle"), dict):
        cy = dict(raw_dict.get("cycle"))
        if "length" not in cy and cy.get("cycle_length") is not None:
            cy["length"] = cy.get("cycle_length")
        payload["cycle"] = cy

    # Normalize previous_state_probs if provided
    if isinstance(raw_dict.get("previous_state_probs"), dict):
        # Pydantic to ensure keys
        psp_model = PreviousStateProbs(**raw_dict["previous_state_probs"]).to_engine()
        payload["previous_state_probs"] = _normalize_probs(psp_model)

    # Load personalized EMISSION_CPT if available in DB
    try:
        with get_session() as s:
            um = s.get(UserModel, {"user_id": req.user_id, "model_type": "EMISSION_CPT"})
            if um and isinstance(um.payload_json, dict) and isinstance(um.payload_json.get("emission_cpt"), dict):
                payload["emission_cpt_override"] = um.payload_json.get("emission_cpt")
    except Exception:
        pass

    # (Baseline already merged into raw_dict prior to mapping.)

    try:
        result = compute_readiness_from_payload(payload)
        
        # FIX: SQLite Date type compatibility
        result_date_obj = result["date"]
        if isinstance(result_date_obj, str):
            try:
                result_date_obj = _date.fromisoformat(result_date_obj)
            except ValueError:
                result_date_obj = _date.today() # Fallback

        # Upsert into user_daily
        row = session.get(UserDaily, {"user_id": result["user_id"], "date": result_date_obj})
        if row is None:
            row = UserDaily(user_id=result["user_id"], date=result_date_obj)
            
        # FIX: Inject evidence_pool for iOS
        if "evidence_pool" not in result:
            # Attempt to retrieve from payload (where we mock injected it in seed/mapping)
            # The engine might not return it directly.
            # In the mapping (main.py:417), we built 'objective' but didn't explicitly populate 'evidence_pool' there in this file code block?
            # Wait, line 409: `mapped = map_inputs_to_states(raw_dict)`
            # The engine service likely doesn't return the raw evidence pool unless configured.
            # Let's construct a synthetic one from mapped states so iOS has SOMETHING to show.
            
            # Retrieve mapped values
            mapped = map_inputs_to_states(raw_dict)
            
            # Construct evidence pool for iOS
            result["evidence_pool"] = {
                "sleep_performance": mapped.get("sleep_performance", "Unknown"),
                "restorative_sleep": mapped.get("restorative_sleep", "Unknown"),
                "hrv_balance": mapped.get("hrv_trend", "Unknown"), # Mapping might name it hrv_trend
                "recovery_index": mapped.get("recovery_index", 50), # Mock/Default
                "subjective_fatigue": raw_dict.get("hooper", {}).get("fatigue", "Unknown")
            }
            
        # Persist raw device metrics for downstream analytics/physio-age
        device_metrics: Dict[str, Any] = {}
        for k in [
            "total_sleep_minutes", "in_bed_minutes", "deep_sleep_minutes", "rem_sleep_minutes",
            "sleep_duration_hours", "sleep_efficiency", "restorative_ratio",
            "deep_sleep_ratio", "rem_sleep_ratio", "hrv_rmssd_today"
        ]:
            if raw_dict.get(k) is not None:
                device_metrics[k] = raw_dict.get(k)
        row.previous_state_probs = payload.get("previous_state_probs")
        row.training_load = None
        row.journal = (payload.get("journal") or {})
        row.objective = (payload.get("objective") or {})
        row.hooper = (payload.get("hooper") or {})
        row.cycle = (payload.get("cycle") or {})
        row.device_metrics = (device_metrics or None)
        # Optional AU persist (no effect on today's compute)
        if raw_dict.get("daily_au") is not None:
            try:
                row.daily_au = int(raw_dict.get("daily_au"))
            except Exception:
                row.daily_au = None
        row.final_readiness_score = result.get("final_readiness_score")
        # 初始化当日“当前剩余准备度”：仅在尚未设置时进行，避免覆写消费后的值
        if row.current_readiness_score is None and row.final_readiness_score is not None:
            try:
                row.current_readiness_score = int(row.final_readiness_score)
            except Exception:
                row.current_readiness_score = row.final_readiness_score
        row.final_diagnosis = result.get("final_diagnosis")
        row.final_posterior_probs = result.get("final_posterior_probs")
        row.next_previous_state_probs = result.get("next_previous_state_probs")
        session.merge(row)
        session.commit()
        return result
    except HTTPException:
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=400, detail=str(e))


class TrainingSessionIn(BaseModel):
    rpe: Optional[int] = Field(None, ge=1, le=10)
    duration_minutes: Optional[int] = Field(None, ge=1)
    label: Optional[str] = None
    au: Optional[float] = Field(None, ge=0)


class ConsumptionRequest(BaseModel):
    user_id: str
    date: Optional[str] = None  # YYYY-MM-DD; default today if None
    sessions: list[TrainingSessionIn]


@app.post("/readiness/consumption")
async def post_readiness_consumption(req: ConsumptionRequest, session: Session = Depends(get_session)) -> Dict[str, Any]:
    from datetime import date as _date
    from libs.training import calculate_consumption

    # Resolve date (default to today)
    d = (req.date or str(_date.today()))
    # Fetch today's readiness from DB
    row = session.get(UserDaily, {"user_id": req.user_id, "date": d})
    if row is None or row.final_readiness_score is None:
        raise HTTPException(status_code=409, detail="今日准备度尚未计算，无法计算消耗")

    payload: Dict[str, Any] = {
        "user_id": req.user_id,
        "date": d,
        # 以当前剩余准备度为基准；若为空，回退到当日初始准备度
        "base_readiness_score": int(row.current_readiness_score if row.current_readiness_score is not None else row.final_readiness_score),
        "training_sessions": [s.model_dump(exclude_none=True) for s in req.sessions],
    }
    result = calculate_consumption(payload)  # type: ignore[arg-type]
    # 将展示用 readiness 写回当前剩余准备度，形成当日可消耗的“状态”
    try:
        row.current_readiness_score = int(result.get("display_readiness") or 0)
        session.merge(row)
        session.commit()
    except Exception:
        session.rollback()
        # 不中断响应，仅记录失败
        pass
    return result


# ---------------- New training/strength endpoints ---------------- #

class TrainingSessionCreate(BaseModel):
    user_id: str
    date: str  # YYYY-MM-DD
    type_tags: list[str] = Field(default_factory=list)
    rpe: Optional[int] = Field(None, ge=1, le=10)
    duration_minutes: Optional[int] = Field(None, ge=0)
    au: Optional[float] = Field(None, ge=0)
    notes: Optional[str] = None


@app.post("/training/session")
async def post_training_session(req: TrainingSessionCreate) -> Dict[str, Any]:
    from datetime import date as _date

    try:
        d = _date.fromisoformat(req.date)
    except Exception:
        raise HTTPException(status_code=422, detail="invalid date format (YYYY-MM-DD)")

    row = UserTrainingSession(
        user_id=req.user_id,
        date=d,
        type_tags=list(req.type_tags or []),
        rpe=req.rpe,
        duration_minutes=req.duration_minutes,
        au=req.au,
        notes=req.notes,
    )
    with get_session() as s:
        s.add(row)
        s.commit()
        s.refresh(row)
    return {"status": "ok", "id": row.id}


class StrengthRecordCreate(BaseModel):
    user_id: str
    exercise_name: str
    record_date: str  # YYYY-MM-DD
    weight_kg: float = Field(..., gt=0)
    reps: int = Field(..., ge=1)
    notes: Optional[str] = None


def _epley_one_rm(weight: float, reps: int) -> float:
    # Epley formula
    return float(weight) * (1.0 + float(reps) / 30.0)


@app.post("/strength/record")
async def post_strength_record(req: StrengthRecordCreate) -> Dict[str, Any]:
    from datetime import date as _date

    try:
        d = _date.fromisoformat(req.record_date)
    except Exception:
        raise HTTPException(status_code=422, detail="invalid record_date (YYYY-MM-DD)")

    one_rm = _epley_one_rm(req.weight_kg, req.reps)
    row = UserStrengthRecord(
        user_id=req.user_id,
        exercise_name=req.exercise_name,
        record_date=d,
        weight_kg=float(req.weight_kg),
        reps=int(req.reps),
        one_rm_est=one_rm,
        notes=req.notes,
    )
    with get_session() as s:
        s.add(row)
        s.commit()
        s.refresh(row)
    return {"status": "ok", "id": row.id, "one_rm_est": round(one_rm, 2)}


@app.get("/training/counts")
async def get_training_counts(user_id: str, tag: Optional[str] = None, days: Optional[int] = None) -> Dict[str, Any]:
    from datetime import date as _date, timedelta as _td
    today = _date.today()
    with get_session() as s:
        q = s.query(UserTrainingSession).filter(UserTrainingSession.user_id == user_id)
        if days and days > 0:
            q = q.filter(UserTrainingSession.date >= (today - _td(days=int(days))))
        if tag:
            # JSON array contains `tag`
            try:
                q = q.filter(UserTrainingSession.type_tags.contains([tag]))
            except Exception:
                # Fallback for dialects lacking JSON contains
                rows = [r for r in q]
                cnt = sum(1 for r in rows if isinstance(r.type_tags, list) and tag in r.type_tags)
                return {"user_id": user_id, "tag": tag, "days": days, "count": int(cnt)}
        count = q.count()
    return {"user_id": user_id, "tag": tag, "days": days, "count": int(count)}


@app.get("/strength/latest")
async def get_strength_latest(user_id: str, exercise: Optional[str] = None) -> Dict[str, Any]:
    from collections import defaultdict
    with get_session() as s:
        if exercise:
            row = (
                s.query(UserStrengthRecord)
                .filter(UserStrengthRecord.user_id == user_id)
                .filter(UserStrengthRecord.exercise_name == exercise)
                .order_by(UserStrengthRecord.record_date.desc(), UserStrengthRecord.created_at.desc())
                .first()
            )
            if not row:
                return {"user_id": user_id, "latest": {}}
            return {
                "user_id": user_id,
                "latest": {
                    exercise: {
                        "record_date": str(row.record_date),
                        "weight_kg": row.weight_kg,
                        "reps": row.reps,
                        "one_rm_est": row.one_rm_est,
                    }
                },
            }
        # All exercises: pick latest per exercise
        rows = (
            s.query(UserStrengthRecord)
            .filter(UserStrengthRecord.user_id == user_id)
            .order_by(UserStrengthRecord.exercise_name.asc(), UserStrengthRecord.record_date.desc(), UserStrengthRecord.created_at.desc())
            .all()
        )
        latest: Dict[str, Any] = {}
        seen: set[str] = set()
        for r in rows:
            if r.exercise_name in seen:
                continue
            latest[r.exercise_name] = {
                "record_date": str(r.record_date),
                "weight_kg": r.weight_kg,
                "reps": r.reps,
                "one_rm_est": r.one_rm_est,
            }
            seen.add(r.exercise_name)
        return {"user_id": user_id, "latest": latest}


@app.get("/strength/history")
async def get_strength_history(user_id: str, exercise: str, days: Optional[int] = 60) -> Dict[str, Any]:
    from datetime import date as _date, timedelta as _td
    start = None
    if days and days > 0:
        start = _date.today() - _td(days=int(days))
    with get_session() as s:
        q = s.query(UserStrengthRecord).filter(UserStrengthRecord.user_id == user_id).filter(UserStrengthRecord.exercise_name == exercise)
        if start is not None:
            q = q.filter(UserStrengthRecord.record_date >= start)
        rows = q.order_by(UserStrengthRecord.record_date.asc(), UserStrengthRecord.created_at.asc()).all()
        out = [
            {
                "record_date": str(r.record_date),
                "weight_kg": r.weight_kg,
                "reps": r.reps,
                "one_rm_est": r.one_rm_est,
            }
            for r in rows
        ]
    return {"user_id": user_id, "exercise": exercise, "days": days, "history": out}


# ---------------- Today vs Baseline Analytics ---------------- #
# (Ported from baseline-api so we only need one backend process)

class TodayVsBaselineAnalyticsRequest(BaseModel):
    user_id: str
    window_days: int = Field(..., ge=1, le=180)
    date: Optional[str] = None  # YYYY-MM-DD (default today)


@app.post("/api/baseline/analytics/today-vs-baseline")
async def post_today_vs_baseline_analytics(req: TodayVsBaselineAnalyticsRequest) -> Dict[str, Any]:
    """Compare today vs past N days baseline. Data from user_daily table."""
    from datetime import date as _date, timedelta
    
    try:
        d = _date.fromisoformat(req.date) if req.date else _date.today()
    except Exception:
        d = _date.today()

    start = d - timedelta(days=int(req.window_days))

    # Collect daily series
    payload_series: Dict[str, list] = {
        'sleep_duration_hours': [],
        'sleep_efficiency': [],
        'restorative_ratio': [],
        'hrv_rmssd': [],
    }

    with get_session() as s:
        rows = (
            s.query(UserDaily)
            .filter(UserDaily.user_id == req.user_id)
            .filter(UserDaily.date >= start)
            .filter(UserDaily.date <= d)
            .order_by(UserDaily.date.asc())
            .all()
        )

    if not rows or len(rows) < 2:
        # Not enough data - return empty analytics with mock fallback
        return {
            "user_id": req.user_id,
            "comparison_window_days": req.window_days,
            "analytics": {
                "hrv_rmssd": {"today": 65.0, "baseline_mean": 60.0, "series": [58, 62, 60, 65, 63, 68, 65]},
                "sleep_efficiency": {"today": 0.88, "baseline_mean": 0.85, "series": [0.82, 0.85, 0.88, 0.84, 0.86, 0.90, 0.88]},
                "restorative_ratio": {"today": 0.22, "baseline_mean": 0.20, "series": [0.18, 0.20, 0.22, 0.19, 0.21, 0.23, 0.22]},
                "sleep_duration_hours": {"today": 7.5, "baseline_mean": 7.2, "series": [7.0, 7.2, 7.5, 6.8, 7.4, 7.8, 7.5]},
            },
            "message": "Using mock data - need more historical records"
        }

    # Extract metrics from device_metrics
    for r in rows:
        dm: Dict[str, Any] = r.device_metrics or {}

        # Sleep hours
        hours = dm.get('sleep_duration_hours')
        if hours is None and dm.get('total_sleep_minutes') is not None:
            try:
                hours = float(dm['total_sleep_minutes']) / 60.0
            except:
                hours = None
        payload_series['sleep_duration_hours'].append(hours)

        # Efficiency
        eff = dm.get('sleep_efficiency')
        if eff is not None and eff > 1.0:
            eff = eff / 100.0
        payload_series['sleep_efficiency'].append(eff)

        # Restorative ratio
        payload_series['restorative_ratio'].append(dm.get('restorative_ratio'))

        # HRV
        payload_series['hrv_rmssd'].append(dm.get('hrv_rmssd_today'))

    # Build analytics response
    analytics: Dict[str, Any] = {}
    for key, series in payload_series.items():
        valid = [v for v in series if v is not None]
        if valid:
            today_val = valid[-1] if valid else None
            baseline_vals = valid[:-1] if len(valid) > 1 else valid
            baseline_mean = sum(baseline_vals) / len(baseline_vals) if baseline_vals else None
            analytics[key] = {
                "today": today_val,
                "baseline_mean": baseline_mean,
                "series": series,
            }

    return {
        "user_id": req.user_id,
        "comparison_window_days": req.window_days,
        "analytics": analytics,
    }

