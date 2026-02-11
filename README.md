# Qwen3-TTS Server

A self-hosted **REST API server for Qwen3-TTS** that ships with its own Docker container and persists users/voices/generations in SQLite.

This server is designed for:

* **Per-user API keys** (`Authorization: Bearer <api_key>`)
* **Per-user isolation** (users can only access what they created)
* **Token-based usage tracking** (tokens ≈ characters of input text)
* **Voice cloning & voice design** with **precomputed prompt blobs** for efficient reuse
* **Optional audio retention** (`store=false` by default)

> Upstream model/project: [Qwen3-TTS by QwenLM.](https://github.com/QwenLM/Qwen3-TTS)

---

## Features

* **Authentication**

  * API-key auth: `Authorization: Bearer <api_key>`
  * Admin-only endpoints to create users and invite codes
  * Invite exchange flow so the admin never sees the final API key

* **Voices**

  * `/clonevoice`: upload reference audio + transcript → creates voice & precomputes a reusable prompt
  * `/designvoice`: generate a reference voice sample from a description → creates voice & precomputes prompt
  * `/voices`: list voices (name, id, created_at, use_count, etc.)
  * `/voices/{voice_id}`: voice detail
  * `/voices/{voice_id}/sample`: download the reference WAV + transcript
  * `/voices/{voice_id}/delete`: delete a voice (with shared-audio dedupe safety)

* **Synthesis**

  * `/tts`: synthesize a single text input (returns audio file + headers with tokens/latency)
  * `/batchtts`: synthesize many texts in one call (returns a ZIP with audio files + manifest)
  * Output formats: `wav`, `mp3`, `ogg` (WAV is the native output; others are converted)

* **Usage**

  * `/usage`: totals for the authenticated user (calls, voices created, tokens used, etc.)

* **Ops**

  * `/health`: liveness check
  * `/ready`: readiness (model loaded + DB available)

---

## Security notes

* **No URL fetching for reference audio**: cloning uses file uploads only (the client can download URLs itself, then upload the file).
* Audio uploads are deduplicated by SHA-256 to avoid storing duplicates.

---

## Quickstart (Docker + GPU)

### Prereqs

* Docker + Docker Compose
* NVIDIA GPU + drivers + NVIDIA Container Toolkit
* Enough VRAM for Qwen3-TTS models (depends on model size)

### Run

```bash
docker compose up --build
```

Then open:

* API docs: `http://localhost:8000/docs`
* Health: `http://localhost:8000/health`

---

## Configuration

Most settings are configured via environment variables in `compose.yml` / the container environment.

Common ones:

* Server:

  * `HOST` (default `0.0.0.0`)
  * `PORT` (default `8000`)
  * `WORKERS` (default `1`)

* Models:

  * `MODEL_BASE_REPO` (HF repo id)
  * `MODEL_CUSTOM_REPO` (HF repo id)
  * `HF_TOKEN` (optional, for private repos)
  * Models are downloaded on startup to the mounted models directory.

* Auth / Admin:

  * `ADMIN_TOKEN` (required to call admin endpoints)

* Storage:

  * `MODELS_DIR` (default `/app/models`)
  * Media/output directory (project-specific; check your Settings in code)

---

## Python Library

https://github.com/MightyElemental/Qwen3-TTS-REST-Client

## Auth flow (Invite → API Key)

### 1) Admin creates a user

```bash
export BASE="http://localhost:8000"
export ADMIN_TOKEN="YOUR_ADMIN_TOKEN"

USER_ID=$(curl -sS -X POST "$BASE/admin/users" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  | python -c "import sys,json; print(json.load(sys.stdin)['user_id'])")

echo "USER_ID=$USER_ID"
```

### 2) Admin creates an invite code for that user

```bash
INVITE_CODE=$(curl -sS -X POST "$BASE/admin/users/$USER_ID/invites?expires_hours=24" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  | python -c "import sys,json; print(json.load(sys.stdin)['invite_code'])")

echo "INVITE_CODE=$INVITE_CODE"
```

### 3) User exchanges invite code for an API key (server returns it once)

```bash
API_KEY=$(curl -sS -X POST "$BASE/auth/exchange-invite" \
  -H "Content-Type: application/json" \
  -d "{\"invite_code\":\"$INVITE_CODE\"}" \
  | python -c "import sys,json; print(json.load(sys.stdin)['api_key'])")

echo "API_KEY=$API_KEY"
```

All user endpoints then use:

```bash
-H "Authorization: Bearer $API_KEY"
```

---

## Create a voice

### Clone voice from reference audio

You must provide:

* `file`: wav/mp3/ogg
* `transcript`: must match what is spoken in the audio (important!)
* `name`: friendly name
* optional `language`

```bash
VOICE_ID=$(curl -sS -X POST "$BASE/clonevoice" \
  -H "Authorization: Bearer $API_KEY" \
  -F "name=Geoff" \
  -F "language=English" \
  -F "transcript=The quick, brown fox jumped over the lazy dog" \
  -F "file=@./ref.mp3" \
  | python -c "import sys,json; print(json.load(sys.stdin)['voice_id'])")

echo "VOICE_ID=$VOICE_ID"
```

### Design a new voice (description → reference sample)

`/designvoice` uses a fixed English “coverage phrase” internally and charges tokens for:
`len(description) + len(standard_phrase)`.

```bash
curl -sS -X POST "$BASE/designvoice" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "warm_narrator",
    "language": "English",
    "description": "Warm, calm narrator voice. Slightly husky. Friendly.",
  }' | python -m json.tool
```

---

## List voices / download reference sample

```bash
curl -sS "$BASE/voices" -H "Authorization: Bearer $API_KEY" | python -m json.tool
curl -sS "$BASE/voices/$VOICE_ID" -H "Authorization: Bearer $API_KEY" | python -m json.tool

curl -sS -L "$BASE/voices/$VOICE_ID/sample" \
  -H "Authorization: Bearer $API_KEY" \
  -o voice_sample.wav
```

---

## Synthesize speech

### `/tts` (single)

* `store` defaults to `false`
* `language` defaults to `"auto"`
* `format`: `wav` | `mp3` | `ogg`

```bash
curl -sS -X POST "$BASE/tts" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -D tts_headers.txt \
  -o out.wav \
  -d "{\"text\":\"Hello from the TTS server.\",\"voice_id\":$VOICE_ID,\"store\":false,\"language\":\"English\",\"format\":\"wav\"}"

cat tts_headers.txt | sed -n 's/^X-//p'
file out.wav
```

You should see headers like:

* `X-Generation-Id`
* `X-Tokens-Used`
* `X-Latency-Ms`

### `/batchtts` (ZIP)

Returns a zip containing:

* `manifest.json` (ids, filenames, tokens, etc.)
* audio files (one per input)

```bash
curl -sS -X POST "$BASE/batchtts" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -D batch_headers.txt \
  -o batch.zip \
  -d "{\"texts\":[\"First line.\",\"Second line.\",\"Third line.\"],\"voice_id\":$VOICE_ID,\"store\":false,\"language\":\"English\",\"format\":\"wav\"}"

cat batch_headers.txt | sed -n 's/^X-//p'
unzip -l batch.zip
unzip -p batch.zip manifest.json | python -m json.tool
```

Batch token accounting uses a **self-calibrated batch discount** (based on observed latency per character) so batches cost fewer tokens than making the same requests individually.

---

## Stored generations

If you call `/tts` or `/batchtts` with `"store": true`, the server will keep:

* audio path
* input text
  …so it can be retrieved later:

```bash
curl -sS -L "$BASE/getstored/$GENERATION_ID" \
  -H "Authorization: Bearer $API_KEY" \
  -o stored.wav
```

If `store=false`, the DB still records usage/latency, but does not retain the audio/text.

---

## Usage stats

```bash
curl -sS "$BASE/usage" -H "Authorization: Bearer $API_KEY" | python -m json.tool
```

---

## Project structure (high level)

* `server.py` – FastAPI app entrypoint (imports/routers, lifecycle)
* `app/` – application code (routers, services, DB, models)
* `compose.yml` – docker compose service definition
* `entrypoint.sh` – downloads models (if missing) and starts Uvicorn
* `Dockerfile` – CUDA-enabled PyTorch base image with audio tooling

---

## Troubleshooting

* **Voice clone sounds wrong / reads the wrong thing**
  Your reference transcript must match the reference audio content closely.

* **GPU not detected**

  * Ensure host has NVIDIA drivers + NVIDIA Container Toolkit
  * Ensure compose is enabling GPU access (see `compose.yml`)

* **Model download issues**

  * Set `HF_TOKEN` if your repos are private
  * Ensure `models/` volume is writable

---

## License / upstream

This repo is a server wrapper around Qwen3-TTS; Qwen3-TTS is released by QwenLM under Apache 2.0.