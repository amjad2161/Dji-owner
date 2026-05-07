# SkyCore Modules Reference

The full module map. Each is independently importable; install only the extras you need.

## Map

```
skycore/
├─ core/                     [required] types, Drone ABC, SafeDrone, EventBus
├─ adapters/                 [required] simulator + tello + mavlink + dji_msdk backends
├─ missions/                 [required] WaypointMission, orbit, lawnmower, Litchi I/O
├─ vision/                   [vision]   YOLO detector + BoT-SORT tracker + visual-follow
├─ video/                    [stdlib]   recorder + RTMP streamer + Gyroflow CLI wrap
├─ analytics/                [analytics] flight-log CSV summary
├─ geofence/                 [geofence] polygon geofence + KML / GeoJSON loaders
├─ weather/                  [stdlib]   Open-Meteo current weather + preflight check
├─ terrain/                  [stdlib]   Open-Elevation lookup + clearance check
├─ planning/                 [planning] A* router around obstacle polygons
├─ scheduler/                [scheduler] sun-position + scheduled async missions
├─ fleet/                    [stdlib]   multi-drone fleet, formations
├─ notifications/            [notifications] Discord/Slack/Telegram webhooks
├─ storage/                  [stdlib]   SQLite flight history
├─ replay/                   [stdlib]   replay CSV log onto an EventBus
├─ photogrammetry/           [stdlib + Docker] OpenDroneMap wrapper
├─ api/                      [api]      FastAPI app + dashboard
└─ cli.py                    [required] click commands
```

## Install

```bash
pip install -e ".[api,analytics,geofence,planning,scheduler,notifications,vision,tracking,tello,mavlink]"
# or
pip install -e ".[all]"
```

## Module quick reference

### `skycore.geofence`

```python
from skycore.geofence import PolygonGeofence, load_kml, load_geojson
from skycore import GeoPoint

# From file (Google Earth KML or QGIS GeoJSON):
fence = load_kml("airport-restricted.kml")
assert fence.contains(GeoPoint(37.62, -122.37)) is False  # outside

# Inverted: drone must stay outside the polygon
no_fly = load_geojson("no-fly.geojson")
no_fly.inverted = True
```

### `skycore.weather`

```python
from skycore.weather import preflight_check

ok, issues, snap = preflight_check(lat=37.7749, lon=-122.4194, max_wind_kph=36)
if not ok:
    print("Do not fly:", issues)
```

Uses Open-Meteo — free, no API key needed. Wind, gust, precipitation, temperature.

### `skycore.terrain`

```python
from skycore.terrain import get_elevation, terrain_clearance

elev_amsl = get_elevation(lat=37.7749, lon=-122.4194)

ok, issues = terrain_clearance(
    [(37.77, -122.42, 100), (37.78, -122.41, 80)],   # lat, lon, alt AMSL
    min_clearance_m=30,
)
```

### `skycore.planning`

```python
from skycore.planning import plan_around_obstacles
from skycore import GeoPoint

restricted = [(37.770, -122.420), (37.770, -122.419), (37.771, -122.419), (37.771, -122.420)]
path = plan_around_obstacles(
    start=GeoPoint(37.769, -122.421),
    end=GeoPoint(37.772, -122.418),
    obstacles=[restricted],
    grid_resolution_m=20,
    altitude_m=40,
)
```

A* on a lat/lon grid avoiding shapely-bufferred polygons.

### `skycore.scheduler`

```python
from datetime import datetime, timezone, timedelta
from skycore.scheduler import Scheduler, ScheduledMission, golden_hour_at

sunrise, m_end, e_start, sunset = golden_hour_at(37.77, -122.42)

async def my_mission(): ...

sched = Scheduler()
sched.add(ScheduledMission("golden hour orbit", e_start, my_mission))
await sched.start()
```

### `skycore.fleet`

```python
from skycore.fleet import Fleet, v_formation

drones = [SimulatorDrone(home=h) for _ in range(5)]
fleet = Fleet(drones)
await fleet.connect_all()
await fleet.takeoff_all(altitude_m=20)
await fleet.execute_in_formation(orbit_mission(...), v_formation(5, spacing_m=8))
```

### `skycore.notifications`

```python
from skycore.notifications import NotificationDispatcher

notify = NotificationDispatcher(
    discord_webhook="https://discord.com/api/webhooks/...",
    slack_webhook="https://hooks.slack.com/...",
)
await notify.send("Mission complete", "Orbit at 60 m radius finished.")
```

### `skycore.storage`

```python
from skycore.storage import FlightDatabase

with FlightDatabase("flights.db") as db:
    fid = db.start_flight("mavic-3", 37.77, -122.42)
    db.record_telemetry(fid, telemetry_dict)
    db.end_flight(fid, summary={"max_alt": 100, "duration_min": 12})
```

### `skycore.replay`

```python
from skycore.replay import replay_csv
from skycore.core.event_bus import EventBus

bus = EventBus()
await replay_csv("airdata-export.csv", bus, speedup=10.0)
```

Replays a CSV onto the bus. Hook the dashboard to that bus and you get a virtual flight playback.

### `skycore.photogrammetry`

```python
from skycore.photogrammetry import run_odm_docker

result = run_odm_docker("./photos", orthophoto_resolution=5, dsm=True)
print("Orthophoto:", result.orthophoto)
print("DSM:", result.dsm)
```

Requires Docker; pulls the `opendronemap/odm` image (~5 GB) on first run.

## CLI commands

| Command | What it does |
|---------|--------------|
| `skycore serve` | Web dashboard + REST + WebSocket |
| `skycore analyze <csv>` | Flight log health summary |
| `skycore weather --lat .. --lon ..` | Pre-flight weather check |
| `skycore elevation --lat .. --lon ..` | Terrain elevation lookup |
| `skycore golden-hour --lat .. --lon ..` | Today's golden-hour windows |
| `skycore mission orbit/survey/run` | Mission generators + executor |
| `skycore flights list` | History from local SQLite |

## Why this architecture

Every new feature is a separate module that depends only on `skycore.core`. That keeps adapters lean (Tello adapter doesn't pull in shapely, scheduler doesn't pull in YOLO). When you `pip install skycore[geofence]`, you get only `shapely`. When you want everything: `pip install skycore[all]`.
