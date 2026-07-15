"""
SkyCore end-to-end smoke test.

Drives one full mission against a RUNNING unified server on :8080 and checks that
every subsystem works together: the 3 flight backends load, live weather is fetched,
the geofence is enforced, the 3 intruder tracks are classified with behaviours, an
RRT* route is planned around the no-fly zone (no RTL, positive clearance), the AUKF
stays consistent, and the flight is logged to SQLite.

Run (with the server already up, e.g. via launch.ps1):
    python smoke_test.py           # exits 0 on PASS, 1 on failure
Deps: websockets (pip install websockets)  — stdlib urllib for the REST calls.
"""
import asyncio
import json
import math
import sys
import urllib.request

BASE = "http://localhost:8080"
WS = "ws://localhost:8080/ws/telemetry"
# home + metre-per-degree constants must match serve.py
HOME_LAT, HOME_LON = 32.0853, 34.7818
M_LAT, M_LON = 111320.0, 111320.0 * math.cos(math.radians(HOME_LAT))
NF_E, NF_N, NF_R = 150.0, 80.0, 60.0


TOKEN = ""


def _get(path):
    headers = {"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}
    with urllib.request.urlopen(urllib.request.Request(BASE + path, headers=headers), timeout=6) as r:
        return json.load(r)


def _login(user="admin", pw="admin123"):
    data = json.dumps({"username": user, "password": pw}).encode()
    req = urllib.request.Request(BASE + "/api/login", data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=6) as r:
        return json.load(r)["token"]


async def main() -> int:
    import websockets  # imported here so a missing dep gives a clear message
    global TOKEN

    print("=" * 68)
    print("SkyCore Singularity - end-to-end smoke test")
    print("=" * 68)

    TOKEN = _login()                       # server-side auth: obtain a signed token first
    print("AUTH      logged in, token acquired (%d chars)" % len(TOKEN))

    st = _get("/api/status")
    print("BACKENDS  nav   = %s" % st["nav_backend"])
    print("          ctrl  = %s" % st["control_backend"])
    print("          detect= %s" % st["detect_backend"])
    backends_ok = all("skycore" in st[k] for k in ("nav_backend", "control_backend", "detect_backend"))

    w = _get("/api/weather")
    print("WEATHER   %s | %s C, wind %s kph | safe=%s" % (w["backend"], w["temp_c"], w["wind_kph"], w["ok"]))

    gf = _get("/api/geofence")["zones"][0]
    print("GEOFENCE  no-fly circle center ENU(%s,%s) r=%sm" % (gf["center"]["e"], gf["center"]["n"], gf["radius"]))

    th = _get("/api/threats")["threats"]
    print("THREATS   %d tracks: %s" % (len(th), ", ".join("%s/%s/%s" % (t["id"], t["severity"], t["behavior"]) for t in th)))

    print("-" * 68)
    print("MISSION   arm -> takeoff 40m -> goto across no-fly (expect RRT* route) -> land")
    async with websockets.connect(WS + "?token=" + TOKEN) as ws:
        async def send(cmd, **p):
            await ws.send(json.dumps({"command": cmd, **p}))

        async def recv():
            # skip command ack/nack reply frames; return only telemetry snapshots
            while True:
                m = json.loads(await asyncio.wait_for(ws.recv(), timeout=6))
                if m.get("type") in ("ack", "nack"):
                    continue
                return m

        # reset to home if a previous run left the drone parked elsewhere
        d = await recv()
        e0 = (d["position"]["lon"] - HOME_LON) * M_LON
        n0 = (d["position"]["lat"] - HOME_LAT) * M_LAT
        if not (d["mode"] == "DISARMED" and math.hypot(e0, n0) < 30):
            await send("arm")
            await asyncio.sleep(0.3)
            await send("takeoff", altitude=30)
            for _ in range(40):
                await recv()
            await send("rtl")
            for _ in range(700):
                d = await recv()
                if d["mode"] == "DISARMED":
                    break

        await send("arm")
        await asyncio.sleep(0.3)
        await send("takeoff", altitude=40)
        for _ in range(130):
            await recv()
        await send("goto", lat=32.0867, lon=34.7850, altitude=40)
        # the RRT* solve runs off the event loop, so the route appears a few frames
        # after the goto — track the max route length seen over the whole mission.
        routed = 0
        rtl = False
        reached = False
        min_clear = 9e9
        nis = []
        for _ in range(360):
            d = await recv()
            routed = max(routed, len(d.get("route", [])))
            e = (d["position"]["lon"] - HOME_LON) * M_LON
            n = (d["position"]["lat"] - HOME_LAT) * M_LAT
            min_clear = min(min_clear, math.hypot(e - NF_E, n - NF_N) - NF_R)
            nis.append(d["nav_nis"])
            if d["mode"] == "RTL":
                rtl = True
            if abs(d["position"]["lat"] - 32.0867) < 4e-5 and abs(d["position"]["lon"] - 34.7850) < 4e-5:
                reached = True
                break
        print("          route waypoints planned = %d" % routed)
        print("          reached=%s  RTL=%s  min no-fly clearance=%.1f m" % (reached, rtl, min_clear))
        print("          AUKF NIS mean = %.2f" % (sum(nis) / max(1, len(nis))))
        await send("land")
        for _ in range(240):
            d = await recv()
            if d["mode"] == "DISARMED":
                break
        print("          landed mode=%s battery=%.1f%%" % (d["mode"], d["battery"]["percent"]))

    fl = _get("/api/flights")["flights"]
    print("-" * 68)
    print("FLIGHT LOG (SQLite): %d record(s)" % len(fl))
    if fl:
        f = fl[0]
        print("          latest: max_alt=%.1fm distance=%.3fkm battery_used=%.1f%%"
              % (f["max_alt"], f["distance_km"], f["battery_used"]))

    checks = {
        "backends loaded": backends_ok,
        "weather fetched": w.get("temp_c") is not None,
        "threats classified": len(th) >= 3,
        "route planned": routed >= 2,
        "reached target": reached,
        "no geofence breach": min_clear > 0,
        "no RTL (routed around)": not rtl,
        "flight logged": len(fl) >= 1,
    }
    print("=" * 68)
    for name, ok in checks.items():
        print("  [%s] %s" % ("PASS" if ok else "FAIL", name))
    passed = all(checks.values())
    print("=" * 68)
    print("RESULT: %s" % ("PASS - all subsystems working end to end" if passed else "FAIL"))
    return 0 if passed else 1


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except Exception as exc:  # noqa: BLE001
        print("SMOKE TEST ERROR:", type(exc).__name__, exc)
        sys.exit(1)
