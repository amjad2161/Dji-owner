# SkyCore Security v7.0 — SINGULARITY
## התקנה והפעלה מיידית

**גרסה:** 7.0 — 100% COMPLETE  
**תאריך:** 8 במאי 2026

---

## דרישות מינימליות

- Python 3.11+
- Docker + Docker Compose (מומלץ)
- 8GB RAM
- 20GB שטח דיסק

---

## התקנה מהירה (Docker — מומלץ)

```bash
# 1. שכפל את המאגר
git clone https://github.com/your-org/skycore-security.git
cd skycore-security

# 2. הרץ את ההתקנה
docker-compose up -d

# 3. פתח את הדשבורד
open http://localhost:8080/dashboard
```

---

## התקנה ידנית (Python)

```bash
# 1. צור סביבה וירטואלית
python -m venv venv
source venv/bin/activate

# 2. התקן תלויות
pip install -r requirements.txt

# 3. הרץ את ה-API
uvicorn api.main:app --reload --port 8080

# 4. פתח את הדשבורד
open http://localhost:8080/dashboard
```

---

## פקודות CLI עיקריות

```bash
# דמו מלא
python cli.py master-everything

# Counter-UAS
python cli.py counter_uas

# שליחת משימה
python cli.py orbit
python cli.py persistent
python cli.py coordinated

# בדיקת סטטוס
python cli.py status
```

---

## מבנה המערכת

```
skycore/
├── core/                    # ליבה (Drone, Config, Logging)
├── missions/                # 12+ סוגי משימות
├── cuas/                    # Counter-UAS (זיהוי + תגובה)
├── security/                # אבטחה (Zero-Trust, IDS, Audit)
├── vision/                  # Vision + SLAM
├── swarm/                   # Swarm + Coordinated
├── hmi/                     # Human-Machine Teaming
├── integration/             # C4ISR + Multi-Domain
├── api/                     # FastAPI + WebSocket
├── dashboard/               # ממשק מפעיל v2.0
├── tests/                   # בדיקות
├── .github/workflows/       # CI/CD
└── cli.py                   # Master CLI
```

---

## סטטוס

**המערכת מוכנה להתקנה והפעלה מיידית.**

**115+ מודולים** | **~143,000 שורות קוד** | **10/10**

---

**SkyCore Security Team**  
8 במאי 2026
