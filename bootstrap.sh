#!/usr/bin/env bash
set -e

GITHUB_REPO="${GITHUB_REPO:?Set GITHUB_REPO}"
DB_PASSWORD="${DB_PASSWORD:-docqa_password}"
OLLAMA_MODEL_PULL="${OLLAMA_MODEL_PULL:-qwen2.5:72b-instruct-q4_K_S}"

export PG_PATH=/workspace/pg
export OLLAMA_MODELS=/workspace/ollama
export HF_HOME=/workspace/hf-cache
export APP_PATH=/workspace/ragdoc
export VENV_PATH=/workspace/venv
mkdir -p "$OLLAMA_MODELS" "$HF_HOME" /workspace/logs

PG_BIN=/usr/lib/postgresql/16/bin

echo "==[1/7]== System packages"
apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq curl ca-certificates gnupg lsb-release sudo tmux git unzip nano build-essential libpq-dev tesseract-ocr tesseract-ocr-eng tesseract-ocr-ara poppler-utils libmagic1 libgl1 libglib2.0-0 libsm6 libxext6 libxrender1

echo "==[2/7]== PostgreSQL"
if ! command -v psql >/dev/null 2>&1; then
    install -d -m 0755 /etc/apt/keyrings
    curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc | gpg --dearmor -o /etc/apt/keyrings/postgresql.gpg
    echo "deb [signed-by=/etc/apt/keyrings/postgresql.gpg] http://apt.postgresql.org/pub/repos/apt jammy-pgdg main" > /etc/apt/sources.list.d/pgdg.list
    apt-get update -qq
    apt-get install -y -qq postgresql-16 postgresql-16-pgvector
fi

if [ ! -s "$PG_PATH/PG_VERSION" ]; then
    echo "  -> initializing Postgres cluster"
    rm -rf "$PG_PATH"
    mkdir -p "$PG_PATH"
    id -u pgrun >/dev/null 2>&1 || useradd -r -d /workspace/pg-home -s /bin/bash pgrun
    mkdir -p /workspace/pg-home
    chown -R pgrun:pgrun /workspace/pg-home "$PG_PATH"
    chmod 700 "$PG_PATH"
    sudo -u pgrun "$PG_BIN/initdb" -D "$PG_PATH" --auth=trust --username=docqa
    echo "host all all 127.0.0.1/32 trust" >> "$PG_PATH/pg_hba.conf"
    echo "listen_addresses = 'localhost'"  >> "$PG_PATH/postgresql.conf"
    echo "unix_socket_directories = '/tmp'" >> "$PG_PATH/postgresql.conf"
fi

echo "==[3/7]== Ollama"
command -v ollama >/dev/null 2>&1 || curl -fsSL https://ollama.com/install.sh | sh

echo "==[4/7]== App code"
if [ ! -d "$APP_PATH/.git" ]; then
    git clone "$GITHUB_REPO" "$APP_PATH"
else
    git -C "$APP_PATH" pull --ff-only || true
fi

echo "==[5/7]== Python venv"
[ -d "$VENV_PATH" ] || python3 -m venv --system-site-packages "$VENV_PATH"
source "$VENV_PATH/bin/activate"
pip install --no-cache-dir --upgrade pip
pip install --no-cache-dir -r "$APP_PATH/requirements.txt"

echo "==[6/7]== Database setup"
sudo -u pgrun "$PG_BIN/pg_ctl" -D "$PG_PATH" -l /tmp/pg.log -o "-k /tmp" start || true
sleep 4
psql -h /tmp -U docqa -d postgres -c "ALTER ROLE docqa WITH PASSWORD '${DB_PASSWORD}';"
psql -h /tmp -U docqa -d postgres -tc "SELECT 1 FROM pg_database WHERE datname='docqa'" | grep -q 1 || psql -h /tmp -U docqa -d postgres -c "CREATE DATABASE docqa OWNER docqa;"
psql -h /tmp -U docqa -d docqa -c "CREATE EXTENSION IF NOT EXISTS vector;"
sudo -u pgrun "$PG_BIN/pg_ctl" -D "$PG_PATH" stop || true

echo "==[7/7]== Pulling Ollama model (30-45 min on first run)"
OLLAMA_MODELS="$OLLAMA_MODELS" ollama serve > /tmp/ollama.log 2>&1 &
OLLAMA_PID=$!
sleep 5
ollama list | grep -q "${OLLAMA_MODEL_PULL%%:*}" || ollama pull "$OLLAMA_MODEL_PULL"
kill "$OLLAMA_PID" || true
sleep 2

echo
echo "=================================================================="
echo "  Bootstrap complete!"
echo "=================================================================="