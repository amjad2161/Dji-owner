#!/usr/bin/env bash
# SkyCore Singularity launcher (macOS / Linux / Git Bash)
# Builds the GCS, sets up the backend, and runs the WHOLE system as one process on http://localhost:8080
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "== SkyCore Singularity =="

# 1. Build the GCS if not already built
if [ ! -f "$root/gcs-web/dist/index.html" ]; then
  echo "Building GCS (npm install + build)..."
  ( cd "$root/gcs-web" && npm install && npm run build )
fi

# 2. Python venv + backend deps
venv="$root/backend/venv"
py="$venv/bin/python"; [ -f "$py" ] || py="$venv/Scripts/python.exe"
if [ ! -f "$py" ]; then
  echo "Creating Python venv..."
  { python3 -m venv "$venv" || python -m venv "$venv"; }
  py="$venv/bin/python"; [ -f "$py" ] || py="$venv/Scripts/python.exe"
fi
"$py" -m pip install -q -r "$root/backend/requirements.txt"

# 3. Run the single unified server (serves UI + telemetry/threat APIs + real AUKF/LQR/C-UAS)
echo "SkyCore up  ->  http://localhost:8080"
exec "$py" "$root/backend/serve.py"
