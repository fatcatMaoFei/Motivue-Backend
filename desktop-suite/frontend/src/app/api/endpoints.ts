import axios from "axios";

export type ReadinessPayload = {
  user_id: string;
  date: string;
  gender?: string;
  sleep_duration_hours?: number;
  sleep_efficiency?: number;
  hrv_rmssd_today?: number;
  hrv_baseline_mu?: number;
  hrv_baseline_sd?: number;
  hooper: {
    sleep?: number;
    fatigue?: number;
    soreness?: number;
    stress?: number;
  };
  journal: Record<string, boolean>;
  daily_au?: number;
  previous_state_probs?: Record<string, number>;
};

export type TrainingSessionCreate = {
  user_id: string;
  date: string;
  type_tags: string[];
  rpe?: number;
  duration_minutes?: number;
  au?: number;
  notes?: string;
};

export type StrengthRecordCreate = {
  user_id: string;
  exercise_name: string;
  record_date: string;
  weight_kg: number;
  reps: number;
  notes?: string;
};

export type WeeklyReportRequest = {
  payload: any;
  sleep_baseline_hours?: number;
  hrv_baseline_mu?: number;
  persist?: boolean;
};

const baseHost = import.meta.env.VITE_API_BASE || "http://127.0.0.1";

const url = (port: number, path: string) => `${baseHost}:${port}${path}`;

export async function postReadiness(port: number, payload: ReadinessPayload) {
  const body = {
    ...payload,
    previous_state_probs: payload.previous_state_probs || {
      Peak: 0.1,
      "Well-adapted": 0.5,
      FOR: 0.3,
      "Acute Fatigue": 0.1,
      NFOR: 0,
      OTS: 0,
    },
    hooper: payload.hooper,
    journal: payload.journal,
  };
  const res = await axios.post(url(port, "/readiness/from-healthkit"), body, {
    headers: { "Content-Type": "application/json" },
  });
  return res.data;
}

export async function postTrainingSession(port: number, payload: TrainingSessionCreate) {
  const res = await axios.post(url(port, "/training/session"), payload, {
    headers: { "Content-Type": "application/json" },
  });
  return res.data;
}

export async function postStrengthRecord(port: number, payload: StrengthRecordCreate) {
  const res = await axios.post(url(port, "/strength/record"), payload, {
    headers: { "Content-Type": "application/json" },
  });
  return res.data;
}

export async function getTrainingCounts(
  port: number,
  params: { user_id: string; tag?: string; days?: number }
) {
  const res = await axios.get(url(port, "/training/counts"), { params });
  return res.data;
}

export async function getStrengthLatest(
  port: number,
  params: { user_id: string; exercise?: string }
) {
  const res = await axios.get(url(port, "/strength/latest"), { params });
  return res.data;
}

export async function getBaseline(port: number, user_id: string, refresh = false) {
  const res = await axios.get(url(port, `/baseline/${encodeURIComponent(user_id)}`), {
    params: { refresh: refresh ? 1 : 0 },
  });
  return res.data;
}

export async function runWeeklyReport(port: number, payload: WeeklyReportRequest) {
  const res = await axios.post(url(port, "/weekly-report/run"), payload, {
    headers: { "Content-Type": "application/json" },
  });
  return res.data;
}
