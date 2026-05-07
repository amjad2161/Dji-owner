# Track 3 — Cinematic Video Pipeline

Footage that feels like it came from a $50K production, using free or low-cost tools and a drone you already own.

## The pipeline at a glance

```
[Drone]
  ├─ Camera profile: D-Log / D-Log M / HLG
  ├─ Bitrate: max your drone supports (H.265, 10-bit if available)
  ├─ Frame rate: 24 fps for cinematic, 60+ for slow-mo source
  └─ Resolution: 4K minimum

[Capture card / direct file copy]
  └─ Backup: keep originals untouched, work on copies

[Gyroflow]
  └─ Stabilization using drone gyro telemetry

[DaVinci Resolve]
  ├─ Color management: DJI D-Log → Resolve color space
  ├─ Apply DJI LUT or build custom node tree
  ├─ Editing
  └─ Export: H.264 / H.265, 50 Mbps for web, ProRes for archive

[Optional: Topaz Video AI / Real-ESRGAN]
  └─ Upscale / denoise specific shots
```

## Step 1 — Capture settings

### Recommended baseline (Mavic 3 / 3 Pro)

- **Codec:** H.265
- **Profile:** D-Log
- **Resolution:** 4K
- **Frame rate:** 24, 30, or 60 fps depending on intent
- **Bitrate:** Maximum (varies by model — Mavic 3 Cine offers up to 3,772 Mbps in ProRes)
- **Color depth:** 10-bit
- **ISO:** Native ISO of the sensor (typically 100 or 400 — check your model's sensor sheet)
- **Shutter:** Use a 1/(2× frame rate) shutter (e.g. 1/50 at 24 fps) — requires ND filters in daylight

### Recommended baseline (Mavic 2 Pro)

- **Codec:** H.265
- **Profile:** D-Log
- **Resolution:** 4K
- **Frame rate:** 30 fps (24 fps available too)
- **Bitrate:** 100 Mbps
- **Color depth:** 10-bit
- **ND filters:** Strongly recommended

### Why D-Log

D-Log is a flat profile that captures more dynamic range than the standard "Normal" profile. It looks ugly out of camera — that's by design. It gives you headroom in post.

**If your drone doesn't have D-Log:** use D-Cinelike, or HLG. Same idea, narrower latitude.

## Step 2 — ND filters

For cinematic motion blur (180° shutter rule), you need:

- **Bright daylight, 24 fps:** ND16 to ND64
- **Overcast, 24 fps:** ND8 to ND16
- **Golden hour, 24 fps:** ND4 to ND8

DJI sells ND kits per drone model. Third-party (Freewell, PolarPro, Tiffen) offer better optical quality at similar price.

## Step 3 — Stabilization in Gyroflow

DJI's mechanical gimbal is excellent. Adding Gyroflow on top removes residual micro-jitter that you can't see in the air but show up on a 65-inch TV.

### Gyroflow workflow

1. Open Gyroflow.
2. Drop your `.mp4` clip in. Gyroflow detects the camera profile automatically for most Mavics.
3. Sync gyro data — usually automatic; manual sync available for tricky clips.
4. Choose smoothness level (recommend 0.5–0.7 for natural look).
5. Choose horizon lock if your clip has tilt drift.
6. Export.

**Gyroflow camera profiles** for DJI drones live in the [Gyroflow Camera Presets](https://github.com/gyroflow/gyroflow-camera-presets) repository.

## Step 4 — Color in DaVinci Resolve

### Quick path with DJI LUT

1. Download the official LUT for your drone from DJI's downloads page (search for your model + LUT).
2. In Resolve, drop the LUT into `~/Library/Application Support/Blackmagic Design/DaVinci Resolve/LUT/` (Mac) or `C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\LUT\` (Windows).
3. Right-click the node in the Color page → 3D LUT → DJI → choose your LUT.

This gives you 80% of a finished look in one click.

### Pro path — full color managed workflow

1. Project Settings → Color Management → Color Science: **DaVinci YRGB Color Managed**.
2. Input Color Space: **DJI D-Log**.
3. Timeline Color Space: **DaVinci Wide Gamut / Intermediate**.
4. Output Color Space: **Rec.709 Gamma 2.4** (broadcast / streaming) or **Rec.2020** (HDR).
5. Build a node tree: Balance → Primaries → Secondaries → Look.

This takes more time but gives you real control. The DJI LUT approach "bakes" the look; color management lets you grade per-shot.

## Step 5 — Optional AI enhancement

- **[Topaz Video AI](https://www.topazlabs.com)** — best-in-class upscaling and denoise. ~$300.
- **[Real-ESRGAN GUI (Upscayl)](https://github.com/upscayl/upscayl)** — free, open source. Good for stills; less mature for video.
- **[FlowFrames](https://github.com/n00mkrad/flowframes)** — frame interpolation for smoother slow-motion.

## Step 6 — Export

| Target | Codec | Bitrate | Notes |
|--------|-------|---------|-------|
| YouTube 4K | H.265 | 50–80 Mbps | YouTube re-encodes anyway |
| Instagram Reel | H.264 | 25 Mbps | 9:16, max 90s for full quality |
| Archive master | ProRes 422 HQ | — | Lossless-ish, large files |
| HDR10 | H.265 10-bit | 100 Mbps | Tag color metadata correctly |

## Common mistakes to avoid

1. **Shooting Normal profile and grading in post.** You can't recover dynamic range that wasn't captured.
2. **No ND filters in daylight.** You'll be at 1/4000 shutter, video looks staccato.
3. **Skipping color management.** Direct 3D LUT on D-Log without proper transforms gives muddy shadows.
4. **Over-stabilization.** Gyroflow at 1.0 smoothness looks unnatural — handheld micro-motion is part of cinematic feel.
5. **Compressing twice.** If your edit timeline is 4K and you export at 1080p H.264, do it once — don't pre-render an intermediate H.264.
