from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Dict, Any

import sys
from pathlib import Path as _P
sys.path.insert(0, str(_P(__file__).resolve().parents[2]))
from physio_age.core import compute_physiological_age


def generate_payload(seed: int = 42) -> Dict[str, Any]:
    random.seed(seed)
    # Generate 30-day SDNN (ms) and RHR (bpm) series with mild noise
    sdnn_base = 45.0
    rhr_base = 65.0
    sdnn_series = [round(sdnn_base + random.gauss(0, 3), 2) for _ in range(30)]
    rhr_series = [round(rhr_base + random.gauss(0, 2.5), 2) for _ in range(30)]

    # Today sleep raw (minutes)
    total_sleep_minutes = 420  # 7 hours
    in_bed_minutes = 480       # 8 hours in bed
    deep_sleep_minutes = 90
    rem_sleep_minutes = 100

    return {
        'user_gender': '男性',
        'sdnn_series': sdnn_series,
        'rhr_series': rhr_series,
        'total_sleep_minutes': total_sleep_minutes,
        'in_bed_minutes': in_bed_minutes,
        'deep_sleep_minutes': deep_sleep_minutes,
        'rem_sleep_minutes': rem_sleep_minutes,
    }


def main() -> None:
    here = Path(__file__).parent
    req_path = here / 'sample_request.json'
    resp_path = here / 'sample_response.json'
    tpl_path = here / 'request_template.json'

    # Template for documentation
    template = {
        'user_gender': "男性 | 女性",
        'sdnn_series': ["ms", "... (len >= 30) ..."],
        'rhr_series': ["bpm", "... (len >= 30) ..."],
        'total_sleep_minutes': 420,
        'in_bed_minutes': 480,
        'deep_sleep_minutes': 90,
        'rem_sleep_minutes': 100,
        '# optional': {
            'age_min': 20,
            'age_max': 80,
            'weights': {'sdnn': 0.45, 'rhr': 0.20, 'css': 0.35},
            'softmin_tau': 0.2,
        }
    }
    tpl_path.write_text(json.dumps(template, ensure_ascii=False, indent=2), encoding='utf-8')

    payload = generate_payload()
    req_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')

    result = compute_physiological_age(payload)
    resp_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')

    print('Request saved to:', req_path)
    print('Response saved to:', resp_path)
    print('\nSummary:')
    print('  physiological_age:', result.get('physiological_age'))
    print('  physiological_age_weighted:', result.get('physiological_age_weighted'))
    print('  window_days_used:', result.get('window_days_used'))
    print('  data_days_count:', result.get('data_days_count'))


if __name__ == '__main__':
    main()
