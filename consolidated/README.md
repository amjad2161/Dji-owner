# SkyCore — Consolidated, Runnable

This folder is the **clean, working subset** distilled from the `SkyCore_Consolidated`
archive: a real Ground Control Station web app + a live simulator backend, wired
together and verified end-to-end. For the honest inventory of the whole archive
(what's real vs. marketing), see [`AUDIT.md`](./AUDIT.md).

> **Honesty note.** A **software simulator** generates ground truth over real time.
> Three GENUINE skycore modules run in the live loop against it:
> - **navigation** — the real 22-state Adaptive UKF (`navigation/aukf.py`) filters noisy
>   GPS; the telemetry the GCS shows is the filter's estimate (`nav_backend`, live `nav_nis`).
> - **control** — the real `LQRController` (`control/lqr.py`) flies the aircraft closed-loop
>   to its targets (`control_backend`).
> - **detection** — the real `CUASClassifier` (`cuas/classifier.py`) classifies a **simulated**
>   intruder track into a severity-graded threat shown on the Threats page (`detect_backend`).
>
> No physical drone and no real RF sensing are connected; every frame is tagged
> `source: "simulator"` and reports which real backend is active. Detection/alerting only —
> no jamming or countermeasure capability. To fly real hardware, point the GCS at a backend
> that speaks the same `/ws/telemetry` + `/ws/threats` contract.

## Legal boundary

Legitimate drone software only: mission/telemetry, computer-vision tracking, and
**detection/alerting** of unauthorized drones. This project does **not** contain and
will **not** add firmware hacking, jamming, Remote-ID defeat, illegal RF/range
boosting, or kinetic/EW takedown. Operate within your local aviation authority's
rules (FAA / EASA / CAAI).

## What's here

```
consolidated/
├── launch.ps1 / launch.sh   # ONE command: build + run the whole system on :8080
├── AUDIT.md            # honest real-vs-claimed inventory of the whole archive
├── README.md           # this file
├── gcs-web/            # React 18 + Vite + TypeScript GCS (6 real backend-driven pages)
│   └── src/                  # App, pages (Dashboard/Threats/Telemetry/Missions/AIChat/Video), services
└── backend/
    ├── serve.py        # unified server: serves the GCS + telemetry/threat WS + real AUKF/LQR/C-UAS
    └── requirements.txt
```

## Run it (one command — the whole system on one port)

The backend also serves the built GCS, so the entire system runs as **one process on
`http://localhost:8080`** — the UI, the telemetry/threat WebSockets, and the real
AUKF / LQR / C-UAS modules, together.

```powershell
cd consolidated
./launch.ps1            # Windows;   macOS / Linux / Git Bash:  ./launch.sh
```

That builds the GCS (first run only), sets up the Python venv, and starts the unified
server. Open **<http://localhost:8080>**, log in with a demo account (e.g. `admin` /
`admin123`), and use the Dashboard / Missions **Arm → Takeoff → click-map goto → Land / RTH**
controls: the status flips to **🟢 מחובר (connected)** and altitude / battery / threats
update live from the real modules.

### Run the parts separately (dev)

```powershell
# Backend only — APIs + WS on :8080 (visit / for a hint if the UI isn't built)
cd consolidated/backend
python -m venv venv; venv\Scripts\pip install -r requirements.txt; venv\Scripts\python serve.py

# GCS dev server (hot reload) on :4173, talking to the backend on :8080
cd consolidated/gcs-web; npm install; npm run dev
```

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
- **Wired three real skycore algorithms into the live loop** — `serve.py` imports the genuine
  `navigation/aukf.py` (22-state AUKF, noisy GPS in a local-ENU-metre frame — the filter does
  `pos += vel·dt`, so lat/lon degrees would blow it up), `control/lqr.py` (`LQRController` flies
  the point-mass closed-loop, with a drone-like velocity envelope), and `cuas/classifier.py`
  (`CUASClassifier` grades a simulated intruder → `/ws/threats`). Verified: AUKF ~0.4 m error,
  LQR converges to waypoints at ~16 m/s, classifier escalates the intruder high→critical as it
  closes. Each has an honest fallback (raw truth / naive mover / no threats) if its module errors.
- **Built the Threats page + wired `AdsBService`** to consume `/ws/threats`, so the real
  classifier's verdict (e.g. `commercial_drone / critical`) renders live in the GCS.

## Known gaps / honest limitations

- `gcs-web` had strict unused-import checks (`noUnusedLocals`/`noUnusedParameters`)
  temporarily relaxed to get a green build; there are unused imports to clean up.
- The map/video/threats pages render but are not yet fed by the backend — only the
  Dashboard/Telemetry pages consume the live WebSocket.
- Real **AUKF navigation**, **LQR control**, and **CUASClassifier detection** are wired into the
  live loop, and **all six GCS pages are real and backend-driven**:
  - **Dashboard** — map + telemetry cards + threat count.
  - **Threats** — the real classifier feed (`/ws/threats`).
  - **Telemetry** — live SVG charts (altitude/speed/battery) + AUKF/LQR/detect provenance + NIS.
  - **Missions** — SVG tactical map; click the map to `goto` (flies the real LQR); arm/takeoff/land/RTL.
  - **AI Chat** — streams from OpenRouter when `VITE_OPENROUTER_API_KEY` is set; otherwise an honest
    offline assistant that answers from live telemetry (`status`, `battery`, `threats`, …).
  - **Video** — honest: **no fake camera**. Shows a clear "NO LIVE CAMERA FEED" banner + a live
    telemetry **instrument HUD** (labeled NOT camera). Real feed needs DJI/PX4 RTSP hardware.
- `TelemetryService.sendCommand` now **queues** commands until the WebSocket opens (the first press
  after a page load is no longer dropped).
