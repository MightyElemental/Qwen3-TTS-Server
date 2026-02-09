FROM pytorch/pytorch:2.10.0-cuda12.8-cudnn9-devel

# Faster, quieter Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update -y && apt-get install -y --no-install-recommends \
        ca-certificates curl git \
        ffmpeg sox libsox-fmt-all \
        libsndfile1 \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -U pip \
 && pip install --no-cache-dir -r /app/requirements.txt \
 && pip install --no-cache-dir --no-build-isolation flash-attn

COPY server.py /app/server.py
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]