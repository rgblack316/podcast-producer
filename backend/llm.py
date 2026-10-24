import httpx
from fastapi import HTTPException

from core import db, NO_ID
from secrets_box import KEY_FIELDS, decrypt

DEFAULT_SETTINGS = {
    "id": "app",
    "show_name": "Bible Bytes",
    "default_provider": "gemini",
    "gemini_api_key": "",
    "gemini_model": "gemini-2.5-flash",
    "openai_api_key": "",
    "openai_model": "gpt-5-mini",
    "extra_instructions": "",
    "image_provider": "gemini",
    "gemini_image_model": "gemini-2.5-flash-image",
    "openai_image_model": "gpt-image-1.5",
    "show_tagline": "",
    "host_names": "",
    "show_description": "",
    "audience": "",
}
TIMEOUT = httpx.Timeout(600.0, connect=20.0)


async def get_settings() -> dict:
    doc = await db.settings.find_one({"id": "app"}, NO_ID)
    merged = {**DEFAULT_SETTINGS, **(doc or {})}
    for k in KEY_FIELDS:
        merged[k] = decrypt(merged.get(k, ""))
    return merged


async def _openai(key: str, model: str, system: str, prompt: str) -> str:
    async with httpx.AsyncClient(timeout=TIMEOUT) as c:
        r = await c.post("https://api.openai.com/v1/chat/completions",
                         headers={"Authorization": f"Bearer {key}"},
                         json={"model": model, "messages": [{"role": "system", "content": system},
                                                            {"role": "user", "content": prompt}]})
    if r.status_code >= 400:
        raise RuntimeError(f"OpenAI error {r.status_code}: {r.text[:500]}")
    return r.json()["choices"][0]["message"]["content"] or ""


async def _gemini(key: str, model: str, system: str, prompt: str) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    body = {"systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}]}
    async with httpx.AsyncClient(timeout=TIMEOUT) as c:
        r = await c.post(url, headers={"x-goog-api-key": key}, json=body)
    if r.status_code >= 400:
        raise RuntimeError(f"Gemini error {r.status_code}: {r.text[:500]}")
    data = r.json()
    parts = (data.get("candidates") or [{}])[0].get("content", {}).get("parts", [])
    text = "".join(p.get("text", "") for p in parts)
    if not text:
        raise RuntimeError(f"Gemini returned no text: {str(data)[:300]}")
    return text


def resolve_provider(settings: dict, provider: str | None) -> str:
    provider = provider or settings["default_provider"]
    if provider not in ("gemini", "openai"):
        raise HTTPException(status_code=400, detail="Unknown AI provider")
    if not settings.get(f"{provider}_api_key"):
        raise HTTPException(status_code=400, detail=f"No API key set for {provider}. An admin can add one in Settings.")
    return provider


async def generate(settings: dict, provider: str, system: str, prompt: str) -> str:
    key, model = settings[f"{provider}_api_key"], settings[f"{provider}_model"]
    fn = _gemini if provider == "gemini" else _openai
    return (await fn(key, model, system, prompt)).strip()
