#!/usr/bin/env bash
# Levanta la demo (mock si no hay .env con MAAS_MODE=live) y abre el navegador.
set -euo pipefail
cd "$(dirname "$0")/../.."

if command -v xdg-open >/dev/null 2>&1; then
  (sleep 1.5 && xdg-open http://127.0.0.1:8080 >/dev/null 2>&1 &)
fi

exec python3 -m src.maas_demo
