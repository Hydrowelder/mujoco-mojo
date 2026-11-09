#!/usr/bin/env bash
# Local Dojo dev: runs a Dojo and the Vite dev server together.
#
#   scripts/dev_dojo.sh <workdir> [dojo-port]
#
#   http://localhost:5173   <- open this one. Vite serves the TypeScript sources straight from src/
#                              (saving a .ts file or a template reloads the page, no rebuild) and proxies
#                              every path the Dojo owns through to the Dojo below.
#   http://127.0.0.1:8000   the Dojo itself (or dojo-port). With MOJO_DOJO_DEV set its pages load their
#                           scripts from Vite, so only Vite should talk to it.
#
# Python edits still need a restart. Stop with Ctrl+C.
set -euo pipefail

if [ $# -lt 1 ]; then
  echo "usage: $0 <workdir> [dojo-port]" >&2
  exit 1
fi
WORKDIR="$1"
PORT="${2:-8000}"

# This script lives in scripts/; the frontend project is relative to the repo root one level up.
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TS_DIR="$ROOT_DIR/src/mujoco_mojo/utils/layers/dojo/templates/static/ts"

# The Dojo hops to the next free port when its own is taken, which would leave Vite proxying to
# whatever is on this one, so refuse to start instead.
if (exec 3<>"/dev/tcp/127.0.0.1/$PORT") 2>/dev/null; then
  echo "Port $PORT is already in use; pass a free one as the second argument." >&2
  exit 1
fi

if [ ! -d "$TS_DIR/node_modules" ]; then
  echo "==> Installing frontend dependencies (first run)"
  (cd "$TS_DIR" && npm install)
fi

# MOJO_DOJO_DEV points the templates at Vite's sources (see dojo/shared.py); DOJO_TARGET is where
# Vite's proxy sends everything else (see vite.config.ts).
export MOJO_DOJO_DEV=1
export DOJO_TARGET="http://127.0.0.1:$PORT"

PIDS=()

cleanup() {
  echo
  echo "==> Stopping dev processes"
  for pid in "${PIDS[@]}"; do
    kill "$pid" >/dev/null 2>&1 || true
  done
  wait >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

# Loopback only (Vite's default): the Dojo gates settings writes on the peer being localhost, and
# behind the proxy every browser looks like it, so don't pass --host here.
echo "==> Starting the Vite dev server on http://localhost:5173 (open this one, not the Dojo's own address below)"
(cd "$TS_DIR" && npm run dev) &
PIDS+=("$!")

echo "==> Starting the Dojo on http://127.0.0.1:$PORT"
echo
mujoco-mojo dojo "$WORKDIR" --host 127.0.0.1 --port "$PORT"
