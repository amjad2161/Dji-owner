# Track 6 — Live Streaming

Broadcast your flight to YouTube, Twitch, Facebook Live, or your own RTMP server.

## Two architectures

### Architecture A — Phone-as-source

```
[Drone] → OcuSync → [RC] → [Phone running DJI Fly]
                                    │
                                    ├─ Built-in RTMP (some models)
                                    │   → YouTube / Facebook directly
                                    │
                                    └─ Screen mirror to PC
                                          │
                                          └─ OBS Studio → RTMP
```

**Pros:** simple, no extra hardware.
**Cons:** lower quality (re-encoded twice), single output destination.

### Architecture B — RC HDMI / USB capture to PC

```
[Drone] → OcuSync → [DJI RC 2 / Smart Controller] → HDMI / USB-C → [Capture card]
                                                                     │
                                                                     └─ OBS Studio
                                                                          │
                                                                          ├─ YouTube
                                                                          ├─ Twitch
                                                                          └─ Facebook (multistream via Restream / Aitum)
```

**Pros:** higher quality, multi-destination, full OBS overlays.
**Cons:** requires a capture card and an RC with HDMI out (not all models have this).

## OBS Studio setup

### One-time installation

```powershell
winget install OBSProject.OBSStudio
```

Or download from [obsproject.com](https://obsproject.com).

### Source configuration

1. Add Source → **Video Capture Device** (for HDMI capture card) or **Window Capture** (for phone-mirrored to PC via [scrcpy](https://github.com/Genymobile/scrcpy)).
2. Set base canvas to 1920×1080.
3. Set output resolution to 1920×1080 at 30 fps for general streaming, 60 fps if your destination supports it and your bandwidth allows.

### Stream settings

- **Service:** YouTube / Twitch / Facebook / Custom.
- **Bitrate:** 6000 Kbps for 1080p30, 9000 Kbps for 1080p60.
- **Encoder:** NVENC (NVIDIA), AMF (AMD), or QuickSync (Intel) — these use the GPU and don't bog down OBS.
- **Keyframe interval:** 2 seconds.

## Multi-destination streaming

- **[Restream.io](https://restream.io)** — paid SaaS. Push to OBS once, fans out to YouTube + Twitch + Facebook + LinkedIn.
- **[Aitum Multistream](https://aitum.tv)** — local OBS plugin. Free for limited destinations.
- **Self-hosted [Nginx-RTMP](https://github.com/arut/nginx-rtmp-module)** — full control, free, requires a server.

## Latency budget

Expect:
- Drone → RC: ~150 ms
- RC → phone / capture: ~50 ms
- OBS encoding: ~500 ms (default)
- RTMP ingest → public viewer: 15–30 seconds

Total end-to-end: ~20 seconds. For lower latency:
- YouTube: enable "Ultra-low latency" mode (drops to ~3 sec).
- Twitch: enable "Low Latency" (drops to ~2 sec).
- Self-hosted RTMP: tune chunk size, can hit < 1 sec.

## Overlays and graphics

- **Drone telemetry overlay:** OBS plugin that reads from your phone via DJI Mobile SDK. Custom development project — see Track 1 / Track 2.
- **Map overlay:** [OBS Browser Source](https://obsproject.com/wiki/Sources-Guide#browser) pointed at a map page that pulls live GPS from your DJI account or Airdata.
- **Lower thirds:** built into OBS or via [StreamFX](https://github.com/Xaymar/obs-StreamFX).

## Recording while streaming

In OBS, **Settings → Output → Recording** can save a local copy at higher bitrate than what you're streaming. This protects you against stream cutouts and gives you better source for later editing.

Recommended local recording: H.265, 50 Mbps, MP4 container.

## Legal note

Live-streaming flights does not change drone law obligations. Make sure you:
- Have permission to film the area.
- Aren't broadcasting in restricted airspace where filming itself may be regulated.
- Aren't streaming PII (faces, license plates) without consent in privacy-sensitive jurisdictions.
