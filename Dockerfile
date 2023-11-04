FROM debian:11-slim

RUN apt-get update -y && apt-get install -y --no-install-recommends libgl1 mkvtoolnix tesseract-ocr git apt-transport-https ca-certificates python3-pip && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY jellyfin2txt /app/jellyfin2txt

COPY pyproject.toml /app

RUN TMPDIR=tmp_dir pip install --cache-dir=tmp_dir --build=tmp_dir .