# Bible Bytes Producer — PRD

## Original problem
Producer for the Bible Bytes podcast: intake (topic, title, scripture…) → AI outline from planning template → approve → full script. Database of past episodes (topics, themes, scriptures). LLM = Gemini or OpenAI (user's own keys). Username/password login, MFA-ready. 100% free of Emergent infrastructure, containerized on a local server, exposed via Cloudflare Tunnel.

## Architecture
- FastAPI backend (`server.py`, `auth.py`, `episodes.py`, `admin.py`, `llm.py` direct REST to Gemini/OpenAI via httpx, `prompts.py`, `bible.py` scripture parser, `docx_utils.py`)
- React frontend (CRA/craco, shadcn), nginx in Docker proxies /api
- MongoDB; docker-compose with mongo/backend/frontend + optional cloudflared profile
- Generation runs as background task; UI polls (avoids Cloudflare 100s limit)

## Personas
Host/producers (create episodes), Admin (users, AI keys, reference docs)

## Implemented (Oct 2026)
- JWT cookie auth (username), refresh, brute-force lockout, admin seeding, admin user mgmt, change password, MFA fields reserved
- Intake, similar-episode warnings (chapter/book/theme/topic)
- Outline/script: generate, revise with notes, manual edit, versions + restore, approve/complete/publish/reopen
- .docx export + copy; library search/filters; dashboard stats
- Reference docs upload (.docx text extraction), single active template, toggle examples, import to library with AI metadata suggestion
- AI settings (provider, models, keys masked, test connection, standing instructions)
- Branding: podcast cover art as favicon, header logo, login art
- Docker + README with Cloudflare Tunnel steps
- Tested: 32/32 backend, frontend smoke flows pass. Real AI generation NOT tested (no keys).
- Iteration 2: Show notes/description/social posts (from finished script, edit/revise), Coverage Map page (OT/NT book heat grid, themes, timeline, AI gap-filling suggestions → prefilled intake), Artwork studio (AI art-director brainstorm chat → concepts → editable prompt → 1:1 image via Gemini Nano Banana or OpenAI GPT Image, gallery select/download/delete; files in MEDIA_DIR volume). 47/47 backend tests pass.

## Backlog
- P1: MFA (TOTP), bulk back-catalog import, coverage views, version diff
- P2: calendar/series, backup/restore UI, audit log
