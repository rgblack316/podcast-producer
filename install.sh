#!/usr/bin/env bash
# Podcast Producer (Bible Bytes) installer for Ubuntu/Debian servers.
#   curl -fsSL https://raw.githubusercontent.com/rgblack316/podcast-producer/main/install.sh | sudo bash
# Optional overrides: REPO_URL, BRANCH, INSTALL_DIR, APP_PORT, CLOUDFLARE_TUNNEL_TOKEN, NONINTERACTIVE=1
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/rgblack316/podcast-producer.git}"
BRANCH="${BRANCH:-main}"
INSTALL_DIR="${INSTALL_DIR:-/opt/podcast-producer}"

say()  { printf '\033[1;33m==>\033[0m %s\n' "$*"; }
ok()   { printf '\033[1;32m✔\033[0m %s\n' "$*"; }
die()  { printf '\033[1;31m✖ %s\033[0m\n' "$*" >&2; exit 1; }

ask() { # ask "Question" default -> echo answer (reads from the terminal even when piped through curl)
  local q="$1" def="${2:-}" ans=""
  if [[ "${NONINTERACTIVE:-0}" == "1" || ! -r /dev/tty ]]; then echo "$def"; return; fi
  read -r -p "$q ${def:+[$def] }" ans </dev/tty || true
  echo "${ans:-$def}"
}

[[ $EUID -eq 0 ]] || die "Please run as root: curl -fsSL <url>/install.sh | sudo bash"
command -v apt-get >/dev/null || die "This installer supports Ubuntu/Debian (apt). See README.md for manual steps."

if [[ -d "$INSTALL_DIR/.git" ]]; then
  say "Podcast Producer is already installed in $INSTALL_DIR."
  say "To update it run: sudo $INSTALL_DIR/upgrade.sh"
  exit 0
fi

say "Installing prerequisites (git, curl, openssl)…"
apt-get update -qq
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq git curl openssl ca-certificates >/dev/null

if ! command -v docker >/dev/null; then
  say "Installing Docker Engine…"
  curl -fsSL https://get.docker.com | sh >/dev/null
fi
systemctl enable --now docker >/dev/null 2>&1 || true
docker compose version >/dev/null 2>&1 || DEBIAN_FRONTEND=noninteractive apt-get install -y -qq docker-compose-plugin >/dev/null
docker compose version >/dev/null 2>&1 || die "Docker Compose plugin is not available."
ok "Docker $(docker --version | awk '{print $3}' | tr -d ,) ready"

say "Downloading Podcast Producer into $INSTALL_DIR…"
git clone --depth 1 --branch "$BRANCH" "$REPO_URL" "$INSTALL_DIR" >/dev/null 2>&1 || die "Could not clone $REPO_URL ($BRANCH)."
cd "$INSTALL_DIR"
chmod +x install.sh upgrade.sh 2>/dev/null || true
mkdir -p backups

say "Configuring…"
PORT="${APP_PORT:-$(ask "Port to serve the web app on this server?" 8080)}"
TUNNEL="${CLOUDFLARE_TUNNEL_TOKEN:-$(ask "Cloudflare Tunnel token (leave blank to set up later):" "")}"
if [[ -n "$TUNNEL" ]]; then
  SECURE=true
else
  HTTPS=$(ask "Will people reach the app over HTTPS (Cloudflare Tunnel or another proxy)? (y/n)" y)
  [[ "$HTTPS" =~ ^[Nn] ]] && SECURE=false || SECURE=true
fi
SETUP_TOKEN=$(openssl rand -hex 6)

cat > .env <<EOF
DB_NAME=biblebytes
JWT_SECRET=$(openssl rand -hex 32)
SETUP_TOKEN=$SETUP_TOKEN
ADMIN_USERNAME=
ADMIN_PASSWORD=
ADMIN_FORCE_RESET=false
COOKIE_SECURE=$SECURE
APP_PORT=$PORT
CLOUDFLARE_TUNNEL_TOKEN=$TUNNEL
EOF
chmod 600 .env
ok "Wrote $INSTALL_DIR/.env"

PROFILE=()
[[ -n "$TUNNEL" ]] && PROFILE=(--profile tunnel)
say "Building and starting containers (first build takes a few minutes)…"
docker compose "${PROFILE[@]}" up -d --build

ln -sf "$INSTALL_DIR/upgrade.sh" /usr/local/bin/podcast-producer-upgrade

IP=$(hostname -I 2>/dev/null | awk '{print $1}')
echo
ok "Podcast Producer is running!"
echo "  Local address : http://${IP:-localhost}:$PORT"
[[ -n "$TUNNEL" ]] && echo "  Public address: your Cloudflare Tunnel hostname (route it to http://frontend:80)"
echo "  Setup token   : $SETUP_TOKEN   (needed once in the first-run setup wizard)"
[[ "$SECURE" == "true" && -z "$TUNNEL" ]] && echo "  Note: sign-in needs HTTPS (or http://localhost). For plain-http LAN use set COOKIE_SECURE=false in .env and run upgrade."
echo "  Upgrade later : sudo podcast-producer-upgrade"
