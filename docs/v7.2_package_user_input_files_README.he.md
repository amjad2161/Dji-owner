# מרכז שליטה לרחפני DJI — Drone Mastery Hub

> ערכת כלים קהילתית, חוקית לחלוטין, להוצאת המקסימום מרחפן ה-DJI Mavic שלך. כוללת את **SkyCore** — רמת-ריצה פייתונית מאוחדת שמאגדה את כל כלי הקוד הפתוח המרכזיים בעולם הרחפנים ל-runtime אחד קוהרנטי.

עברית · **[English](README.md)**

---

## שתי דרכים להשתמש

### 1. טייסים — התקן כלי GUI ועקוב אחרי המדריכים

המתקן ל-Windows וששת המסלולים העיקריים. ראה [Getting Started](docs/he/getting-started.md).

### 2. מפתחים — השתמש ב-SkyCore

`skycore/` היא פלטפורמת הפעלה מואחדת לרחפנים. API אסינכרוני אחד מעל ה-DJI, MAVLink (PX4 / ArduPilot), Tello, וסימולטור מובנה. מפתחים משימות, ראייה ממוחשבת ו-dashboards בלי חומרה — אותו הקוד רץ מול כל מערכת.

```python
import asyncio
from skycore import SimulatorDrone, GeoPoint
from skycore.missions import orbit_mission

async def main():
    poi = GeoPoint(37.7749, -122.4194)
    drone = SimulatorDrone(home=poi)
    mission = orbit_mission(poi, radius_m=60, altitude_m=40, waypoints=12)
    async with drone:
        await mission.execute(drone)

asyncio.run(main())
```

## מה ש-SkyCore כוללת

| שכבה | מה היא עושה |
|------|--------------|
| **מתאמים** | Simulator, Tello, MAVLink, DJI bridge |
| **ליבה** | ממשק `Drone`, `Telemetry`, `SafeDrone` (גדר גיאו + RTH + סוללה), `EventBus` |
| **משימות** | מנוע waypoints, מחוללי orbit / lawnmower-survey, ייבוא/יצוא Litchi CSV |
| **ראייה** | מזהה YOLO + מעקב BoT-SORT + בקר visual-follow |
| **וידאו** | מקליט H.264/H.265, streamer RTMP, מעטפת Gyroflow CLI |
| **אנליטיקה** | מנתח CSV לוגי טיסה עם `FlightSummary` מובנה |
| **API** | FastAPI REST + WebSocket telemetry + dashboard כהה |
| **CLI** | `skycore serve / mission / analyze` |
| **דיפלוי** | `docker compose up` — סימולטור רצים על :8080 |

התיעוד המלא: [docs/en/skycore-architecture.md](docs/en/skycore-architecture.md), [docs/en/skycore-getting-started.md](docs/en/skycore-getting-started.md).

## שישה מסלולי יכולת

| # | מסלול | מה תשיג |
|---|-------|---------|
| 1 | [שליטה מהמחשב](docs/en/01-pc-flight-control.md) | טיסה בלי טלפון |
| 2 | [מעקב חכם](docs/en/02-smart-tracking.md) | מעקב אובייקטים מתקדם |
| 3 | [וידאו קולנועי](docs/en/03-cinematic-video.md) | Pipeline פוסט מלא |
| 4 | [תכנון משימות](docs/en/04-mission-planning.md) | Waypoints + מיפוי |
| 5 | [ניתוח לוגים](docs/en/05-log-analysis.md) | זיהוי תקלות |
| 6 | [שידור חי](docs/en/06-streaming.md) | YouTube / Twitch / Facebook |

## התחלה מהירה

### טייסים (כלי GUI ל-Windows)

```powershell
iwr https://raw.githubusercontent.com/amjad2161/dji-owner/main/scripts/windows/install-toolkit.ps1 -UseBasicParsing | iex
```

### מפתחים (SkyCore)

```bash
git clone https://github.com/amjad2161/dji-owner.git
cd dji-owner
pip install -e ".[api,analytics]"
skycore serve --backend simulator     # → http://localhost:8080
```

או דרך Docker:

```bash
docker compose up
```

### שכפול כל ה-SDK המרכזיים

```powershell
iwr https://raw.githubusercontent.com/amjad2161/dji-owner/main/scripts/windows/clone-dev-repos.ps1 -UseBasicParsing | iex
```

מוריד DJI MSDK / OSDK / PSDK / Tello-Python, PX4, ArduPilot, MAVSDK, QGroundControl, Gyroflow, YOLO, BoxMOT, OpenDroneMap, ו-DJITelloPy אל תוך `~/dji-dev/`.

## תאימות מהירה

| משפחה | טיסה ממחשב | Litchi | ActiveTrack | Mobile SDK | SkyCore דרך |
|-------|-------------|--------|-------------|------------|-----------|
| Mavic 3 / 3 Pro / 3 Cine | חלקי | ❌ | 5.0 | V5 | DJI bridge |
| Mavic 3 Enterprise | כן | ❌ | 5.0 | V5 | PSDK |
| Mavic Air 3 / 2S / 2 | מוגבל | רק Air 2 | 4.0 / 5.0 | V5 / V4 | DJI bridge |
| Mini 4 Pro / 3 Pro | מוגבל | ❌ | 360° / 4.0 | V5 | DJI bridge |
| Mini 2 / SE | בסיסי | ❌ | ❌ | ❌ | — |
| Mavic 2 Pro / Zoom | כן | ✅ | 2.0 | V4 | DJI bridge (legacy) |
| Tello / Tello EDU | Native | ❌ | n/a | Tello SDK | TelloDrone |
| כל PX4 / ArduPilot | כן | ❌ | n/a | n/a | MavlinkDrone |

## חוקיות ובטיחות

הפרויקט פועל **בתוך** ה-SDK של היצרן וכללי התעופה הלאומיים. אנחנו **לא** מפרסמים: הסרת NFZ, הגברת הספק שידור, עקיפת Remote ID, או הסרת מגבלות גובה/מהירות מעבר למה ש-DJI חושף רשמית. ראה [legal-and-safety](docs/he/legal-and-safety.md).

## סטטוס

🚧 Alpha. הליבה של SkyCore (סימולטור + משימות + אנליטיקה + API) נבדקה ועובדת. מתאמי חומרה אמיתית מממשים את אותו חוזה. תרומות מתקבלות בברכה — ראה [CONTRIBUTING.md](CONTRIBUTING.md).

## רישיון

MIT — ראה [LICENSE](LICENSE).
