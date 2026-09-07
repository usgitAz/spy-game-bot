#!/bin/sh
# Ensure the (possibly host-mounted) logs directory is writable, then drop
# privileges to the non-root ``spybot`` user when started as root.
set -e

LOG_DIR="${LOG_DIR:-/app/logs}"
mkdir -p "$LOG_DIR"

if [ "$(id -u)" = "0" ]; then
  # Volume mounts replace the image's /app/logs ownership; fix at runtime.
  chown -R spybot:spybot "$LOG_DIR" 2>/dev/null || true
  # runuser is available on Debian slim (util-linux).
  exec runuser -u spybot -- "$@"
fi

exec "$@"
