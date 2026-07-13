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
  live loop, and **four GCS pages are real and backend-driven**: Dashboard, Threats (classifier
  feed), Telemetry (live AUKF charts + backend provenance), and Missions (click-map → `goto` flies
  the LQR). Remaining stubs: **Video** (the backend has no real camera feed — deliberately not faked)
  and **AI Chat** (needs a `VITE_OPENROUTER_API_KEY`).
- Minor papercut: `TelemetryService.sendCommand` silently drops a command if the WebSocket hasn't
  finished opening — the very first button press right after a page load can no-op; press again.
