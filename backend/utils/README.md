# Sleep Metrics (Minimal)

只做一件事：从原始分钟数计算两个数值，供你们后续自行映射/入库/组装 payload。

- 文件：`backend/utils/sleep_metrics.py`
- 函数：`compute_sleep_metrics(data: Dict[str, Any], decimals: int = 4)`
- 不依赖基线，不输出枚举，不涉及 readiness 内部逻辑。

输入（分钟）
- `total_sleep_minutes`：实际睡着的分钟（必需）
- `in_bed_minutes` 或 `time_in_bed_minutes`：在床分钟（必需）
- `deep_sleep_minutes`、`rem_sleep_minutes`：深睡/REM 分钟（用于恢复性计算）

输出
- `sleep_efficiency`：0..1（= total_sleep_minutes / in_bed_minutes，边界夹紧）
- `sleep_efficiency_pct`：0..100（百分数）
- `restorative_ratio`：0..1（= (deep + rem) / total_sleep_minutes，边界夹紧）

示例
```python
from backend.utils.sleep_metrics import compute_sleep_metrics

raw = {
    'total_sleep_minutes': 420,
    'in_bed_minutes': 480,
    'deep_sleep_minutes': 90,
    'rem_sleep_minutes': 100,
}
print(compute_sleep_metrics(raw))
# {'sleep_efficiency': 0.875, 'sleep_efficiency_pct': 87.5, 'restorative_ratio': 0.4524}
```

备注
- 任一必要值缺失时，对应输出为 None（不抛异常，方便上层容错）。
- 你们若需要四舍五入位数可通过 `decimals` 参数控制（默认 4 位）。
