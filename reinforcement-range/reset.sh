#!/usr/bin/env bash
# Reconstruye el contenedor objetivo desde cero: red aislada, IP fija, datos
# de seed/ recién cargados. Requiere pertenecer al grupo `docker`.
set -euo pipefail
cd "$(dirname "$0")"

NETWORK=rr-net
SUBNET=172.28.0.0/24
TARGET_IP=172.28.0.10
IMAGE=rr-target
CONTAINER=rr-target

docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
docker network rm "$NETWORK" >/dev/null 2>&1 || true

docker network create --internal --subnet "$SUBNET" "$NETWORK" >/dev/null

docker build -q -t "$IMAGE" -f target/Dockerfile . >/dev/null

docker run -d \
  --name "$CONTAINER" \
  --network "$NETWORK" \
  --ip "$TARGET_IP" \
  --cap-drop=ALL \
  --pids-limit=128 \
  --memory=256m \
  --cpus=1 \
  "$IMAGE" >/dev/null

echo "Objetivo listo en http://$TARGET_IP/ (red $NETWORK, sin salida a internet)"
