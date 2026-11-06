"""OpenRouter + DeepSeek Chat client. Key comes from env var / Streamlit secrets, never from code or DB.
NOTE: the original repo did not contain an API interviewer file."""
import requests

from . import config
from .jsonutil import extract_json
from .local_ai import clamp_result
from .prompts import INTERVIEWER_SYSTEM_PROMPT, batch_evaluation_prompt, evaluation_prompt, generation_prompt


class ApiNotConfigured(RuntimeError):
    pass


def chat(messages: list, api_key: str = None, json_mode: bool = True, timeout: int = 120) -> str:
    key = api_key or config.openrouter_key()
    if not key:
        raise ApiNotConfigured("OPENROUTER_API_KEY is not set (use .env or Streamlit secrets).")
    body = {"model": config.OPENROUTER_MODEL, "messages": messages, "temperature": 0.2}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    r = requests.post(config.OPENROUTER_URL, json=body, timeout=timeout,
                      headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def score_with_api(question: dict, transcript: str, api_key: str = None) -> dict:
    raw = chat([{"role": "user", "content": evaluation_prompt(question, transcript)}], api_key)
    return clamp_result(extract_json(raw), "api_openrouter")


def score_batch_with_api(items: list, api_key: str = None) -> list:
    """ONE API call for a whole interview (Hybrid mode). items: [{'n','question','reference','transcript'}]."""
    raw = chat([{"role": "user", "content": batch_evaluation_prompt(items)}], api_key, timeout=180)
    results = extract_json(raw).get("results", [])
    by_n = {r.get("n"): r for r in results}
    out = []
    for it in items:
        r = by_n.get(it["n"])
        out.append(clamp_result(dict(r), "hybrid_api_batch") if r else None)
    return out


def generate_questions(profile: dict, existing: list, k: int = 3, api_key: str = None) -> list:
    """Returns raw candidate question dicts (stream attached). Caller MUST validate + save as pending."""
    raw = chat([{"role": "system", "content": INTERVIEWER_SYSTEM_PROMPT},
                {"role": "user", "content": generation_prompt(profile, existing, k)}], api_key)
    qs = extract_json(raw).get("questions", [])
    for q in qs:
        q["stream"] = profile["stream"]
        q["specialization"] = profile.get("specialization")
        q["experience_level"] = profile["experience_level"]
        q["interview_type"] = profile["interview_type"]
    return qs
