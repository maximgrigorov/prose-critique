FROM python:3.11-slim AS base

LABEL maintainer="prose-critique"
LABEL description="Prose analysis and critique tool"

RUN groupadd -r critique && useradd -r -g critique -m critique

WORKDIR /app

COPY requirements-web.txt .
RUN pip install --no-cache-dir -r requirements-web.txt

COPY modules/ ./modules/
COPY web/ ./web/
COPY main.py ./
COPY config.json ./config.json

RUN mkdir -p /app/workspace/logs /app/workspace/runs /app/workspace/cache \
    && chown -R critique:critique /app

VOLUME ["/app/workspace"]

USER critique

EXPOSE 8020

ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "web.app", "--host", "0.0.0.0", "--port", "8020"]
