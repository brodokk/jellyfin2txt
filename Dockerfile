FROM python:3.11.6-slim-bookworm

RUN apt-get update -y && apt-get install -y --no-install-recommends libgl1 mkvtoolnix tesseract-ocr git apt-transport-https ca-certificates python3-pip python3-poetry && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY jellyfin2txt /app/jellyfin2txt

COPY pyproject.toml /app

ENV POETRY_VIRTUALENVS_CREATE=false

RUN poetry install