FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev || uv sync --no-dev
COPY . .
EXPOSE 8000
# $PORT is provided by Railway; falls back to 8000 for `docker run` / compose.
CMD ["sh", "-c", "uv run uvicorn platform_api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
