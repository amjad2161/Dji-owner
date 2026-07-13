# SkyCore — Honest Audit (real vs. claimed)

_Independent review of everything under `SkyCore_Consolidated/`. Goal: separate
what actually works from what is stub code or marketing language, so decisions
are made on facts._

## TL;DR

- The archive is **3 overlapping, heavily-duplicated code snapshots + 145 mostly-duplicated docs**, produced across many prior AI sessions.
- The documentation's headline numbers — *"124/155 modules", "128,000–146,000 lines", "God Mode", "certified", "military-grade"* — are **not substantiated by the code**. Real Python is a few thousand lines of genuine work wrapped in a lot of empty scaffolding and self-congratulatory markdown.
- **Nothing illegal is actually implemented anywhere.** The scary-sounding files (jamming, EW, counter-swarm) are `print()` statements, string returns, or empty folders — theater, not capability. Detection/monitoring code (RF scan, GPS-spoofing detection, ADS-B) is real-ish and legal.
- The genuinely valuable, working pieces: a real **22-state AUKF** navigation filter, real **PID/MPC/LQR** control, a real **React GCS**, real **voice-intent parsing**, and one honest reference adapter (`reference/sky.py`).
- This `consolidated/` folder packages the parts that actually run into a clean, live system (see `README.md`).

## The three code snapshots

| Snapshot | Size | Verdict |
|---|---|---|
| `src/skycore_v1.0.0/skycore/` | 245 `.py` | **Canonical / most real.** Genuine AUKF, control laws, detection C-UAS, FastAPI skeleton, React web app. |
| `src/skycore_v7.2/` | 87 `.py`, **~3,519 lines total** | **Thin scaffold.** ~43 of ~75 module folders are empty; "AES-256"/"CRYSTALS-Kyber" crypto is fake (returns a hash + plaintext); not importable as installed (entry point → empty package). Inferior to v1.0.0. |
| `src/grokdrone_pro/` | 1 `.py` + docs | **Design-only skeleton.** `INTEGRATION_MASTER.py` imports ~24 modules that don't exist → `ImportError` on line 1; self-reports fake `"100% COMPLETE, 155 modules"`. |
| `reference/sky.py` | ~287 lines | **The honest one.** Real ISS/OSRM API calls, labels every result's provenance, refuses to claim "flown" unless a real controller armed. Use it as the tone model. |

Duplication: `v1.0.0/extracted/skycore/` is ~100% redundant against `v1.0.0/skycore/`; across all trees roughly **half of the ~415 Python files are duplicate copies**. The 145 docs are largely the same files under two version prefixes.

## Real vs. stub (representative sample)

| File (canonical v1.0.0/skycore) | Verdict | Note |
|---|---|---|
| `navigation/aukf.py` (658 L) | **REAL** | 22-state AUKF, sigma points, RTK LAMBDA ratio test |
| `control/pid.py`, `mpc.py`, `lqr.py`, `geometric.py` (~2,240 L) | **REAL** | anti-windup, gain scheduling, substantial |
| `cuas/classifier.py`, `cuas/spoofing.py` | **REAL (detection, legal)** | RCS/Doppler features; C/N0 spoof-vs-jam logic |
| `defense/rf_scanner.py` | **REAL (detection only)** | header: _"detection only, no jamming, no transmission"_ |
| `core/drone.py` (`SimulatorDrone`) | **REAL interface / static data** | good ABC; camera frame is a drawn PIL mock; no time-evolution |
| `api/main.py` | **REAL FastAPI / static-fake telemetry** | `/ws/telemetry` streams a hardcoded dict, shape-incompatible with the GCS |
| `cuas/counter_swarm.py`, `cognitive_ew.py`, `mitigation.py` | **STUB / THEATER** | `print("EW jamming authorized")`, string returns, empty module |
| v7.2 `comms/encrypted.py`, `security/quantum_resistant_full.py` | **FAKE CRYPTO** | labeled AES-256 / Kyber; actually returns a hash |

## Claims vs. reality

Four docs give four different, mutually inconsistent module counts (106 / 115 / 124 / 155) and LOC figures (128k / 143k / 146k) — a tell that they were generated, not measured. `STATUS.md` lists 90+ module filenames as evidence of "0 syntax errors" for code that largely doesn't exist. Treat every superlative in the `FINAL_*`, `GOD_MODE`, `SINGULARITY_*`, `CERTIFICATION_*`, `MILITARY_*` docs as **aspirational, not factual.**

## Legal / safety finding

No file implements RF jamming, Remote-ID spoofing/defeat, firmware rooting/patching, geofence bypass, or kinetic takedown. The only "offensive" content is:
- `cuas/counter_swarm.py` → a `print()` line, no SDR/transmit.
- `cognitive_ew.py` → returns countermeasure *strings*, no logic.
- Docs (`REPOS_ANALYSIS_REPORT.md`) that **name and explicitly exclude** third-party illegal tools ("Attack/jamming/hijacking tools are EXCLUDED per legal constraints").

**Recommendation:** delete the theater stubs (`counter_swarm.py`, `cognitive_ew.py`, `mitigation.py`) and the fake-crypto modules — they are non-functional and actively misleading. Keep the real detection/monitoring modules, which are legal and useful.

## What this `consolidated/` folder delivers

The working subset, made genuinely runnable and wired together live:
- `gcs-web/` — the React GCS, with its missing Vite build files added and a real browser-env bug fixed (`process.env` → `import.meta.env`). **Builds and runs.**
- `backend/serve.py` — a clean, honest live server. A simulator drives ground truth (battery drain, climb, waypoint motion); noisy GPS is filtered by the **real 22-state `skycore/navigation/aukf.py`**, and the filter's estimate is streamed in the exact shape the GCS expects. Every frame is tagged `source:"simulator"` + `nav_backend`.
- Verified end-to-end: browser **Takeoff** → WebSocket command → simulator flies → **real AUKF** filters it → live telemetry (FLYING, altitude climbing, battery draining) back in the GCS. A `goto` waypoint test tracked at ~9 m/s with ~0.4 m filter error, AUKF stable throughout.

## Suggested next steps

1. Adopt `src/skycore_v1.0.0/skycore/` as the single canonical Python package; delete `extracted/` and `v7.2` (or move to `archives/`).
2. Fix the canonical `api/main.py` to serve real evolving telemetry in the GCS shape (fold in `backend/serve.py`), and fix its fragile bare `core.` imports.
3. Delete theater/fake modules listed above.
4. Collapse the 145 docs to a handful of accurate ones; retire the inflated claims.
5. The real AUKF is now wired behind `serve.py`. Next: drive the genuine **control** (PID/MPC/LQR) and **C-UAS detection** modules from the live loop too.
