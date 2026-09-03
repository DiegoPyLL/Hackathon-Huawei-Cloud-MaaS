#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
CALLER_MODEL="${MAAS_MODEL:-}"
set -a
source .env
set +a
if [ -n "$CALLER_MODEL" ]; then
  MAAS_MODEL="$CALLER_MODEL"
fi
/usr/bin/sg docker -c "MAAS_API_KEY='$MAAS_API_KEY' MAAS_BASE_URL='$MAAS_BASE_URL' MAAS_MODEL='$MAAS_MODEL' STATE_PATH='${STATE_PATH:-reinforcement-range/state.json}' TRANSCRIPT_PATH='${TRANSCRIPT_PATH:-}' PACE_SECONDS='${PACE_SECONDS:-12}' HARDEN_BRIEF='${HARDEN_BRIEF:-}' python3 -u reinforcement-range/orchestrator/harden.py"
