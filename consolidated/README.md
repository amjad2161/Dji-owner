# SkyCore — Consolidated, Runnable

This folder is the **clean, working subset** distilled from the `SkyCore_Consolidated`
archive: a real Ground Control Station web app + a live simulator backend, wired
together and verified end-to-end. For the honest inventory of the whole archive
(what's real vs. marketing), see [`AUDIT.md`](./AUDIT.md).

> **Honesty note.** A **software simulator** generates ground truth (battery drains,
> the aircraft climbs and flies to waypoints over real time). Noisy GPS measurements
> of that truth are filtered by the **real skycore 22-state Adaptive UKF**
> (`src/skycore_v1.0.0/skycore/navigation/aukf.py`) — so the telemetry the GCS shows
> is the genuine navigation filter's estimate, and every frame reports
> `nav_backend: "skycore.navigation.aukf.AdaptiveUKF (22-state)"` and its live `nav_nis`.
> No physical drone is connected, every frame is tagged `source: "simulator"`, and
> nothing here claims otherwise. To fly real hardware, point the GCS at a backend that
> speaks the same `/ws/telemetry` contract.

## Legal boundary

Legitimate drone software only: mission/telemetry, computer-vision tracking, and
**detection/alerting** of unauthorized drones. This project does **not** contain and
will **not** add firmware hacking, jamming, Remote-ID defeat, illegal RF/range
boosting, or kinetic/EW takedown. Operate within your local aviation authority's
rules (FAA / EASA / CAAI).

## What's here

```
consolidated/
├── AUDIT.md            # honest real-vs-claimed inventory of the whole archive
├── README.md           # this file
├── gcs-web/            # React 18 + Vite + TypeScript Ground Control Station
│   ├── index.html            # (added — was missing; app couldn't build without it)
│   ├── vite.config.ts        # (added)
│   ├── tsconfig.node.json    # (added)
│   └── src/                  # App, 7 pages, 3 services
└── backend/
    ├── serve.py        # live simulator: telemetry + command WebSocket on :8080
    └── requirements.txt
```

## Run it (two terminals)

### 1. Backend — live simulator on port 8080

```powershell
cd consolidated/backend
python -m venv venv
venv\Scripts\pip install -r requirements.txt
venv\Scripts\python serve.py
```

Check it: open <http://localhost:8080/telemetry> — you'll see live JSON that changes
over time once the GCS sends a `takeoff` command.

### 2. GCS web app — port 4173

```powershell
cd consolidated/gcs-web
npm install
npm run build
npm run preview        # http://localhost:4173   (or: npm run dev)
```

Log in with a demo account shown on the login screen (e.g. `admin` / `admin123`),
then use the Dashboard **Arm → Takeoff → Land / RTH** buttons. You'll see the status
flip to **🟢 מחובר (connected)**, altitude climb, and battery drain — all streamed
live from the backend.

### Optional — AI Chat page

The AI Chat page calls OpenRouter. It stays inert without a key. To enable it, create
`gcs-web/.env` with:

```
VITE_OPENROUTER_API_KEY=sk-or-...
```

(Do not commit real keys; a client-side key is exposed to the browser — for local use only.)

## Fixes applied during consolidation

- **Web app didn't build at all** — added the missing `index.html`, `vite.config.ts`,
  and `tsconfig.node.json` (Vite has no entry point without them).
- **`OpenRouterService` used `process.env`**, which is undefined in a Vite browser
  build — changed to `import.meta.env.VITE_OPENROUTER_API_KEY` and added `vite-env.d.ts`.
- **Backend telemetry was static and shape-incompatible** with the GCS — replaced with
  `serve.py`, which evolves state over real time and emits the exact shape the GCS's
  `TelemetryService` reads (`battery.percent`, `position.{lat,lon,altitude}`,
  `velocity.speed`, `attitude.yaw`, `mode`) and handles `arm/disarm/takeoff/land/rtl/goto`.
- **Wired the real 22-state AUKF into the live loop** — `serve.py` imports the genuine
  `skycore/navigation/aukf.py`, feeds it noisy GPS measurements in a local-ENU-metre frame
  (the filter integrates `pos += vel·dt`, so lat/lon degrees would blow it up), and streams
  the filter's estimate. Verified converging (~0.4 m tracking error) and stable in flight;
  falls back to raw truth and says so if the filter ever goes non-finite.

## Known gaps / honest limitations

- `gcs-web` had strict unused-import checks (`noUnusedLocals`/`noUnusedParameters`)
  temporarily relaxed to get a green build; there are unused imports to clean up.
- The map/video/threats pages render but are not yet fed by the backend — only the
  Dashboard/Telemetry pages consume the live WebSocket.
- The real **AUKF navigation** is now wired in (above). The rest of the genuine library —
  **control** (PID/MPC/LQR) and **C-UAS detection** at `../src/skycore_v1.0.0/skycore/` —
  is not yet driven by the live loop; wiring those in is the natural next step (see `AUDIT.md`).
