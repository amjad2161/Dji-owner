# SkyCore Quick Start

Go from "git clone" to a working flight (in simulation) in three commands.

## Install

```bash
git clone https://github.com/amjad2161/dji-owner.git
cd dji-owner
python -m venv .venv
source .venv/bin/activate            # Linux / macOS
.venv\Scripts\Activate.ps1           # Windows PowerShell
pip install -e ".[api,analytics]"
```

For real hardware, add the relevant extras: `[tello]`, `[mavlink]`, `[vision]`, `[tracking]`, or `[all]`.

## Run the dashboard

```bash
skycore serve --backend simulator
```

Open http://127.0.0.1:8080. You'll see live telemetry from the simulator, plus buttons for takeoff / goto / land / photo / record. Click "Takeoff" and watch the altitude metric climb.

## Fly a mission from the CLI

Generate an orbit mission:

```bash
skycore mission orbit --center 37.7749,-122.4194 --radius 60 --altitude 40 --out orbit.csv
```

Execute it (against the simulator by default):

```bash
skycore mission run orbit.csv
```

Watch logs as it takes off, flies all 12 waypoints, captures photos, and returns home.

To run against a real drone:

```bash
# Tello (default Wi-Fi)
skycore mission run orbit.csv --backend tello

# PX4 / ArduPilot at SITL
skycore mission run orbit.csv --backend mavlink --connection-url udp://:14540

# DJI Mavic via the Android bridge app
skycore mission run orbit.csv --backend dji-bridge --connection-url ws://192.168.1.100:8765
```

## Photogrammetry survey

```bash
skycore mission survey \
  --sw 37.7700,-122.4200 \
  --ne 37.7710,-122.4180 \
  --altitude 60 \
  --out survey.csv
skycore mission run survey.csv
```

Process the photos with [OpenDroneMap](https://www.opendronemap.org).

## Analyze a flight log

```bash
skycore analyze /path/to/airdata-export.csv
```

Get a one-page summary of duration, altitude, battery, GPS, and motor health.

## Use SkyCore as a Python library

```python
import asyncio
from skycore import SimulatorDrone, GeoPoint
from skycore.missions import orbit_mission

async def main():
    poi = GeoPoint(37.7749, -122.4194)
    drone = SimulatorDrone(home=poi)
    mission = orbit_mission(poi, radius_m=80, altitude_m=50, waypoints=16)
    async with drone:
        await mission.execute(drone)

asyncio.run(main())
```

## Vision: visual follow

```python
import asyncio
import cv2
from skycore import SimulatorDrone, GeoPoint
from skycore.vision import ObjectDetector, ObjectTracker, VisualFollowController

async def main():
    drone = SimulatorDrone(home=GeoPoint(0, 0))
    detector = ObjectDetector(weights="yolov8n.pt", classes=[0])  # person
    tracker = ObjectTracker("botsort")
    follower = VisualFollowController(drone, detector, tracker)

    async with drone:
        await drone.takeoff(10)
        cap = cv2.VideoCapture(0)  # webcam stand-in for video stream
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            await follower.step(frame, frame.shape[1], frame.shape[0])

asyncio.run(main())
```

## Docker

```bash
docker compose up
```

Dashboard at http://localhost:8080 with the simulator backend.

## Tests

```bash
pip install -e ".[dev]"
pytest
```

The simulator-based tests run in seconds; they verify takeoff, goto distance, mission generation, Litchi round-trip, and the analytics pipeline.

## Where to go next

- [SkyCore architecture](skycore-architecture.md) — how the layers fit together.
- [Six capability tracks](getting-started.md) — the higher-level tutorials.
- [Awesome drone repos](awesome-drone-repos.md) — the open-source projects SkyCore stitches together.
