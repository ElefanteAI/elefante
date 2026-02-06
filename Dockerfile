FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Basic build tooling for any wheels that may need compilation.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Persist Elefante state outside the container.
ENV ELEFANTE_DATA_DIR=/data
RUN mkdir -p /data

EXPOSE 8000

# Default: run the dashboard server (HTTP on port 8000).
CMD ["python", "-m", "src.dashboard.server"]
