# מדריך משתמש — SkyCore Security v7.0

**גרסה:** 7.0 SINGULARITY  
**תאריך:** 8 במאי 2026

---

## 1. התחלה מהירה

### 1.1 התקנה
```bash
docker-compose up -d
open http://localhost:8080/dashboard
```

### 1.2 כניסה ראשונית
1. פתח את הדשבורד
2. בחר רחפן ירוק (שלך)
3. לחץ על המפה להגדרת נקודת יעד
4. הגדר גובה, מהירות ותאורה
5. לחץ "EXECUTE MISSION"

---

## 2. פקודות CLI עיקריות

```bash
# דמו מלא
python cli.py master-everything

# Counter-UAS
python cli.py counter_uas

# משימות
python cli.py orbit
python cli.py persistent
python cli.py coordinated
python cli.py building
python cli.py spiral
python cli.py reveal

# בדיקת סטטוס
python cli.py status
```

---

## 3. ממשק הדשבורד

### 3.1 בחירת רחפן
- **ירוק** = רחפן שלך (ניתן לשליטה)
- **אדום** = רחפן חשוד/עוין (לא ניתן לשליטה)

### 3.2 הגדרת משימה
- **גובה** — 10-500 מטר
- **מהירות** — 1-30 מ'/שנייה
- **תאורה** — Off / Low / Medium / High / Strobe

### 3.3 פקודות חירום
- **EMERGENCY LOCKDOWN** — עצירת כל הרחפנים
- **LAUNCH DEFENSIVE SWARM** — הפעלת נחיל הגנתי

---

## 4. משימות נפוצות

| משימה | פקודה | תיאור |
|-------|-------|-------|
| Orbit | `python cli.py orbit` | הקפה סביב נקודה |
| Persistent Surveillance | `python cli.py persistent` | סיור 24/7 |
| Coordinated Mission | `python cli.py coordinated` | משימה מתואמת |
| Building Inspection | `python cli.py building` | בדיקת בניין |
| Cinematic Reveal | `python cli.py reveal` | Reveal דרמטי |

---

## 5. אבטחה

- **Zero-Trust** — כל פקודה מאומתת
- **Encrypted** — כל התקשורת מוצפנת
- **Audit Log** — כל פעולה מתועדת
- **Emergency Lockdown** — עצירה מיידית

---

## 6. תמיכה

**לשאלות:** פנה למפתח המערכת

**גרסה:** 7.0 SINGULARITY  
**סטטוס:** מוכן לפריסה

---

**SkyCore Security Team**  
8 במאי 2026
