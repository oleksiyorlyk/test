ARG PLAYWRIGHT_VERSION=1.64.1
FROM ghcr.io/astral-sh/uv:0.13.7 AS uv
FROM mcr.microsoft.com/playwright:v${PLAYWRIGHT_VERSION}-noble
ARG PLAYWRIGHT_VERSION
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PATH="/opt/venv/bin:${PATH}"
ENV UV_PROJECT_ENVIRONMENT=/opt/venv UV_PYTHON_DOWNLOADS=never
COPY --from=uv /uv /uvx /usr/local/bin/
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-venv \
    && python3 -m venv /opt/venv && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml uv.lock /app/
RUN uv sync --frozen --no-dev --no-install-project
WORKDIR /app/runner
COPY runner/package.json runner/package-lock.json ./
RUN npm ci --no-audit --no-fund \
    && PLAYWRIGHT_EXPECTED=${PLAYWRIGHT_VERSION} node -e "if(require('@playwright/test/package.json').version !== process.env.PLAYWRIGHT_EXPECTED) process.exit(1)"
WORKDIR /app
COPY backend/ /app/backend/
COPY runner/ /app/runner/
COPY target-app/ /app/target-app/
RUN mkdir -p /app/backend/data/control /app/runner/generated-tests /app/runner/test-results /app/runner/playwright-report
EXPOSE 8001
CMD ["python", "-m", "uvicorn", "backend.api:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1"]
