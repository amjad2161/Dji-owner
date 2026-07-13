FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml requirements.txt ./
COPY skycore ./skycore

RUN pip install --no-cache-dir -e .[api,analytics]

EXPOSE 8080

CMD ["skycore", "serve", "--host", "0.0.0.0", "--port", "8080"]
