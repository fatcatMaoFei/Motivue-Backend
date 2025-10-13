from __future__ import annotations

"""
Quick ECharts preview for WeeklyReportPackage charts.

Usage:
  python samples/preview_charts.py \
    --input samples/weekly_report_sample_run.json \
    --output samples/preview_charts.html

Opens the generated HTML in the default browser if --open is set.
"""

import argparse
import json
import webbrowser
from pathlib import Path


HTML_TMPL = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <title>Weekly Report Charts Preview</title>
  <script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif; margin: 16px; }
    .chart { width: 1000px; height: 360px; margin: 16px 0; border: 1px solid #eee; }
    h3 { margin: 8px 0; }
    .note { color: #666; font-size: 12px; }
  </style>
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate" />
  <meta http-equiv="Pragma" content="no-cache" />
  <meta http-equiv="Expires" content="0" />
  <meta http-equiv="Content-Security-Policy" content="default-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; img-src 'self' data:;" />
  <script>
    function mkOption(spec) {
      const d = spec.data || {};
      // Basic axes
      let opt = {
        title: { text: spec.title || spec.chart_id },
        tooltip: { trigger: 'axis' },
        legend: {},
        grid: { left: 48, right: 24, top: 48, bottom: 48 },
      };

      // Radar special-case
      if (spec.chart_type === 'radar' || d.indicator) {
        opt.tooltip = { trigger: 'item' };
        opt.radar = { indicator: d.indicator || [] };
        opt.series = (d.series || []).map(s => ({ ...s, type: 'radar' }));
        return opt;
      }

      // Category X axis
      if (Array.isArray(d.xAxis)) {
        opt.xAxis = { type: 'category', data: d.xAxis };
      } else if (typeof d.xAxis === 'object') {
        // Allow passing through {type, data}
        opt.xAxis = d.xAxis;
      } else {
        opt.xAxis = { type: 'category', data: [] };
      }

      // yAxis passthrough or default
      if (Array.isArray(d.yAxis)) {
        opt.yAxis = d.yAxis;
      } else if (typeof d.yAxis === 'object') {
        opt.yAxis = d.yAxis;
      } else {
        opt.yAxis = { type: 'value' };
      }

      // Series passthrough; enforce type if provided by spec
      opt.series = (d.series || []).map(s => {
        const t = s.type || (spec.chart_type === 'bar' ? 'bar' : 'line');
        return { ...s, type: t, smooth: s.smooth ?? (t === 'line') };
      });

      return opt;
    }
  </script>
</head>
<body>
  <h2>Weekly Report Charts Preview</h2>
  <div id="mount"></div>
  <script>
    const specs = __SPECS__;
    const mount = document.getElementById('mount');
    specs.forEach((spec, idx) => {
      const container = document.createElement('div');
      const title = document.createElement('h3');
      title.textContent = `${idx+1}. ${spec.title || spec.chart_id}`;
      const note = document.createElement('div');
      note.className = 'note';
      note.textContent = spec.notes || '';
      const el = document.createElement('div');
      el.className = 'chart';
      el.id = `chart_${idx}`;
      container.appendChild(title);
      container.appendChild(note);
      container.appendChild(el);
      mount.appendChild(container);
      const chart = echarts.init(el);
      const option = mkOption(spec);
      chart.setOption(option);
    });
  </script>
</body>
</html>
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="WeeklyReportPackage JSON path")
    ap.add_argument("--output", required=True, help="Output HTML path")
    ap.add_argument("--open", action="store_true", help="Open in default browser")
    args = ap.parse_args()

    input_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve()
    data = json.loads(input_path.read_text(encoding="utf-8"))

    specs = data.get("charts") or []
    html = HTML_TMPL.replace("__SPECS__", json.dumps(specs, ensure_ascii=False))
    output_path.write_text(html, encoding="utf-8")

    print(f"Wrote chart preview -> {output_path}")
    if args.open:
        webbrowser.open(output_path.as_uri())


if __name__ == "__main__":
    main()

