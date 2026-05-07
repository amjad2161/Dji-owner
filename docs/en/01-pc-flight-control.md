# Track 1 — PC Flight Control

Fly your drone without your phone. Three approaches, ranked by complexity.

## Why this track

- Phones overheat in summer. Tablets are awkward. The standalone DJI RC 2 already removed the phone for many pilots, but you still can't *plan, monitor and analyze* from a desktop.
- For mission-style work — surveying, repeated camera moves, multi-flight projects — a PC is enormously more productive.

## Approach 1 — Standalone DJI RC 2 (easiest)

For: Mavic 3 family, Air 3, Mini 4 Pro, Mini 3 Pro (when bundled).

**Setup:**
1. The DJI RC 2 has a built-in screen running DJI Fly. No phone or PC needed in flight.
2. Use a PC only for **post-flight**: connect the RC over USB, import footage and logs.

**Limitations:**
- You're still using DJI Fly. No mission scripting, no third-party apps.

## Approach 2 — DJI Assistant 2 simulator + USB control (intermediate)

For: All Mavic models, including legacy.

**What this gives you:**
- A high-fidelity flight simulator that uses your real RC + drone.
- Practice indoors, log practice flights, build muscle memory.
- Verify firmware and calibrations.

**Setup:**
1. Install [DJI Assistant 2](https://www.dji.com/downloads) for your drone family. Note: the Mavic 3 series uses **DJI Assistant 2 for Mavic** specifically.
2. Plug the drone into your PC via USB-C.
3. Power on the drone (props off!).
4. Open Assistant 2, click **Simulator**.
5. Power on the RC and connect to the drone normally.
6. The RC sticks now drive the simulated drone on screen.

**Pro tips:**
- Use a USB-C hub to charge the drone while simulating long sessions.
- Try Sport mode practice in the simulator to learn yaw rates without crashing your real drone.

## Approach 3 — DJI Pilot 2 on a Windows tablet (Enterprise drones only)

For: Mavic 3 Enterprise / Thermal / Multispectral, Matrice series.

**What this gives you:**
- Full flight control from a Windows tablet — no phone at all.
- Mission planning, live mapping, payload triggers.

**Setup:**
- DJI Pilot 2 ships with the Smart Controller Enterprise. For tablet use, contact DJI Enterprise channels — it's not a public download.

## Approach 4 — Custom Mobile SDK app via Bridge (advanced, requires development)

For: Anyone willing to write code.

**What this gives you:**
- Build your own flight app and run it on a Windows machine via Android emulator or a USB-tethered Android device, with the RC connected to the drone.
- Mobile SDK V5 includes a **Bridge App** sample that proxies SDK calls between your dev machine and the RC.

**Setup:**
1. Register at [developer.dji.com](https://developer.dji.com) and get an App Key.
2. Clone [`dji-sdk/Mobile-SDK-Android`](https://github.com/dji-sdk/Mobile-SDK-Android).
3. Open the **Bridge** sample in Android Studio.
4. Build and install the bridge app on a phone connected to the RC.
5. Run your dev app on a desktop emulator that connects to the bridge IP.

**Realistic timeline:** 4–8 weeks to a working custom flight app, assuming Android Java/Kotlin background. Not a beginner project — but worth it for repeat workflows.

## Joystick / gamepad control

Independent of approach, you can use a USB joystick or Xbox controller for desktop flight if you go the SDK route. The Mobile SDK exposes Virtual Sticks — `setVirtualStick()` accepts pitch, roll, yaw, throttle vectors that match a standard gamepad layout.

Reference projects:
- [`mavlink/QGroundControl`](https://github.com/mavlink/qgroundcontrol) — for MAVLink-compatible drones (not DJI by default, but instructive).
- DJI Mobile SDK `VirtualStickSample` — included in the SDK repo.

## What this track does NOT do

- Does not unlock features your drone doesn't physically have.
- Does not let you skip RC pairing — you still need a real DJI RC.
- Does not bypass any geofencing.
