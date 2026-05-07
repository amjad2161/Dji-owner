# Track 5 — Log Analysis

Every DJI flight produces logs. Reading them turns guesswork into data.

## Three log formats

| Format | Source | What's in it | Tools |
|--------|--------|--------------|-------|
| `.txt` flight record | DJI Fly / GO 4 on phone | Telemetry summary, sensor history | Airdata, CsvView, our `analyze.py` |
| `.DAT` raw flight log | Drone internal storage | Full sensor stream, encrypted | DatCon, DJI internal tools |
| `.LOG` RC log | Remote controller storage | Stick inputs, link quality | Less commonly analyzed |

## Tool 1 — Airdata UAV (web, easy mode)

[airdata.com](https://airdata.com) is the obvious starting point.

**Setup:**
1. Sign up for a free account.
2. Either:
   - Auto-sync from DJI Fly via the **Airdata Sync** plugin app (iOS/Android), or
   - Manually upload `.txt` files from `Android/data/dji.go.v5/files/DJI/dji.go.v5/FlightRecord/` (path varies).
3. Open any flight in the dashboard.

**What to look at:**
- **Battery health timeline** — see capacity drift over flights.
- **Vibration graph** — high motor vibration = props need balancing or replacing.
- **GPS satellite count** — anything below 10 at takeoff is a yellow flag.
- **Wind estimate** — from the angle of attack vs. ground speed.
- **Motor RPM variance** — if one motor consistently runs hotter or higher RPM, it's wearing.
- **Cell voltage delta** — 0.1 V+ between cells indicates battery imbalance.

## Tool 2 — DatCon / CsvView (raw DAT decoding)

For raw `.DAT` files pulled directly from the drone via DJI Assistant 2 (Settings → Logs).

- [DatCon](https://datfile.net/CsvView/intro.html) — converts encrypted DAT to CSV/KML.
- [CsvView](https://datfile.net/CsvView/intro.html) — visualizes the CSV with charts and a 3D map.

Useful for: post-crash analysis, IMU calibration drift, motor burnout investigation.

## Tool 3 — Our Python log analyzer

We ship a small Python script in [`tools/log-analyzer/`](../../tools/log-analyzer/) that takes an Airdata CSV export and produces a one-page health summary.

**Usage:**
```bash
cd tools/log-analyzer
pip install -r requirements.txt
python analyze.py path/to/airdata-export.csv
```

Output: max altitude, max distance, max horizontal/vertical speed, total flight time, average wind estimate, battery delta over flight, vibration peaks per motor, list of flagged events.

See [`tools/log-analyzer/README.md`](../../tools/log-analyzer/README.md) for details.

## What to look for

### After every flight

1. Battery cell voltage delta < 0.05 V at landing.
2. No motor flagged for high vibration.
3. GPS satellites stayed >12 throughout.
4. No compass interference warnings.
5. RTH altitude was set high enough (review the trajectory).

### Once a month

1. Battery health % vs. number of cycles. Healthy LiPo loses ~1% per 20 cycles.
2. Motor RPM symmetry across all four motors at hover.
3. Average wind handled vs. battery duration.

### After any incident

1. Pull the `.DAT` from the drone.
2. Run through DatCon.
3. Look at IMU data, motor outputs, and command inputs in the 5 seconds before the event.
4. Cross-check with weather data for that location and time.

## Privacy note

Flight logs contain GPS tracks of every flight. If you publish or share logs:
- Strip home-point coordinates.
- Consider redacting time-of-day if it reveals routine patterns.
- Airdata supports public/private toggles per flight.
