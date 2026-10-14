from core import db, NO_ID

TEMPLATE_CAP = 30000
EXAMPLE_CAP = 15000
EXAMPLES_TOTAL_CAP = 45000


async def reference_context() -> dict:
    template = await db.documents.find_one({"kind": "template", "active": True}, NO_ID)
    examples = await db.documents.find({"kind": "example", "active": True}, NO_ID).sort("created_at", -1).to_list(50)
    ex_texts, total = [], 0
    for ex in examples:
        chunk = ex["text"][:EXAMPLE_CAP]
        if total + len(chunk) > EXAMPLES_TOTAL_CAP:
            break
        total += len(chunk)
        ex_texts.append(f"--- EXAMPLE: {ex['filename']} ---\n{chunk}")
    return {"template": template["text"][:TEMPLATE_CAP] if template else "", "examples": ex_texts}


async def covered_summary(exclude_id: str | None) -> str:
    q = {"id": {"$ne": exclude_id}} if exclude_id else {}
    eps = await db.episodes.find(q, {"_id": 0, "title": 1, "episode_number": 1, "topic": 1,
                                     "primary_scripture": 1, "themes": 1}).sort("created_at", -1).to_list(80)
    lines = [f"- #{e.get('episode_number') or '?'} {e.get('title')}: topic '{e.get('topic')}', "
             f"scripture {e.get('primary_scripture')}, themes {', '.join(e.get('themes') or [])}" for e in eps]
    return "\n".join(lines) or "(none yet)"


def system_prompt(settings: dict, ctx: dict) -> str:
    parts = [
        f"You are the producer and head writer for the Christian podcast \"{settings['show_name']}\". "
        "You write faithful, biblically grounded, engaging podcast content. Quote scripture accurately and name the "
        "translation when quoting. Never invent verses. Output clean Markdown only (headings with #, bullet lists, "
        "and > blockquotes for scripture). Do not wrap the output in code fences and do not add commentary "
        "before or after the document.",
    ]
    about = [f"{label}: {settings.get(k)}" for k, label in
             (("show_tagline", "Tagline"), ("host_names", "Host(s)"), ("show_description", "About the show"),
              ("audience", "Audience")) if settings.get(k)]
    if about:
        parts.append("ABOUT THE SHOW\n" + "\n".join(about))
    if settings.get("extra_instructions"):
        parts.append(f"Standing instructions from the show team:\n{settings['extra_instructions']}")
    if ctx["template"]:
        parts.append("PLANNING TEMPLATE (every episode must follow this structure and its guidance):\n" + ctx["template"])
    else:
        parts.append("No planning template has been uploaded yet; use a clear hook, scripture reading, context, "
                     "main teaching points, application and closing structure.")
    if ctx["examples"]:
        parts.append("PREVIOUS EPISODES (match their tone, voice, pacing and format; do not copy content):\n\n"
                     + "\n\n".join(ctx["examples"]))
    return "\n\n".join(parts)


def intake_block(ep: dict) -> str:
    return "\n".join([
        f"Episode title: {ep.get('title')}",
        f"Episode number: {ep.get('episode_number') or 'n/a'}",
        f"Topic: {ep.get('topic')}",
        f"Primary scripture: {ep.get('primary_scripture')}",
        f"Supporting scriptures: {', '.join(ep.get('supporting_scriptures') or []) or 'none'}",
        f"Themes: {', '.join(ep.get('themes') or []) or 'none'}",
        f"Target length: {ep.get('target_length') or 'standard episode length'}",
        f"Target publication date: {ep.get('target_date') or 'not set'}",
        f"Audience notes: {ep.get('audience_notes') or 'none'}",
        f"Additional guidance: {ep.get('guidance') or 'none'}",
    ])


def outline_prompt(ep: dict, covered: str, current: str | None, notes: str | None) -> str:
    base = (f"EPISODE INTAKE\n{intake_block(ep)}\n\nEPISODES ALREADY COVERED (avoid repeating their angles, "
            f"illustrations and applications):\n{covered}\n\n")
    if current and notes:
        return base + (f"CURRENT OUTLINE\n{current}\n\nREVISION NOTES FROM THE PRODUCER\n{notes}\n\n"
                       "Rewrite the complete outline applying these notes. Keep everything that the notes don't ask "
                       "to change. Return the full revised outline.")
    extra = f"\nProducer notes for this draft: {notes}\n" if notes else ""
    return base + extra + ("Write a detailed episode OUTLINE that follows the planning template section by section. "
                           "For each section include the key points, the scriptures used, and estimated timing.")


def script_prompt(ep: dict, covered: str, current: str | None, notes: str | None) -> str:
    base = (f"EPISODE INTAKE\n{intake_block(ep)}\n\nAPPROVED OUTLINE (follow it closely)\n{ep.get('outline')}\n\n"
            f"EPISODES ALREADY COVERED:\n{covered}\n\n")
    if current and notes:
        return base + (f"CURRENT SCRIPT\n{current}\n\nREVISION NOTES FROM THE PRODUCER\n{notes}\n\n"
                       "Rewrite the complete script applying these notes. Return the full revised script.")
    extra = f"\nProducer notes for this draft: {notes}\n" if notes else ""
    return base + extra + ("Write the FULL word-for-word podcast SCRIPT for this episode, based on the approved "
                           "outline and the planning template. Use the section headings from the outline, write "
                           "natural spoken language for the host, and set scripture readings as blockquotes.")


def metadata_prompt(text: str) -> str:
    return ("Read this past podcast episode and return ONLY a JSON object (no code fences) with keys: "
            "title (string), episode_number (string or empty), topic (string), primary_scripture (string), "
            "supporting_scriptures (array of strings), themes (array of 2-5 short strings).\n\nEPISODE:\n"
            + text[:20000])
