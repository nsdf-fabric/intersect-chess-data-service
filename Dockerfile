FROM python:3.11-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY pyproject.toml uv.lock README.md /app/
COPY src /app/src

RUN uv sync --frozen --no-dev

COPY scripts /app/scripts
COPY local-conf.json /app/local-conf.json

CMD ["uv", "run", "python", "scripts/launch_service.py"]
