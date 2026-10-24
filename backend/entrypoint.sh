#!/bin/sh
# Start as root only long enough to fix volume ownership (older installs created it as root),
# then drop to the unprivileged "app" user for the server itself.
set -e
if [ "$(id -u)" = "0" ]; then
  mkdir -p "${MEDIA_DIR:-/data/media}" "${TMPDIR:-/tmp}" || echo "entrypoint: could not create folders (continuing)" >&2
  find "${TMPDIR:-/tmp}" -mindepth 1 -mtime +1 -delete 2>/dev/null || true
  chown -R app:app "${MEDIA_DIR:-/data/media}" || echo "entrypoint: could not fix ownership (continuing)" >&2
  exec setpriv --reuid=app --regid=app --clear-groups -- "$@"
fi
exec "$@"
