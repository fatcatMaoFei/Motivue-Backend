import { create } from "zustand";

type SettingsState = {
  apiHost: string;
  readinessPort: number;
  baselinePort: number;
  weeklyReportPort: number;
  physioPort: number;
  googleApiKey?: string;
  useLlm: boolean;
  set: (partial: Partial<SettingsState>) => void;
};

export const useSettings = create<SettingsState>((set) => ({
  apiHost: "http://127.0.0.1",
  readinessPort: 8000,
  baselinePort: 8001,
  weeklyReportPort: 8003,
  physioPort: 8002,
  googleApiKey: undefined,
  useLlm: false,
  set: (partial) => set(partial),
}));
