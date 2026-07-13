# Track 4 — Mission Planning

Repeatable, programmable flights. Mapping, inspections, panoramas, time-lapses across days.

## Tools by drone

| Drone family | Best tool |
|--------------|-----------|
| Mavic 3 family | DJI Fly (native waypoints) + DJI Pilot 2 for Enterprise |
| Air 3 | DJI Fly (native waypoints, FW 2024+) |
| Mini 4 Pro | DJI Fly (native waypoints) |
| Air 2S / Mavic Air 2 | Litchi or DJI Fly (limited) |
| Mini 3 Pro / Mini 3 | DJI Fly (limited) |
| Mavic 2 Pro / Zoom | Litchi (best) or DJI GO 4 |
| Mavic Pro / Air 1 | Litchi |

## Tool 1 — DJI Fly native waypoints

Introduced for Mavic 3 in late 2023, then ported to other recent drones.

**What you can do:**
- Up to 99 waypoints per mission.
- Per-waypoint altitude, gimbal pitch, heading.
- Per-waypoint actions: take photo, start/stop recording, hover.
- Save and re-fly from the drone's storage.

**Limitations:**
- No PC editor. Plan only on the RC / phone.
- No KML / CSV import or export.
- No mid-flight resume on most models.

## Tool 2 — Litchi Mission Hub (PC browser)

The gold standard for older DJI drones.

**Workflow:**
1. Open [flylitchi.com/hub](https://flylitchi.com/hub) in any desktop browser.
2. Plan a mission on a 2D / satellite map. Drop waypoints, set per-point altitude, heading, gimbal pitch, speed, photo intervals.
3. **POI (Point of Interest):** lock the camera on a target while flying past it.
4. **Curved paths:** waypoints with curve radius give you smooth orbits.
5. **Save**, then in the Litchi mobile app pull the mission down via your account.
6. Fly.

**Import / export formats:**
- CSV (see [`presets/litchi-missions/`](../../presets/litchi-missions/) for templates)
- KML (Google Earth)
- Airdata

**Limitations:**
- Only supports drones up to and including Mavic 2 / Air 2 / Mini 2 with caveats.
- No support for Mavic 3, Mini 3+, Air 3.

## Tool 3 — DJI Pilot 2 (Enterprise)

For Mavic 3 Enterprise / Thermal / Multispectral, Matrice series. Runs on the Smart Controller Enterprise.

**Capabilities:**
- Photogrammetry (oblique + nadir grids)
- Linear flight (corridor mapping for power lines / pipelines)
- Smart oblique
- KML import
- Multi-flight resume on battery swap (M300/M350)

## Tool 4 — Drone Harmony (advanced)

[Drone Harmony](https://www.droneharmony.com) — third-party mission planner with strong automation.

- 3D inspection patterns (around a building, around a tower)
- LiDAR / photogrammetry
- Subscription-based

## Tool 5 — Open-source alternative: QGroundControl

Not for stock DJI, but if you ever go Pixhawk / ArduPilot:
- [QGroundControl](https://github.com/mavlink/qgroundcontrol) — the standard MAVLink ground station. Cross-platform.

## Mission templates

We ship reusable Litchi CSVs in [`presets/litchi-missions/`](../../presets/litchi-missions/). Open in Litchi Mission Hub to load. Edit lat/lon to your location.

Included templates:
- **Orbit** — 12-point smooth orbit around a fixed POI at variable radius and altitude.
- *More templates accepted as community contributions.*

## Practical workflow recipes

### Time-lapse across multiple days

1. Plan mission in Litchi or DJI Fly.
2. Save and re-fly daily at the same time.
3. Use Airdata to compare battery / wind across days.
4. Stack the resulting clips by frame in DaVinci Resolve.

### Photogrammetry survey (Enterprise / Mavic 3E)

1. Use DJI Pilot 2 "Mapping" mission.
2. Set 75% front overlap, 65% side overlap.
3. Fly twice — nadir grid for ground, oblique grid for facades.
4. Process in [`OpenDroneMap`](https://github.com/OpenDroneMap/ODM) (free) or commercial tools (Pix4D, DroneDeploy, DJI Terra).

### Reveal shot (any drone, with Litchi)

A 2-waypoint reveal: low foreground waypoint, high background waypoint, gimbal pitch transitioning. See [`presets/litchi-missions/`](../../presets/litchi-missions/) for the template (community contributions welcome).
