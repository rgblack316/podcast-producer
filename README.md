# Podcast Producer (Bible Bytes)

A private, self-hosted studio for planning, writing and tracking episodes of the **Bible Bytes** podcast.

You enter an episode's topic, title and scripture. The AI writes an outline that follows your planning template. You approve the outline, and the AI writes the full script. Show notes, social posts and cover art can follow from there. Every episode, new or imported from your RSS feed, is kept in a searchable library. The library tracks books of the Bible, themes, series and your publishing schedule.

Everything runs on your own server with Docker. The app calls **Google Gemini** or **OpenAI** directly with **your own API keys**. No Emergent services are used at runtime.

---

## Contents
- [Features](#features)
- [Quick install (Ubuntu/Debian)](#quick-install-ubuntudebian)
- [Upgrading](#upgrading)
- [First-run setup](#first-run-setup)
- [Publishing through Cloudflare Tunnel](#publishing-through-cloudflare-tunnel)
- [Configuration (.env)](#configuration-env)
- [Using the app](#using-the-app)
- [Backups and restore](#backups-and-restore)
- [Everyday commands](#everyday-commands)
- [Troubleshooting](#troubleshooting)
- [Manual install](#manual-install-without-the-script)
- [Local development](#local-development)
- [Project structure](#project-structure)

---

## Features
| Area | What you get |
|---|---|
| **Episode workflow** | Intake form, then AI outline (revise with notes, edit by hand, version history, approve), then AI full script (same loop), then mark complete and published. Export to `.docx` or copy the text. |
| **Reference documents** | Upload your planning template and example episodes as `.docx` files. The AI follows them for structure and tone. |
| **Show notes** | One click turns a finished script into show notes, an episode description, and Instagram, Facebook, X and YouTube captions. |
| **Artwork studio** | Brainstorm with an AI art director, pick a concept, edit the prompt, then generate square cover art (Gemini "Nano Banana" or OpenAI GPT Image). |
| **RSS import** | Pull your back catalog from the feed. The app uses transcripts when the feed has them and show notes otherwise. The AI suggests topic, scripture and themes for you to review before import. Feed artwork and show notes are copied in too. |
| **Library** | Search and filter by status, theme, book or series. Sort by episode number, scripture (in Bible order) or publication date. Show 10, 25, 50, 100 or all episodes per page. |
| **Coverage map** | Heat map of all 66 books, theme history and timeline, plus AI-suggested topics that fill gaps. |
| **Series** | Color-coded series with their own pages, showing cover art, episode list and scripture coverage. Add episodes from the Library, the episode page or the Planner. |
| **Planner** | Month calendar. Drag suggestions or drafts onto days. The Dashboard shows upcoming episodes and flags any that are *Overdue*, *Behind schedule* or *Not started*. |
| **Repetition awareness** | The intake form warns about past episodes with the same scripture, book or theme. The AI is told what has already been covered. |
| **Accounts and security** | Username/password login with httpOnly cookies, lockout after 5 failed attempts, and Admin and Producer roles. There is no public sign-up. Accounts are ready for MFA to be added later. |
| **Backups** | One-click `.zip` backup (database plus artwork) from the Dashboard. Restore it in Settings, or during first-run setup on a new server. |

## Stack
| Service | Role |
|---|---|
| `mongo` | MongoDB 7 (volume `mongo_data`) |
| `backend` | FastAPI / Python 3.11: auth, episodes, AI calls, RSS, `.docx` import/export, backups. Artwork in volume `media_data` |
| `frontend` | React app served by nginx, which also proxies `/api` to the backend |
| `cloudflared` | Optional Cloudflare Tunnel connector (`--profile tunnel`) |

---

## Quick install (Ubuntu/Debian)
```bash
curl -fsSL https://raw.githubusercontent.com/rgblack316/podcast-producer/main/install.sh | sudo bash
```
The installer:
1. Installs `git`, `curl`, `openssl` and **Docker Engine + Compose**, if they are missing.
2. Clones the repo to **`/opt/podcast-producer`**.
3. Asks for the web **port** (default `8080`) and an optional **Cloudflare Tunnel token**.
4. Writes `/opt/podcast-producer/.env` with a fresh `JWT_SECRET` and `SETUP_TOKEN`.
5. Builds and starts the containers. The first build takes a few minutes.
6. Prints the local address and the **setup token** you'll need once in the browser.

Optional overrides: `REPO_URL`, `BRANCH`, `INSTALL_DIR`, `APP_PORT`, `CLOUDFLARE_TUNNEL_TOKEN`, `NONINTERACTIVE=1`, for example:
```bash
curl -fsSL https://raw.githubusercontent.com/rgblack316/podcast-producer/main/install.sh | sudo APP_PORT=9000 NONINTERACTIVE=1 bash
```
> The repository must be **public** for the `curl` command to work.

## Upgrading
```bash
sudo podcast-producer-upgrade          # same as: sudo /opt/podcast-producer/upgrade.sh
```
The upgrade script:
1. Saves a **pre-upgrade backup** to `/opt/podcast-producer/backups/` (database archive plus artwork `.tgz`). It keeps the last 10.
2. Fetches the latest code and **resets tracked files to GitHub**. Local edits to app files are discarded. `.env`, `backups/` and all data in Docker volumes are never touched.
3. Rebuilds and restarts the containers, then prunes old images.

Options: `BRANCH=main`, `SKIP_BACKUP=1`, `KEEP_BACKUPS=10`, `FORCE_REBUILD=1`.

---

## First-run setup
On a fresh install no accounts exist, so the browser shows the **setup wizard** instead of the login page.

- **Start fresh**
  1. Enter the **setup token**, which was printed by the installer and is stored as `SETUP_TOKEN` in `.env`.
  2. Create the **admin account**.
  3. Describe the **podcast**: name, tagline, host(s), about the show, audience. The AI reads this before every generation.
  4. Choose the **AI provider** and, optionally, paste Gemini and/or OpenAI keys.
- **Restore a backup**: upload a `bible-bytes-backup-*.zip` to restore accounts, episodes, documents, plans, series, settings and artwork in one step. Then sign in with an account from the backup.

After setup:
1. **Settings → AI provider & keys**: add keys and click **Test connection**. Choose the text and image models.
   - Gemini key: https://aistudio.google.com/apikey
   - OpenAI key: https://platform.openai.com/api-keys
2. **Settings → Reference documents**: upload the planning template and example `.docx` episodes.
3. **Import**: paste your RSS feed URL and bring in the back catalog.
4. **Settings → Users**: add your team as Admins or Producers.

---

## Publishing through Cloudflare Tunnel
1. Cloudflare → **Zero Trust → Networks → Tunnels → Create a tunnel** (type *Cloudflared*). Copy the **token**.
2. Add a **Public hostname**, e.g. `producer.yourdomain.com`, with service type **HTTP** and URL **`frontend:80`**.
3. Put the token in `/opt/podcast-producer/.env` as `CLOUDFLARE_TUNNEL_TOKEN=...` (or enter it during install).
4. Apply it with `sudo podcast-producer-upgrade`. The tunnel container starts automatically when a token is set. The manual equivalent is `docker compose --profile tunnel up -d`.
5. Visit `https://producer.yourdomain.com`.

Extra hardening (optional):
- **Zero Trust → Access → Applications**: protect the hostname so Cloudflare asks for an email one-time code before the login page appears.
- Once the tunnel works, block `APP_PORT` on the server firewall, or remove the `ports:` block in `docker-compose.yml`. The app is then reachable only through Cloudflare.

---

## Configuration (.env)
| Variable | Purpose |
|---|---|
| `DB_NAME` | MongoDB database name (default `biblebytes`) |
| `JWT_SECRET` | Long random string used to sign login tokens (`openssl rand -hex 32`) |
| `SETUP_TOKEN` | Required to complete the first-run wizard, so strangers can't claim the admin account. If it is empty, setup is locked and cannot be completed. Wrong guesses are rate-limited |
| `COOKIE_SECURE` | `true` when accessed over HTTPS (tunnel). `false` only for plain-http LAN use |
| `APP_PORT` | Port on the server where the web app is published (default `8080`) |
| `CLOUDFLARE_TUNNEL_TOKEN` | Optional tunnel token. When set, the `cloudflared` container runs |
| `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `ADMIN_FORCE_RESET` | **Recovery only.** Leave them blank normally (see [Troubleshooting](#troubleshooting)) |

API keys, models, podcast details and the RSS feed URL are **not** in `.env`. They are stored in the database and edited in **Settings**.

---

## Using the app
**Dashboard**: stats, upcoming planned episodes with schedule flags, episodes in progress, recent episodes, top themes and books. Admins also get **Back up now**.

**New episode → Outline → Script → Done**
1. Fill in the intake form. Similar past episodes appear as a warning.
2. **Generate outline**, or *Write it myself*. Revise with notes or edit by hand. Earlier versions are kept and can be restored. Click **Approve outline**.
3. **Generate script** from the approved outline and refine it the same way. Click **Mark script complete**, then **Mark published**.
4. Export the outline or script as `.docx`, or copy it.
5. **Show notes** tab: one click creates show notes, a description and social posts.
6. **Artwork** tab: brainstorm concepts, generate images, and set the episode art.
7. The **Series** panel on the episode page adds the episode to a series, moves it or removes it.

Background generations keep running even if Cloudflare's 100-second request limit is hit. The page checks back until the result is ready.

**Library**: search; filter by status, theme, book or series; sort by **#**, **Scripture** (Bible order) or **Published**. Click a header again to reverse the order. Choose **10 / 25 / 50 / 100 / All** per page. Tick episodes, then **Add to series** or **Remove from series**.

**Import (admins)**
1. **Fetch feed** reads every episode. Running it again only adds new ones.
2. **Analyze N new with AI** fills in topic, scripture and themes in the background. It stops early if the API key is rejected.
3. Review the suggestions in **Ready to review**. Correct them in the review dialog, then **Add to library**. Episodes are added as Published with their feed date, artwork and show notes.
4. **Pull artwork & show notes** updates episodes imported earlier. Show notes you have edited are never overwritten.

**Coverage**: Old and New Testament heat maps, theme history and a monthly timeline. **Suggest** asks the AI for gap-filling topics, each with **Start episode** and **Add to plan**.

**Planner**: month calendar with colored series. Drag Coverage suggestions or in-progress episodes onto days. Drag chips to reschedule, or drop them on *Unscheduled*. Clicking a chip lets you edit it, open the episode or start one.

**Series**: a grid of series covers. Each series page shows its episodes in date order, its books and themes, and a **cover art** section. You can upload an image, copy artwork from one of its episodes, or generate one with the AI studio.

**Settings (admins)**
- **AI**: podcast information, default text and image provider, models, API keys (only the last 4 characters are ever shown), standing instructions.
- **Reference documents**: one active planning template, plus example episodes you can switch on or off.
- **Users**: add, deactivate, change roles, reset passwords.
- **Backup**: download a backup, or restore one.

**Account**: change your password.

---

## Backups and restore
**From the app (recommended):** **Dashboard → Back up now**, or **Settings → Backup**, downloads `bible-bytes-backup-YYYY-MM-DD.zip`. It contains the database collections and all artwork.
> The backup includes API keys and password hashes, so store it privately.

**Restore** a backup in **Settings → Backup** (this replaces everything and signs you out) or in the **first-run wizard** on a new server.

**Automatic:** every `upgrade.sh` run saves a pre-upgrade backup to `backups/`.

**Command line:**
```bash
cd /opt/podcast-producer
docker compose exec -T mongo mongodump --archive --db biblebytes > backups/manual-$(date +%F).archive
docker run --rm -v podcast-producer_media_data:/m -v $PWD/backups:/b alpine tar czf /b/media-$(date +%F).tgz -C /m .

# restore
docker compose exec -T mongo mongorestore --archive --drop < backups/manual-YYYY-MM-DD.archive
docker run --rm -v podcast-producer_media_data:/m -v $PWD/backups:/b alpine sh -c "rm -rf /m/* && tar xzf /b/media-YYYY-MM-DD.tgz -C /m"
```

---

## Everyday commands
```bash
cd /opt/podcast-producer
docker compose ps                         # status
docker compose logs -f backend            # API logs
docker compose restart backend            # restart one service
docker compose down                       # stop (data stays in the volumes)
docker compose up -d                      # start again
sudo podcast-producer-upgrade             # update to the latest version
```
If you use the tunnel, add `--profile tunnel` to `up`/`down`, or simply use the upgrade script.

## Troubleshooting
| Problem | Fix |
|---|---|
| Login works on `localhost` but not over plain `http://<ip>` | Browsers reject secure cookies over http. Use the tunnel (HTTPS), or set `COOKIE_SECURE=false` and run the upgrade script. |
| "API key not valid" during generation or RSS analysis | Re-enter the key in **Settings → AI** and click **Test connection**. |
| Lost the admin password | In `.env`, set `ADMIN_USERNAME=<admin>`, `ADMIN_PASSWORD=<new>` and `ADMIN_FORCE_RESET=true`. Run `sudo podcast-producer-upgrade`, sign in, then clear those three values and run the upgrade again. |
| Installer was interrupted (closed terminal, build error) | Run the same `curl … | sudo bash` command again. If no `.env` exists yet, it updates the download and continues the install; once `.env` exists, use `sudo /opt/podcast-producer/upgrade.sh` instead. |
| Setup wizard says "Invalid setup token" | Use the `SETUP_TOKEN` value from `/opt/podcast-producer/.env`. |
| Large backup restore fails | Uploads are limited to 512 MB (nginx `client_max_body_size`). Restore larger backups from the command line. |
| Tunnel shows an error page | In Cloudflare, check that the public hostname points to `http://frontend:80`, and run `docker compose logs cloudflared`. |

---

## Manual install (without the script)
Requirements: Docker Engine with the Compose plugin (Linux, macOS, or Windows with WSL2).
```bash
git clone https://github.com/rgblack316/podcast-producer.git /opt/podcast-producer
cd /opt/podcast-producer
cp .env.example .env
nano .env        # set JWT_SECRET (openssl rand -hex 32), SETUP_TOKEN, APP_PORT, COOKIE_SECURE
docker compose up -d --build                     # add --profile tunnel when using Cloudflare Tunnel
```
Open `http://<server-ip>:<APP_PORT>` and complete the setup wizard.

## Local development
Backend (Python 3.11):
```bash
cd backend
pip install -r requirements.docker.txt
# backend/.env: MONGO_URL, DB_NAME, JWT_SECRET, COOKIE_SECURE=false, MEDIA_DIR=./media, CORS_ORIGINS=http://localhost:3000
uvicorn server:app --reload --port 8001
```
Frontend:
```bash
cd frontend
yarn install
REACT_APP_BACKEND_URL=http://localhost:8001 yarn start
```
Tests: `cd backend && python -m pytest tests/`. `tests/conftest.py` snapshots the database's real data before the tests and restores it afterwards.

## Project structure
```
install.sh / upgrade.sh     one-line installer and safe upgrader
docker-compose.yml          mongo, backend, frontend (nginx), optional cloudflared
.env.example                server configuration template
backend/
  server.py                 app + router wiring, indexes, startup
  auth.py                   login, cookies/JWT, lockout, users (admin)
  setup.py                  first-run wizard, backup download/restore
  episodes.py               episodes, versions, status flow, export, similar, sorting keys
  extras.py                 show notes, coverage map + suggestions, episode artwork studio
  rss_import.py             feed fetch/parse, transcript reading, AI analysis, import + artwork/show-notes sync
  planner.py                series, plan items, series membership
  series_art.py             series detail page data + series cover art
  admin.py                  settings (AI keys/models, podcast info), reference documents
  llm.py / prompts.py       Gemini/OpenAI REST clients and prompt building
  bible.py / docx_utils.py  scripture parsing, .docx text extraction and export
frontend/src/
  pages/                    Dashboard, NewEpisode, Episode, Library, Coverage, Planner, Series, Import, Settings, Setup, Login
  components/               editors, artwork studio, planner, settings panels, shadcn/ui
```

## Notes
- Scripture references are free text. The app doesn't fetch verse text, so check quotations against your preferred translation.
- Only text is extracted from uploaded `.docx` files. Exported `.docx` files use clean, simple formatting.
- AI usage is billed by Google or OpenAI to your own keys.
