FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

ENV DEBIAN_FRONTEND=noninteractive
ENV UV_SYSTEM_PYTHON=1
ENV UV_COMPILE_BYTECODE=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential pkg-config curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml setup.py uv.lock MANIFEST.in LICENSE ./
COPY lightrag ./lightrag
COPY raganything ./raganything

RUN --mount=type=cache,target=/root/.local/share/uv \
    uv sync --frozen --no-dev --extra api --extra offline --no-editable

FROM python:3.12-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV UV_SYSTEM_PYTHON=1

COPY --from=builder /app /app

ENV PATH=/app/.venv/bin:/root/.local/bin:$PATH
ENV WORKING_DIR=/app/data/rag_storage
ENV INPUT_DIR=/app/data/inputs
ENV TIKTOKEN_CACHE_DIR=/app/data/tiktoken

RUN mkdir -p /app/data/rag_storage /app/data/inputs /app/data/tiktoken

EXPOSE 9621
EXPOSE 8621

CMD ["python", "-m", "lightrag.api.lightrag_server"]
