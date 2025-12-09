from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


def _to_int(x: Any) -> Optional[int]:
    try:
        if x is None:
            return None
        return int(x)
    except Exception:
        return None


def _to_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None


@dataclass
class _SleepSegment:
    start_ts: int  # seconds since epoch
    end_ts: int    # seconds since epoch
    sleep_type: Optional[int]

    @property
    def duration_minutes(self) -> float:
        return max(0.0, (self.end_ts - self.start_ts) / 60.0)


def _normalize_sleep_segments(raw_segments: Iterable[Dict[str, Any]]) -> List[_SleepSegment]:
    """Normalize raw sci-sleep segments into internal representation.

    This is intentionally tolerant to field names so that clients can either
    send SDK-shaped payloads (timeStamp/sleepTime/sleepType) or the simplified
    nightly_sleep_segments schema (start_ts/duration_minutes/sleep_type).
    """
    segments: List[_SleepSegment] = []
    for item in raw_segments:
        if not isinstance(item, dict):
            continue
        # Support multiple possible keys for start timestamp
        start = _to_int(
            item.get("start_ts")
            if item.get("start_ts") is not None
            else item.get("timeStamp") or item.get("timestamp")
        )
        # Duration in minutes
        dur_min = _to_int(
            item.get("duration_minutes")
            if item.get("duration_minutes") is not None
            else item.get("sleepTime") or item.get("duration_min")
        )
        if start is None or dur_min is None or dur_min <= 0:
            continue
        sleep_type = _to_int(item.get("sleep_type") or item.get("sleepType"))
        end = start + int(dur_min * 60)
        segments.append(_SleepSegment(start_ts=start, end_ts=end, sleep_type=sleep_type))
    segments.sort(key=lambda s: s.start_ts)
    return segments


def _merge_into_episodes(
    segments: Sequence[_SleepSegment],
    *,
    max_gap_minutes: float,
) -> List[Tuple[int, int, float]]:
    """Merge consecutive segments into sleep episodes.

    Returns a list of (episode_start_ts, episode_end_ts, total_minutes).
    """
    if not segments:
        return []

    episodes: List[Tuple[int, int, float]] = []
    cur_start = segments[0].start_ts
    cur_end = segments[0].end_ts
    cur_total_min = segments[0].duration_minutes

    for seg in segments[1:]:
        gap_min = max(0.0, (seg.start_ts - cur_end) / 60.0)
        if gap_min <= max_gap_minutes:
            # Same episode
            cur_end = max(cur_end, seg.end_ts)
            cur_total_min += seg.duration_minutes
        else:
            episodes.append((cur_start, cur_end, cur_total_min))
            cur_start = seg.start_ts
            cur_end = seg.end_ts
            cur_total_min = seg.duration_minutes

    episodes.append((cur_start, cur_end, cur_total_min))
    return episodes


def _normalize_hrv_samples(raw_samples: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalize raw minute-level health samples.

    Expected schema (flexible):
      - ts / timestamp: seconds since epoch
      - step: optional int
      - dynamic_hr / dynamicHeartRate: optional int
      - hrv_index / heartRateVariability / hrv: numeric HRV index
    """
    out: List[Dict[str, Any]] = []
    for item in raw_samples:
        if not isinstance(item, dict):
            continue
        ts = _to_int(item.get("ts") or item.get("timestamp"))
        if ts is None:
            continue
        hrv = _to_float(
            item.get("hrv_index")
            if item.get("hrv_index") is not None
            else item.get("heartRateVariability") or item.get("hrv")
        )
        if hrv is None or hrv <= 0:
            # Without HRV index the point is not useful for our metric
            continue
        step = _to_int(item.get("step"))
        dyn_hr = _to_int(item.get("dynamic_hr") or item.get("dynamicHeartRate"))
        out.append(
            {
                "ts": ts,
                "hrv_index": float(hrv),
                "step": step,
                "dynamic_hr": dyn_hr,
            }
        )
    out.sort(key=lambda x: x["ts"])
    return out


def compute_nightly_hrv_metric(
    *,
    sleep_segments: Iterable[Dict[str, Any]],
    hrv_samples: Iterable[Dict[str, Any]],
    min_episode_minutes: float = 180.0,
    max_gap_minutes: float = 90.0,
    step_threshold: int = 10,
    min_points: int = 20,
    trim_fraction: float = 0.1,
    allowed_sleep_types: Optional[Iterable[int]] = None,
) -> Dict[str, Any]:
    """Compute a robust nightly HRV index from raw sleep + HRV samples.

    This function is intentionally conservative:
      - Only uses samples during the main sleep episode (longest block of sleep).
      - Restricts to NREM-like stages by default (sleep_type in {1,2,4}).
      - Filters out minutes with large step counts or missing HRV.
      - Applies trimmed median aggregation to reduce the impact of outliers.

    Returns:
        {
          "hrv_rmssd_today": float,
          "valid_points": int,
          "total_main_minutes": float,
          "coverage": float,
          "quality_band": "high" | "medium" | "low",
          "main_sleep_start_ts": int,
          "main_sleep_end_ts": int,
        }
        or {} if data is insufficient.
    """
    segments = _normalize_sleep_segments(sleep_segments)
    samples = _normalize_hrv_samples(hrv_samples)
    if not segments or not samples:
        return {}

    episodes = _merge_into_episodes(segments, max_gap_minutes=max_gap_minutes)
    if not episodes:
        return {}

    # Choose the longest episode as "main sleep"
    main_start, main_end, main_total_min = max(episodes, key=lambda e: e[2])
    if main_total_min <= 0:
        return {}

    # Restrict segments to those overlapping main sleep
    main_segments: List[_SleepSegment] = [
        s
        for s in segments
        if s.end_ts > main_start and s.start_ts < main_end
    ]
    main_segments.sort(key=lambda s: s.start_ts)

    # Allowed sleep types: 1=deep, 2=light, 4=REM by default (SDK SciSleep)
    if allowed_sleep_types is None:
        allowed_sleep_types = {1, 2, 4}
    allowed_set = set(int(t) for t in allowed_sleep_types if t is not None)

    def _sleep_type_for_ts(ts: int) -> Optional[int]:
        for seg in main_segments:
            if seg.start_ts <= ts < seg.end_ts:
                return seg.sleep_type
        return None

    # Collect candidate HRV points within main sleep episode and restful minutes
    values: List[float] = []
    total_points = 0
    for sample in samples:
        ts = int(sample["ts"])
        if ts < main_start or ts >= main_end:
            continue
        total_points += 1
        stype = _sleep_type_for_ts(ts)
        if stype is None or (allowed_set and stype not in allowed_set):
            continue
        step = sample.get("step")
        if step is not None and step > step_threshold:
            continue
        hrv_val = sample.get("hrv_index")
        if hrv_val is None:
            continue
        values.append(float(hrv_val))

    if len(values) < min_points:
        # Not enough high-quality minutes to form a robust nightly metric
        return {}

    values.sort()
    n = len(values)
    trim_n = int(n * trim_fraction)
    if trim_n > 0 and 2 * trim_n < n:
        trimmed = values[trim_n : n - trim_n]
    else:
        trimmed = values

    if not trimmed:
        return {}

    hrv_today = float(median(trimmed))
    coverage = len(values) / max(1.0, main_total_min)
    if coverage >= 0.6:
        q_band = "high"
    elif coverage >= 0.3:
        q_band = "medium"
    else:
        q_band = "low"

    return {
        "hrv_rmssd_today": hrv_today,
        "valid_points": len(values),
        "total_main_minutes": main_total_min,
        "coverage": coverage,
        "quality_band": q_band,
        "main_sleep_start_ts": main_start,
        "main_sleep_end_ts": main_end,
    }


__all__ = ["compute_nightly_hrv_metric"]

