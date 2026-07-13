"""
SkyCore Professional Security Dashboard
Simple but effective command center interface
"""

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

security_app = FastAPI(title="SkyCore Security Command Center")

@security_app.get("/", response_class=HTMLResponse)
async def dashboard():
    return """
    <html>
    <head><title>SkyCore Security Command Center</title></head>
    <body style="background:#0a0a0a; color:#00ff00; font-family:monospace">
        <h1>🛡️ SKYCORE SECURITY COMMAND CENTER</h1>
        <h2>Status: OPERATIONAL</h2>
        <div id="threats"></div>
        <script>
            // In real version: WebSocket connection to live threats
            console.log("Security Dashboard loaded");
        </script>
    </body>
    </html>
    """
