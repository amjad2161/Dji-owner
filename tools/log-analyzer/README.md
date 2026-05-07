# Log Analyzer

A small Python CLI that reads a flight log CSV and prints a one-page health summary.

## Install

Use a virtualenv:

```bash
python -m venv .venv
.venv\Scripts\activate    # Windows
source .venv/bin/activate # Linux / Mac
pip install -r requirements.txt
```

## Usage

```bash
python analyze.py path/to/flight-export.csv
```

## Where to get a CSV

1. **Airdata UAV (easiest):** open the flight detail page → Download → Detailed CSV.
2. **DatCon:** convert a `.DAT` to CSV via the GUI.
3. **DJI Pilot 2:** export flight data from the controller.

## Sample output

```
============================================================
Flight summary  —  2025-04-12-orbit.csv
============================================================
Duration:         14.32 min
Max height AGL:    122.4 m
Max distance:     1820.5 m
Max horiz speed:    14.8 m/s
Max vert speed:      6.1 kph
Battery:           98% → 22% (delta 76%)
Voltage:           17.18 V → 14.92 V (delta -2.26 V)
GPS satellites:    avg  17.4, min 14
Motor RPM avg:
   motor1_rpm:   6034
   motor2_rpm:   6041
   motor3_rpm:   6018
   motor4_rpm:   6029
============================================================
```

## Supported column conventions

- Airdata UAV CSV (default)
- DatCon CSV (`OSD.*` and `BATTERY.*` prefix)
- DJI Fly TXT → CSV (manual conversion)

If your CSV format isn't recognized, open an issue with a column header sample.

## Roadmap

- Per-motor temperature tracking
- Vibration peak detection
- Wind-speed estimate from pitch vs. ground speed
- HTML report with charts
- Multi-flight comparison mode

Contributions welcome.
