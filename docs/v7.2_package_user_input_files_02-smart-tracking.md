# Track 2 — Smart Tracking

Getting more out of object tracking than what DJI Fly exposes by default.

## What's already on your drone

DJI ships several flavors of subject tracking depending on model:

- **ActiveTrack 5.0 / 6.0** — Mavic 3 family, Air 3, Mini 4 Pro. Multi-axis follow, obstacle aware, very robust on people / vehicles.
- **ActiveTrack 4.0** — Air 2S, Mini 3 Pro. Solid baseline.
- **ActiveTrack 360°** — Mini 4 Pro, Air 3. Lateral orbits while tracking.
- **Spotlight Pro** — Mavic 3 Pro, Air 3. Locks the gimbal on a subject while you fly free.
- **Master Shots** — Auto-cinematic sequence around a subject.
- **Hyperlapse with subject lock** — moving timelapse.

**Use these first.** They are the easiest, the safest, and free.

## When the built-ins aren't enough

Three common reasons people want more:

1. **Track a subject the AI doesn't recognize** — a sailboat at distance, a horse, a specific industrial vehicle.
2. **Drive tracking from external logic** — e.g. follow whichever subject is currently fastest.
3. **Custom orbit / overhead patterns** that aren't in DJI's preset list.

## Approach 1 — Litchi (older drones)

For: Mavic Pro, Air 1, Mavic 2, Mavic Air 2, Mini 2 (limited), Phantom 4 series.

- **Track Mode:** Touch any object in the live view. Litchi tracks it via its own CV pipeline. Often more aggressive and more configurable than DJI's ActiveTrack on these models.
- **Focus Mode:** Locks gimbal on a subject while you fly manually.
- **Orbit:** Define a center and radius, drone orbits autonomously.
- **POI (Point of Interest):** Multi-segment tracking around a fixed location.

**Cost:** $25 one-time per platform.

## Approach 2 — Custom CV via Mobile SDK V5 (modern drones)

For: Mavic 3 family, Air 3, Mini 4 Pro / 3 Pro.

**Pipeline:**
1. Build an Android app on Mobile SDK V5.
2. Pull the live H.264 video frames from `IMediaManager` / `IVideoFeeder`.
3. Decode to bitmaps and run a YOLO model (YOLOv8 / v11) for detection.
4. Track the chosen detection across frames with a tracker (BoT-SORT, ByteTrack).
5. Compute pixel-space error (target offset from frame center).
6. Convert to drone command via Virtual Stick:
   - Pixel-X error → yaw rate
   - Pixel-Y error → gimbal pitch rate
   - Bounding box size → forward/back velocity (maintain distance)

**Reference repositories:**
- [`dji-sdk/Mobile-SDK-Android`](https://github.com/dji-sdk/Mobile-SDK-Android) — VirtualStickSample, VideoStreamSample.
- [`ultralytics/ultralytics`](https://github.com/ultralytics/ultralytics) — YOLO models including mobile-friendly variants.
- [`mikel-brostrom/boxmot`](https://github.com/mikel-brostrom/boxmot) — multi-object trackers.

**Practical notes:**
- On-device inference: use a quantized YOLOv8n (≈ 6 MB) or YOLOv11n. Targets 15–25 FPS on a modern phone.
- Off-device inference: stream H.264 to a desktop, run inference there, send commands back via the Bridge App. Higher latency but full GPU power.
- Gimbal smoothing matters. Add a low-pass filter on yaw rate to avoid jitter.

## Approach 3 — Onboard SDK + Companion Computer (Enterprise)

For: Mavic 3 Enterprise / Thermal / Multispectral, M30/M300/M350.

Mount a Jetson Orin Nano or Raspberry Pi 5 + Coral TPU as a payload via PSDK. Run the full CV pipeline on the drone itself. No video round-trip latency.

Reference: [`dji-sdk/Payload-SDK`](https://github.com/dji-sdk/Payload-SDK).

## Safety

- Always have a manual override binding. Most pilots use a flight-mode toggle on the RC: any input from the sticks immediately suspends autonomous control.
- Geofence your tracking. Define a max radius and altitude in your code; refuse to fly past it.
- Test in open spaces with no people downrange.
- Test obstacle avoidance: even with custom tracking, leave the drone's onboard obstacle sensors enabled.
