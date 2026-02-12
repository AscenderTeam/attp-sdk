#!/usr/bin/env bash
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

export ATTP_SHARED_SECRET="${ATTP_SHARED_SECRET:-change-me}"
export ATTP_AUTH_DEBUG="${ATTP_AUTH_DEBUG:-1}"

PORT_MAIN="${PORT_MAIN:-8001}"
PORT_PEER1="${PORT_PEER1:-8002}"
PORT_PEER2="${PORT_PEER2:-8003}"

pids=()

kill_listeners() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    local pids_on_port
    pids_on_port="$(lsof -tiTCP:"$port" -sTCP:LISTEN || true)"
    if [[ -n "$pids_on_port" ]]; then
      echo "Killing listeners on port ${port}: ${pids_on_port}"
      kill $pids_on_port 2>/dev/null || true
    fi
  elif command -v ss >/dev/null 2>&1; then
    local pids_on_port
    pids_on_port="$(ss -ltnp 2>/dev/null | awk -v p=":$port" '$4 ~ p {print $NF}' | sed 's/.*pid=\\([0-9]*\\).*/\\1/' | sort -u)"
    if [[ -n "$pids_on_port" ]]; then
      echo "Killing listeners on port ${port}: ${pids_on_port}"
      kill $pids_on_port 2>/dev/null || true
    fi
  fi
}

for port in 6563 6564 6565 "$PORT_MAIN" "$PORT_PEER1" "$PORT_PEER2"; do
  kill_listeners "$port"
done

start_node() {
  local name="$1"
  local port="$2"
  local cfg="$3"

  echo "Starting ${name} on HTTP port ${port} with ${cfg}"
  ATTP_CONFIG="$cfg" \
  ascender run serve --port "$port" &
  pids+=($!)
}

cleanup() {
  echo "Stopping servers..."
  for pid in "${pids[@]:-}"; do
    kill "$pid" 2>/dev/null || true
  done
}

trap cleanup EXIT

start_node "peer-1" "$PORT_PEER1" "attp.peer1.jsonc"
start_node "peer-2" "$PORT_PEER2" "attp.peer2.jsonc"
start_node "main" "$PORT_MAIN" "attp.jsonc"

wait
