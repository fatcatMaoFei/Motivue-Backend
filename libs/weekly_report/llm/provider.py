from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional, Sequence

from pydantic import ValidationError

from .models import CritiqueResponse, TotResponse
from weekly_report.models import (
    AnalystReport,
    ChartSpec,
    CommunicatorReport,
    ReportCritique,
    WeeklyFinalReport,
    WeeklyHistoryEntry,
    WeeklyReportPackage,
)
from weekly_report.state import InsightItem, ReadinessState, TrainingSessionInput

logger = logging.getLogger(__name__)


class LLMNotConfiguredError(RuntimeError):
    """Raised when LLM integration is disabled or not configured."""


class LLMCallError(RuntimeError):
    """Raised when an upstream LLM call fails irrecoverably."""


class LLMProvider:
    """Abstract provider for readiness LLM tasks (Phase 3A / Phase 4)."""

    def generate_tot(self, state: ReadinessState, complexity: Dict[str, Any]) -> TotResponse:
        raise NotImplementedError

    def generate_critique(
        self,
        state: ReadinessState,
        complexity: Dict[str, Any],
        tot_payload: TotResponse,
    ) -> CritiqueResponse:
        raise NotImplementedError

    def generate_weekly_analyst(
        self,
        state: ReadinessState,
        charts: Sequence[ChartSpec],
        *,
        report_notes: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> AnalystReport:
        raise NotImplementedError

    def generate_weekly_communicator(
        self,
        state: ReadinessState,
        analyst_report: AnalystReport,
        charts: Sequence[ChartSpec],
        *,
        report_notes: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> CommunicatorReport:
        raise NotImplementedError

    def generate_weekly_report_critique(
        self,
        analyst_report: AnalystReport,
        communicator_report: CommunicatorReport,
        charts: Sequence[ChartSpec],
    ) -> ReportCritique:
        raise NotImplementedError

    def generate_weekly_final_report(
        self,
        weekly_package: WeeklyReportPackage,
        history: Sequence[WeeklyHistoryEntry],
        *,
        report_notes: Optional[str] = None,
        training_sessions: Optional[Sequence[TrainingSessionInput]] = None,
        next_week_plan: Optional[Dict[str, Any]] = None,
    ) -> WeeklyFinalReport:
        raise NotImplementedError


# -------- Helpers for environment/config -------- #


def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    raw_lc = raw.strip().lower()
    if raw_lc in {"1", "true", "yes", "on"}:
        return True
    if raw_lc in {"0", "false", "no", "off"}:
        return False
    return default


def _clean_models(primary: str, fallback: Optional[str]) -> List[str]:
    models: List[str] = []
    seeds: List[str] = [primary] if primary else []
    if fallback:
        seeds.extend(fallback.split(","))
    for name in seeds or []:
        trimmed = name.strip()
        if trimmed and trimmed not in models:
            models.append(trimmed)
    if not models:
        models.extend(["gemini-2.5-flash", "gemini-1.5-flash", "gemini-1.5-pro"])
    return models


# -------- Prompt + schema material -------- #


_SCHEMA_UNSUPPORTED_KEYS = {
    "$defs",
    "$schema",
    "definitions",
    "additionalProperties",
    "minItems",
    "maxItems",
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "pattern",
    "const",
    "title",
    "description",
    "examples",
    "default",
    "minLength",
    "maxLength",
    "anyOf",
    "oneOf",
    "allOf",
}


def _sanitize_schema(schema: Dict[str, Any]) -> Dict[str, Any]:
    """Remove JSON Schema keywords that Gemini JSON mode does not yet support."""

    def _clean(value: Any) -> Any:
        if isinstance(value, dict):
            cleaned: Dict[str, Any] = {}
            for key, val in value.items():
                if key in _SCHEMA_UNSUPPORTED_KEYS:
                    continue
                cleaned[key] = _clean(val)
            return cleaned
        if isinstance(value, list):
            return [_clean(item) for item in value]
        return value

    return _clean(schema)


def _flatten_schema(schema: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve $ref entries in a Pydantic JSON schema by inlining definitions."""

    definitions = schema.get("$defs") or schema.get("definitions") or {}

    def resolve(node: Any, seen: Optional[set[str]] = None) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                ref = node["$ref"]
                resolved: Any = {}
                if ref.startswith("#/$defs/"):
                    key = ref.split("/")[-1]
                    if key in definitions:
                        seen = seen or set()
                        if key not in seen:
                            seen.add(key)
                            resolved = resolve(definitions[key], seen)
                            seen.remove(key)
                elif ref.startswith("#/definitions/"):
                    key = ref.split("/")[-1]
                    if key in definitions:
                        seen = seen or set()
                        if key not in seen:
                            seen.add(key)
                            resolved = resolve(definitions[key], seen)
                            seen.remove(key)
                extras = {k: resolve(v, seen) for k, v in node.items() if k != "$ref"}
                if not extras:
                    return resolved
                merged: Dict[str, Any] = {}
                if isinstance(resolved, dict):
                    merged.update(resolved)
                elif resolved is not None:
                    return resolved
                merged.update(extras)
                return merged
            return {k: resolve(v, seen) for k, v in node.items() if k not in {"$defs", "definitions"}}
        if isinstance(node, list):
            return [resolve(item, seen) for item in node]
        return node

    flattened = resolve(schema)
    if isinstance(flattened, dict):
        flattened.pop("$defs", None)
        flattened.pop("definitions", None)
    return flattened


def _prepare_schema(model_cls: type) -> Dict[str, Any]:
    raw = model_cls.model_json_schema()
    flattened = _flatten_schema(raw)
    return _sanitize_schema(flattened)


TOT_SYSTEM_PROMPT = """
You are an elite sports data scientist supporting a high-performance coach.

## Mission
Explain the athlete's current readiness by combining objective biomarkers and subjective feedback, and propose
coaching hypotheses that respect sports science principles.

## Method — S&C 五步诊断
1. Identify objective signals: training load (e.g., ACWR, consecutive high days), recovery metrics (HRV Z-score,
   sleep duration/efficiency, CMJ/VBT if present).
2. Link probable stressors: relate load spikes, lifestyle events, travel, illness, or session notes to the signals.
3. Integrate subjective context: incorporate Hooper评分、fatigue sliders、journal事件，指出客观与主观的
   一致或冲突（例如“HRV下降但主观感觉良好”）。
4. Evaluate recovery response: 当 HRV/睡眠连续下降后出现休息或低负荷日，比较休息前后的 readiness、
   HRV、睡眠变化（最好使用百分比或 ΔZ）；若恢复不足，要指出 Hooper 是否同步或出现分歧。
5. Formulate hypotheses: summarise the likely driver on readiness/performance, with actionable interpretation.

## Output Requirements
- Generate ≥3 distinct hypotheses; each `factor` should be简洁（6~12字左右）并聚焦单一驱动因素。
- 每条 `evidence` 必须引用具体数据或阈值（如“ACWR 1.45 超过 1.25 阈值”“HRV Z-score -0.86”）。
- 至少一条 `evidence` 需要关注恢复窗口（休息日/低负荷日）后的 readiness、HRV、睡眠、Hooper 变化，
  若恢复不足要解释可能原因。
- 说明客观 vs 主观是否一致，以及相关的生活方式事件或缺失数据。
- `confidence` 0.0~1.0，依据证据强弱；不确定时保持中低置信度并说明原因。
- 输出 JSON，严格符合 Schema；禁止返回额外文本。

## Principles
- 不编造数据；若缺乏某项指标，说明“数据缺失”。
- 优先考虑训练压力、恢复状态与生活方式的交互作用。
- 用客观证据支撑，避免空泛建议。
- 数据质量与 ACWR：当存在极端 AU（>2000）时，系统在计算 ACWR 之前会对 AU 进行裁剪（clip 到阈值），以避免失真；
  若你需要提及离群值，请说明“已排除该离群值对 ACWR 的影响（已裁剪）”，不要宣称“ACWR 失准/不可用”。
  对离群值本身可给出复核建议，但避免基于其原始值做因果推断。
""".strip()


TOT_RESPONSE_SCHEMA: Dict[str, Any] = _prepare_schema(TotResponse)


CRITIQUE_SYSTEM_PROMPT = """
You are a meticulous sports performance peer reviewer.

## Goal
Audit the generated hypotheses before they reach the coaching staff, highlighting logical errors, missing evidence,
or overlooked risks.

## Checklist
1. Coverage: 是否同时评估训练负荷、恢复（HRV/睡眠）、主观反馈以及生活方式事件？
2. Evidence quality: 数据引用是否准确？是否遗漏关键阈值（ACWR、HRV Z-score、Hooper 分项）？
3. Conflict logic: 当客观与主观信号冲突时，是否给出解释或提醒进一步排查？
4. Actionability: 假设是否提供可执行方向？是否存在过于模糊的结论？

## Output Requirements
- `issues`: 每条包含 `statement`（指明问题部分）、`reason`（为什么有问题）、`severity`（low|medium|high）。
- `suggestions`: 针对具体 `target_factor` 给出可操作的改进或补充。
- `overall_confidence`: 0.0~1.0，说明对整组假设的信心；若发现高风险问题，应显著降低。
- 若未发现问题，返回空数组，但仍需给出理由充分的 `overall_confidence`。
- 仅返回 JSON，严格匹配 Schema。

## Principles
- 直截了当，勿模棱两可；发现缺失数据要明确指出。
- 将严重性与潜在风险匹配：影响训练安全或错误建议 → high；逻辑缺口但可修正 → medium；措辞或补充信息 → low。
- 建议应具体（例如“补充睡眠卫生建议”“解释为何主观良好但 HRV 下降”）。
""".strip()


CRITIQUE_RESPONSE_SCHEMA: Dict[str, Any] = _prepare_schema(CritiqueResponse)

ANALYST_SYSTEM_PROMPT = """
You are an experienced strength & conditioning data analyst supporting a weekly readiness review.

## Inputs
- metrics_summary: objective signals (HRV, sleep, load 等).
- insights_summary: Phase 3 rule-based insights.
- insight_reviews: Phase 3A outputs（复杂度 / ToT / critique）.
- journal_summary & report_notes: lifestyle context and coach/athlete notes.
- chart_specs: candidate chart specifications.

## Tasks
1. 训练回顾（开头，先力量→再有氧→再球类）：
   - 列出本周 7 天训练次数，并与近 30 天次数对比（例如 “胸 1 次 vs 30 天 8 次 → 本周偏少”）；
   - 指出 1–2 条“部位覆盖/负荷不均衡”的最大差异（按 7d vs 30d 的相对差），给出下周建议频次（如“胸 1–2 次，间隔≥48h”）。
   - 对训练强度与部位均衡做简短评价（是否集中在某部位、是否存在单日强度过高）。
2. 先给出“下一周总体建议（headline）”：简洁说明建议的周类型（剪载/维持/容量回升/冲击（建议）），并引用关键证据（ACWR 区间、HRV Z、睡眠相对基线、主观疲劳/压力）。避免绝对化；不要给具体日期或逐日安排。
3. 提炼 3-5 个 summary_points，解释本周状态变化及驱动。
2. 明确指出训练负荷与恢复的关联，尤其是休息日/低负荷日后的 readiness、HRV、睡眠与 Hooper
   变化（如能以百分比或 ΔZ 表达更佳）。
3. 列出 risks（metric/value/reason，若有 severity 请注明），优先提示恢复不足或主客观分歧的风险。
4. 列出 opportunities，给出可执行建议与简短理由（包括如何改进恢复或安排休息）。
5. 甄选最相关的图表，以 `chart_ids` 字段列出对应的 chart_id。
6. 仅输出 JSON，严格遵循提供的 schema。
7. 数据质量与 ACWR：当发现离群 AU（>2000）时，可在 summary/risk 作出“数据需复核”的提示；
   请明确“ACWR 计算前已对极端 AU 做裁剪处理，已排除其影响”，不要因为离群值而否定 ACWR 本身。
8. 指标定义（首次出现时简述其含义）：
   - HRV Z-score：相对个人基线的标准化分数，<0 表示低于基线，绝对值越大偏离越多。
   - CSS（恢复/睡眠综合分）：综合睡眠效率/结构与恢复特征的归一化评分，用于观察恢复质量趋势（仅作参考，不取代 HRV/主观信号）。
8. 建议规则：当 ACWR ≥1.30 或连续高负荷≥3 天，优先提示“建议维持或减载”；当 ACWR 处于 0.8–1.0 且恢复稳定（HRV Z>-0.3、睡眠接近基线、主观正常），才给出“冲击（建议）”。当 ACWR ≤0.6 且恢复允许，提示“容量回升（逐步加量）”，并说明 ACWR 过低也不理想。
9. 周期化幅度指引（仅做建议，不替代排期）：
   - 冲击（建议）：总量较上周 +10%~15%；高强度≤2日（间隔≥48h）；以中强度为主，插入主动恢复。
   - 容量回升：总量 +5%~10%，将 ACWR 拉回 0.8–1.0 区间。
   - 维持：总量 ±0%~5%，以中强度与技术巩固为主。
   - 剪载：总量 -10%~15%，强度降档，恢复/技术优先。
   输出时不要写具体日期或每天的训练内容。
""".strip()

ANALYST_RESPONSE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "summary_points": {
            "type": "array",
            "items": {"type": "string"},
        },
        "risks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "metric": {"type": "string"},
                    "value": {"type": "string"},
                    "reason": {"type": "string"},
                    "severity": {"type": "string"},
                },
                "required": ["metric", "reason"],
            },
        },
        "opportunities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "area": {"type": "string"},
                    "recommendation": {"type": "string"},
                    "reason": {"type": "string"},
                },
                "required": ["area", "recommendation"],
            },
        },
        "chart_ids": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["summary_points", "risks", "opportunities"],
}

COMMUNICATOR_SYSTEM_PROMPT = """
You are a professional, empathetic S&C coach communicator.

## Inputs
- analyst_report: 上一步分析结果。
- chart_specs: 数据图表（可引用标题或趋势要点）。
- report_notes: 教练/运动员自由文本背景。

## Style
- 先给积极反馈，再讨论风险；语气积极、建设性、行动导向。
- 使用清晰 Markdown 段落（可含 bullet 列表），语言简洁。
 - 在第一段先给出“本周→下周的总体建议（headline）”，如“建议维持/减载/容量回升/冲击（建议）”，并简要引用 ACWR/HRV/睡眠/主观证据；详细分析放在后面段落。
 - 不要给具体日期或逐日安排；可使用频次/强度分布描述（例如“高强度≤2日、以中强度为主、总量 +10%~15%”）。
 - 若 analyst 总结提供了训练回顾（7d vs 30d），在“建议与行动”中必须给出 1–2 条“部位覆盖/负荷均衡”建议；
   当本周与 30 天基线差异明显时，点名说明（例如“胸本周 1 次 vs 30 天 8 次 → 本周偏少，建议下周 1–2 次，间隔≥48h”）。
 - 首次出现 HRV Z-score/CSS 等专业指标时，请在同段内用半句解释其含义，确保读者理解。

## Output
- sections: [{title, body_markdown}]。
- 在“建议与行动”段落中，若有 training_summary/strength_summary，必须包含 1–2 条基于 7d vs 30d 的“部位覆盖/负荷均衡”建议，并给出明确频次（如 1–2 次/周，间隔≥48h）。
- 引用关键图表时在句末附 `[[chart:<id>]]` 锚点。
- tone: 语气标签（例如 professional_encouraging）。
- call_to_action: 明确的行动项。
- 仅输出 JSON。
""".strip()

COMMUNICATOR_RESPONSE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "sections": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "body_markdown": {"type": "string"},
                },
                "required": ["title", "body_markdown"],
            },
        },
        "tone": {"type": "string"},
        "call_to_action": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["sections"],
}

REPORT_CRITIQUE_SYSTEM_PROMPT = """
You are an S&C analyst reviewer ensuring the communicator's draft is factual and aligned with the analyst findings.

## Inputs
- analyst_report: 原始风险/机会结论。
- communicator_report: 对外沟通草稿。
- chart_specs: 相关数据图表。

## Task
- 若发现事实错误、遗漏或语气不当，记录 issue（sentence + reason + fix）。
- 核查是否覆盖了“训练回顾/部位均衡/强度”要点（基于 7d/30d 对比），若缺失请补充建议。
- 核查是否添加了图表引用锚点（[[chart:<id>]]）用于关键结论；若缺失请补充。
- 首次出现 HRV Z-score/CSS 等指标是否附简短定义；若缺失请补充说明。
- 内容准确时返回空数组，可补 overall_feedback。
- 仅输出 JSON。
""".strip()

REPORT_CRITIQUE_RESPONSE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "sentence": {"type": "string"},
                    "reason": {"type": "string"},
                    "fix": {"type": "string"},
                },
                "required": ["sentence", "reason", "fix"],
            },
        },
        "overall_feedback": {"type": "string"},
    },
    "required": ["issues"],
}

FINALIZER_SYSTEM_PROMPT = """
You are “Finalizer”, a senior sports scientist and performance coach editor.

## Goal
Produce a weekly readiness report whose Markdown结构与参考模板高度一致：分段、逐日表格、逐日要点、关联洞察、行动计划与鼓励语全部齐备。

## Workflow
1. **Critique first**：若 `critique.issues` 非空，先把 communicator 中对应句子替换成 `fix`，再开始写作。
2. **数据权威**：仅可使用 `history` 与 `weekly_package.charts` 的数值。若文字与图表数据冲突，必须改用图表数值并注明依据。
3. **固定 Markdown 骨架**（所有标题用 `##`，按以下顺序排列；表格列名、bullet 结构必须与示例一致，不得增减标题或改变顺序）：

```
# 周报总览（{latest_history_date}）

## 本周概览
- 本周训练总体情况（含训练日、AU 区间）
- 周均准备度与范围（引用准备度趋势图）
- ACWR 状态与风险提醒（引用训练负荷图）
- 关键生活方式驱动及恢复重点（引用生活方式图）

## 训练负荷与表现
| 日期 | 训练量 (AU) | 准备度分数 / 分档 | 生活方式事件 / 备注 |
| --- | --- | --- | --- |
{逐日 7 行，按时间顺序}
- 每日重点
  - 09-09: …（共 7 条，格式固定，逐日说明训练量/准备度/事件/建议）
- 其它训练洞察（≥2 条，分析 ACWR、连续高负荷风险，引用图表）

## 恢复与生理信号
| 日期 | HRV (RMSSD) | Z-score | 训练 / 事件备注 |
| --- | --- | --- | --- |
{逐日 7 行}
- HRV 与训练/事件的关系（≥2 条，解释 Z-score 含义，引用图表）
- 至少一条需要描述休息/低负荷日后的 readiness、HRV 回升（或未回升）幅度，并说明 Hooper 主观反馈是否对齐，
  建议使用百分比或 ΔZ。
| 日期 | 睡眠时长 (h) | 深睡 (min) | REM (min) | 事件 |
| --- | --- | --- | --- | --- |
{逐日 7 行}
- 睡眠与训练/事件的关系（≥2 条，指出高负荷日对睡眠的影响，并说明休息后的恢复幅度，引用图表）

## 主观反馈（Hooper 指数）
| 日期 | 疲劳 | 酸痛 | 压力 | 睡眠质量 | 说明 |
| --- | --- | --- | --- | --- | --- |
{逐日 7 行，说明列需写当天的生活事件或状态}
- Hooper 四项趋势总结（≥2 条，说明与客观指标是否吻合）

## 生活方式事件
- 若无事件：写 “- 本周无显著生活方式事件记录。”
- 若有事件：逐日写 bullet，格式 “- 09-13: travel → 次日 HRV 下降 2 ms …”

## 自由备注与训练日志洞察
- 将 report_notes 与 training_sessions.notes 的关键信息写成 1–3 条 bullet，说明它们如何影响准备度/HRV/睡眠。

## 相关性洞察
- ≥3 条 bullet，总结训练量、睡眠、HRV、Hooper、生活方式之间的因果或相关关系，并给出触发阈值提醒；
  至少一条需评估休息日后的恢复成效（例如 readiness 回升百分比、HRV ΔZ、Hooper 是否同步改善）。

## 下周行动计划
用 `next_week_plan`（若存在）作为主要信息源：
- 第一句先给“下一周总体建议（headline）”，例如“建议维持/减载/容量回升/冲击（建议）”，并引用 ACWR/HRV/睡眠/主观依据；语气使用“建议”，避免绝对化；
- 将 `next_week_plan.week_objective` 与 `guidelines` 组织为 2–4 条 bullet；
- 仅给出强度分布与重点方向，不要逐日罗列；不要写具体日期或每天的训练内容，可用“高强度≤2日（间隔≥48h）、以中强度为主、插入主动恢复”等表述；
- 周期化幅度指引（仅做建议）：冲击 +10%~15%；容量回升 +5%~10%；维持 ±0%~5%；剪载 -10%~15%。
- 强调“本段不替代教练排期”，属于建议与原理说明；
- 若无 `next_week_plan`，再退回 `call_to_action` + 分析建议。

## 鼓励与后续
- 1 段鼓励语：肯定投入、提醒执行行动项，并说明下周重点关注的指标。
```

4. **写作要求**
   - 所有列表使用 `-` 或 `  -`，不要使用 `*` 或额外标题。  
   - 语句简洁、要点化，解释 ACWR、HRV Z-score 等专业指标的含义与风险。  
   - 引用图表时必须在句末加上锚点 `[[chart:<chart_id>]]`；使用 `chart_catalog` 中的 `chart_id`，若只知标题请同时写标题与最近似的 `chart_id`。
   - 首次出现 CSS/HRV Z-score 等指标时，紧随其后以括号补充 1 句含义说明。

## Output
返回 JSON，字段必须符合 schema；`markdown_report` 必须严格遵循上述结构、表格与逐日分析。
""".strip()

FINALIZER_RESPONSE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "markdown_report": {"type": "string"},
        "html_report": {"type": "string"},
        "chart_ids": {
            "type": "array",
            "items": {"type": "string"},
        },
        "call_to_action": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["markdown_report", "chart_ids", "call_to_action"],
}


# -------- Payload builders -------- #


def _round_or_none(value: Optional[float], ndigits: int = 2) -> Optional[float]:
    if value is None:
        return None
    try:
        return round(float(value), ndigits)
    except Exception:
        return None


def _metrics_summary(state: ReadinessState) -> Dict[str, Any]:
    m = state.metrics
    return {
        "training_load": {
            "acwr_value": m.training_load.acwr_value,
            "acwr_band": m.training_load.acwr_band,
            "acute_load": m.training_load.acute_load,
            "chronic_load": m.training_load.chronic_load,
            "consecutive_high_days": m.training_load.consecutive_high_days,
        },
        "recovery": {
            "sleep_duration_hours": m.recovery.sleep_duration_hours,
            "sleep_duration_delta": m.recovery.sleep_duration_delta,
            "sleep_efficiency": _round_or_none(m.recovery.sleep_efficiency, 3),
            "css_score": m.recovery.css_score,
        },
        "physiology": {
            "hrv_z_score": m.physiology.hrv_z_score,
            "hrv_state": m.physiology.hrv_state,
            "hrv_trend": m.physiology.hrv_trend,
        },
        "subjective": {
            "hooper_bands": m.subjective.hooper_bands or {},
            "fatigue_score": m.subjective.fatigue_score,
            "doms_score": m.subjective.doms_score,
            "energy_score": m.subjective.energy_score,
        },
        "baselines": {
            "sleep_hours": m.baselines.sleep_baseline_hours,
            "sleep_efficiency": m.baselines.sleep_baseline_efficiency,
            "hrv_mu": m.baselines.hrv_mu,
            "hrv_sigma": m.baselines.hrv_sigma,
        },
    }


def _journal_summary(state: ReadinessState) -> Dict[str, Any]:
    journal = state.raw_inputs.journal
    lifestyle_tags = list(journal.lifestyle_tags or [])
    events: List[str] = []
    if journal.alcohol_consumed:
        events.append("alcohol")
    if journal.late_caffeine:
        events.append("late_caffeine")
    if journal.screen_before_bed:
        events.append("screen_before_bed")
    if journal.late_meal:
        events.append("late_meal")
    return {
        "flags": events,
        "tags": lifestyle_tags,
        "sliders": journal.sliders or {},
        "is_sick": journal.is_sick,
        "is_injured": journal.is_injured,
    }


def _hooper_summary(state: ReadinessState) -> Dict[str, Any]:
    hooper = state.raw_inputs.hooper
    return {
        "fatigue": hooper.fatigue,
        "soreness": hooper.soreness,
        "stress": hooper.stress,
        "sleep": hooper.sleep,
    }


def _draft_insights(state: ReadinessState) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for item in state.insights:
        if not isinstance(item, InsightItem):
            continue
        results.append(
            {
                "id": item.id,
                "trigger": item.trigger,
                "summary": item.summary,
                "explanation": item.explanation,
                "confidence": item.confidence,
                "tags": list(item.tags or []),
            }
        )
    return results


def _recent_training_sessions(state: ReadinessState) -> List[Dict[str, Any]]:
    sessions = []
    for sess in state.raw_inputs.training_sessions:
        sessions.append(
            {
                "label": sess.label,
                "rpe": sess.rpe,
                "duration_minutes": sess.duration_minutes,
                "au": sess.au,
                "notes": sess.notes,
            }
        )
    return sessions


def _base_payload(state: ReadinessState, complexity: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "user_id": state.raw_inputs.user_id,
        "date": state.raw_inputs.date,
        "metrics_summary": _metrics_summary(state),
        "journal_summary": _journal_summary(state),
        "hooper_scores": _hooper_summary(state),
        "training_sessions": _recent_training_sessions(state),
        "draft_insights": _draft_insights(state),
        "complexity_score": complexity.get("score"),
        "complexity_reasons": complexity.get("reasons", []),
        "report_notes": state.raw_inputs.report_notes,
    }


def _group_training_counts(counts: Dict[str, Any]) -> Dict[str, Any]:
    out = {"strength": [], "cardio": [], "sport": [], "other": []}
    for tag, obj in (counts or {}).items():
        try:
            v7 = int(obj.get("7d", 0) if isinstance(obj, dict) else 0)
            v30 = int(obj.get("30d", 0) if isinstance(obj, dict) else 0)
        except Exception:
            v7, v30 = 0, 0
        bucket = "other"
        if isinstance(tag, str):
            if tag.startswith("strength:"):
                bucket = "strength"
            elif tag.startswith("cardio:"):
                bucket = "cardio"
            elif tag.startswith("sport:"):
                bucket = "sport"
        out[bucket].append({"tag": tag, "7d": v7, "30d": v30})
    # sort by 7d desc
    for k in out:
        out[k].sort(key=lambda x: x.get("7d", 0), reverse=True)
    return out


def _strength_levels_summary(levels: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for ex, entry in (levels or {}).items():
        latest = entry.get("latest") if isinstance(entry, dict) else None
        base = entry.get("baseline_30d") if isinstance(entry, dict) else None
        def _cast_one(x: Any) -> Dict[str, Any]:
            if not isinstance(x, dict):
                return {}
            return {
                "date": x.get("date"),
                "weight_kg": x.get("weight_kg"),
                "reps": x.get("reps"),
                "one_rm_est": x.get("one_rm_est"),
            }
        lat = _cast_one(latest)
        bas = _cast_one(base)
        try:
            d = None
            if lat.get("one_rm_est") is not None and bas.get("one_rm_est") is not None:
                d = float(lat.get("one_rm_est")) - float(bas.get("one_rm_est"))
        except Exception:
            d = None
        out[ex] = {"latest": lat, "baseline_30d": bas if base else None, "delta_one_rm": d}
    return out


def _build_tot_payload(state: ReadinessState, complexity: Dict[str, Any]) -> Dict[str, Any]:
    payload = _base_payload(state, complexity)
    payload["raw_inputs_snapshot"] = {
        "sleep": {
            "total_sleep_minutes": state.raw_inputs.sleep.total_sleep_minutes,
            "in_bed_minutes": state.raw_inputs.sleep.in_bed_minutes,
        },
        "hrv": {
            "today": state.raw_inputs.hrv.hrv_rmssd_today,
            "baseline_mu": state.metrics.baselines.hrv_mu,
            "baseline_sigma": state.metrics.baselines.hrv_sigma,
        },
        "bodyweight_kg": state.raw_inputs.body_metrics.bodyweight_kg,
        "resting_hr": state.raw_inputs.body_metrics.resting_hr,
    }
    return payload


def _build_critique_payload(
    state: ReadinessState,
    complexity: Dict[str, Any],
    tot_payload: TotResponse,
) -> Dict[str, Any]:
    payload = _base_payload(state, complexity)
    payload["hypotheses"] = [
        {
            "factor": item.factor,
            "evidence": item.evidence,
            "confidence": item.confidence,
            "supporting_metrics": item.supporting_metrics,
        }
        for item in tot_payload.hypotheses
    ]
    return payload


def _insights_summary(state: ReadinessState) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for item in state.insights:
        if not isinstance(item, InsightItem):
            continue
        results.append(
            {
                "summary": item.summary,
                "explanation": item.explanation,
                "confidence": item.confidence,
                "tags": list(item.tags or []),
            }
        )
    return results


def _insight_reviews_summary(state: ReadinessState) -> List[Dict[str, Any]]:
    reviews: List[Dict[str, Any]] = []
    for review in state.insight_reviews:
        entry: Dict[str, Any] = {}
        complexity = review.get("complexity")
        if complexity:
            entry["complexity"] = complexity
        tot = review.get("tot_hypotheses")
        if tot:
            entry["tot_hypotheses"] = tot.get("hypotheses", [])
        critique = review.get("critique")
        if critique:
            entry["critique"] = critique
        if entry:
            reviews.append(entry)
    return reviews


def _charts_payload(charts: Sequence[ChartSpec]) -> List[Dict[str, Any]]:
    return [chart.model_dump() for chart in charts]


def _build_weekly_analyst_payload(
    state: ReadinessState,
    charts: Sequence[ChartSpec],
    report_notes: Optional[str],
    *,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "metrics_summary": _metrics_summary(state),
        "journal_summary": _journal_summary(state),
        "insights_summary": _insights_summary(state),
        "insight_reviews": _insight_reviews_summary(state),
        "chart_specs": _charts_payload(charts),
        "report_notes": report_notes or state.raw_inputs.report_notes,
        "next_week_plan": (
            state.next_week_plan.model_dump(mode="json")
            if getattr(state, "next_week_plan", None)
            else None
        ),
    }
    if isinstance(extra, dict):
        counts = extra.get("training_tag_counts")
        levels = extra.get("strength_levels")
        if counts:
            payload["training_summary"] = _group_training_counts(counts)
        if levels:
            payload["strength_summary"] = _strength_levels_summary(levels)
    return payload


def _build_weekly_communicator_payload(
    state: ReadinessState,
    analyst_report: AnalystReport,
    charts: Sequence[ChartSpec],
    report_notes: Optional[str],
    *,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "analyst_report": analyst_report.model_dump(),
        "chart_specs": _charts_payload(charts),
        "report_notes": report_notes or state.raw_inputs.report_notes,
        "insights_summary": _insights_summary(state),
        "next_week_plan": (
            state.next_week_plan.model_dump(mode="json")
            if getattr(state, "next_week_plan", None)
            else None
        ),
    }
    if isinstance(extra, dict):
        counts = extra.get("training_tag_counts")
        levels = extra.get("strength_levels")
        if counts:
            payload["training_summary"] = _group_training_counts(counts)
        if levels:
            payload["strength_summary"] = _strength_levels_summary(levels)
    return payload


def _build_weekly_report_critique_payload(
    analyst_report: AnalystReport,
    communicator_report: CommunicatorReport,
    charts: Sequence[ChartSpec],
) -> Dict[str, Any]:
    return {
        "analyst_report": analyst_report.model_dump(),
        "communicator_report": communicator_report.model_dump(),
        "chart_specs": _charts_payload(charts),
    }


def _build_weekly_finalizer_payload(
    weekly_package: WeeklyReportPackage,
    history: Sequence[WeeklyHistoryEntry],
    report_notes: Optional[str],
    training_sessions: Optional[Sequence[TrainingSessionInput]],
) -> Dict[str, Any]:
    chart_catalog = {chart.chart_id: chart.title for chart in weekly_package.charts}
    sessions_payload: List[Dict[str, Any]] = []
    for sess in training_sessions or []:
        sessions_payload.append(
            {
                "label": sess.label,
                "rpe": sess.rpe,
                "duration_minutes": sess.duration_minutes,
                "au": sess.au,
                "notes": sess.notes,
            }
        )
    return {
        "weekly_package": weekly_package.model_dump(mode="json"),
        "history": [entry.model_dump(mode="json") for entry in history],
        "report_notes": report_notes,
        "training_sessions": sessions_payload,
        "chart_catalog": chart_catalog,
    }


# -------- Gemini provider implementation -------- #


class GeminiLLMProvider(LLMProvider):
    def __init__(self, models: Sequence[str], api_key: str, temperature: float = 0.4) -> None:
        try:
            import google.generativeai as genai  # type: ignore
        except Exception as exc:  # pragma: no cover - import guard
            raise LLMNotConfiguredError("google-generativeai package not available") from exc

        if not models:
            raise LLMNotConfiguredError("No Gemini models configured")

        self._genai = genai
        self._models = list(models)
        self._temperature = temperature
        genai.configure(api_key=api_key)

    def _invoke(
        self,
        models: Sequence[str],
        *,
        system_prompt: str,
        user_payload: Dict[str, Any],
        schema: Dict[str, Any],
    ) -> Dict[str, Any]:
        last_error: Optional[Exception] = None
        for model_name in models:
            try:
                model = self._genai.GenerativeModel(
                    model_name, system_instruction=system_prompt
                )
                response = model.generate_content(
                    contents=[
                        {
                            "role": "user",
                            "parts": [
                                {
                                    "text": json.dumps(
                                        user_payload, ensure_ascii=False
                                    )
                                }
                            ],
                        }
                    ],
                    generation_config={
                        "temperature": self._temperature,
                        "top_p": 0.95,
                        "response_mime_type": "application/json",
                        "response_schema": schema,
                    },
                )
                text = response.text
                if not text:
                    raise ValueError("Empty response text")
                return json.loads(text)
            except Exception as err:  # pragma: no cover - network call
                last_error = err
                logger.warning("Gemini model %s failed: %s", model_name, err)
                continue
        if last_error is None:
            raise LLMCallError("Gemini invocation failed without specific error")
        raise LLMCallError("All configured Gemini models failed") from last_error

    def generate_tot(self, state: ReadinessState, complexity: Dict[str, Any]) -> TotResponse:
        payload = _build_tot_payload(state, complexity)
        raw = self._invoke(
            self._models,
            system_prompt=TOT_SYSTEM_PROMPT,
            user_payload=payload,
            schema=TOT_RESPONSE_SCHEMA,
        )
        try:
            return TotResponse.model_validate(raw)
        except ValidationError as exc:  # pragma: no cover - validation guard
            raise LLMCallError("ToT response validation failed") from exc

    def generate_critique(
        self,
        state: ReadinessState,
        complexity: Dict[str, Any],
        tot_payload: TotResponse,
    ) -> CritiqueResponse:
        payload = _build_critique_payload(state, complexity, tot_payload)
        raw = self._invoke(
            self._models,
            system_prompt=CRITIQUE_SYSTEM_PROMPT,
            user_payload=payload,
            schema=CRITIQUE_RESPONSE_SCHEMA,
        )
        try:
            return CritiqueResponse.model_validate(raw)
        except ValidationError as exc:  # pragma: no cover - validation guard
            raise LLMCallError("Critique response validation failed") from exc

    def generate_weekly_analyst(
        self,
        state: ReadinessState,
        charts: Sequence[ChartSpec],
        *,
        report_notes: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> AnalystReport:
        payload = _build_weekly_analyst_payload(state, charts, report_notes, extra=extra)
        raw = self._invoke(
            self._models,
            system_prompt=ANALYST_SYSTEM_PROMPT,
            user_payload=payload,
            schema=ANALYST_RESPONSE_SCHEMA,
        )
        try:
            return AnalystReport.model_validate(raw)
        except ValidationError as exc:  # pragma: no cover
            raise LLMCallError("Weekly analyst report validation failed") from exc

    def generate_weekly_communicator(
        self,
        state: ReadinessState,
        analyst_report: AnalystReport,
        charts: Sequence[ChartSpec],
        *,
        report_notes: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> CommunicatorReport:
        payload = _build_weekly_communicator_payload(
            state, analyst_report, charts, report_notes, extra=extra
        )
        raw = self._invoke(
            self._models,
            system_prompt=COMMUNICATOR_SYSTEM_PROMPT,
            user_payload=payload,
            schema=COMMUNICATOR_RESPONSE_SCHEMA,
        )
        try:
            return CommunicatorReport.model_validate(raw)
        except ValidationError as exc:  # pragma: no cover
            raise LLMCallError("Communicator report validation failed") from exc

    def generate_weekly_report_critique(
        self,
        analyst_report: AnalystReport,
        communicator_report: CommunicatorReport,
        charts: Sequence[ChartSpec],
    ) -> ReportCritique:
        payload = _build_weekly_report_critique_payload(
            analyst_report, communicator_report, charts
        )
        raw = self._invoke(
            self._models,
            system_prompt=REPORT_CRITIQUE_SYSTEM_PROMPT,
            user_payload=payload,
            schema=REPORT_CRITIQUE_RESPONSE_SCHEMA,
        )
        try:
            return ReportCritique.model_validate(raw)
        except ValidationError as exc:  # pragma: no cover
            raise LLMCallError("Report critique validation failed") from exc

    def generate_weekly_final_report(
        self,
        weekly_package: WeeklyReportPackage,
        history: Sequence[WeeklyHistoryEntry],
        *,
        report_notes: Optional[str] = None,
        training_sessions: Optional[Sequence[TrainingSessionInput]] = None,
        next_week_plan: Optional[Dict[str, Any]] = None,
    ) -> WeeklyFinalReport:
        payload = _build_weekly_finalizer_payload(
            weekly_package,
            history,
            report_notes,
            training_sessions,
        )
        if next_week_plan is not None:
            payload["next_week_plan"] = next_week_plan
        raw = self._invoke(
            self._models,
            system_prompt=FINALIZER_SYSTEM_PROMPT,
            user_payload=payload,
            schema=FINALIZER_RESPONSE_SCHEMA,
        )
        try:
            return WeeklyFinalReport.model_validate(raw)
        except ValidationError as exc:  # pragma: no cover
            raise LLMCallError("Weekly final report validation failed") from exc


# -------- Provider factory -------- #


_PROVIDER_INITIALISED = False
_CACHED_PROVIDER: Optional[LLMProvider] = None


def get_llm_provider() -> Optional[LLMProvider]:
    global _PROVIDER_INITIALISED, _CACHED_PROVIDER
    if _PROVIDER_INITIALISED:
        return _CACHED_PROVIDER

    _PROVIDER_INITIALISED = True

    if not _env_flag("READINESS_LLM_ENABLED", True):
        logger.info("LLM provider disabled via READINESS_LLM_ENABLED")
        return None

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        logger.info("LLM provider not configured: GOOGLE_API_KEY missing")
        return None

    primary = os.getenv("READINESS_LLM_MODEL", "gemini-2.5-flash")
    fallback = os.getenv("READINESS_LLM_FALLBACK_MODELS")
    models = _clean_models(primary, fallback)

    try:
        provider = GeminiLLMProvider(models, api_key)
    except Exception as exc:  # pragma: no cover - guard initialisation
        logger.warning("Failed to initialise Gemini provider: %s", exc)
        return None

    _CACHED_PROVIDER = provider
    return provider


__all__ = [
    "LLMProvider",
    "LLMNotConfiguredError",
    "LLMCallError",
    "get_llm_provider",
]
