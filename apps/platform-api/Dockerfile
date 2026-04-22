FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY app ./app
COPY main.py worker.py ./

RUN pip install --no-cache-dir uv \
    && uv pip install --system .

EXPOSE 2142

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "2142"]
