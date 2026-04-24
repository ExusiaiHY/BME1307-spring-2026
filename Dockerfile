# syntax=docker/dockerfile:1.6

ARG PYTHON_VERSION=3.9
FROM python:${PYTHON_VERSION}-slim AS core

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    BUSAT_DATA_DIR=/data/busat \
    BUSAT_OUTPUTS_DIR=/app/outputs/part2 \
    BUSAT_MASKS_DIR=/app/outputs/part2/busat_masks \
    PART1_METADATA_FILE=/data/part1/metadata.csv \
    PART1_IMAGES_DIR=/data/part1 \
    PART1_OUTPUTS_DIR=/app/outputs/part1 \
    PART3_PART1_METADATA_FILE=/data/part1/metadata.csv \
    PART3_PART1_IMAGES_DIR=/data/part1 \
    PART3_OUTPUTS_DIR=/app/outputs/part3 \
    PART3_CACHE_DIR=/app/.cache/part3 \
    MPLCONFIGDIR=/app/.cache/matplotlib

RUN apt-get update && apt-get install -y --no-install-recommends \
        libglib2.0-0 \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements-core.txt requirements-dev.txt requirements-fm.txt ./
RUN python -m pip install --upgrade pip \
    && pip install -r requirements-core.txt

COPY src/ ./src/
COPY scripts/ ./scripts/
COPY notebooks/ ./notebooks/
COPY docs/ ./docs/
COPY README.md BME1307_Project_Description.md ./

RUN mkdir -p /app/outputs /app/.cache /data/busat /data/part1

VOLUME ["/data/busat", "/data/part1", "/app/outputs", "/app/.cache"]

CMD ["python", "scripts/check_environment.py", "--mode", "core"]


FROM core AS dev

RUN pip install -r requirements-dev.txt

EXPOSE 8888

CMD ["jupyter", "lab", "--ip=0.0.0.0", "--port=8888", "--no-browser", "--allow-root", "--ServerApp.token=bme1307"]


FROM core AS fm

RUN pip install -r requirements-fm.txt

CMD ["python", "scripts/check_environment.py", "--mode", "fm"]
