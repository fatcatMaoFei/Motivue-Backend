import { useState } from "react";
import { useSettings } from "../store/settings";
import { postReadiness } from "../api/endpoints";

type HooperKey = "sleep" | "fatigue" | "soreness" | "stress";

export function Today() {
  const settings = useSettings();
  const todayStr = new Date().toISOString().slice(0, 10);
  const [userId, setUserId] = useState("u001");
  const [date, setDate] = useState(todayStr);
  const [sleepHours, setSleepHours] = useState<number | undefined>(7.0);
  const [sleepEff, setSleepEff] = useState<number | undefined>(92);
  const [hrvToday, setHrvToday] = useState<number | undefined>(55);
  const [hrvMu, setHrvMu] = useState<number | undefined>(60);
  const [hrvSd, setHrvSd] = useState<number | undefined>(8);
  const [dailyAu, setDailyAu] = useState<number | undefined>(undefined);
  const [hooper, setHooper] = useState<Record<HooperKey, number>>({
    sleep: 4,
    fatigue: 4,
    soreness: 2,
    stress: 3,
  });
  const [journal, setJournal] = useState({
    alcohol_consumed: false,
    late_caffeine: false,
    late_meal: false,
    screen_before_bed: false,
    is_sick: false,
    is_injured: false,
  });

  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const updateHooper = (key: HooperKey, value: number) =>
    setHooper((prev) => ({ ...prev, [key]: value }));

  const toggle = (key: keyof typeof journal) =>
    setJournal((prev) => ({ ...prev, [key]: !prev[key] }));

  const submit = async () => {
    setLoading(true);
    setError(null);
    try {
      const payload = {
        user_id: userId,
        date,
        gender: "male",
        sleep_duration_hours: sleepHours,
        sleep_efficiency: sleepEff,
        hrv_rmssd_today: hrvToday,
        hrv_baseline_mu: hrvMu,
        hrv_baseline_sd: hrvSd,
        hooper,
        journal,
        daily_au: dailyAu || undefined,
      };
      const data = await postReadiness(settings.readinessPort, payload);
      setResult(data);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || "请求失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="grid">
      <div className="card">
        <h2 className="section-title">Morning Check-in</h2>
        <p className="muted">
          Manual entry for sleep/Hooper and yesterday habits. Data stays local.
        </p>
        <div className="grid two" style={{ marginBottom: 12 }}>
          <div>
            <label className="muted">User ID</label>
            <input
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
              style={{ width: "100%", padding: 10, borderRadius: 10, border: "1px solid #233043", background: "#0f1621", color: "white" }}
            />
          </div>
          <div>
            <label className="muted">Date</label>
            <input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              style={{ width: "100%", padding: 10, borderRadius: 10, border: "1px solid #233043", background: "#0f1621", color: "white" }}
            />
          </div>
        </div>
        <div className="grid two" style={{ marginBottom: 16 }}>
          <div>
            <label className="muted">Sleep hours (optional)</label>
            <input
              type="number"
              value={sleepHours ?? ""}
              onChange={(e) => setSleepHours(e.target.value === "" ? undefined : Number(e.target.value))}
              style={{ width: "100%", padding: 10, borderRadius: 10, border: "1px solid #233043", background: "#0f1621", color: "white" }}
            />
          </div>
          <div>
            <label className="muted">Sleep efficiency % (optional)</label>
            <input
              type="number"
              value={sleepEff ?? ""}
              onChange={(e) => setSleepEff(e.target.value === "" ? undefined : Number(e.target.value))}
              style={{ width: "100%", padding: 10, borderRadius: 10, border: "1px solid #233043", background: "#0f1621", color: "white" }}
            />
          </div>
          <div>
            <label className="muted">HRV today (rmssd, optional)</label>
            <input
              type="number"
              value={hrvToday ?? ""}
              onChange={(e) => setHrvToday(e.target.value === "" ? undefined : Number(e.target.value))}
              style={{ width: "100%", padding: 10, borderRadius: 10, border: "1px solid #233043", background: "#0f1621", color: "white" }}
            />
          </div>
          <div>
            <label className="muted">HRV baseline μ (optional)</label>
            <input
              type="number"
              value={hrvMu ?? ""}
              onChange={(e) => setHrvMu(e.target.value === "" ? undefined : Number(e.target.value))}
              style={{ width: "100%", padding: 10, borderRadius: 10, border: "1px solid #233043", background: "#0f1621", color: "white" }}
            />
          </div>
          <div>
            <label className="muted">HRV baseline σ (optional)</label>
            <input
              type="number"
              value={hrvSd ?? ""}
              onChange={(e) => setHrvSd(e.target.value === "" ? undefined : Number(e.target.value))}
              style={{ width: "100%", padding: 10, borderRadius: 10, border: "1px solid #233043", background: "#0f1621", color: "white" }}
            />
          </div>
          <div>
            <label className="muted">Daily AU (optional)</label>
            <input
              type="number"
              value={dailyAu ?? ""}
              onChange={(e) => setDailyAu(e.target.value === "" ? undefined : Number(e.target.value))}
              style={{ width: "100%", padding: 10, borderRadius: 10, border: "1px solid #233043", background: "#0f1621", color: "white" }}
            />
          </div>
        </div>
        <div className="grid">
          {(["sleep", "fatigue", "soreness", "stress"] as HooperKey[]).map((key) => (
            <div key={key}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ textTransform: "capitalize" }}>{key}</span>
                <span className="muted">{hooper[key]}/7</span>
              </div>
              <input
                type="range"
                min={1}
                max={7}
                value={hooper[key]}
                onChange={(e) => updateHooper(key, Number(e.target.value))}
                style={{ width: "100%" }}
              />
            </div>
          ))}
        </div>
        <div style={{ marginTop: 16 }}>
          <div style={{ marginBottom: 8, fontWeight: 600 }}>Yesterday's habits</div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
            {(
              Object.keys(journal) as Array<keyof typeof journal>
            ).map((key) => (
              <button
                key={key}
                onClick={() => toggle(key)}
                className="nav-btn"
                style={{
                  background: journal[key] ? "rgba(77,224,194,0.2)" : "rgba(255,255,255,0.05)",
                  borderColor: journal[key] ? "rgba(77,224,194,0.6)" : "transparent",
                  textTransform: "capitalize",
                }}
              >
                {key.replace(/_/g, " ")}
              </button>
            ))}
          </div>
        </div>
        <div style={{ marginTop: 20 }}>
          <button className="cta" onClick={submit} disabled={loading}>
            {loading ? "Calculating..." : "Calculate Readiness"}
          </button>
        </div>
        {error && <p style={{ color: "#f95e5e", marginTop: 12 }}>{error}</p>}
        {result && (
          <div className="card" style={{ marginTop: 16, background: "#0f1621" }}>
            <div style={{ fontWeight: 700 }}>Result</div>
            <div className="muted" style={{ marginTop: 6 }}>
              final_readiness_score: {result.final_readiness_score ?? "—"}
            </div>
            <div className="muted">final_diagnosis: {result.final_diagnosis ?? "—"}</div>
            <pre style={{ background: "#0b111a", padding: 10, borderRadius: 12, overflowX: "auto" }}>
              {JSON.stringify(result, null, 2)}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}
