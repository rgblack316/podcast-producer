#!/bin/sh
# Start as root only long enough to fix volume ownership (older installs created it as root),
# then drop to the unprivileged "app" user for the server itself.
set -e
if [ "$(id -u)" = "0" ]; then
  mkdir -p "${MEDIA_DIR:-/data/media}" "${TMPDIR:-/tmp}"
  find "${TMPDIR:-/tmp}" -mindepth 1 -mtime +1 -delete 2>/dev/null || true
  chown -R app:app "${MEDIA_DIR:-/data/media}"
  exec setpriv --reuid=app --regid=app --clear-groups -- "$@"
fi
exec "$@"
