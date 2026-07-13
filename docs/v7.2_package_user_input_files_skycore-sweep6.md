# SkyCore Awareness, Capture, Recording, and Voice

The sweep-6 modules add manned-aircraft awareness, photo geotagging, hyperlapse rendering, MCAP telemetry recording, wind estimation, HLS video proxy, voice transcription, and pilot competency checks.

## OpenSky aircraft awareness (`skycore.awareness`)

Free real-time ADS-B-based traffic data from OpenSky Network. Use it to check for manned aircraft near your operating area before / during flight.

```python
from skycore.awareness import OpenSkyClient, is_traffic_concern
from skycore import GeoPoint

client = OpenSkyClient()  # anonymous (100 req/day) or pass username/password
home = GeoPoint(37.7749, -122.4194)
aircraft = client.near(home, radius_km=10)
for a in aircraft:
    print(a.callsign, a.origin_country, a.geo_altitude_m, a.velocity_mps)

concern, hits = is_traffic_concern(home, drone_alt_amsl_m=120, radius_km=5)
if concern:
    print("WARNING: aircraft nearby:", [h.callsign for h in hits])
```

Note: ADS-B requires the manned aircraft to broadcast it. Light GA aircraft without ADS-B Out won't appear. Always maintain VLOS.

## Photo EXIF geotagging (`skycore.exif`)

DJI cameras already write GPS EXIF. Use this when:
- Photos came from a payload camera without GPS
- Photos lost EXIF in editing
- You want to backfill geotags from a recorded telemetry log

```python
from skycore.exif import geotag_photo, geotag_directory_from_telemetry

geotag_photo("shot.jpg", lat=37.77, lon=-122.42, altitude_m=120, timestamp=datetime.utcnow())

# Bulk: match all photos in a folder to nearest-time telemetry sample
telemetry = [
    {"ts": "2026-05-08T14:32:01", "lat": 37.77, "lon": -122.42, "alt": 50},
    {"ts": "2026-05-08T14:32:05", "lat": 37.77, "lon": -122.42, "alt": 60},
]
geotag_directory_from_telemetry("photos/", telemetry)
```

## Hyperlapse rendering (`skycore.hyperlapse`)

Photos → MP4 with deflicker, optional crop, and configurable framerate / bitrate.

```python
from skycore.hyperlapse import render_hyperlapse

render_hyperlapse(
    "./photos",
    "./hyperlapse.mp4",
    fps=30,
    bitrate="50M",
    crop_aspect="16:9",
    deflicker=True,
)
```

Wraps `ffmpeg`'s concat-demuxer pipeline. Works with the photo output of any of the SkyCore mission templates (especially `hyperlapse_line`).

## MCAP telemetry recording (`skycore.mcap_recording`)

MCAP is the modern container format for time-series robotics data. Write your flight telemetry as MCAP and replay it in [Foxglove Studio](https://foxglove.dev) for chart + 3D-path + scrubbable timeline analysis.

```python
from skycore.mcap_recording import McapRecorder

with McapRecorder("flight.mcap") as rec:
    async for tm in drone.telemetry_stream():
        rec.write(tm.to_dict())
        # Multi-channel: also record vision detections on a separate topic
        rec.write_to("/skycore/detections", {"frame": 42, "objects": ["person"]})
```

The written file opens directly in Foxglove with full schema awareness.

## Wind estimation (`skycore.wind`)

Estimate wind speed + direction from telemetry. Compares ground velocity to airspeed inferred from pitch / roll.

```python
from skycore.wind import estimate_wind

# Take a 5-second window of telemetry at 10 Hz
samples = []
async for tm in drone.telemetry_stream():
    samples.append(tm)
    if len(samples) >= 50:
        break
est = estimate_wind(samples)
print(f"Wind: {est.speed_kph:.0f} kph from bearing {est.bearing_deg:.0f}° (confidence {est.confidence:.2f})")
```

Coarse but useful for advisory display. Don't use for navigation decisions.

## HLS video proxy (`skycore.streaming`)

Ingest an RTMP / RTSP stream and republish as HLS for browser playback.

```python
from skycore.streaming import HlsProxy

proxy = HlsProxy(input_url="rtmp://localhost/live/stream", output_dir="./hls")
proxy.start()
# In your dashboard: <video src="/hls/stream.m3u8"></video>
```

Wraps `ffmpeg`. Works with OBS → RTMP, DJI RC → OBS → RTMP, or any pipeline that outputs RTMP/RTSP.

## Voice transcription (`skycore.voice`)

Whisper-based STT plus a simple command grammar. Voice commands are **not** auto-executed; the parser hands you a `VoiceCommand` and you decide whether to run it.

```python
from skycore.voice import VoiceTranscriber, parse_command

t = VoiceTranscriber(model_name="base.en")  # or backend="faster-whisper"
text = t.transcribe("command.wav")
cmd = parse_command(text)
if cmd:
    print(f"Heard: {cmd.action}({cmd.args})")
    # Confirm with the pilot before executing!
```

Grammar:
```
skycore takeoff [N]      → takeoff(altitude=N or 5)
skycore land             → land
skycore return           → return-to-home
skycore photo            → take-photo
skycore recording start  → start-recording
skycore recording stop   → stop-recording
skycore goto LAT LON     → goto
skycore orbit [RADIUS]   → orbit
```

## Pilot competency self-check (`skycore.pilot`)

A short pre-flight quiz that asks the pilot to attest to operational basics: NOTAMs, weather, battery, props, compass, observers, emergency plan, airspace, VLOS.

```python
from skycore.pilot import CompetencyCheck

check = CompetencyCheck()
# CLI:
result = check.run_interactive()
# or from a web form submission:
result = check.from_dict({"notams": True, "weather": True, ...})
if not result.passed(check.questions):
    print("Missing:", result.missing(check.questions))
```

Not a substitute for proper certification. A nudge to make sure the right things were verified before takeoff.

## Optional extras matrix

| Extra | Modules enabled |
|-------|-----------------|
| `[exif]` | EXIF geotagging |
| `[mcap]` | MCAP recorder |
| `[voice]` | OpenAI Whisper STT |
| `[voice-fast]` | faster-whisper backend |
