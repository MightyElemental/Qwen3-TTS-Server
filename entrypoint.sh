#!/usr/bin/env bash
set -euo pipefail

# ---- Config ----
: "${HOST:=0.0.0.0}"
: "${PORT:=8000}"
: "${WORKERS:=1}"

: "${MODEL_BASE_REPO:=Qwen/Qwen3-TTS-12Hz-1.7B-Base}"
: "${MODEL_CUSTOM_REPO:=Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice}"

: "${MODELS_DIR:=/app/models}"
BASE_DIR="${MODELS_DIR}/Qwen3-TTS-12Hz-1.7B-Base"
CUSTOM_DIR="${MODELS_DIR}/Qwen3-TTS-12Hz-1.7B-CustomVoice"

mkdir -p "${MODELS_DIR}"

download_if_missing() {
  local repo="$1"
  local out_dir="$2"

  if [[ -d "${out_dir}" && -n "$(ls -A "${out_dir}" 2>/dev/null || true)" ]]; then
    echo "[entrypoint] Model already present at: ${out_dir}"
  else
    echo "[entrypoint] Downloading ${repo} -> ${out_dir}"
    # If you need private models, pass HF_TOKEN via env and the CLI will use it.
    hf download "${repo}" --local-dir "${out_dir}"
  fi
}

download_if_missing "${MODEL_BASE_REPO}" "${BASE_DIR}"
download_if_missing "${MODEL_CUSTOM_REPO}" "${CUSTOM_DIR}"

echo "[entrypoint] Starting FastAPI (uvicorn) on ${HOST}:${PORT}"
exec python -m uvicorn server:app \
  --host "${HOST}" \
  --port "${PORT}" \
  --workers "${WORKERS}"