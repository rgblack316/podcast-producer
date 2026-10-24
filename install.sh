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

# The script itself arrives on stdin (curl | bash), so prompts must read from the terminal on a separate fd.
# Reads happen in this shell (never inside $(...)), which avoids the child shell being stopped by the terminal.
TTY_OK=0
if [[ "${NONINTERACTIVE:-0}" != "1" ]] && { exec 3</dev/tty; } 2>/dev/null; then
  TTY_OK=1
fi

ask() { # ask VAR "Question" default
  local __var="$1" __q="$2" __def="${3:-}" __ans=""
  if [[ $TTY_OK -eq 1 ]]; then
    printf '\n%s %s' "$__q" "${__def:+[$__def] }" >/dev/tty
    IFS= read -r -u 3 __ans || true
  fi
  printf -v "$__var" '%s' "${__ans:-$__def}"
}

[[ $EUID -eq 0 ]] || die "Please run as root: curl -fsSL <url>/install.sh | sudo bash"
command -v apt-get >/dev/null || die "This installer supports Ubuntu/Debian (apt). See README.md for manual steps."

RESUME=0
if [[ -d "$INSTALL_DIR/.git" ]]; then
  if [[ -f "$INSTALL_DIR/.env" ]]; then
    say "Podcast Producer is already installed in $INSTALL_DIR."
    say "To update it run: sudo $INSTALL_DIR/upgrade.sh"
    exit 0
  fi
  RESUME=1
  say "Found an unfinished install in $INSTALL_DIR. Continuing where it left off…"
fi

say "Installing prerequisites (git, curl, openssl)…"
apt-get update -qq </dev/null
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq git curl openssl ca-certificates </dev/null >/dev/null

if ! command -v docker >/dev/null; then
  say "Installing Docker Engine (this can take a minute)…"
  curl -fsSL https://get.docker.com | sh </dev/null >/dev/null
fi
systemctl enable --now docker >/dev/null 2>&1 || true
docker compose version >/dev/null 2>&1 || DEBIAN_FRONTEND=noninteractive apt-get install -y -qq docker-compose-plugin </dev/null >/dev/null
docker compose version >/dev/null 2>&1 || die "Docker Compose plugin is not available."
ok "Docker $(docker --version | awk '{print $3}' | tr -d ,) ready"

if [[ $RESUME -eq 1 ]]; then
  say "Updating the existing download…"
  git -C "$INSTALL_DIR" fetch --depth 1 origin "$BRANCH" </dev/null >/dev/null 2>&1 \
    && git -C "$INSTALL_DIR" reset --hard "origin/$BRANCH" >/dev/null || say "Could not update; using the existing files."
else
  say "Downloading Podcast Producer into $INSTALL_DIR…"
  git clone --depth 1 --branch "$BRANCH" "$REPO_URL" "$INSTALL_DIR" </dev/null >/dev/null 2>&1 || die "Could not clone $REPO_URL ($BRANCH)."
fi
cd "$INSTALL_DIR"
chmod +x install.sh upgrade.sh 2>/dev/null || true
mkdir -p backups

say "Configuring (press Enter to accept the value in [brackets])…"
if [[ -n "${APP_PORT:-}" ]]; then PORT="$APP_PORT"; else ask PORT "Port to serve the web app on this server?" 8080; fi
[[ "$PORT" =~ ^[0-9]+$ ]] || die "Port must be a number (got '$PORT')."
ok "Port set to $PORT"

if [[ -n "${CLOUDFLARE_TUNNEL_TOKEN:-}" ]]; then TUNNEL="$CLOUDFLARE_TUNNEL_TOKEN"
else ask TUNNEL "Cloudflare Tunnel token (optional - press Enter to skip and add it later):" ""; fi

# auto = login cookies are marked Secure only for HTTPS requests (via the tunnel), so plain-http LAN sign-in also works
SECURE=auto
if [[ -n "$TUNNEL" ]]; then
  ok "Cloudflare Tunnel will be started"
else
  ok "Login cookies: Secure over HTTPS, plain over http (auto)"
fi
[[ $TTY_OK -eq 1 ]] && exec 3<&-
SETUP_TOKEN=$(openssl rand -hex 16)

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
say "Building and starting containers (first build takes several minutes)…"
if ! docker compose "${PROFILE[@]}" up -d --build </dev/null; then
  die "Build failed. Fix the error above, then run: cd $INSTALL_DIR && sudo docker compose ${PROFILE[*]} up -d --build"
fi

ln -sf "$INSTALL_DIR/upgrade.sh" /usr/local/bin/podcast-producer-upgrade

IP=$(hostname -I 2>/dev/null | awk '{print $1}')
echo
ok "Podcast Producer is running!"
echo "  Local address : http://${IP:-localhost}:$PORT"
[[ -n "$TUNNEL" ]] && echo "  Public address: your Cloudflare Tunnel hostname (route it to http://frontend:80)"
echo "  Setup token   : $SETUP_TOKEN   (needed once in the first-run setup wizard; also saved in $INSTALL_DIR/.env)"
if [[ -z "$TUNNEL" ]]; then
  echo "  Note: over plain http on your LAN the login cookie is not marked Secure. Use a Cloudflare Tunnel (HTTPS) for outside access."
fi
echo "  Upgrade later : sudo podcast-producer-upgrade"
