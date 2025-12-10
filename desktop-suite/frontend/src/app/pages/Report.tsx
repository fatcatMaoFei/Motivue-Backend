import { useState } from "react";
import { useSettings } from "../store/settings";
import { runWeeklyReport } from "../api/endpoints";

const samplePayload = {
  user_id: "u001",
  raw_inputs: {
    user_id: "u001",
    date: "2025-11-22",
    report_notes: "Sample notes",
    journal: { lifestyle_tags: [], alcohol_consumed: false },
    hooper: { fatigue: 4, soreness: 3, stress: 3, sleep: 4 },
    training_sessions: [],
  },
  history: [
    { date: "2025-11-15", readiness_score: 72, readiness_band: "Well-adapted", hrv_rmssd: 62, sleep_duration_hours: 7.5, daily_au: 320, hooper: { fatigue: 3, soreness: 2, stress: 3, sleep: 4 }, lifestyle_events: [] },
    { date: "2025-11-16", readiness_score: 70, readiness_band: "Well-adapted", hrv_rmssd: 61, sleep_duration_hours: 7.3, daily_au: 280, hooper: { fatigue: 3, soreness: 3, stress: 3, sleep: 4 }, lifestyle_events: [] },
    { date: "2025-11-17", readiness_score: 68, readiness_band: "FOR", hrv_rmssd: 58, sleep_duration_hours: 7.0, daily_au: 420, hooper: { fatigue: 4, soreness: 4, stress: 4, sleep: 3 }, lifestyle_events: [] },
    { date: "2025-11-18", readiness_score: 65, readiness_band: "FOR", hrv_rmssd: 55, sleep_duration_hours: 6.8, daily_au: 450, hooper: { fatigue: 5, soreness: 4, stress: 4, sleep: 3 }, lifestyle_events: [] },
    { date: "2025-11-19", readiness_score: 66, readiness_band: "Well-adapted", hrv_rmssd: 57, sleep_duration_hours: 7.1, daily_au: 200, hooper: { fatigue: 4, soreness: 3, stress: 3, sleep: 4 }, lifestyle_events: [] },
    { date: "2025-11-20", readiness_score: 69, readiness_band: "Well-adapted", hrv_rmssd: 60, sleep_duration_hours: 7.6, daily_au: 180, hooper: { fatigue: 3, soreness: 2, stress: 3, sleep: 5 }, lifestyle_events: [] },
    { date: "2025-11-21", readiness_score: 71, readiness_band: "Well-adapted", hrv_rmssd: 61, sleep_duration_hours: 7.4, daily_au: 150, hooper: { fatigue: 3, soreness: 2, stress: 3, sleep: 5 }, lifestyle_events: [] }
  ],
  recent_training_au: [320, 280, 420, 450, 200, 180, 150],
};

export function Report() {
  const { weeklyReportPort, apiHost, useLlm } = useSettings();
  const [payloadText, setPayloadText] = useState(JSON.stringify(samplePayload, null, 2));
  const [resp, setResp] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const submit = async () => {
    setLoading(true);
    setError(null);
    setResp(null);
    try {
      const parsed = JSON.parse(payloadText);
      const data = await runWeeklyReport(weeklyReportPort, {
        payload: parsed,
        persist: false,
      });
      setResp(data);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || "请求失败（请确认 JSON 与 GOOGLE_API_KEY/LLM 配置）");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="card">
      <h2 className="section-title">Weekly Report</h2>
      <p className="muted">
        Generate Phase3/4/5 weekly reports. LLM: {useLlm ? "on (需要 GOOGLE_API_KEY)" : "off（若未配置 Key 将报 503）"}.
      </p>
      <p className="muted">
        Target API: {apiHost}:{weeklyReportPort}. 需要提供 history（近 7 天）和 recent_training_au。
      </p>
      <textarea
        value={payloadText}
        onChange={(e) => setPayloadText(e.target.value)}
        rows={18}
        style={{ width: "100%", marginTop: 12, padding: 12, borderRadius: 12, border: "1px solid #233043", background: "#0f1621", color: "white", fontFamily: "monospace", resize: "vertical" }}
      />
      <div style={{ marginTop: 12 }}>
        <button className="cta" onClick={submit} disabled={loading}>
          {loading ? "Generating..." : "Run weekly-report"}
        </button>
      </div>
      {error && <p style={{ color: "#f95e5e", marginTop: 10 }}>{error}</p>}
      {resp && (
        <pre style={{ background: "#0b111a", padding: 10, borderRadius: 12, marginTop: 12, overflowX: "auto", maxHeight: 500 }}>
          {JSON.stringify(resp, null, 2)}
        </pre>
      )}
    </div>
  );
}
