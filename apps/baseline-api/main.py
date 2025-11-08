from __future__ import annotations

from typing import Any, Dict, Optional, List
from datetime import date as _date, timedelta
import json
import os
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.analytics.service import (
    update_baseline_smart,
    get_user_baseline,
)
from libs.analytics.storage import get_default_storage, SQLAlchemyBaselineStorage
from libs.analytics.daily_vs_baseline import compare_today_vs_baseline
from libs.core_domain.utils.sleep import compute_sleep_metrics
# TODO: Decouple from api/db and use a shared db infra module
from libs.core_domain.db import get_session, UserDaily


app = FastAPI(title="Baseline Service", version="0.1.0")


class SleepRecordIn(BaseModel):
    date: str
    sleep_duration_hours: float = Field(..., ge=0)
    sleep_efficiency: float = Field(..., ge=0, le=1)
    deep_sleep_minutes: Optional[float] = Field(None, ge=0)
    rem_sleep_minutes: Optional[float] = Field(None, ge=0)
    total_sleep_minutes: Optional[float] = Field(None, ge=0)
    restorative_ratio: Optional[float] = Field(None, ge=0, le=1)


class HRVRecordIn(BaseModel):
    timestamp: str
    sdnn_value: float = Field(..., ge=0)


class UpdateRequest(BaseModel):
    sleep_data: List[SleepRecordIn]
    hrv_data: List[HRVRecordIn]


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/api/baseline/user/{user_id}/update")
async def post_update_baseline(user_id: str, req: UpdateRequest) -> Dict[str, Any]:
    storage = _resolve_storage()
    result = update_baseline_smart(
        user_id=user_id,
        sleep_data=[r.model_dump() for r in req.sleep_data],
        hrv_data=[r.model_dump() for r in req.hrv_data],
        storage=storage,
    )

    # 成功（含 success_with_defaults）时发布 MQ 通知
    if result.get('status') in {'success', 'success_with_defaults'}:
        try:
            _publish_baseline_updated(user_id, result.get('baseline'))
        except Exception:
            # MQ 失败不影响主流程
            pass

    return result


@app.get("/api/baseline/user/{user_id}")
async def get_baseline(user_id: str) -> Dict[str, Any]:
    storage = _resolve_storage()
    baseline = get_user_baseline(user_id, storage)
    if not baseline:
        raise HTTPException(status_code=404, detail="baseline not found")
    return baseline.to_dict()


def _publish_baseline_updated(user_id: str, baseline_payload: Optional[Dict[str, Any]]) -> None:
    import pika

    url = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/%2f")
    params = pika.URLParameters(url)
    connection = pika.BlockingConnection(params)
    channel = connection.channel()
    queue_name = 'readiness.baseline_updated'
    channel.queue_declare(queue=queue_name, durable=False)

    message = {
        'event': 'baseline_updated',
        'user_id': user_id,
        'baseline': baseline_payload or {},
    }
    channel.basic_publish(exchange='', routing_key=queue_name, body=json.dumps(message).encode('utf-8'))
    connection.close()


def _resolve_storage():
    url = os.getenv("BASELINE_DATABASE_URL")
    if url:
        return SQLAlchemyBaselineStorage(url)
    return get_default_storage()


class TodayVsBaselineRequest(BaseModel):
    user_id: str
    window_days: int = Field(..., ge=1, le=180)
    date: Optional[str] = None  # YYYY-MM-DD (default today)


@app.post("/api/baseline/analytics/today-vs-baseline")
async def post_today_vs_baseline(req: TodayVsBaselineRequest) -> Dict[str, Any]:
    """对比“今天 vs 过去 window_days 天的动态基线（不让客户端选 metric）。”

    数据来源：readiness 的 `user_daily` 表（需要 baseline 容器具备 DATABASE_URL 访问权限）。
    计算：将序列最后一项视为“今天”，窗口均值不包含“今天”。
    """
    # Resolve date
    try:
        d = _date.fromisoformat(req.date) if req.date else _date.today()
    except Exception:
        d = _date.today()

    start = d - timedelta(days=int(req.window_days))

    # Collect daily series from user_daily
    payload_series: Dict[str, List[float]] = {
        'sleep_duration_hours': [],
        'sleep_efficiency': [],
        'restorative_ratio': [],
        'hrv_rmssd': [],
        'training_au': [],
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
        return {"user_id": req.user_id, "comparison_window_days": req.window_days, "analytics": {}, "message": "数据不足，至少需要今天+历史天数"}

    for r in rows:
        dm: Dict[str, Any] = r.device_metrics or {}

        # sleep hours
        hours = None
        if dm.get('sleep_duration_hours') is not None:
            try:
                hours = float(dm.get('sleep_duration_hours'))
            except Exception:
                hours = None
        elif dm.get('total_sleep_minutes') is not None:
            try:
                hours = float(dm.get('total_sleep_minutes')) / 60.0
            except Exception:
                hours = None
        payload_series['sleep_duration_hours'].append(hours if hours is not None else None)

        # efficiency & restorative via backend utils (fallback to raw fields)
        eff = None
        rr = None
        try:
            sm = compute_sleep_metrics(dm)
            eff = sm.get('sleep_efficiency')
            rr = sm.get('restorative_ratio')
        except Exception:
            pass
        if eff is None and dm.get('sleep_efficiency') is not None:
            try:
                val = float(dm.get('sleep_efficiency'))
                eff = val / 100.0 if val > 1.0 else val
            except Exception:
                eff = None
        if rr is None and dm.get('restorative_ratio') is not None:
            try:
                rr = float(dm.get('restorative_ratio'))
            except Exception:
                rr = None
        payload_series['sleep_efficiency'].append(eff if eff is not None else None)
        payload_series['restorative_ratio'].append(rr if rr is not None else None)

        # HRV (RMSSD today stored as hrv_rmssd_today)
        hrv = None
        if dm.get('hrv_rmssd_today') is not None:
            try:
                hrv = float(dm.get('hrv_rmssd_today'))
            except Exception:
                hrv = None
        payload_series['hrv_rmssd'].append(hrv if hrv is not None else None)

        # Training AU (optional)
        au = None
        if r.daily_au is not None:
            try:
                au = float(r.daily_au)
            except Exception:
                au = None
        payload_series['training_au'].append(au if au is not None else None)

    # Build analytics payload (exclude series with all None)
    analytics_input: Dict[str, Any] = {}
    for k, arr in payload_series.items():
        if any(x is not None for x in arr):
            analytics_input[k] = arr

    # Compute comparisons for the requested window only
    analytics = compare_today_vs_baseline(analytics_input, windows=[int(req.window_days)])

    return {
        "user_id": req.user_id,
        "comparison_window_days": int(req.window_days),
        "analytics": analytics,
    }
