import { useState } from "react";
import { useSettings } from "../store/settings";
import { getBaseline } from "../api/endpoints";

export function Baseline() {
  const { baselinePort, apiHost } = useSettings();
  const [userId, setUserId] = useState("u001");
  const [data, setData] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const fetchBaseline = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getBaseline(baselinePort, userId, true);
      setData(res);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || "获取失败（可能未计算过基线）");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="card">
      <h2 className="section-title">Baseline</h2>
      <p className="muted">
        View and refresh personalized baselines. API target: {apiHost}:{baselinePort}
      </p>
      <div style={{ marginTop: 12 }}>
        <label className="muted">User ID</label>
        <input
          value={userId}
          onChange={(e) => setUserId(e.target.value)}
          style={{ width: "100%", padding: 10, borderRadius: 10, border: "1px solid #233043", background: "#0f1621", color: "white" }}
        />
        <div style={{ marginTop: 12 }}>
          <button className="cta" onClick={fetchBaseline} disabled={loading}>
            {loading ? "Loading..." : "Fetch baseline"}
          </button>
        </div>
      </div>
      {error && <p style={{ color: "#f95e5e", marginTop: 10 }}>{error}</p>}
      {data && (
        <pre style={{ background: "#0b111a", padding: 10, borderRadius: 12, marginTop: 12, overflowX: "auto" }}>
          {JSON.stringify(data, null, 2)}
        </pre>
      )}
      <p className="muted" style={{ marginTop: 12 }}>
        说明：基线需要基础睡眠/HRV 历史才能计算。若为空，请先通过 readiness 流程写入用户数据后再尝试。
      </p>
    </div>
  );
}
