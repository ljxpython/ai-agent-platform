FROM python:3.13-slim

COPY --from=ghcr.io/astral-sh/uv:0.9.9 /uv /usr/local/bin/uv

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/app/.venv/bin:$PATH"

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
COPY migrations ./migrations
COPY alembic.ini ./
RUN uv sync --frozen --no-dev --no-editable

EXPOSE 2142

CMD ["uvicorn", "platform_api.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "2142"]
