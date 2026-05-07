# Litchi Mission Templates

Ready-to-use Litchi Mission Hub CSV files. Import via [Litchi Mission Hub](https://flylitchi.com/hub) → Missions → Import → Choose CSV.

## Compatibility

Litchi only supports older DJI drones:

| Drone | Litchi support |
|-------|----------------|
| Mavic Pro / Air 1 | ✅ |
| Mavic 2 Pro / Zoom | ✅ |
| Mavic Air 2 | ✅ (limited) |
| Mini 2 | ⚠️ Beta |
| Mavic 3 / Air 3 / Mini 3+ | ❌ Not supported by DJI's MSDK V5 path |

For newer drones, use DJI Fly's native waypoints (Mavic 3 family, Air 3, Mini 4 Pro have native waypoint missions in 2024+ firmware).

## Templates

### `orbit-template.csv`

A 12-point smooth orbit around a fixed Point of Interest (POI).

- **Default location:** San Francisco (37.7749, -122.4194). **You must edit lat/lon to your location.**
- **Default altitude:** 30 m above takeoff point
- **Default radius:** ~50 m around the POI
- **Default speed:** 4 m/s
- **Gimbal mode:** Focus POI (camera always points at center)
- **Photo trigger:** every 5 m of travel

### How to customize

1. Open the CSV in any spreadsheet (Excel, Google Sheets, LibreOffice).
2. Replace `latitude` and `longitude` columns with your target coordinates.
3. Replace `poi_latitude` and `poi_longitude` with the center point you want the camera to track.
4. Adjust `altitude(m)` if your subject needs a different camera height.
5. Adjust `speed(m/s)` — lower for cinematic, higher for fast scouting.
6. Save as CSV.
7. In Litchi Mission Hub: **Missions → Import → Litchi CSV**.

### Calculating orbit waypoints for a different radius

For a circle of radius `R` meters centered on `(lat0, lon0)`:

```
d_lat = R / 111000
d_lon = R / (111000 * cos(lat0_radians))
```

Then for each angle θ (0° to 330° in 30° steps for 12 waypoints):

```
lat = lat0 + d_lat * cos(θ)
lon = lon0 + d_lon * sin(θ)
```

## Adding more templates

We accept community contributions. Open a PR with:

- The CSV file
- A short description in this README
- Recommended drone models / firmware
- A safety note (recommended takeoff height, obstacle clearance)

Ideas we'd like:

- **Reveal shot:** low foreground waypoint → high background waypoint with gimbal tilt-up
- **Rooftop survey:** lawn-mower grid with nadir camera at fixed altitude
- **Hyperlapse runway:** straight line with photo every 2 m
- **Around-a-tower:** spiraling orbit climbing 5 m per revolution
