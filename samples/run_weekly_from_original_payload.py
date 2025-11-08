from __future__ import annotations

"""Run Phase 1→5 end-to-end using samples/original_payload_sample.json.

Outputs:
  - samples/original_weekly_package_run_llm.json
  - samples/original_weekly_final_run_llm.json
  - samples/original_weekly_final_run_llm.md
"""

import json
from pathlib import Path
import sys
from typing import Any, Dict, List

# Ensure project root on sys.path for package proxies
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from weekly_report.workflow.graph import run_workflow
from weekly_report.models import WeeklyHistoryEntry
from weekly_report.llm.provider import get_llm_provider, LLMNotConfiguredError
from weekly_report.pipeline import generate_weekly_report
from weekly_report.finalizer import generate_weekly_final_report


def _load_payload(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_history(items: List[Dict[str, Any]]) -> List[WeeklyHistoryEntry]:
    return [WeeklyHistoryEntry.model_validate(it) for it in items]


def main() -> None:
    here = Path(__file__).parent
    payload_path = here / "original_payload_sample.json"
    payload = _load_payload(payload_path)

    # 1-3: workflow (ingest→metrics→insights→plan→ToT→critique)
    history_items = payload.get("history") or []
    history = _validate_history(history_items)
    graph = run_workflow(dict(payload), use_llm=True)
    state = graph.state

    # 4: weekly package (Analyst + Communicator + charts)
    provider = get_llm_provider()
    if provider is None:
        raise LLMNotConfiguredError("LLM provider not configured (GOOGLE_API_KEY missing?)")
    extra_ctx = {
        "training_tag_counts": payload.get("training_tag_counts"),
        "strength_levels": payload.get("strength_levels"),
    }
    package = generate_weekly_report(
        state,
        history,
        sleep_baseline_hours=payload.get("sleep_baseline_hours"),
        hrv_baseline=payload.get("hrv_baseline_mu"),
        provider=provider,
        use_llm=True,
        extra=extra_ctx,
    )

    # 5: final report (Markdown + CTA + chart ids)
    final_report = generate_weekly_final_report(
        state,
        package,
        history,
        report_notes=state.raw_inputs.report_notes,
        training_sessions=state.raw_inputs.training_sessions,
        provider=provider,
        use_llm=True,
    )

    out_pkg = here / "original_weekly_package_run_llm.json"
    out_pkg.write_text(
        json.dumps(package.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    out_final_json = here / "original_weekly_final_run_llm.json"
    out_final_json.write_text(
        json.dumps(final_report.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    out_final_md = here / "original_weekly_final_run_llm.md"
    out_final_md.write_text(final_report.markdown_report, encoding="utf-8")

    print(f"Weekly package JSON -> {out_pkg}")
    print(f"Final report JSON  -> {out_final_json}")
    print(f"Final report MD    -> {out_final_md}")


if __name__ == "__main__":
    main()
