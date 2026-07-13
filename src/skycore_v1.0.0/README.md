# SkyCore - מערכת הפעלה לרחפנים אוטונומיים
## SkyCore - Autonomous Drone Operating System

**גרסה 1.0.0**

---

## תכונות עיקריות | Key Features

- **22-State AUKF Navigation** - מערכת ניווט מתקדמת עם Kalman Filter מותאם
- **Multi-Drone Support** - תמיכה ברחפנים מרובים ו-swarm
- **Computer Vision** - זיהוי אובייקטים עם YOLOv8
- **C-UAS Detection** - מערכת זיהוי והתגוננות מרחפנים לא מורשים
- **Mission Planning** - תכנון משימות עם Litchi CSV
- **Web GCS** - ממשק ניהול מבוסס Web
- **Emergency Failsafe** - מערכת בטיחות אוטומטית
- **Local AI** - תמיכה ב-Ollama להחלטות AI מקומיות

---

## התקנה | Installation

### דרישות מערכת | System Requirements

- Python 3.9+
- Windows 10/11 או Linux
- 4GB RAM מינימום (8GB מומלץ)
- GPU אופציונלי לזיהוי תמונה (CUDA supported)

### התקנה מהירה | Quick Install

```powershell
# 1. שכפל את התיקייה
cd SkyCore

# 2. התקן תלויות
pip install -r requirements.txt

# 3. התקן את החבילה
python setup.py install

# 4. הפעל
python run.py --simulator
```

### התקנה במצב פיתוח | Development Install

```powershell
pip install -e .[dev,simulation]
```

---

## שימוש | Usage

### מצב סימולטור (ברירת מחדל)

```powershell
python run.py --simulator
```

### התחבר לרחפן אמיתי | Connect Real Drone

```powershell
# DJI Tello
python run.py --tello

# MAVLink (PX4/ArduPilot)
python run.py --mavlink

# DJI Drone
python run.py --dji
```

### ממשק Web GCS

```powershell
python run.py --gui --port 8080
```
פתח בדפדפן: http://localhost:8080

### הרץ משימה | Run Mission

```powershell
python run.py --mission path/to/mission.csv --takeoff 30
```

---

## מבנה הפרויקט | Project Structure

```
SkyCore/
├── skycore/              # קוד ראשי
│   ├── navigation/        # מערכות ניווט (Kalman, EKF, AUKF, A*, RRT*)
│   ├── control/          # בקרי PID, LQR, MPC
│   ├── adapters/         # מתאמי רחפנים (Simulator, Tello, MAVLink, DJI)
│   ├── vision/           # ראייה ממוחשבת (YOLO, Visual Tracking)
│   ├── missions/          # ניהול משימות
│   ├── safety/           # מערכות בטיחות
│   ├── swarm/            # תיאום swarm
│   ├── ai_brain/         # מנוע AI
│   ├── weather/          # מזג אוויר
│   └── web/              # ממשק GCS
├── run.py                # נקודת כניסה
├── setup.py              # הגדרות התקנה
├── requirements.txt      # תלויות
└── README.md
```

---

## דוגמאות קוד | Code Examples

### חיבור לסימולטור

```python
import asyncio
from skycore.adapters.simulator import SimulatorDrone
from skycore.core.types import GeoPoint

async def main():
    drone = SimulatorDrone(home=GeoPoint(37.7749, -122.4194, 0.0))
    
    await drone.connect()
    await drone.takeoff(20.0)
    
    telemetry = await drone.get_telemetry()
    print(f"Position: {telemetry.position}")
    
    await drone.land()
    await drone.disconnect()

asyncio.run(main())
```

### ניווט עם Kalman Filter

```python
from skycore.navigation.kalman import KalmanFilter

kf = KalmanFilter(dim_x=6, dim_z=3)
kf.initialize([lat, lon, alt, vx, vy, vz])

state = kf.predict(dt=0.1)
kf.update(measurement)
```

### הרצת משימה

```python
from skycore.missions.litchi import LitchiMission
from skycore.missions.executor import MissionExecutor

mission = LitchiMission.from_csv("mission.csv")
# Convert and execute
```

---

## פקודות שימושיות | Useful Commands

```powershell
# בדיקת מודולים
python test_all_modules.py

# בדיקת אינטגרציה
python integration_test.py

# הפעלת סימולטור
python run.py --simulator

# הפעלת GCS
python run.py --gui --port 8080

# הרצת משימה
python run.py --mission mission.csv --takeoff 30
```

---

## תמיכה | Support

לבעיות ושאלות, בדוק:
1. שגיאות ב-`test_all_modules.py`
2. שגיאות ב-`integration_test.py`
3. לוגים בקובץ `skycore.log`

---

## רישיון | License

MIT License

---

## קרדיטים | Credits

פותח על ידי SkyCore Team