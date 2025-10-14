from __future__ import annotations

import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class MonitorThresholds(BaseModel):
    readiness_lt: Optional[float] = Field(
        None, description="当日准备度低于该阈值则触发调整"
    )
    hrv_z_lt: Optional[float] = Field(
        None, description="当日 HRV Z-score 低于该阈值则触发调整"
    )
    hooper_fatigue_gt: Optional[float] = Field(
        None, description="当日 Hooper 疲劳高于该阈值则触发调整"
    )


class DayPlan(BaseModel):
    date: Optional[datetime.date] = Field(
        None, description="建议执行日期（通常为下周 7 天）"
    )
    day_label: Optional[str] = Field(None, description="例如 Mon/Tue … 或 09-16")
    load_target: str = Field(
        ..., description="low | moderate | high 或者可读的 AU 区间描述"
    )
    session_type: str = Field(
        ..., description="technique | capacity | strength | speed | recovery"
    )
    key_drills: List[str] = Field(default_factory=list, description="关键训练要点")
    recovery_tasks: List[str] = Field(default_factory=list, description="恢复任务")
    rationale: Optional[str] = Field(None, description="与洞察/阈值的关联依据")
    adjustments: Optional[dict] = Field(
        None, description="即时调整指令，如 {if_trigger, action}"
    )
    au_target_low: Optional[float] = Field(
        None, description="建议 AU 区间下限（非强制，便于控制急慢性平衡）"
    )
    au_target_high: Optional[float] = Field(
        None, description="建议 AU 区间上限（非强制）"
    )
    notes: Optional[str] = Field(None, description="补充说明（可根据习惯调整，不强制）")


class NextWeekPlan(BaseModel):
    week_objective: str = Field(..., description="本周核心目标")
    monitor_thresholds: MonitorThresholds = Field(
        default_factory=MonitorThresholds, description="全局监测阈值"
    )
    day_plans: List[DayPlan] = Field(default_factory=list, description="分日计划")
    guidelines: List[str] = Field(default_factory=list, description="执行原则（非强制）")
    confidence: Optional[float] = Field(
        None, description="0-1，数据充分性与规则置信度"
    )


__all__ = ["MonitorThresholds", "DayPlan", "NextWeekPlan"]
