FROM python:3.11-slim

LABEL maintainer="prose-critique"
LABEL description="Prose analysis and critique tool"

RUN groupadd -r critique && useradd -r -g critique -m critique

WORKDIR /app

COPY requirements-web.txt .
RUN pip install --no-cache-dir -r requirements-web.txt

COPY . .

RUN mkdir -p workspace/logs workspace/runs workspace/cache && \
    chown -R critique:critique /app

USER critique

EXPOSE 8020

CMD ["python", "-m", "web.app", "--host", "0.0.0.0", "--port", "8020"]
