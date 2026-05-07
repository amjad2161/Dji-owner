# מרכז שליטה לרחפני DJI — Drone Mastery Hub

> ערכת כלים קהילתית, חוקית לחלוטין, להוצאת המקסימום מרחפן ה-DJI Mavic שלך — בלי לשנות קושחה, בלי לעקוף מערכות בטיחות, ובלי להפר את חוקי התעופה.

עברית · **[English](README.md)**

---

## מה זה

מדריך אוצר ומסודר למשתמשי Mavic שרוצים להוציא את המקסימום מהרחפן שלהם — **רק באמצעות SDK רשמיים, כלים נתמכים, ותוכנות קהילה חוקיות**. בלי תיקוני קושחה, בלי הסרת אזורי אי-טיסה, בלי הגברת הספק שידור. רק את כל מה שאפשר לעשות בצורה לגיטימית — מוסבר היטב, עם כלים אמיתיים שמסופקים בריפו הזה.

## למי זה מיועד

- **טייסים חדשים** שזה עתה רכשו Mavic ורוצים מפת דרכים מלאה
- **חובבים** שעברו את שלב DJI Fly ורוצים יותר
- **יוצרי תוכן** שרודפים אחרי לקטעי וידאו קולנועיים
- **צלמים ומומחי GIS** שבונים זרימות עבודה חוזרות
- **מפתחים** שמוכנים לבנות מעל ה-DJI Mobile / Onboard SDK

## שישה מסלולי יכולת

| # | מסלול | מה תשיג |
|---|-------|---------|
| 1 | [שליטה מהמחשב](docs/en/01-pc-flight-control.md) | טיסה בלי טלפון — לפטופ + שלט + ג'ויסטיק |
| 2 | [מעקב חכם](docs/en/02-smart-tracking.md) | מעקב אובייקטים מעבר ל-ActiveTrack ברירת המחדל |
| 3 | [וידאו קולנועי](docs/en/03-cinematic-video.md) | Pipeline פוסט: D-Log → Gyroflow → DaVinci Resolve |
| 4 | [תכנון משימות](docs/en/04-mission-planning.md) | Waypoints תלת-ממדיים, צילומים חוזרים, מיפוי |
| 5 | [ניתוח לוגים](docs/en/05-log-analysis.md) | זיהוי תקלות לפני שהן הופכות להתרסקויות |
| 6 | [שידור חי](docs/en/06-streaming.md) | שידור הטיסה ל-YouTube / Twitch / Facebook בזמן אמת |

## מה יש בריפו

```
dji-owner/
├─ docs/                       תיעוד דו-לשוני (en + he)
├─ scripts/windows/             סקריפטי PowerShell להתקנה ולהסדרה
├─ tools/log-analyzer/         מנתח לוגים בפייתון
└─ presets/litchi-missions/    תבניות משימות Litchi
```

## התחלה מהירה (Windows)

```powershell
# 1. התקנת כל ה-GUI tools (DaVinci, OBS, Python, Git, scrcpy, VLC, ...)
iwr https://raw.githubusercontent.com/amjad2161/dji-owner/main/scripts/windows/install-toolkit.ps1 -UseBasicParsing | iex

# 2. אופציונלי — שכפול כל ה-SDKs (DJI MSDK, OSDK, PSDK, MAVLink, Gyroflow,
#    ODM, YOLO, BoxMOT, ...) אל תוך ~/dji-dev/
iwr https://raw.githubusercontent.com/amjad2161/dji-owner/main/scripts/windows/clone-dev-repos.ps1 -UseBasicParsing | iex
```

להתקנה ידנית, ראה [Getting Started](docs/en/getting-started.md).

## המערכת הקהילתית

הקטלוג המלא של הריפויים הקשורים ב-GitHub מתועד בקובץ [docs/en/awesome-drone-repos.md](docs/en/awesome-drone-repos.md): SDK רשמיים של DJI, מערכות קוד פתוח (PX4, ArduPilot), תחנות קרקע (QGroundControl, MAVSDK), Gyroflow, YOLO + tracking, OpenDroneMap, ו-Tello-Python ללומדים. הסקריפט `clone-dev-repos.ps1` מוריד את כולם בפקודה אחת.

## תאימות מהירה

לא כל רחפן תומך בכל זרימה. בדוק את [טבלת התאימות המלאה](docs/en/compatibility-matrix.md) לפני שאתה מתחייב.

| משפחה | טיסה ממחשב | Litchi | ActiveTrack | Mobile SDK | Onboard / Payload SDK |
|-------|-------------|--------|-------------|------------|------------------------|
| Mavic 3 / 3 Pro / 3 Cine | חלקי | ❌ | 5.0 | V5 | ❌ |
| Mavic 3 Enterprise / Thermal | כן | ❌ | 5.0 | V5 | כן (PSDK) |
| Mavic Air 3 / Air 2S / Air 2 | מוגבל | רק Air 2 | 4.0 / 5.0 | V5 / V4 | ❌ |
| Mini 4 Pro / Mini 3 Pro | מוגבל | ❌ | 360° / 4.0 | V5 | ❌ |
| Mini 2 / Mini SE | בסיסי | ❌ | ❌ | ❌ | ❌ |
| Mavic 2 Pro / Zoom | כן | ✅ | 2.0 | V4 | ❌ |
| Mavic Pro / Air 1 | כן | ✅ | 1.0 | V4 (legacy) | ❌ |

## חוקיות ובטיחות

הפרויקט פועל **בתוך** ה-SDK של היצרן וכללי התעופה הלאומיים. אנחנו **לא** מפרסמים:

- תיקוני קושחה שמשביתים אזורי אי-טיסה (NFZ / Geofencing)
- כלים שחורגים מהספק שידור חוקי (מגבלות FCC / CE / MIC / SRRC)
- שיטות לעקוף Remote ID
- הסרת מגבלות גובה או מהירות מעבר למה ש-DJI חושף רשמית

האחריות לציית לחוקים המקומיים (רת"א / FAA / EASA / וכו') היא שלך. ראה [legal-and-safety](docs/he/legal-and-safety.md) לפירוט.

## סטטוס

🚧 בשלב מוקדם, מונע קהילה. תרומות מתקבלות בברכה — ראה [CONTRIBUTING.md](CONTRIBUTING.md).

## רישיון

MIT — ראה [LICENSE](LICENSE).
