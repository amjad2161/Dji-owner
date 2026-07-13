# SkyCore Architecture

SkyCore is the unified runtime for everything in the toolkit. It sits between hardware (drones, simulators) and applications (CLI, web dashboard, custom Python scripts), giving every layer a single coherent API.

```
┌─────────────────────────────────────────────────────┐
│  Applications: web dashboard │ CLI │ user Python scripts                  │
├─────────────────────────────────────────────────────┤
│  Capability layer: missions │ vision │ video │ analytics                 │
├─────────────────────────────────────────────────────┤
│  Core layer: Drone interface │ Telemetry │ SafeDrone │ EventBus           │
├─────────────────────────────────────────────────────┤
│  Adapters: SimulatorDrone | TelloDrone | MavlinkDrone | DjiBridgeDrone   │
└─────────────────────────────────────────────────────┘
          │             │             │                 │
     in-process     djitellopy   MAVSDK (PX4/      DJI Bridge App
     simulation                  ArduPilot)        (Android)
```

## Layers

### Adapters (`skycore/adapters/`)

Every drone backend implements the same `Drone` ABC. This is the only place hardware-specific code lives. Today: simulator, Tello, MAVLink, DJI bridge. Adding a new backend (e.g. Skydio, Yuneec) means writing one file.

### Core (`skycore/core/`)

- **`Drone`** — abstract async interface (connect, takeoff, goto, set_velocity, etc.)
- **`Telemetry`, `GeoPoint`, `MissionStep`** — the canonical types every layer speaks.
- **`SafeDrone`** — wrapper enforcing geofence + battery RTH + GPS minimum.
- **`EventBus`** — in-process pub/sub used to fan out telemetry.

### Capabilities (`skycore/missions`, `vision`, `video`, `analytics`)

Backend-agnostic features:

- **Missions** — waypoint executor, generators (orbit, lawnmower), Litchi CSV round-trip.
- **Vision** — YOLO detector, BoT-SORT tracker, visual-follow controller.
- **Video** — H.264/H.265 recorder, RTMP streamer, Gyroflow CLI wrapper.
- **Analytics** — flight-log CSV analyzer with structured `FlightSummary`.

### Applications (`skycore/api`, `skycore/cli.py`)

- **REST + WebSocket API** (FastAPI). HTTP for commands, WebSocket for telemetry.
- **Web dashboard** — single HTML page, no build step, uses the WebSocket directly.
- **CLI** (Click) — `skycore serve`, `skycore mission orbit/survey/run`, `skycore analyze`.

## Async-first

Everything is `async`. The simulator runs a physics loop on the event loop; adapters use the underlying SDK's async hooks (MAVSDK is async-native, djitellopy is sync and runs in `executor`). This means a single Python process can handle: telemetry stream, mission execution, video recording, vision pipeline, and the web UI without threads.

## Why the simulator matters

The simulator is a real backend, not a mock. It implements the full `Drone` contract with simple kinematics. You can develop and test missions, vision pipelines, and the web stack on a laptop with no hardware — and the same code runs unchanged against a real Mavic via the bridge or a MAVLink craft via MAVSDK.

## Where SkyCore stops

SkyCore is **not** a flight controller. It does not run on the drone. It does not generate motor PWM. The actual stabilization, attitude control, and motor mixing happens on whatever flight stack the drone uses (DJI's closed firmware, PX4, ArduPilot). SkyCore commands these stacks at a high level: "take off," "go to point," "orbit POI," "follow that person."

## Extensibility

- **New backend** — implement `Drone` in `skycore/adapters/<name>.py`.
- **New mission pattern** — add a generator returning `WaypointMission` in `skycore/missions/`.
- **New analytic** — add a function in `skycore/analytics/` that returns a dataclass.
- **New API endpoint** — add a route in `skycore/api/app.py`.
