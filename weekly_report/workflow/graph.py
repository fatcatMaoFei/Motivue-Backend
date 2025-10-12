from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from pydantic import BaseModel, Field, ValidationError

from weekly_report.analysis import run_analysis
from weekly_report.analysis.models import AnalysisBundle
from weekly_report.llm.models import CritiqueResponse, TotHypothesis, TotResponse
from weekly_report.models import WeeklyHistoryEntry
from weekly_report.state import ReadinessState
from weekly_report.state_utils import create_state, state_to_json
from weekly_report.state_builder import hydrate_raw_inputs
from weekly_report.metrics_extractors import populate_metrics
from weekly_report.insights import generate_analysis_insights, populate_insights
from weekly_report.insights.complexity import score_complexity
from weekly_report.llm import LLMCallError, get_llm_provider


class GraphState(BaseModel):
    """Shared state for the readiness multi-node workflow."""

    state: ReadinessState = Field(default_factory=ReadinessState)
    payload: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    logs: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    history: List[WeeklyHistoryEntry] = Field(default_factory=list)
    analysis: Optional[AnalysisBundle] = None

    def log(self, message: str) -> None:
        self.logs.append(message)

    def add_error(self, message: str) -> None:
        self.errors.append(message)


# -------- Node implementations -------- #


def ingest_node(graph_state: GraphState) -> GraphState:
    """Populate raw_inputs from incoming payload."""
    try:
        payload = graph_state.payload
        state = graph_state.state
        if state.raw_inputs.user_id is None:
            state.raw_inputs.user_id = payload.get("user_id")
        if state.raw_inputs.date is None:
            state.raw_inputs.date = payload.get("date")
        if state.raw_inputs.gender is None:
            state.raw_inputs.gender = payload.get("gender")
        hydrate_raw_inputs(state, payload, payload.get("training_sessions"))
        history_entries = payload.get("history") or payload.get("weekly_history")
        if isinstance(history_entries, Sequence) and not isinstance(
            history_entries, (str, bytes)
        ):
            parsed: List[WeeklyHistoryEntry] = []
            for item in history_entries:
                try:
                    parsed.append(WeeklyHistoryEntry.model_validate(item))
                except ValidationError:
                    continue
            if parsed:
                graph_state.history = parsed
                graph_state.log(f"ingest_node: parsed {len(parsed)} history entries")
        graph_state.log("ingest_node: raw inputs populated")
    except Exception as exc:  # pragma: no cover
        graph_state.add_error(f"ingest_node failed: {exc!r}")
        raise
    return graph_state


def metrics_node(
    graph_state: GraphState,
    *,
    recent_training_au: Optional[Sequence[float]] = None,
    recent_training_loads: Optional[Sequence[str]] = None,
    baselines: Optional[Dict[str, float]] = None,
    personalized_thresholds: Optional[Dict[str, float]] = None,
) -> GraphState:
    """Compute deterministic metrics and write to state.metrics."""
    try:
        payload = graph_state.payload
        populate_metrics(
            graph_state.state,
            recent_training_au=recent_training_au or payload.get("recent_training_au"),
            recent_training_loads=recent_training_loads
            or payload.get("recent_training_loads"),
            baselines=baselines
            or {
                "sleep_baseline_hours": payload.get("sleep_baseline_hours"),
                "sleep_baseline_eff": payload.get("sleep_baseline_eff"),
                "rest_baseline_ratio": payload.get("rest_baseline_ratio"),
                "hrv_baseline_mu": payload.get("hrv_baseline_mu"),
                "hrv_baseline_sd": payload.get("hrv_baseline_sd"),
            },
            personalized_thresholds=personalized_thresholds
            or payload.get("personalized_thresholds"),
        )
        graph_state.log("metrics_node: metrics populated")
    except Exception as exc:  # pragma: no cover
        graph_state.add_error(f"metrics_node failed: {exc!r}")
        raise
    return graph_state


def analysis_node(graph_state: GraphState) -> GraphState:
    """Run statistical analysis prior to insight generation."""
    if not graph_state.history:
        graph_state.log("analysis_node: skipped (no history)")
        return graph_state
    try:
        analysis = run_analysis(graph_state.history, state=graph_state.state)
        graph_state.analysis = analysis
        graph_state.metadata["analysis"] = analysis.model_dump()
        graph_state.log("analysis_node: analysis bundle computed")
    except Exception as exc:  # pragma: no cover
        graph_state.add_error(f"analysis_node failed: {exc!r}")
        raise
    return graph_state


def insights_node(graph_state: GraphState) -> GraphState:
    """Generate insights based on the populated metrics."""
    try:
        populate_insights(graph_state.state)
        if graph_state.analysis is not None:
            extra = generate_analysis_insights(graph_state.state, graph_state.analysis)
            if extra:
                graph_state.state.insights.extend(extra)
                graph_state.log(
                    f"insights_node: appended {len(extra)} analysis-derived insights"
                )
        graph_state.log("insights_node: insights generated")
    except Exception as exc:  # pragma: no cover
        graph_state.add_error(f"insights_node failed: {exc!r}")
        raise
    return graph_state


def complexity_check_node(graph_state: GraphState) -> GraphState:
    """Score complexity to decide whether advanced reasoning is required."""
    try:
        complexity = score_complexity(graph_state.state)
        graph_state.metadata["complexity"] = complexity
        graph_state.log(
            f"complexity_check_node: score={complexity['score']} label={complexity['label']}"
        )
    except Exception as exc:  # pragma: no cover
        graph_state.add_error(f"complexity_check_node failed: {exc!r}")
        raise
    return graph_state


def _mock_tot_output(state: ReadinessState) -> TotResponse:
    """Placeholder ToT output until LLM integration is ready."""
    if state.insights:
        entries = []
        for item in state.insights:
            entries.append(
                TotHypothesis(
                    factor=item.summary or item.trigger or "unspecified_factor",
                    evidence=item.explanation,
                    confidence=0.6,
                    supporting_metrics=[],
                )
            )
    else:
        entries = [
            TotHypothesis(
                factor="insufficient_data",
                evidence="No rule-based insights available yet.",
                confidence=0.25,
                supporting_metrics=[],
            )
        ]
    return TotResponse(hypotheses=entries)


def tot_reasoning_node(graph_state: GraphState) -> GraphState:
    """Placeholder ToT reasoning node (mock implementation)."""
    complexity = graph_state.metadata.get("complexity", {})
    if complexity.get("label") != "complex":
        graph_state.log("tot_reasoning_node: skipped (simple case)")
        return graph_state
    if not graph_state.metadata.get("use_llm", True):
        graph_state.log("tot_reasoning_node: skipped (LLM disabled)")
        return graph_state
    try:
        provider = get_llm_provider()
        if provider is None:
            graph_state.log("tot_reasoning_node: LLM disabled, using mock output")
            tot_result = _mock_tot_output(graph_state.state)
        else:
            try:
                tot_result = provider.generate_tot(graph_state.state, complexity)
                graph_state.log(
                    "tot_reasoning_node: Gemini generated %s hypotheses"
                    % len(tot_result.hypotheses)
                )
            except LLMCallError as err:
                graph_state.add_error(f"tot_reasoning_node LLM failure: {err}")
                graph_state.log("tot_reasoning_node: fallback to mock output")
                tot_result = _mock_tot_output(graph_state.state)
        graph_state.metadata["tot_hypotheses"] = tot_result.model_dump()
        graph_state.metadata["_tot_response_obj"] = tot_result
    except Exception as exc:  # pragma: no cover
        graph_state.add_error(f"tot_reasoning_node failed: {exc!r}")
        raise
    return graph_state


def _mock_critique(state: ReadinessState) -> CritiqueResponse:
    """Placeholder critique output prior to LLM integration."""
    return CritiqueResponse(
        issues=[],
        suggestions=[],
        overall_confidence=0.6 if state.insights else 0.3,
    )


def critique_node(graph_state: GraphState) -> GraphState:
    """Placeholder critique node (mock implementation)."""
    if "tot_hypotheses" not in graph_state.metadata:
        graph_state.log("critique_node: skipped (no ToT output)")
        return graph_state
    if not graph_state.metadata.get("use_llm", True):
        graph_state.log("critique_node: skipped (LLM disabled)")
        return graph_state
    try:
        tot_obj = graph_state.metadata.get("_tot_response_obj")
        if not isinstance(tot_obj, TotResponse):
            try:
                tot_obj = TotResponse.model_validate(graph_state.metadata.get("tot_hypotheses"))
            except Exception as exc:  # pragma: no cover - validation fallback
                graph_state.add_error(f"critique_node invalid ToT payload: {exc!r}")
                tot_obj = _mock_tot_output(graph_state.state)
        provider = get_llm_provider()
        if provider is None:
            graph_state.log("critique_node: LLM disabled, using mock review")
            critique = _mock_critique(graph_state.state)
        else:
            try:
                critique = provider.generate_critique(
                    graph_state.state,
                    graph_state.metadata.get("complexity", {}),
                    tot_obj,
                )
                graph_state.log(
                    "critique_node: Gemini produced critique with %s issues"
                    % len(critique.issues)
                )
            except LLMCallError as err:
                graph_state.add_error(f"critique_node LLM failure: {err}")
                graph_state.log("critique_node: fallback to mock review")
                critique = _mock_critique(graph_state.state)
        graph_state.metadata["critique"] = critique.model_dump()
        graph_state.metadata.pop("_tot_response_obj", None)
    except Exception as exc:  # pragma: no cover
        graph_state.add_error(f"critique_node failed: {exc!r}")
        raise
    return graph_state


def revision_node(graph_state: GraphState) -> GraphState:
    """Append review metadata to the state for downstream usage."""
    if "tot_hypotheses" not in graph_state.metadata and "critique" not in graph_state.metadata:
        graph_state.log("revision_node: nothing to record")
        return graph_state
    review_record = {
        "complexity": graph_state.metadata.get("complexity"),
        "tot_hypotheses": graph_state.metadata.get("tot_hypotheses"),
        "critique": graph_state.metadata.get("critique"),
    }
    graph_state.state.insight_reviews.append(review_record)
    graph_state.log("revision_node: insight review appended")
    return graph_state


# -------- Workflow runner -------- #


def run_workflow(
    payload: Dict[str, Any],
    *,
    recent_training_au: Optional[Sequence[float]] = None,
    recent_training_loads: Optional[Sequence[str]] = None,
    baselines: Optional[Dict[str, float]] = None,
    personalized_thresholds: Optional[Dict[str, float]] = None,
    auto_insights: bool = True,
    use_llm: bool = True,
) -> GraphState:
    """Execute ingest -> metrics -> (insights) nodes in sequence."""
    graph_state = GraphState(
        state=create_state(
            user_id=payload.get("user_id"),
            date=payload.get("date"),
            gender=payload.get("gender"),
        ),
        payload=dict(payload),
    )
    graph_state.metadata["use_llm"] = use_llm

    ingest_node(graph_state)
    metrics_node(
        graph_state,
        recent_training_au=recent_training_au,
        recent_training_loads=recent_training_loads,
        baselines=baselines,
        personalized_thresholds=personalized_thresholds,
    )
    analysis_node(graph_state)
    if auto_insights:
        insights_node(graph_state)
        complexity_check_node(graph_state)
        tot_reasoning_node(graph_state)
        critique_node(graph_state)
        revision_node(graph_state)
    else:
        complexity_check_node(graph_state)
    return graph_state


def run_workflow_json(
    payload: Dict[str, Any],
    **kwargs: Any,
) -> str:
    """Convenience wrapper returning the final state as JSON string."""
    graph_state = run_workflow(payload, **kwargs)
    return state_to_json(graph_state.state, indent=2)


__all__ = [
    "GraphState",
    "ingest_node",
    "metrics_node",
    "insights_node",
    "complexity_check_node",
    "tot_reasoning_node",
    "critique_node",
    "revision_node",
    "run_workflow",
    "run_workflow_json",
]
