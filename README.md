# Bible Bytes Producer

Self-hosted episode planning and scripting studio for the **Bible Bytes** podcast.
Intake → AI outline (from your planning template + example episodes) → review/revise/approve → AI full script → export .docx.

Runs entirely on your own server with Docker. It talks directly to Google Gemini or OpenAI using **your own API keys** — no Emergent services are used at runtime.

## Stack
| Service | What it does |
|---|---|
| `mongo` | MongoDB 7 database (episodes, users, documents, settings) stored in the `mongo_data` volume |
| `backend` | FastAPI (Python) API: auth, episodes, AI generation, .docx import/export |
| `frontend` | React app served by nginx, which also proxies `/api` to the backend |
| `cloudflared` | Optional Cloudflare Tunnel connector (enabled with `--profile tunnel`) |

## 1. Install on the local server
Requirements: Docker Engine + Docker Compose plugin (Linux, macOS or Windows with WSL2).

```bash
git clone <your repo> bible-bytes-producer && cd bible-bytes-producer
cp .env.example .env
openssl rand -hex 32        # paste the result into JWT_SECRET in .env
nano .env                   # set ADMIN_USERNAME / ADMIN_PASSWORD
docker compose up -d --build
```
Open `http://<server-ip>:8080` (or the `APP_PORT` you chose).

> **Note on cookies:** with `COOKIE_SECURE=true` (the default and recommended for the tunnel) browsers only keep the login cookie over HTTPS or on `http://localhost`. For plain-http LAN testing from another machine, temporarily set `COOKIE_SECURE=false` and run `docker compose up -d`.

## 2. First sign-in
1. Sign in with `ADMIN_USERNAME` / `ADMIN_PASSWORD`.
2. **Settings → AI provider & keys**: paste a Gemini key (https://aistudio.google.com/apikey) and/or an OpenAI key (https://platform.openai.com/api-keys), pick the default, click **Test connection**. Model names are editable (defaults `gemini-2.5-flash`, `gpt-5-mini`).
3. **Settings → Reference documents**: upload the planning template `.docx` and your past episode `.docx` files. Use **Add to library** on each example to track it as a published episode (AI can suggest the title/scripture/themes).
4. **Settings → Users**: add your team (Admin or Producer).

The admin password in `.env` is only used to create the account the first time. To recover a lost admin password, set `ADMIN_FORCE_RESET=true`, run `docker compose up -d`, sign in, then set it back to `false`.

## 3. Publish through Cloudflare Tunnel
1. Cloudflare dashboard → **Zero Trust → Networks → Tunnels → Create a tunnel** (type *Cloudflared*). Copy the tunnel **token**.
2. Add a **Public hostname**, e.g. `producer.yourdomain.com`, Service **HTTP** → `frontend:80`.
3. Put the token in `.env` as `CLOUDFLARE_TUNNEL_TOKEN=...`
4. Start with the tunnel profile:
   ```bash
   docker compose --profile tunnel up -d --build
   ```
5. Visit `https://producer.yourdomain.com`.

Optional extra layer: **Zero Trust → Access → Applications** → add a self-hosted app for that hostname so Cloudflare requires an email one-time code before the login page is even shown.

You can also close `APP_PORT` on your firewall (or remove the `ports:` block) once the tunnel works, so the app is only reachable through Cloudflare.

## Everyday commands
```bash
docker compose logs -f backend          # watch the API
docker compose pull && docker compose up -d --build   # update after pulling new code
docker compose down                     # stop (data is kept in the volume)
```

## Backups
Generated episode artwork is stored as PNG files in the `media_data` volume (`/data/media` in the backend container); back it up alongside the database:
```bash
docker run --rm -v bible-bytes-producer_media_data:/m -v $PWD:/b alpine tar czf /b/media-$(date +%F).tgz -C /m .
```
```bash
docker compose exec mongo mongodump --archive --db biblebytes > backup-$(date +%F).archive
# restore
docker compose exec -T mongo mongorestore --archive --drop < backup-YYYY-MM-DD.archive
```

## Notes
- Long generations run in the background and the page polls for the result, so Cloudflare's 100-second request limit doesn't cut off a script.
- API keys are stored in your MongoDB only and are never sent to the browser (only the last 4 characters are shown).
- Scripture references are free text; always check quotations against your preferred translation.
- Accounts already have `mfa_enabled` / `mfa_secret` fields reserved for authenticator-app MFA in Phase 2.

## Local development (without Docker)
Backend: `cd backend && pip install -r requirements.docker.txt && uvicorn server:app --reload --port 8001` with a `backend/.env` containing `MONGO_URL`, `DB_NAME`, `JWT_SECRET`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `COOKIE_SECURE=false`.
Frontend: `cd frontend && yarn install && REACT_APP_BACKEND_URL=http://localhost:8001 yarn start` (set `CORS_ORIGINS=http://localhost:3000` on the backend).
