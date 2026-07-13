# Compatibility Matrix

What you can do with each Mavic family. **Verify against your specific firmware version** — DJI changes capabilities between firmware releases.

## Legend

- ✅ Fully supported
- ⚠️ Partial / with caveats
- ❌ Not supported
- 🛠️ Requires Enterprise / Payload SDK

## Current consumer drones (2024–2026)

| Drone | Mobile SDK | Litchi | DJI Fly | ActiveTrack | Waypoints (native) | Master Shots | D-Log | Onboard / PSDK |
|-------|-----------|--------|---------|-------------|--------------------|--------------|-------|-----------------|
| **Mavic 3 Pro** | V5 | ❌ | ✅ | 5.0 | ✅ | ✅ | ✅ (Hasselblad) | ❌ |
| **Mavic 3 / 3 Cine** | V5 | ❌ | ✅ | 5.0 | ✅ | ✅ | ✅ | ❌ |
| **Mavic 3 Classic** | V5 | ❌ | ✅ | 5.0 | ✅ | ✅ | ❌ | ❌ |
| **Mavic 3 Enterprise** | V5 | ❌ | DJI Pilot 2 | 5.0 | ✅ | ❌ | ✅ | ✅ PSDK |
| **Mavic 3 Thermal** | V5 | ❌ | DJI Pilot 2 | 5.0 | ✅ | ❌ | ✅ | ✅ PSDK |
| **Mavic 3 Multispectral** | V5 | ❌ | DJI Pilot 2 | 5.0 | ✅ | ❌ | ❌ | ✅ PSDK |
| **Air 3 / Air 3S** | V5 | ❌ | ✅ | 360° | ✅ | ✅ | ✅ | ❌ |
| **Air 2S** | V4 (legacy) | ⚠️ Beta | ✅ | 4.0 | ⚠️ Update needed | ✅ | ✅ | ❌ |
| **Mavic Air 2** | V4 | ✅ | ✅ | 3.0 | ✅ | ✅ | ❌ | ❌ |
| **Mini 4 Pro** | V5 | ❌ | ✅ | 360° | ✅ | ✅ | D-Log M | ❌ |
| **Mini 3 Pro** | V5 | ❌ | ✅ | 4.0 | ✅ | ✅ | ❌ | ❌ |
| **Mini 3** | V5 | ❌ | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ |
| **Mini 2 SE / Mini 2** | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Mini SE / Mini** | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |

## Legacy drones (2017–2021)

| Drone | Mobile SDK | Litchi | DJI GO 4 | ActiveTrack | Waypoints | D-Log | Onboard SDK |
|-------|-----------|--------|----------|-------------|-----------|-------|--------------|
| **Mavic 2 Pro** | V4 | ✅ | ✅ | 2.0 | ✅ | ✅ | ❌ |
| **Mavic 2 Zoom** | V4 | ✅ | ✅ | 2.0 | ✅ | ❌ | ❌ |
| **Mavic 2 Enterprise** | V4 | ✅ | DJI Pilot | 2.0 | ✅ | ✅ | ✅ |
| **Mavic Pro / Platinum** | V4 (legacy) | ✅ | ✅ | 1.0 | ✅ | ❌ | ⚠️ |
| **Mavic Air (1st gen)** | V4 (legacy) | ✅ | ✅ | 1.0 | ❌ | ❌ | ❌ |

## What "PC Flight" means per drone

| Method | Mavic 3 family | Air 3 / 2S / 2 | Mini family | Mavic 2 family | Mavic Pro / Air 1 |
|--------|----------------|-----------------|-------------|-----------------|--------------------|
| **DJI RC 2 standalone** (no phone) | ✅ Native | ⚠️ RC 2 only | ⚠️ Mini 4 Pro only | ❌ | ❌ |
| **DJI Assistant 2 simulator** | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Litchi mission from PC + sync to phone** | ❌ | ⚠️ Air 2 only | ❌ | ✅ | ✅ |
| **DJI Pilot 2 on Windows tablet** | ✅ Enterprise only | ❌ | ❌ | ✅ Enterprise | ❌ |
| **MSDK V5 Bridge App** (development) | ✅ | ✅ where SDK exists | ⚠️ Mini 3 Pro / 4 Pro | ❌ | ❌ |
| **Onboard SDK** (companion computer on drone) | 🛠️ Enterprise | ❌ | ❌ | 🛠️ Enterprise | ❌ |

## Camera profile support

| Drone | D-Log | D-Log M | D-Cinelike | HLG | 10-bit | RAW (DNG) photos |
|-------|-------|---------|------------|-----|--------|------------------|
| Mavic 3 Pro | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Mavic 3 / Cine | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Mavic 3 Classic | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Air 3 / 3S | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Air 2S | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ |
| Mavic Air 2 | ❌ | ❌ | ❌ | ✅ | ❌ | ✅ |
| Mini 4 Pro | ❌ | ✅ | ❌ | ✅ | ✅ | ✅ |
| Mini 3 Pro | ❌ | ❌ | ❌ | ✅ | ❌ | ✅ |
| Mavic 2 Pro | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ |
| Mavic 2 Zoom | ❌ | ❌ | ✅ | ❌ | ❌ | ✅ |

## Notes

- DJI removed legacy SDK V4 from active development. Mobile SDK V4 still works on existing apps (Litchi, others), but new apps must use V5.
- Mobile SDK V5 currently does **not** include all features of V4 — particularly waypoint mission editor APIs differ.
- "Native waypoints in DJI Fly" was reintroduced for Mavic 3 family in 2023 firmware updates. Older firmware may not have it.
- Submit corrections via PR — this matrix is community-maintained.
