# Drone Mastery Hub — DJI Pilot Toolkit

> A community-driven, fully legal toolkit for getting the most out of your DJI Mavic drone — without modifying firmware, bypassing safety systems, or breaking aviation regulations. Includes **SkyCore**, a unified Python platform that ties every open-source drone tool into one coherent runtime.

**[עברית](README.he.md)** · English

---

## What this is

A curated, beginner-friendly playbook for DJI Mavic owners who want to push their drone to its full potential **using only official SDKs, supported tools, and legal community software**. No firmware patching. No No-Fly-Zone removal. No transmit-power boosting. Everything you can legitimately do — explained well, with real working tools shipped in this repo.

## Two ways to use this repo

### 1. Pilots — install GUI tools, follow the tutorials

If you just want a better workflow with your drone, run the Windows installer and follow the [Getting Started guide](docs/en/getting-started.md). Six capability tracks cover everything from PC flight to cinematic video to log analysis.

### 2. Builders — use SkyCore, the unified Python runtime

`skycore/` is a complete drone-operations platform that exposes a single async API across DJI, MAVLink (PX4 / ArduPilot), Tello, and a built-in simulator. Develop missions, vision pipelines, and dashboards without hardware; deploy the same code against any backend.

## SkyCore at a glance

```python
import asyncio
from skycore import SimulatorDrone, GeoPoint
from skycore.missions import orbit_mission

async def main():
    poi = GeoPoint(37.7749, -122.4194)
    drone = SimulatorDrone(home=poi)
    mission = orbit_mission(poi, radius_m=60, altitude_m=40, waypoints=12)
    async with drone:
        await mission.execute(drone)

asyncio.run(main())
```

The same mission runs against a real Tello (`TelloDrone()`), a PX4/ArduPilot via MAVSDK (`MavlinkDrone()`), or a real DJI Mavic through the Android bridge app (`DjiBridgeDrone()`).

### What SkyCore includes

| Layer | What it does |
|-------|--------------|
| **Adapters** | Simulator, Tello, MAVLink (PX4/ArduPilot), DJI bridge |
| **Core** | `Drone` ABC, `Telemetry`, `SafeDrone` (geofence + RTH + battery), `EventBus` |
| **Missions** | Waypoint executor, orbit / lawnmower-survey generators, Litchi CSV import/export |
| **Vision** | YOLO detector + BoT-SORT tracker + visual-follow controller (works on any backend) |
| **Video** | H.264/H.265 recorder, RTMP streamer, Gyroflow CLI wrapper |
| **Analytics** | CSV flight-log analyzer with structured `FlightSummary` |
| **API** | FastAPI REST + WebSocket telemetry + dark dashboard |
| **CLI** | `skycore serve / mission / analyze` (Click-based) |
| **Deploy** | `docker compose up` — simulator backend running at :8080 |

See [SkyCore architecture](docs/en/skycore-architecture.md) and [SkyCore quick start](docs/en/skycore-getting-started.md).

## Six capability tracks

| # | Track | What you achieve |
|---|-------|------------------|
| 1 | [PC Flight Control](docs/en/01-pc-flight-control.md) | Fly without your phone — laptop + RC + joystick |
| 2 | [Smart Tracking](docs/en/02-smart-tracking.md) | Object tracking beyond default ActiveTrack |
| 3 | [Cinematic Video](docs/en/03-cinematic-video.md) | Hollywood-style post pipeline: D-Log → Gyroflow → Resolve |
| 4 | [Mission Planning](docs/en/04-mission-planning.md) | 3D waypoints, repeatable shots, automated mapping |
| 5 | [Log Analysis](docs/en/05-log-analysis.md) | Find issues before they become crashes |
| 6 | [Live Streaming](docs/en/06-streaming.md) | Push your flight to YouTube / Twitch / Facebook live |

## Repository structure

```
dji-owner/
├─ skycore/                      ← unified Python runtime
│  ├─ core/                       Drone interface, Telemetry, SafeDrone, EventBus
│  ├─ adapters/                   simulator | tello | mavlink | dji_msdk
│  ├─ missions/                   waypoint executor + generators + Litchi I/O
│  ├─ vision/                     detector + tracker + visual-follow
│  ├─ video/                      recorder + RTMP streamer + Gyroflow
│  ├─ analytics/                  flight-log analyzer
│  ├─ api/                        FastAPI app + dark HTML dashboard
│  └─ cli.py                      `skycore` command
├─ docs/                         Bilingual documentation (en + he)
│  ├─ en/                         English guides + reference
│  └─ he/                         Hebrew translations
├─ scripts/windows/              install-toolkit.ps1, clone-dev-repos.ps1
├─ tools/log-analyzer/           Standalone Python CLI (also wrapped by SkyCore)
├─ presets/litchi-missions/      Ready-to-use Litchi waypoint CSVs
├─ tests/                        pytest suite for SkyCore
├─ Dockerfile + docker-compose.yml
└─ pyproject.toml                Modern Python packaging
```

## Quick start

### Pilots (Windows GUI tools)

```powershell
iwr https://raw.githubusercontent.com/amjad2161/dji-owner/main/scripts/windows/install-toolkit.ps1 -UseBasicParsing | iex
```

### Builders (SkyCore)

```bash
git clone https://github.com/amjad2161/dji-owner.git
cd dji-owner
pip install -e ".[api,analytics]"
skycore serve --backend simulator     # → http://localhost:8080
```

or in Docker:

```bash
docker compose up
```

### Clone every major drone SDK at once

```powershell
iwr https://raw.githubusercontent.com/amjad2161/dji-owner/main/scripts/windows/clone-dev-repos.ps1 -UseBasicParsing | iex
```

Pulls DJI MSDK / OSDK / PSDK / Tello-Python, PX4, ArduPilot, MAVSDK, QGroundControl, Gyroflow, YOLO, BoxMOT, OpenDroneMap, and DJITelloPy into `~/dji-dev/`.

## The open-source ecosystem

The drone ecosystem on GitHub is large. We track legal, well-maintained, currently-relevant projects in the [Awesome Drone Repos catalog](docs/en/awesome-drone-repos.md). SkyCore wraps the most useful ones into a single API.

## Compatibility

Not every drone supports every workflow. Check the [full compatibility matrix](docs/en/compatibility-matrix.md) before you commit.

| Family | PC Flight | Litchi | ActiveTrack | Mobile SDK | SkyCore via |
|--------|-----------|--------|-------------|------------|-------------|
| Mavic 3 / 3 Pro / 3 Cine | Partial | ❌ | 5.0 | V5 | DJI bridge |
| Mavic 3 Enterprise | Yes | ❌ | 5.0 | V5 | PSDK |
| Mavic Air 3 / 2S / 2 | Limited | Air 2 only | 4.0 / 5.0 | V5 / V4 | DJI bridge |
| Mini 4 Pro / 3 Pro | Limited | ❌ | 360° / 4.0 | V5 | DJI bridge |
| Mini 2 / Mini SE | Basic | ❌ | ❌ | ❌ | (none) |
| Mavic 2 Pro / Zoom | Yes | ✅ | 2.0 | V4 | DJI bridge (legacy) |
| Mavic Pro / Air 1 | Yes | ✅ | 1.0 | V4 (legacy) | (limited) |
| Tello / Tello EDU | Native | ❌ | n/a | Tello SDK | TelloDrone |
| Any PX4 / ArduPilot | Yes | ❌ | n/a | n/a | MavlinkDrone |

## Legal and safety

This project operates **inside** manufacturer SDKs and national aviation rules. We do **not** publish:

- Firmware patches that disable geofencing (No-Fly Zones)
- Tools that exceed legal transmit power (FCC / CE / MIC / SRRC limits)
- Methods to bypass Remote ID
- Altitude or speed limit removal beyond what DJI exposes officially

You are responsible for following your local civil aviation authority's rules. See [legal-and-safety](docs/en/legal-and-safety.md) for per-country detail.

## Project status

🚧 Alpha. Core SkyCore (simulator + missions + analytics + API) is tested and works. Real-hardware adapters (Tello, MAVLink, DJI bridge) are implemented and follow the same contract; the Tello and MAVLink paths use third-party libraries already proven on the relevant hardware. The DJI bridge requires a small Android companion app (separate project; protocol documented in `skycore/adapters/dji_msdk.py`).

Contributions welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT — see [LICENSE](LICENSE).
