"""
SkyCore FastAPI Server
REST + WebSocket for telemetry and mission control
"""

from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse, StreamingResponse
import asyncio
from typing import Dict
from core.drone import SimulatorDrone

app = FastAPI(title="SkyCore Drone API", version="5.0")

# In-memory state (in real: use DB)
drones: Dict = {}
telemetry_data = {"lat": 32.0853, "lon": 34.7818, "alt": 0, "battery": 95}
live_drone = SimulatorDrone()  # For live demo

@app.get("/")
async def root():
    return {"message": "SkyCore API - Legal Drone Control Platform", "status": "running"}

@app.get("/telemetry")
async def get_telemetry():
    return telemetry_data

@app.post("/mission/orbit")
async def start_orbit(radius: float = 60, waypoints: int = 12):
    # In full: trigger mission
    return {"status": "mission started", "type": "orbit", "radius": radius, "waypoints": waypoints}

@app.websocket("/ws/telemetry")
async def websocket_telemetry(websocket: WebSocket):
    await websocket.accept()
    while True:
        await websocket.send_json(telemetry_data)
        await asyncio.sleep(1)

# ========== LIVE CAMERA STREAM ==========
async def video_frame_generator():
    """Generate MJPEG stream from drone camera"""
    while True:
        frame_bytes = await live_drone.get_camera_frame()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        await asyncio.sleep(0.1)  # 10 FPS

@app.get("/video/live")
async def live_video():
    """Live drone camera feed (MJPEG stream)"""
    return StreamingResponse(
        video_frame_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

@app.websocket("/ws/video")
async def websocket_video(websocket: WebSocket):
    """WebSocket for real-time video frames (base64 JPEG)"""
    await websocket.accept()
    import base64
    while True:
        frame_bytes = await live_drone.get_camera_frame()
        b64_frame = base64.b64encode(frame_bytes).decode('utf-8')
        await websocket.send_json({"type": "video_frame", "data": b64_frame, "timestamp": "now"})
        await asyncio.sleep(0.2)

# Simple dashboard HTML
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    return """
    <html>
    <head>
        <title>SkyCore Security Dashboard</title>
        <style>
            body { font-family: Arial, sans-serif; background: #0a0a0a; color: #0f0; margin: 0; padding: 20px; }
            .header { text-align: center; border-bottom: 2px solid #0f0; padding-bottom: 10px; }
            .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-top: 20px; }
            .panel { background: #111; border: 1px solid #0f0; padding: 15px; border-radius: 8px; }
            h1, h2 { color: #0f0; text-shadow: 0 0 10px #0f0; }
            #video-feed { width: 100%; max-width: 640px; border: 3px solid #0f0; border-radius: 4px; }
            .status { color: #0f0; font-size: 14px; }
            pre { background: #000; padding: 10px; overflow: auto; }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🛡️ SKYCORE SECURITY - LIVE COMMAND CENTER</h1>
            <p class="status">🔴 LIVE | DRONE: MAVIC 3 PRO | MISSION: ACTIVE | THREAT LEVEL: LOW</p>
        </div>
        
        <div class="grid">
            <!-- LIVE VIDEO PANEL -->
            <div class="panel">
                <h2>📹 LIVE DRONE CAMERA</h2>
                <p>Real-time feed from drone camera (simulated for demo)</p>
                <img id="video-feed" src="/video/live" alt="Live Drone Camera Feed" style="width:100%; max-height: 400px; object-fit: contain;" />
                <div class="status">✅ Stream Active | 10 FPS | 1280x720 | Recording: ON</div>
                <button onclick="location.reload()">🔄 Refresh Stream</button>
            </div>
            
            <!-- TELEMETRY PANEL -->
            <div class="panel">
                <h2>📡 TELEMETRY</h2>
                <div id="telemetry"></div>
                <p><a href="/video/live" target="_blank">Direct MJPEG Stream</a> | <a href="/ws/video" target="_blank">WebSocket Video</a></p>
            </div>
        </div>
        
        <script>
            // Telemetry WebSocket
            const ws = new WebSocket('ws://localhost:8080/ws/telemetry');
            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                document.getElementById('telemetry').innerHTML = '<pre>' + JSON.stringify(data, null, 2) + '</pre>';
            };
            
            // Video WebSocket (alternative)
            const videoWs = new WebSocket('ws://localhost:8080/ws/video');
            videoWs.onmessage = (event) => {
                const msg = JSON.parse(event.data);
                if (msg.type === 'video_frame') {
                    // Could update a canvas or second image here if needed
                    console.log('Video frame received via WS');
                }
            };
            
            console.log('SkyCore Dashboard initialized - Live video + telemetry ready');
        </script>
    </body>
    </html>
    """
