from __future__ import annotations

from typing import Any, Dict

import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from weekly_report.workflow.graph import run_workflow
from libs.core_domain.models import WeeklyHistoryEntry, WeeklyReportPackage, WeeklyFinalReport
from weekly_report.pipeline import generate_weekly_report
from weekly_report.finalizer import generate_weekly_final_report
from weekly_report.llm.provider import get_llm_provider
# TODO: Decouple from api/db and use a shared db infra module
from libs.core_domain.db import (
    init_db,
    get_session,
    WeeklyReportRecord,
    UserTrainingSession,
    UserStrengthRecord,
)


app = FastAPI(
    title="Weekly Report Service",
    version="0.1.0",
    description="Generate analyst/communicator/final weekly reports from readiness payloads.",
)

logger = logging.getLogger(__name__)


class WeeklyReportRequest(BaseModel):
    """Input schema for the weekly report microservice (LLM required)."""

    payload: Dict[str, Any] = Field(
        ...,
        description=(
            "Phase 1 ingest payload：包含今日 raw_inputs（可选）+ history（必需，7 条 WeeklyHistoryEntry），"
            "需同时提供 recent_training_au 以计算 ACWR。payload 样例见 samples/original_payload_sample.json。"
        ),
    )
    sleep_baseline_hours: float | None = Field(
        default=None, description="覆盖 payload 内的 sleep_baseline_hours（可选）。"
    )
    hrv_baseline_mu: float | None = Field(
        default=None, description="覆盖 payload 内的 hrv_baseline_mu（可选）。"
    )
    persist: bool = Field(
        default=False,
        description="为 True 时会把 Phase 5 结果写入 weekly_reports 表（需数据库配置完成）。",
    )


class WeeklyReportResponse(BaseModel):
    """统一返回 Phase 3、Phase 4、Phase 5 的结果，方便数据库或前端直接使用。

    - phase3_state：包含 metrics/insights/next_week_plan。
    - package：图表及多智能体文稿。
    - final_report：Markdown（含 `[[chart:<id>]]` 锚点）、HTML（可选）、chart_ids、call_to_action。
    """

    phase3_state: Dict[str, Any]
    package: WeeklyReportPackage
    final_report: WeeklyFinalReport
    persisted: bool = False


@app.on_event("startup")
async def _startup() -> None:
    init_db()


@app.post("/weekly-report/run", response_model=WeeklyReportResponse)
async def run_weekly_report(request: WeeklyReportRequest) -> WeeklyReportResponse:
    """
    执行完整 Phase 1 → Phase 5 流程。

    - payload：今天的 raw_inputs（可选） + `history`（必需，近 7 天 `WeeklyHistoryEntry`）+ `recent_training_au`（建议 28 天）。
    - 本服务强制走 LLM 路径；需配置 GOOGLE_API_KEY。
    """

    payload = dict(request.payload)
    history_payload = payload.get("history")
    if not history_payload:
        raise HTTPException(status_code=400, detail="payload.history 缺失或为空。")

    try:
        history_entries = [
            WeeklyHistoryEntry.model_validate(item) for item in history_payload
        ]
    except Exception as exc:  # pragma: no cover - 输入验证
        raise HTTPException(
            status_code=422, detail=f"history 验证失败: {exc}"
        ) from exc

    # Always run LLM path inside workflow (ToT/Critique gates)
    # Enrich payload with training summaries (7d/30d) and strength snapshots when possible
    try:
        _enrich_payload_with_training(payload)
    except Exception as exc:
        # Enrichment失败不阻断主流程
        logger.warning("weekly-report enrichment failed: %s", exc, exc_info=True)

    graph_state = run_workflow(payload, use_llm=True)
    state = graph_state.state

    sleep_baseline = (
        request.sleep_baseline_hours
        if request.sleep_baseline_hours is not None
        else payload.get("sleep_baseline_hours")
    )
    hrv_baseline = (
        request.hrv_baseline_mu
        if request.hrv_baseline_mu is not None
        else payload.get("hrv_baseline_mu")
    )

    # LLM provider is mandatory
    provider = get_llm_provider()
    if provider is None:
        raise HTTPException(status_code=503, detail="LLM provider not configured; set GOOGLE_API_KEY")
    # Prepare optional extra context (training/strength summaries) for provider
    extra_ctx = {
        "training_tag_counts": payload.get("training_tag_counts"),
        "strength_levels": payload.get("strength_levels"),
    }

    package = generate_weekly_report(
        state,
        history_entries,
        sleep_baseline_hours=sleep_baseline,
        hrv_baseline=hrv_baseline,
        provider=provider,
        use_llm=True,
        extra=extra_ctx,
    )

    final_report = generate_weekly_final_report(
        state,
        package,
        history_entries,
        report_notes=state.raw_inputs.report_notes,
        training_sessions=state.raw_inputs.training_sessions,
        provider=provider,
        use_llm=True,
    )

    persisted = False
    if request.persist:
        user_id = payload.get("user_id")
        if not user_id:
            raise HTTPException(status_code=400, detail="payload.user_id 缺失，无法持久化周报。")
        week_start = min(entry.date for entry in history_entries)
        week_end = max(entry.date for entry in history_entries)
        record = WeeklyReportRecord(
            user_id=user_id,
            week_start=week_start,
            week_end=week_end,
            report_version="weekly_report.api@0.1.0",
            report_payload=final_report.model_dump(mode="json"),
            markdown_report=final_report.markdown_report,
        )
        with get_session() as session:
            session.merge(record)
            session.commit()
        persisted = True

    return WeeklyReportResponse(
        phase3_state=state.model_dump(mode="json"),
        package=package,
        final_report=final_report,
        persisted=persisted,
    )


# ---------- Helpers: enrich payload with training/strength summaries ---------- #

def _enrich_payload_with_training(payload: Dict[str, Any]) -> None:
    """Populate `training_tag_counts` (7d/30d) and `strength_levels` (latest/baseline_30d)
    into the payload when `user_id` is present. No-op on failure.
    """
    from datetime import date as _date, timedelta as _td

    user_id = payload.get("user_id")
    if not user_id:
        return

    today = _date.today()
    start7 = today - _td(days=7)
    start30 = today - _td(days=30)

    # 7/30 日训练次数（按标签聚合）
    counts_7: Dict[str, int] = {}
    counts_30: Dict[str, int] = {}
    try:
        with get_session() as s:
            rows = (
                s.query(UserTrainingSession)
                .filter(UserTrainingSession.user_id == user_id)
                .filter(UserTrainingSession.date >= start30)
                .filter(UserTrainingSession.date <= today)
                .all()
            )
        for r in rows:
            tags = []
            try:
                if isinstance(r.type_tags, list):
                    tags = [str(t) for t in r.type_tags if t]
                elif isinstance(r.type_tags, dict):
                    # allow {"tags":[...]}
                    inner = r.type_tags.get("tags") if isinstance(r.type_tags, dict) else None
                    if isinstance(inner, list):
                        tags = [str(t) for t in inner if t]
            except Exception:
                tags = []
            if not tags:
                continue
            for tag in set(tags):
                counts_30[tag] = counts_30.get(tag, 0) + 1
                if r.date >= start7:
                    counts_7[tag] = counts_7.get(tag, 0) + 1
    except Exception as exc:
        logger.warning("training counts enrichment failed: %s", exc, exc_info=True)
        counts_7, counts_30 = {}, {}

    if counts_7 or counts_30:
        merged: Dict[str, Dict[str, int]] = {}
        for tag in set(list(counts_7.keys()) + list(counts_30.keys())):
            merged[tag] = {"7d": int(counts_7.get(tag, 0)), "30d": int(counts_30.get(tag, 0))}
        payload["training_tag_counts"] = merged

    # 力量水平（latest 与 baseline_30d）
    try:
        with get_session() as s:
            # 最新记录：每个动作取最新一条
            latest_rows = (
                s.query(UserStrengthRecord)
                .filter(UserStrengthRecord.user_id == user_id)
                .order_by(
                    UserStrengthRecord.exercise_name.asc(),
                    UserStrengthRecord.record_date.desc(),
                    UserStrengthRecord.created_at.desc(),
                )
                .all()
            )
            latest_map: Dict[str, Any] = {}
            seen: set[str] = set()
            for r in latest_rows:
                ex = r.exercise_name
                if ex in seen:
                    continue
                latest_map[ex] = {
                    "date": str(r.record_date),
                    "weight_kg": r.weight_kg,
                    "reps": r.reps,
                    "one_rm_est": r.one_rm_est,
                }
                seen.add(ex)

            # 30 天基准：选取 record_date <= start30 的最近一条
            baseline_map: Dict[str, Any] = {}
            for ex in latest_map.keys():
                r = (
                    s.query(UserStrengthRecord)
                    .filter(UserStrengthRecord.user_id == user_id)
                    .filter(UserStrengthRecord.exercise_name == ex)
                    .filter(UserStrengthRecord.record_date <= start30)
                    .order_by(UserStrengthRecord.record_date.desc(), UserStrengthRecord.created_at.desc())
                    .first()
                )
                if r:
                    baseline_map[ex] = {
                        "date": str(r.record_date),
                        "weight_kg": r.weight_kg,
                        "reps": r.reps,
                        "one_rm_est": r.one_rm_est,
                    }

        if latest_map:
            levels: Dict[str, Any] = {}
            for ex, lat in latest_map.items():
                entry = {"latest": lat}
                if ex in baseline_map:
                    entry["baseline_30d"] = baseline_map[ex]
                levels[ex] = entry
            payload["strength_levels"] = levels
    except Exception as exc:
        # ignore failures but record
        logger.warning("strength levels enrichment failed: %s", exc, exc_info=True)


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}
