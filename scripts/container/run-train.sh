#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "${SCRIPT_DIR}/source-ros.sh"
TRAIN_DIR="${H2F_TRAIN_DIR:-/workspace/drone_rl}"
if [[ ! -f "${TRAIN_DIR}/train.py" ]]; then
  TRAIN_DIR="${HOME}/drone_rl"
fi
if [[ ! -f "${TRAIN_DIR}/train.py" ]]; then
  echo "train.py not found. Set H2F_TRAIN_DIR or mount repo at /workspace." >&2
  exit 1
fi
cd "${TRAIN_DIR}"
exec python3 train.py
