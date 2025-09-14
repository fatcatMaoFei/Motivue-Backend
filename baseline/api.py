from __future__ import annotations

from typing import Any, Dict, Optional, List
import json
import os

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .service import (
    update_baseline_smart,
    get_user_baseline,
)
from .storage import get_default_storage, SQLAlchemyBaselineStorage


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


