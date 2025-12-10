import { useSettings } from "../store/settings";

export function Settings() {
  const settings = useSettings();

  const update = (key: keyof typeof settings, value: any) => {
    if (typeof settings.set === "function") {
      settings.set({ [key]: value } as any);
    }
  };

  return (
    <div className="card">
      <h2 className="section-title">Settings</h2>
      <div className="grid two">
        <div>
          <label className="muted">API host</label>
          <input
            value={settings.apiHost}
            onChange={(e) => update("apiHost", e.target.value)}
            style={{ width: "100%", padding: 10, borderRadius: 10, border: "1px solid #233043", background: "#0f1621", color: "white" }}
          />
        </div>
        <div>
          <label className="muted">Readiness port</label>
          <input
            type="number"
            value={settings.readinessPort}
            onChange={(e) => update("readinessPort", Number(e.target.value))}
            style={{ width: "100%", padding: 10, borderRadius: 10, border: "1px solid #233043", background: "#0f1621", color: "white" }}
          />
        </div>
        <div>
          <label className="muted">Baseline port</label>
          <input
            type="number"
            value={settings.baselinePort}
            onChange={(e) => update("baselinePort", Number(e.target.value))}
            style={{ width: "100%", padding: 10, borderRadius: 10, border: "1px solid #233043", background: "#0f1621", color: "white" }}
          />
        </div>
        <div>
          <label className="muted">Weekly report port</label>
          <input
            type="number"
            value={settings.weeklyReportPort}
            onChange={(e) => update("weeklyReportPort", Number(e.target.value))}
            style={{ width: "100%", padding: 10, borderRadius: 10, border: "1px solid #233043", background: "#0f1621", color: "white" }}
          />
        </div>
        <div>
          <label className="muted">Physio-age port</label>
          <input
            type="number"
            value={settings.physioPort}
            onChange={(e) => update("physioPort", Number(e.target.value))}
            style={{ width: "100%", padding: 10, borderRadius: 10, border: "1px solid #233043", background: "#0f1621", color: "white" }}
          />
        </div>
        <div>
          <label className="muted">GOOGLE_API_KEY (optional)</label>
          <input
            value={settings.googleApiKey || ""}
            onChange={(e) => update("googleApiKey", e.target.value)}
            placeholder="leave empty for offline"
            style={{ width: "100%", padding: 10, borderRadius: 10, border: "1px solid #233043", background: "#0f1621", color: "white" }}
          />
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 12 }}>
          <input
            id="use-llm"
            type="checkbox"
            checked={settings.useLlm}
            onChange={(e) => update("useLlm", e.target.checked)}
          />
          <label htmlFor="use-llm">Use LLM (set API key to enable cloud mode)</label>
        </div>
      </div>
      <p className="muted" style={{ marginTop: 16 }}>
        Import/export of local data (JSON/CSV) will be added here.
      </p>
    </div>
  );
}
