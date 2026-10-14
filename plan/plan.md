# Bible Bytes Producer

A private, self-hosted web app for planning and writing episodes of the Bible Bytes podcast. You enter an episode's topic, title and scripture, and AI drafts an outline using your planning template; once you approve the outline, it writes the full script.

## Who it's for
- The Bible Bytes host and a small production team who need a consistent, repeatable way to plan, write and track episodes.
- An admin who manages team accounts, AI provider settings and the reference documents.

## Core features and experience
- **Secure login**: Username and password for each team member. The admin creates, deactivates and resets accounts. The login system is built so MFA (authenticator app codes) can be added later without redoing accounts.
- **New episode intake**: A form for show title, episode number, topic, primary and supporting scripture references, theme(s), target length, audience notes and any extra guidance.
- **Outline generation**: AI writes a structured outline that follows the uploaded planning template. Previous example episodes are used for tone and format.
- **Outline review loop**: Edit the outline directly, or give the AI revision notes ("make the intro shorter, add an application point") and get a new version. Earlier versions are kept. Approving locks the outline and opens the script step.
- **Script generation**: AI writes the full script from the approved outline, the planning template and the examples. It can be edited inline or revised with notes, the same way as the outline.
- **Export**: Download the final script as a .docx file, or copy the text in one click.
- **Episode library (database)**: Every episode is saved with its status (Draft → Outline Approved → Script Complete → Published), topic, themes, scriptures, dates, outline and script. Search and filter by topic, theme, book of the Bible or scripture.
- **Repetition awareness**: When you start a new episode, the app shows past episodes that used the same scripture or theme. The AI is also told what has already been covered so it doesn't repeat itself.
- **Reference documents**: Upload the planning template and past episode .docx files. The app extracts their text and stores it as AI guidance. You can replace a template or turn individual examples on or off.
- **Import past episodes**: Uploaded example episodes can also be added to the library (with title, scripture and themes filled in by hand or suggested by AI) so tracking starts with your full back catalog.
- **AI settings**: Choose Google Gemini or OpenAI ChatGPT as the default, and switch per generation if you want. API keys are entered by the admin and stored on your server only.

## User flow
1. Sign in.
2. Open the Dashboard to see recent episodes, what's in progress and a "New Episode" button.
3. Fill in the intake form. Similar past episodes appear as a warning.
4. Generate the outline, then review it, edit it or request revisions until it's ready, and approve.
5. Generate the script from the approved outline, then review it, edit it or revise with notes.
6. Mark the script complete, then export it as .docx or copy it.
7. Later, mark the episode Published. It stays searchable in the library.
- Admin only: Settings → Users, AI Provider & Keys, Reference Documents.

## UI/UX feel
- A calm, editorial writing room: warm paper-toned surfaces, a classic serif for headings and scripture, and a clean sans-serif for interface text.
- A side-by-side workspace for review, with the intake details and scripture on one side and the outline or script editor on the other.
- A clear step indicator (Intake → Outline → Script → Done) on every episode.
- Comfortable reading widths and generous spacing, built for long writing sessions. Desktop comes first, and it stays usable on a tablet or phone.

## Implementation phases
**Phase 1 — MVP (built now)**
- Username/password login, admin-managed team accounts, and an account structure ready for MFA.
- Episode intake, outline generation with the revise/edit/approve loop, and script generation with the same loop.
- Gemini and OpenAI support using your own API keys, selectable in settings.
- Upload the planning template and example episodes as .docx files, with text extraction used as AI guidance.
- Episode library with search and filters, status tracking and similar-episode warnings.
- .docx export and copy text.
- Fully containerized (one command to start) with setup instructions for your local server and a Cloudflare Tunnel. No Emergent services or keys are used.

**Phase 2**
- MFA (authenticator app) per user, which can be made required for everyone.
- Bulk import of the back catalog with AI-suggested topics, themes and scriptures.
- Topic and theme coverage views (for example, books of the Bible covered, themes over time) and AI-suggested future topics.
- Version comparison between outline and script revisions.

**Phase 3**
- Extra production assets from the script: show notes, episode description, social posts and title ideas.
- Episode calendar and series planning.
- Backup/restore from the settings page, plus an audit log of who changed what.

## Assumptions
- Because the app must be free of Emergent infrastructure, it calls Google and OpenAI directly with **your own API keys**. The Emergent universal key is not used. AI usage is billed by those providers.
- The first admin account is created during setup with credentials you choose (from the configuration file). The admin adds the other team members. There is no public sign-up.
- Two roles: **Admin** (users, settings, reference documents) and **Producer** (create and edit episodes). All producers can see and edit all episodes.
- One active planning template at a time. Multiple example episodes can be active at once.
- Only text is extracted from .docx uploads. Images and complex formatting in the source files are ignored.
- Exported .docx scripts use clean, simple formatting (headings, paragraphs, scripture callouts), not a copy of your original document styling.
- Scripture references are free text. The app does not fetch Bible verse text from an outside source. The AI uses its own knowledge, and you remain responsible for checking quotations and translation.
- HTTPS is provided by Cloudflare Tunnel. Optionally, Cloudflare Access can be put in front of the app as an extra security layer.
- Data (episodes, documents, users) lives in a database volume on your server. Backups are your responsibility in Phase 1.
- Model choices default to a current fast Gemini model and a current OpenAI GPT model, and can be changed in settings.
