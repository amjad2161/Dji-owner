# SkyCore Singularity — one container, one port (8080).
# Stage 1 builds the GCS; stage 2 runs the unified server (UI + telemetry/threat
# WS + real AUKF/LQR/C-UAS). The real modules are vendored under backend/skycore/,
# so the image is self-contained.

# ---- stage 1: build the GCS ----
FROM node:20-alpine AS gcs
WORKDIR /gcs
COPY gcs-web/package*.json ./
RUN npm install
COPY gcs-web/ ./
RUN npm run build

# ---- stage 2: python runtime ----
FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/ ./backend/
COPY --from=gcs /gcs/dist ./gcs-web/dist
EXPOSE 8080
# serve.py finds the GCS at ../gcs-web/dist and the real modules at ./skycore
CMD ["python", "backend/serve.py"]
