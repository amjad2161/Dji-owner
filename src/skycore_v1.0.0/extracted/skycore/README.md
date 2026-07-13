# Drone Mastery Hub — DJI Pilot Toolkit (SkyCore)

**Legal, Open-Source Toolkit for DJI Mavic Owners**

This is a continuation and full implementation of the SkyCore platform from the community repo.

## What is SkyCore?
A unified Python platform for drone operations:
- Supports DJI (via Mobile SDK bridge), Tello, MAVLink (PX4/ArduPilot), Simulator
- Mission planning, vision AI, video processing, safety systems
- Fully legal - uses official SDKs only. No firmware mods, no NFZ bypass.

## Quick Start (in this sandbox)
```bash
cd /home/workdir/artifacts/skycore
pip install -e .
skycore serve --backend simulator
```

## Key Features (52 Modules)
- Core flight control
- Orbit, waypoint, survey missions (Litchi compatible)
- YOLO + BoT-SORT smart tracking
- Gyroflow integration for cinematic video
- Geofence, weather, airspace awareness
- Voice commands (EN/HE/AR)
- ADS-B for manned aircraft avoidance
- Swarm intelligence, Digital Twin, Edge AI, SAR patterns, Counter-UAS

## Compatibility
See original repo for Mavic 3, Air 3, Mini 4 Pro etc.

## Legal Notice
This project strictly adheres to aviation regulations. All operations within manufacturer limits and local laws (CAAI, FAA, EASA).

## Continue Development
This is an active build. Run `python -m skycore.cli` or use the API at http://localhost:8080

For full details, see SPEC.md (to be added).
