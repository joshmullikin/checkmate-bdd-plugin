#!/usr/bin/env bash
# native-start.sh
# Start checkmate, playwright-http, checkmate-mcp natively.
# Requires repos already cloned by clone-deps.sh.

set -e

DEPS_DIR="${HOME}/.checkmate-bdd"
PID_DIR="${DEPS_DIR}/pids"
LOG_DIR="${DEPS_DIR}/logs"
mkdir -p "$PID_DIR" "$LOG_DIR"

start_service() {
  local name="$1"
  local dir="$2"
  local cmd="$3"
  local pid_file="${PID_DIR}/${name}.pid"

  if [ -f "$pid_file" ] && kill -0 "$(cat "$pid_file")" 2>/dev/null; then
    echo "${name} already running (pid $(cat "$pid_file"))"
    return 0
  fi

  echo "Starting ${name}..."
  pushd "$dir" > /dev/null
  eval "$cmd" > "${LOG_DIR}/${name}.log" 2>&1 &
  echo $! > "$pid_file"
  popd > /dev/null
  echo "${name} started (pid $(cat "$pid_file"))"
}

start_service "checkmate" \
  "${DEPS_DIR}/checkmate" \
  "uv run uvicorn api.main:app --host 127.0.0.1 --port 8000"

start_service "playwright-http" \
  "${DEPS_DIR}/playwright-http" \
  "uv run uvicorn executor.main:app --host 127.0.0.1 --port 8932"

# Build checkmate-mcp if dist/ missing
if [ ! -f "${DEPS_DIR}/checkmate-mcp/dist/server.js" ]; then
  echo "Building checkmate-mcp..."
  pushd "${DEPS_DIR}/checkmate-mcp" > /dev/null
  npm ci --silent
  npm run build --silent
  popd > /dev/null
fi

start_service "checkmate-mcp" \
  "${DEPS_DIR}/checkmate-mcp" \
  "CHECKMATE_URL=http://127.0.0.1:8000 PORT=3003 node dist/server.js"

echo ""
echo "All services started. Logs: ${LOG_DIR}/"
