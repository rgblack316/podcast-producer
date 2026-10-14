#!/usr/bin/env bash
# Upgrade Podcast Producer to the latest version from GitHub.
#   sudo /opt/podcast-producer/upgrade.sh        (or: sudo podcast-producer-upgrade)
# Local edits to tracked files are discarded; .env, backups/ and all data (Docker volumes) are kept.
# Options: BRANCH=main, SKIP_BACKUP=1, KEEP_BACKUPS=10
set -euo pipefail

SCRIPT_PATH="$(readlink -f "${BASH_SOURCE[0]}")"
APP_DIR="$(dirname "$SCRIPT_PATH")"
BRANCH="${BRANCH:-main}"
KEEP_BACKUPS="${KEEP_BACKUPS:-10}"

say() { printf '\033[1;33m==>\033[0m %s\n' "$*"; }
ok()  { printf '\033[1;32m✔\033[0m %s\n' "$*"; }
die() { printf '\033[1;31m✖ %s\033[0m\n' "$*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "Please run with sudo."
cd "$APP_DIR"
[[ -d .git ]] || die "$APP_DIR is not a git checkout. Reinstall with install.sh."
[[ -f .env ]] || die "Missing $APP_DIR/.env"
set -a; . ./.env; set +a

if [[ "${SKIP_BACKUP:-0}" != "1" ]] && docker compose ps --status running mongo 2>/dev/null | grep -q mongo; then
  mkdir -p backups
  STAMP=$(date +%Y%m%d-%H%M%S)
  say "Backing up the database to backups/pre-upgrade-$STAMP.archive…"
  docker compose exec -T mongo mongodump --archive --db "${DB_NAME:-biblebytes}" > "backups/pre-upgrade-$STAMP.archive"
  docker run --rm -v "$(basename "$APP_DIR")_media_data:/m" -v "$APP_DIR/backups:/b" alpine \
    tar czf "/b/pre-upgrade-$STAMP-media.tgz" -C /m . 2>/dev/null || true
  ls -1t backups/pre-upgrade-*.archive 2>/dev/null | tail -n +$((KEEP_BACKUPS + 1)) | while read -r f; do
    rm -f "$f" "${f%.archive}-media.tgz"
  done
  ok "Backup saved"
fi

OLD=$(git rev-parse --short HEAD)
say "Fetching the latest code ($BRANCH)…"
git fetch --depth 1 origin "$BRANCH"
# Discard local changes to tracked files only; untracked/ignored files (.env, backups/) are left alone.
git reset --hard "origin/$BRANCH" >/dev/null
NEW=$(git rev-parse --short HEAD)
chmod +x install.sh upgrade.sh 2>/dev/null || true

if [[ "$OLD" == "$NEW" && "${FORCE_REBUILD:-0}" != "1" ]]; then
  ok "Already up to date ($NEW). Restarting containers to apply any .env changes…"
else
  ok "Updated $OLD → $NEW"
fi

PROFILE=()
[[ -n "${CLOUDFLARE_TUNNEL_TOKEN:-}" ]] && PROFILE=(--profile tunnel)
say "Rebuilding and restarting…"
docker compose "${PROFILE[@]}" up -d --build --remove-orphans
docker image prune -f >/dev/null 2>&1 || true
ok "Podcast Producer is running version $NEW"
