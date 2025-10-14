from __future__ import annotations

from typing import Any, Dict, List, Optional
from datetime import date as _date

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from libs.physio.core import compute_physiological_age
# TODO: Decouple from api/db and use a shared db infra module
from libs.core_domain.db import get_session, UserDaily


app = FastAPI(title="Physio-Age Service", version="0.1.0")


class PhysioAgeRequest(BaseModel):
    user_id: str
    date: Optional[str] = None  # YYYY-MM-DD (default today)
    user_gender: Optional[str] = None
    sdnn_series: List[float] = Field(..., min_items=30)
    rhr_series: List[float] = Field(..., min_items=30)


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/physio-age")
async def post_physio_age(req: PhysioAgeRequest) -> Dict[str, Any]:
    # Resolve date
    try:
        d = _date.fromisoformat(req.date) if req.date else _date.today()
    except Exception:
        d = _date.today()

    # Load today's sleep raw metrics from user_daily.device_metrics
    with get_session() as s:
        row = s.get(UserDaily, {"user_id": req.user_id, "date": d})
    if row is None or not isinstance(row.device_metrics, dict):
        raise HTTPException(status_code=404, detail="今日睡眠原始数据不存在，无法计算 CSS")

    dm = dict(row.device_metrics)

    # Build payload for physio-age core
    payload: Dict[str, Any] = {
        "sdnn_series": req.sdnn_series,
        "rhr_series": req.rhr_series,
        "user_gender": req.user_gender or "male",
        # raw sleep fields for CSS computation
        "total_sleep_minutes": dm.get("total_sleep_minutes"),
        "in_bed_minutes": dm.get("in_bed_minutes"),
        "deep_sleep_minutes": dm.get("deep_sleep_minutes"),
        "rem_sleep_minutes": dm.get("rem_sleep_minutes"),
        "sleep_duration_hours": dm.get("sleep_duration_hours"),
        "sleep_efficiency": dm.get("sleep_efficiency"),
        "restorative_ratio": dm.get("restorative_ratio"),
        "deep_sleep_ratio": dm.get("deep_sleep_ratio"),
        "rem_sleep_ratio": dm.get("rem_sleep_ratio"),
    }

    res = compute_physiological_age(payload)
    if res.get("status") != "ok":
        raise HTTPException(status_code=400, detail=res.get("message", "physio-age compute failed"))
    return {"user_id": req.user_id, "date": str(d), **res}


