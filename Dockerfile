FROM python:3.13-slim

RUN apt-get update && apt-get install -y \
    espeak-ng \
    espeak-ng-data \
    libespeak-ng-dev \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# pyttsx3 hardcodes the default voice as "gmw/en" but espeak-ng reorganised
# voice paths — create a minimal voice definition so SetVoiceByName doesn't crash
RUN ESPEAK_DATA=$(find /usr/lib -maxdepth 4 -name "espeak-ng-data" -type d 2>/dev/null | head -1) && \
    mkdir -p "${ESPEAK_DATA}/voices/gmw" && \
    printf 'name en\nlanguage en\n' > "${ESPEAK_DATA}/voices/gmw/en"

ENV ESPEAK_DATA_PATH=/usr/lib/x86_64-linux-gnu/espeak-ng-data

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock* ./

RUN uv sync --frozen --no-dev

COPY src/ ./src/
COPY config/ ./config/

RUN mkdir -p /tmp/tts_output

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "tts_service.main:app", "--host", "0.0.0.0", "--port", "8000"]
