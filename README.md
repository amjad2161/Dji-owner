# Drone Mastery Hub — DJI Pilot Toolkit

> A community-driven, fully legal toolkit for getting the most out of your DJI Mavic drone — without modifying firmware, bypassing safety systems, or breaking aviation regulations.

**[עברית](README.he.md)** · English

---

## What this is

A curated, beginner-friendly playbook for DJI Mavic owners who want to push their drone to its full potential **using only official SDKs, supported tools, and legal community software**. No firmware patching. No No-Fly-Zone removal. No transmit-power boosting. Just everything you can legitimately do — explained well, with real tools shipped in this repo.

## Who it's for

- **New pilots** who just bought a Mavic and want a complete roadmap
- **Hobbyists** who have outgrown DJI Fly and want more
- **Content creators** chasing cinematic footage
- **Photographers and surveyors** building repeatable mission workflows
- **Developers** ready to build on top of the DJI Mobile / Onboard SDKs

## Six capability tracks

| # | Track | What you achieve |
|---|-------|------------------|
| 1 | [PC Flight Control](docs/en/01-pc-flight-control.md) | Fly without your phone — laptop + RC + joystick |
| 2 | [Smart Tracking](docs/en/02-smart-tracking.md) | Object tracking beyond default ActiveTrack |
| 3 | [Cinematic Video](docs/en/03-cinematic-video.md) | Hollywood-style post pipeline: D-Log → Gyroflow → Resolve |
| 4 | [Mission Planning](docs/en/04-mission-planning.md) | 3D waypoints, repeatable shots, automated mapping |
| 5 | [Log Analysis](docs/en/05-log-analysis.md) | Find issues before they become crashes |
| 6 | [Live Streaming](docs/en/06-streaming.md) | Push your flight to YouTube / Twitch / Facebook live |

## What's in this repo

```
dji-owner/
├─ docs/                       Bilingual documentation (en + he)
│  ├─ en/
│  │  ├─ getting-started.md
│  │  ├─ 01-pc-flight-control.md … 06-streaming.md
│  │  ├─ compatibility-matrix.md  Per-drone capability table
│  │  ├─ awesome-drone-repos.md   Curated open-source ecosystem
│  │  └─ legal-and-safety.md
│  └─ he/                       Hebrew
├─ scripts/windows/
│  ├─ install-toolkit.ps1       One-shot install of all GUI tools
│  └─ clone-dev-repos.ps1       Clones the major drone SDKs
├─ tools/
│  └─ log-analyzer/             Python CLI for flight log health checks
└─ presets/
   └─ litchi-missions/          Ready-to-use waypoint missions
```

## Quick start (Windows)

```powershell
# 1. Install the GUI toolset (DaVinci Resolve, OBS, Python, Git, scrcpy, VLC, ...)
iwr https://raw.githubusercontent.com/amjad2161/dji-owner/main/scripts/windows/install-toolkit.ps1 -UseBasicParsing | iex

# 2. Optional — clone every major drone SDK for development (DJI MSDK, OSDK,
#    PSDK, MAVLink, Gyroflow, ODM, YOLO, BoxMOT, ...) into ~/dji-dev/
iwr https://raw.githubusercontent.com/amjad2161/dji-owner/main/scripts/windows/clone-dev-repos.ps1 -UseBasicParsing | iex
```

Prefer manual installation? Follow the [Getting Started guide](docs/en/getting-started.md).

## Open-source ecosystem

The drone ecosystem on GitHub is large. We track the legal, well-maintained, currently-relevant projects in the [Awesome Drone Repos catalog](docs/en/awesome-drone-repos.md) — official DJI SDKs, open flight stacks (PX4, ArduPilot), ground stations (QGroundControl, MAVSDK), Gyroflow, YOLO + tracking, OpenDroneMap, and the Tello-Python ecosystem for learners.

The `clone-dev-repos.ps1` script pulls the most-used ones in one command.

## Compatibility quick view

Not every drone supports every workflow. Check the [full compatibility matrix](docs/en/compatibility-matrix.md) before you commit.

| Family | PC Flight | Litchi | ActiveTrack | Mobile SDK | Onboard / Payload SDK |
|--------|-----------|--------|-------------|------------|------------------------|
| Mavic 3 / 3 Pro / 3 Cine | Partial | ❌ | 5.0 | V5 | ❌ |
| Mavic 3 Enterprise / Thermal | Yes | ❌ | 5.0 | V5 | Yes (PSDK) |
| Mavic Air 3 / Air 2S / Air 2 | Limited | Air 2 only | 4.0 / 5.0 | V5 / V4 | ❌ |
| Mini 4 Pro / Mini 3 Pro | Limited | ❌ | 360° / 4.0 | V5 | ❌ |
| Mini 2 / Mini SE | Basic | ❌ | ❌ | ❌ | ❌ |
| Mavic 2 Pro / Zoom | Yes | ✅ | 2.0 | V4 | ❌ |
| Mavic Pro / Air 1 | Yes | ✅ | 1.0 | V4 (legacy) | ❌ |

## Legal and safety

This project operates **inside** manufacturer SDKs and national aviation rules. We do **not** publish:

- Firmware patches that disable geofencing (No-Fly Zones)
- Tools that exceed legal transmit power (FCC / CE / MIC / SRRC limits)
- Methods to bypass Remote ID
- Altitude or speed limit removal beyond what DJI exposes officially

You are responsible for following your local civil aviation authority's rules. See [legal-and-safety](docs/en/legal-and-safety.md) for per-country detail.

## Project status

🚧 Early-stage, community-driven. Contributions welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT — see [LICENSE](LICENSE).
