# התחלה מהירה

תוכנית של שבעה ימים — מהיום שפתחת את הקופסה ועד שיש לך זרימת עבודה אמיתית. בלי תכנות.

## לפני שמתחילים

- רחפן DJI Mavic (כל דגם נוכחי או יחסית עדכני — ראה [טבלת תאימות](../en/compatibility-matrix.md))
- מחשב Windows 10 או 11
- חשבון DJI רשום
- 30 GB פנויים בדיסק (DaVinci Resolve כבד)

## תוכנית שבעה ימים

### יום 1 — תשתית

1. הורד והתקן את [DJI Assistant 2 for Mavic](https://www.dji.com/downloads). הכלי הרשמי של DJI למחשב: עדכוני קושחה, כיולים, וסימולטור טיסה.
2. חבר את הרחפן ל-USB. בדוק עדכוני קושחה.
3. פתח את הסימולטור המובנה. תרגל 30 דקות לפני שאתה טס בחוץ. זה כלי האימון החינמי הכי פחות מנוצל של DJI.

### יום 2 — טיסה אמיתית, אפליקציה רשמית

1. התקן את האפליקציה הרשמית לדגם שלך:
   - **DJI Fly** — Mini 2 ומעלה, Air 2/2S/3, Mavic 3
   - **DJI GO 4** — Mavic 2, Mavic Pro, Air 1, Mini ישן
2. טיסה של 15 דקות באזור פתוח וחוקי בגובה נמוך. ודא נעילת GPS, גובה RTH, התנהגות סוללה.
3. תרגל שליטה ידנית ב-gimbal ובמצבי הטיסה (Position / Sport / Cine / Tripod).

### יום 3 — תכנון משימות עם Litchi (אם התומך)

Litchi היא האפליקציה החיצונית הכי טובה ל-DJI ישנים. $25 חד-פעמי. בדוק [טבלת תאימות](../en/compatibility-matrix.md) — ל-Mavic 3 / Mini 3+ / Air 3 זה **לא** עובד, דלג ליום 4.

1. הירשם ב-[flylitchi.com](https://flylitchi.com).
2. פתח את ה-**Mission Hub** בדפדפן במחשב. שם מתכננים משימות waypoint.
3. תכנן משימה פשוטה של 4 waypoints מעל פארק מקומי.
4. סנכרן לאפליקציה, טוס. זה הרגע הראשון של "מחשב מתכנן, רחפן מבצע".

### יום 4 — Pipeline פוסט קולנועי (Gyroflow + DaVinci Resolve)

1. התקן [Gyroflow](https://gyroflow.xyz). חינם, קוד פתוח, ייצוב gimbal מקצועי בפוסט.
2. התקן [DaVinci Resolve](https://www.blackmagicdesign.com/products/davinciresolve) — הגרסה החינמית מספיקה.
3. הורד את ה-[LUTs הרשמיים של DJI](https://www.dji.com/downloads) לדגם שלך.
4. צלם קליפ אחד ב-D-Log או D-Cinelike, העבר ב-Gyroflow, ואז עשה color grading עם ה-LUT ב-Resolve.

להדרכה מלאה, ראה [03-cinematic-video.md](../en/03-cinematic-video.md).

### יום 5 — שידור חי (OBS Studio)

1. התקן [OBS Studio](https://obsproject.com). חינם, קוד פתוח.
2. הגדר screen capture של הטלפון (USB tethering או mirror-to-PC של DJI).
3. הגדר פלט RTMP ל-YouTube Live או Twitch.
4. בדיקה: שידור 5 דקות מתוך הסימולטור.

פרטים: [06-streaming.md](../en/06-streaming.md).

### יום 6 — ניתוח לוגים (Airdata)

1. הירשם ב-[airdata.com](https://airdata.com). השכבה החינמית מספיקה לרוב החובבים.
2. חבר את Airdata לחשבון DJI Fly שלך, או העלה קובצי `.txt` ידנית.
3. קרא את הדוח הראשון. הסתכל על בריאות סוללה, רעידות, ומספר לוויינים לאורך זמן.

מה לחפש: [05-log-analysis.md](../en/05-log-analysis.md).

### יום 7 — בחר מסלול ולך לעומק

בשלב הזה יש לך בסיס מלא. בחר אחד מששת המסלולים והשקע בו את החודש הקרוב:

1. [שליטה מהמחשב](../en/01-pc-flight-control.md)
2. [מעקב חכם](../en/02-smart-tracking.md)
3. [וידאו קולנועי](../en/03-cinematic-video.md)
4. [תכנון משימות](../en/04-mission-planning.md)
5. [ניתוח לוגים](../en/05-log-analysis.md)
6. [שידור חי](../en/06-streaming.md)

## התקנה אוטומטית של Windows

אם אתה מעדיף הכל בפקודה אחת:

```powershell
iwr https://raw.githubusercontent.com/amjad2161/dji-owner/main/scripts/windows/install-toolkit.ps1 -UseBasicParsing | iex
```

ראה [scripts/windows/README.md](../../scripts/windows/README.md) לפרטים.
