FROM python:3.13-slim@sha256:bf503bb2243c5aad0aa951544dd60d165f992646441d35dea90893703fc26251

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_HTTP_TIMEOUT=120 \
    PATH="/app/.venv/bin:${PATH}"

WORKDIR /app

COPY . /app/

RUN apt-get update \
    && apt-get install -y --no-install-recommends docker-cli \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir "uv==0.9.9"

RUN uv sync --locked --no-dev --no-editable --no-cache \
    && python -c "import importlib.metadata as m; assert m.version('graphharbor') == '0.13.0.post43'; assert m.version('graphharbor-runtime') == '0.13.0.post43'"

ENTRYPOINT ["graphharbor"]
