# SkyCore Extended Capabilities

The modules added beyond core flight + missions + vision. Each is independently importable and ships with its own optional-dependency extra.

## Pre-flight checklist (`skycore.checklist`)

Orchestrates connectivity, telemetry, battery, GPS, and weather checks into a single report.

```python
from skycore.checklist import PreflightChecklist

cl = PreflightChecklist(drone=drone, home=GeoPoint(37.77, -122.42))
report = await cl.run()
print(report.render())
print("Safe?", report.ok)
```

Wired to `POST /api/preflight/checklist` and rendered live in the dashboard.

## Mission template library (`skycore.templates`)

Ready-made mission generators for common shots:

| Function | What it does |
|----------|--------------|
| `panorama_mission` | Stationary multi-row panorama — yaw × gimbal-pitch grid |
| `perimeter_patrol` | Traverse a polygon perimeter with corner heading |
| `building_inspection` | Stacked orbits at multiple altitudes |
| `hyperlapse_line` | Evenly-spaced photo waypoints along a line |
| `vertical_panorama` | Single point, gimbal sweep |
| `spiraling_orbit` | Climbing helix (cinematic structure reveal) |
| `facade_scan` | Lawnmower along a building facade at multiple altitudes |
| `cinematic_reveal` | Two-waypoint dolly-up reveal shot |

Generate from the API: `POST /api/missions/template` with `{kind, params}`.

## Battery registry (`skycore.battery`)

SQLite-backed cycle and health tracker. Logs each flight against a battery serial; estimates health from cycles + heavy-discharge events.

```python
with BatteryRegistry("batteries.db") as reg:
    reg.register(BatteryRecord(serial="BAT-A1", nominal_capacity_mah=5000))
    cid = reg.start_cycle("BAT-A1", start_percent=98)
    # ... flight ...
    reg.end_cycle(cid, end_percent=22, min_voltage=14.7)
    health = reg.get_health("BAT-A1")
```

## Drone profiles (`skycore.profiles`)

Known specs for 12 current Mavic models (Mavic 3 family, Air, Mini, Mavic 2, Tello). Used to set safe defaults.

```python
p = get_profile("Mavic 3 Pro")
assert p.max_wind_resistance_kph == 12 * 3.6
```

Exposed via `GET /api/profiles`.

## Lifecycle events (`skycore.events`)

Typed async pub/sub for drone lifecycle. 18 event types: connection, takeoff, landing, goto, RTH, battery, geofence, mission, photo/record.

```python
from skycore.events import EventEmitter, TakeoffComplete, BatteryWarning

emitter = EventEmitter()
emitter.on(BatteryWarning, lambda ev: notify.send("Low battery", f"{ev.percent}%"))
```

Useful for wiring notifications, persistence, dashboards.

## Airspace (`skycore.airspace`)

Loads OpenAIP GeoJSON exports and answers "what airspace is at this point?"

```python
from skycore.airspace import load_openaip_geojson

db = load_openaip_geojson("openaip-airspace-il.geojson")
features = db.query(GeoPoint(31.97, 34.79, 100))
for f in features:
    print(f.cls, f.name, f"{f.floor_m_amsl}-{f.ceiling_m_amsl}m")

critical, hits = db.is_critical_at(GeoPoint(31.97, 34.79, 100))
```

## MQTT bridge (`skycore.mqtt`)

Fan out telemetry to any MQTT broker (Mosquitto, EMQX, HiveMQ, AWS IoT). Useful for Home Assistant, Node-RED, Grafana, or fleet management dashboards.

```python
bridge = MqttBridge(drone_name="mavic-3", broker_host="localhost")
await bridge.connect()
asyncio.create_task(bridge.fanout_telemetry(drone))
```

Topics: `skycore/<drone>/telemetry`, `.../events`, `.../cmd`.

## Cloud sync (`skycore.cloud`)

S3-compatible upload (AWS, MinIO, Backblaze B2, Cloudflare R2). Run after flights to back up footage and logs.

```python
s3 = S3Sync(bucket="my-flights", endpoint_url="https://s3.minio.local")
key = await s3.upload_file("./flight.mp4", key="2026-05-08/flight.mp4")
url = await s3.presigned_url("2026-05-08/flight.mp4", expires_s=86400)
```

## Foxglove WebSocket bridge (`skycore.foxglove`)

Expose live telemetry to [Foxglove Studio](https://foxglove.dev) for advanced 3D visualization, time-series, and replay.

```python
fg = FoxgloveServer(port=8765)
await fg.start()
asyncio.create_task(fg.fanout_bus(bus, topic="telemetry"))
# In Foxglove Studio: New connection → Foxglove WebSocket → ws://localhost:8765
```

## Dashboard (Leaflet map view)

The `/` route now serves a full dashboard with:

- Live OpenStreetMap tiles (dark-themed)
- Real-time drone marker + trail polyline
- Click map to set goto target
- Home marker (auto-placed from telemetry)
- Telemetry panel: altitude / battery / yaw / mode / GPS / voltage
- Flight controls: takeoff / land / RTH / photo / record
- Pre-flight checklist runner with status per item

No build step — vanilla HTML + CDN-loaded Leaflet.

## Optional extras matrix

| Extra | What it pulls | Modules enabled |
|-------|---------------|-----------------|
| `[geofence]` | shapely | polygon geofencing |
| `[airspace]` | shapely | airspace classification |
| `[planning]` | shapely | A* obstacle planner |
| `[scheduler]` | astral | sun-aware scheduler |
| `[notifications]` | aiohttp | Discord/Slack/Telegram |
| `[mqtt]` | paho-mqtt | MQTT bridge |
| `[cloud]` | boto3 | S3 upload |
| `[foxglove]` | websockets | Foxglove WS bridge |
| `[vision]` | ultralytics, opencv-python | YOLO detector |
| `[tracking]` | boxmot | BoT-SORT tracker |
| `[tello]` | djitellopy, opencv-python | Tello adapter |
| `[mavlink]` | mavsdk | MAVLink adapter |
| `[all]` | everything above | full stack |
