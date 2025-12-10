import { useState } from "react";
import { useSettings } from "../store/settings";
import {
  postTrainingSession,
  postStrengthRecord,
  getTrainingCounts,
  getStrengthLatest,
} from "../api/endpoints";

export function Train() {
  const { readinessPort, apiHost } = useSettings();
  const todayStr = new Date().toISOString().slice(0, 10);

  const [userId, setUserId] = useState("u001");
  const [sessionDate, setSessionDate] = useState(todayStr);
  const [tags, setTags] = useState("strength:chest");
  const [rpe, setRpe] = useState<number | undefined>(7);
  const [duration, setDuration] = useState<number | undefined>(45);
  const [au, setAu] = useState<number | undefined>(undefined);
  const [notes, setNotes] = useState("");

  const [exercise, setExercise] = useState("bench_press");
  const [recordDate, setRecordDate] = useState(todayStr);
  const [weight, setWeight] = useState<number>(80);
  const [reps, setReps] = useState<number>(5);
  const [strengthNotes, setStrengthNotes] = useState("");

  const [sessionMsg, setSessionMsg] = useState<string | null>(null);
  const [strengthMsg, setStrengthMsg] = useState<string | null>(null);
  const [counts, setCounts] = useState<any>(null);
  const [latest, setLatest] = useState<any>(null);

  const submitSession = async () => {
    setSessionMsg(null);
    try {
      const res = await postTrainingSession(readinessPort, {
        user_id: userId,
        date: sessionDate,
        type_tags: tags.split(",").map((t) => t.trim()).filter(Boolean),
        rpe,
        duration_minutes: duration,
        au,
        notes: notes || undefined,
      });
      setSessionMsg(`Saved training session (id ${res.id || "ok"})`);
      const c = await getTrainingCounts(readinessPort, { user_id: userId, days: 7 });
      setCounts(c);
    } catch (err: any) {
      setSessionMsg(err?.response?.data?.detail || err?.message || "保存失败");
    }
  };

  const submitStrength = async () => {
    setStrengthMsg(null);
    try {
      const res = await postStrengthRecord(readinessPort, {
        user_id: userId,
        exercise_name: exercise,
        record_date: recordDate,
        weight_kg: weight,
        reps,
        notes: strengthNotes || undefined,
      });
      setStrengthMsg(`Saved strength record (id ${res.id || "ok"}, est 1RM ${res.one_rm_est ?? "?"})`);
      const latestRes = await getStrengthLatest(readinessPort, { user_id: userId });
      setLatest(latestRes);
    } catch (err: any) {
      setStrengthMsg(err?.response?.data?.detail || err?.message || "保存失败");
    }
  };

  return (
    <div className="card">
      <h2 className="section-title">Train & Strength</h2>
      <p className="muted">
        API target: {apiHost}:{readinessPort}
      </p>

      <div className="grid two" style={{ marginTop: 16 }}>
        <div>
          <h3>Training session</h3>
          <label className="muted">User ID</label>
          <input
            value={userId}
            onChange={(e) => setUserId(e.target.value)}
            style={{ width: "100%", padding: 10, borderRadius: 10, border: "1px solid #233043", background: "#0f1621", color: "white" }}
          />
          <label className="muted">Date</label>
          <input
            type="date"
            value={sessionDate}
            onChange={(e) => setSessionDate(e.target.value)}
            style={{ width: "100%", padding: 10, borderRadius: 10, border: "1px solid #233043", background: "#0f1621", color: "white" }}
          />
          <label className="muted">Tags (comma separated)</label>
          <input
            value={tags}
            onChange={(e) => setTags(e.target.value)}
            placeholder="strength:chest, cardio:rower"
            style={{ width: "100%", padding: 10, borderRadius: 10, border: "1px solid #233043", background: "#0f1621", color: "white" }}
          />
          <label className="muted">RPE (1-10)</label>
          <input
            type="number"
            value={rpe ?? ""}
            onChange={(e) => setRpe(e.target.value === "" ? undefined : Number(e.target.value))}
            style={{ width: "100%", padding: 10, borderRadius: 10, border: "1px solid #233043", background: "#0f1621", color: "white" }}
          />
          <label className="muted">Duration minutes</label>
          <input
            type="number"
            value={duration ?? ""}
            onChange={(e) => setDuration(e.target.value === "" ? undefined : Number(e.target.value))}
            style={{ width: "100%", padding: 10, borderRadius: 10, border: "1px solid #233043", background: "#0f1621", color: "white" }}
          />
          <label className="muted">AU (optional)</label>
          <input
            type="number"
            value={au ?? ""}
            onChange={(e) => setAu(e.target.value === "" ? undefined : Number(e.target.value))}
            style={{ width: "100%", padding: 10, borderRadius: 10, border: "1px solid #233043", background: "#0f1621", color: "white" }}
          />
          <label className="muted">Notes</label>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={2}
            style={{ width: "100%", padding: 10, borderRadius: 10, border: "1px solid #233043", background: "#0f1621", color: "white", resize: "vertical" }}
          />
          <div style={{ marginTop: 10 }}>
            <button className="cta" onClick={submitSession}>Save session</button>
          </div>
          {sessionMsg && <p className="muted" style={{ marginTop: 8 }}>{sessionMsg}</p>}
        </div>

        <div>
          <h3>Strength record</h3>
          <label className="muted">Exercise</label>
          <input
            value={exercise}
            onChange={(e) => setExercise(e.target.value)}
            style={{ width: "100%", padding: 10, borderRadius: 10, border: "1px solid #233043", background: "#0f1621", color: "white" }}
          />
          <label className="muted">Record date</label>
          <input
            type="date"
            value={recordDate}
            onChange={(e) => setRecordDate(e.target.value)}
            style={{ width: "100%", padding: 10, borderRadius: 10, border: "1px solid #233043", background: "#0f1621", color: "white" }}
          />
          <label className="muted">Weight (kg)</label>
          <input
            type="number"
            value={weight}
            onChange={(e) => setWeight(Number(e.target.value))}
            style={{ width: "100%", padding: 10, borderRadius: 10, border: "1px solid #233043", background: "#0f1621", color: "white" }}
          />
          <label className="muted">Reps</label>
          <input
            type="number"
            value={reps}
            onChange={(e) => setReps(Number(e.target.value))}
            style={{ width: "100%", padding: 10, borderRadius: 10, border: "1px solid #233043", background: "#0f1621", color: "white" }}
          />
          <label className="muted">Notes</label>
          <textarea
            value={strengthNotes}
            onChange={(e) => setStrengthNotes(e.target.value)}
            rows={2}
            style={{ width: "100%", padding: 10, borderRadius: 10, border: "1px solid #233043", background: "#0f1621", color: "white", resize: "vertical" }}
          />
          <div style={{ marginTop: 10 }}>
            <button className="cta" onClick={submitStrength}>Save strength</button>
          </div>
          {strengthMsg && <p className="muted" style={{ marginTop: 8 }}>{strengthMsg}</p>}
        </div>
      </div>

      <div className="grid two" style={{ marginTop: 16 }}>
        <div className="card">
          <h3 className="section-title" style={{ fontSize: 16 }}>Training counts (auto refreshed after save)</h3>
          <pre style={{ background: "#0b111a", padding: 10, borderRadius: 12, minHeight: 140, overflowX: "auto" }}>
            {counts ? JSON.stringify(counts, null, 2) : "No data"}
          </pre>
        </div>
        <div className="card">
          <h3 className="section-title" style={{ fontSize: 16 }}>Strength latest</h3>
          <pre style={{ background: "#0b111a", padding: 10, borderRadius: 12, minHeight: 140, overflowX: "auto" }}>
            {latest ? JSON.stringify(latest, null, 2) : "No data"}
          </pre>
        </div>
      </div>
    </div>
  );
}
