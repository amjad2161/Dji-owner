# Getting Started

A seven-day path from "unboxed my Mavic last week" to "I have a real workflow." No coding required.

## Before you start

- A DJI Mavic drone (any current or recent model — see [compatibility matrix](compatibility-matrix.md))
- A Windows 10 or 11 PC
- A registered DJI account
- 30 GB of free disk space (DaVinci Resolve is large)

## The seven-day plan

### Day 1 — Foundation

1. Download and install [DJI Assistant 2 for Mavic](https://www.dji.com/downloads). This is DJI's official PC tool: firmware updates, calibration, and a flight simulator.
2. Plug the drone into the PC over USB. Check for firmware updates.
3. Open the built-in flight simulator. Practice for 30 minutes before flying outdoors. The simulator is the most underused free training tool DJI ships.

### Day 2 — Real flight, official app

1. Install the official app for your drone:
   - **DJI Fly** — Mini 2 and newer, Air 2/2S/3, Mavic 3 family
   - **DJI GO 4** — Mavic 2, Mavic Pro, Air 1, older Mini
2. Take a 15-minute flight in an open, legal area at low altitude. Verify GPS lock, RTH (Return to Home) altitude, and battery behavior.
3. Practice manual gimbal control and the basic flight modes (Position / Sport / Cine / Tripod).

### Day 3 — Mission planning with Litchi (if your drone supports it)

Litchi is the single best paid app for older DJI drones. $25 one-time. Check the [compatibility matrix](compatibility-matrix.md) — for Mavic 3 / Mini 3+ / Air 3 it does **not** work and you should skip to Day 4.

1. Sign up at [flylitchi.com](https://flylitchi.com).
2. Open the **Mission Hub** in your browser on the PC. This is where waypoint missions are designed.
3. Plan a simple 4-waypoint mission over your local park.
4. Sync to the Litchi app, fly the mission. This is your first "PC plans, drone executes" moment.

### Day 4 — Cinematic post-pipeline (Gyroflow + DaVinci Resolve)

1. Install [Gyroflow](https://gyroflow.xyz). Free, open source, professional-grade gimbal stabilization in post.
2. Install [DaVinci Resolve](https://www.blackmagicdesign.com/products/davinciresolve) — the free version is enough.
3. Download the official [DJI LUTs](https://www.dji.com/downloads) for your drone (search the downloads page for your model name + LUT).
4. Take one cinematic clip in D-Log or D-Cinelike, run it through Gyroflow, then color grade with the LUT in Resolve.

For a full walkthrough, see [03-cinematic-video.md](03-cinematic-video.md).

### Day 5 — Live streaming (OBS Studio)

1. Install [OBS Studio](https://obsproject.com). Free, open source.
2. Set up a screen capture of your phone (using a USB tethering app or DJI's mirror-to-PC feature).
3. Configure RTMP output to YouTube Live or Twitch.
4. Test a 5-minute simulator flight broadcast.

Details: [06-streaming.md](06-streaming.md).

### Day 6 — Log analysis (Airdata)

1. Sign up at [airdata.com](https://airdata.com). Free tier covers most hobbyist needs.
2. Connect Airdata to your DJI Fly account, or upload `.txt` flight records manually.
3. Read your first flight report. Look at battery health, vibrations, and GPS satellite count over time.

What to look for: [05-log-analysis.md](05-log-analysis.md).

### Day 7 — Pick a track and go deep

At this point you have a complete baseline. Choose one of the six capability tracks and spend the next month going deeper:

1. [PC Flight Control](01-pc-flight-control.md)
2. [Smart Tracking](02-smart-tracking.md)
3. [Cinematic Video](03-cinematic-video.md)
4. [Mission Planning](04-mission-planning.md)
5. [Log Analysis](05-log-analysis.md)
6. [Live Streaming](06-streaming.md)

## One-shot Windows install

If you'd rather have everything installed at once:

```powershell
iwr https://raw.githubusercontent.com/amjad2161/dji-owner/main/scripts/windows/install-toolkit.ps1 -UseBasicParsing | iex
```

See [scripts/windows/README.md](../../scripts/windows/README.md) for details.
