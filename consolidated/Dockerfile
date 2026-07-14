# SkyCore Singularity — one container, one port (8080).
# Stage 1 builds the GCS; stage 2 runs the unified server (UI + telemetry/threat
# WS + real AUKF/LQR/C-UAS). The real modules are vendored under backend/skycore/,
# so the image is self-contained.

# ---- stage 1: build the GCS ----
FROM node:20-alpine AS gcs
WORKDIR /gcs
COPY gcs-web/package*.json ./
RUN npm ci
COPY gcs-web/ ./
RUN npm run build

# ---- stage 2: python runtime ----
FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/ ./backend/
COPY --from=gcs /gcs/dist ./gcs-web/dist
# run as a non-root user; the container network boundary is the isolation, so bind
# 0.0.0.0 INSIDE the container (the app defaults to loopback outside Docker)
RUN useradd --system --uid 10001 skycore && chown -R skycore /app
USER skycore
ENV SKYCORE_HOST=0.0.0.0 SKYCORE_DB=/app/backend/flights.db
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=4s --start-period=10s \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/api/healthz',timeout=3).status==200 else 1)"
# serve.py finds the GCS at ../gcs-web/dist and the real modules at ./skycore
CMD ["python", "backend/serve.py"]
