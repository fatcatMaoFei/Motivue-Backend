# Motivue Desktop Suite (Offline-first)

This folder holds a self-contained desktop setup for running Motivue readiness, baseline, training, and weekly report workflows entirely on your machine (SQLite, no external services required). Services run via Docker Compose; the UI is a Tauri + React shell that talks to the local APIs.

## What you get
- FastAPI services: readiness, baseline, weekly-report, physio-age (all offline; weekly report can run without LLM).
- Local storage: SQLite file mounted at `./data/local.db`.
- Desktop UI: Tauri + React (dark theme, Today/Baseline/Train/Report/Settings pages).
- Optional LLM: leave `GOOGLE_API_KEY` empty for offline heuristic reports; fill it to enable LLM.

## Prerequisites
- Docker Desktop (Windows/macOS) or any recent Docker engine.
- Node 18+ and Rust toolchain (for Tauri dev/build). If you only use the browser dev server, Rust is not needed until you package the desktop app.

## Quick start (offline)
```bash
cd desktop-suite
cp .env.example .env          # keep GOOGLE_API_KEY empty for offline
docker compose up -d          # start all backend services with SQLite
cd frontend
npm install                   # or pnpm/yarn
npm run dev                   # open http://localhost:5173 to use the UI
```

To build the desktop app with Tauri:
```bash
cd desktop-suite/frontend
npm run tauri:dev             # dev with Tauri window (needs Rust toolchain)
npm run tauri:build           # create desktop bundles
```

## Services and ports (default)
- readiness-api: http://127.0.0.1:8000
- baseline-api:  http://127.0.0.1:8001
- physio-age:    http://127.0.0.1:8002
- weekly-report: http://127.0.0.1:8003 (LLM optional)

All share the same SQLite at `./data/local.db` (mounted inside containers at `/data/local.db`).

## Environment
- `.env` (copy from `.env.example`) sets `DATABASE_URL`, optional `GOOGLE_API_KEY`, and service URLs.
- Offline mode: keep `GOOGLE_API_KEY` empty; weekly-report will use heuristic fallback.
- You can change host ports in `docker-compose.yml` if they conflict.

## Frontend pages (planned skeleton)
- Today: sliders for Hooper/sleep, journal toggles, optional training AU/RPE, CTA “Calculate Readiness”.
- Baseline: view/update baselines, trigger recalculation, show physio-age card.
- Train/Strength: log sessions and strength records, show latest and 30d baseline.
- Report: generate weekly report (LLM on/off), preview Markdown/HTML, download.
- Settings: data path, API host/ports, GOOGLE_API_KEY, language/theme, import/export JSON/CSV.

## Notes
- Everything stays local; no cloud storage. You can import/export JSON/CSV from the Settings page.
- If Docker is unavailable, you can run the FastAPI apps directly with `uvicorn` using `DATABASE_URL=sqlite:///./local.db`, but the Compose path above is the recommended path.
