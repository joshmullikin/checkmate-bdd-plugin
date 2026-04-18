#!/usr/bin/env bash
# native-stop.sh
# Stop services started by native-start.sh.

PID_DIR="${HOME}/.checkmate-bdd/pids"

stop_service() {
  local name="$1"
  local pid_file="${PID_DIR}/${name}.pid"

  if [ ! -f "$pid_file" ]; then
    echo "${name}: no pid file"
    return 0
  fi

  local pid
  pid=$(cat "$pid_file")
  if kill -0 "$pid" 2>/dev/null; then
    echo "Stopping ${name} (pid ${pid})..."
    kill "$pid"
    sleep 1
  else
    echo "${name}: not running"
  fi
  rm -f "$pid_file"
}

# Stop in reverse dependency order
stop_service "checkmate-mcp"
stop_service "checkmate"
stop_service "playwright-http"
