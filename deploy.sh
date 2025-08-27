#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<EOF
Usage: ./deploy.sh -r <repo> -h <host> [-t tag] [-a admin_ids] [-u user] [-d remote_dir] [-k bot_token]
  -r  Docker Hub repo (e.g. mylogin/versavija-bot) (required)
  -h  Remote host/IP (required)
  -t  Tag (default: latest)
  -a  Admin IDs (default: 5607311019,669501992)
  -u  Remote SSH user (default: admin)
  -d  Remote dir (default: ~/versavija-bot)
  -k  BOT_TOKEN (if omitted will prompt)
EOF
}

REPO=""; TAG="latest"; ADMIN_IDS="5607311019,669501992"; REMOTE_USER="admin"; REMOTE_HOST=""; REMOTE_DIR="~/versavija-bot"; BOT_TOKEN=""
while getopts ":r:t:a:u:h:d:k:" opt; do
  case $opt in
    r) REPO="$OPTARG";;
    t) TAG="$OPTARG";;
    a) ADMIN_IDS="$OPTARG";;
    u) REMOTE_USER="$OPTARG";;
    h) REMOTE_HOST="$OPTARG";;
    d) REMOTE_DIR="$OPTARG";;
    k) BOT_TOKEN="$OPTARG";;
    *) usage; exit 1;;
  esac
done

[[ -z "$REPO" || -z "$REMOTE_HOST" ]] && { usage; exit 1; }
if [[ -z "$BOT_TOKEN" ]]; then
  read -rsp "Введите BOT_TOKEN: " BOT_TOKEN; echo
fi

IMAGE="$REPO:$TAG"
echo "[1/8] Build $IMAGE"
docker build -t "$IMAGE" .

echo "[2/8] Docker login (если нужно)"
docker login || true

echo "[3/8] Push $IMAGE"
docker push "$IMAGE"

echo "[4/8] Подготовка .env"
TMP_ENV=$(mktemp)
printf 'BOT_TOKEN=%s\nADMIN_IDS=%s\nDOCKER_HUB_IMAGE=%s\n' "$BOT_TOKEN" "$ADMIN_IDS" "$IMAGE" > "$TMP_ENV"

echo "[5/8] Копирование файлов"
ssh "$REMOTE_USER@$REMOTE_HOST" "mkdir -p $REMOTE_DIR"
scp docker-compose.yml "$REMOTE_USER@$REMOTE_HOST:$REMOTE_DIR/docker-compose.yml"
scp "$TMP_ENV" "$REMOTE_USER@$REMOTE_HOST:$REMOTE_DIR/.env"

echo "[6/8] Compose up"
ssh "$REMOTE_USER@$REMOTE_HOST" "cd $REMOTE_DIR && docker pull $IMAGE && docker compose up -d"

echo "[7/8] Logs tail"
ssh "$REMOTE_USER@$REMOTE_HOST" "docker logs --tail 10 versavija-bot 2>/dev/null || true"

echo "[8/8] Done"
rm -f "$TMP_ENV"
