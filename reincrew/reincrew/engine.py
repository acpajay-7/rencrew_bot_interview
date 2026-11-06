"""Evaluation engine for the three modes.
API    : every answer scored by OpenRouter/DeepSeek.
LOCAL  : Ollama on loopback only; if unavailable falls back to the RULE scorer (still zero external calls) and says so.
HYBRID : answers scored locally (Ollama or rules) during the interview; ONE batched API call at the end; results cached.
"""
import hashlib
import json

from . import api_ai, local_ai
from .scorer import score_answer

MODES = ["API Mode", "Local AI Mode", "Hybrid Mode"]
MODE_NOTES = {
    "API Mode": "Uses OpenRouter (DeepSeek Chat) - external API. Answers are sent to a third party.",
    "Local AI Mode": "Runs on your computer via Ollama. No external AI API calls.",
    "Hybrid Mode": "Local scoring during the interview + ONE external API call at the end. Not offline.",
}


def _local_eval(question: dict, transcript: str) -> dict:
    """Ollama if reachable, else rule-based. Never touches an external API."""
    try:
        return local_ai.score_with_ollama(question, transcript)
    except Exception as e:
        r = score_answer(question, transcript)
        r["scoring_mode"] = "rule_based_fallback"
        r["explanation"] += f" (Local model unavailable: {e.__class__.__name__}; rule-based scorer used.)"
        return r


def _cache_key(question: dict, transcript: str, mode: str) -> str:
    return hashlib.sha256(json.dumps([question["question"], transcript, mode]).encode()).hexdigest()


def evaluate_answer(mode: str, question: dict, transcript: str, db=None, api_key: str = None) -> dict:
    if not (transcript or "").strip():
        return score_answer(question, "")
    if mode == "API Mode":
        key = _cache_key(question, transcript, mode)
        if db and (hit := db.cache_get(key)):
            return hit
        try:
            res = api_ai.score_with_api(question, transcript, api_key)
        except Exception as e:  # surface, then fall back to rules so the interview can continue
            res = score_answer(question, transcript)
            res["scoring_mode"] = "rule_based_fallback"
            res["explanation"] += f" (API unavailable: {e.__class__.__name__}.)"
            return res
        if db:
            db.cache_set(key, res)
        return res
    return _local_eval(question, transcript)  # Local and Hybrid (interim) scoring


def finalize_hybrid(items: list, db=None, api_key: str = None) -> list:
    """items: [{'question': q, 'transcript': t, 'evaluation': local_eval}] -> upgraded evaluations.
    One API call for all non-empty answers. On any failure the local evaluations are kept."""
    live = [(i, it) for i, it in enumerate(items) if (it["transcript"] or "").strip()]
    if not live:
        return [it["evaluation"] for it in items]
    payload = [{"n": n + 1, "question": it["question"]["question"], "reference": it["question"].get("reference", ""),
                "transcript": it["transcript"]} for n, (_, it) in enumerate(live)]
    key = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    cached = db.cache_get(key) if db else None
    try:
        results = cached["results"] if cached else api_ai.score_batch_with_api(payload, api_key)
        if db and not cached:
            db.cache_set(key, {"results": results})
    except Exception as e:
        out = [it["evaluation"] for it in items]
        for ev in out:
            ev["explanation"] = ev.get("explanation", "") + f" (Hybrid API step failed: {e.__class__.__name__}; local scores kept.)"
        return out
    out = [it["evaluation"] for it in items]
    for (idx, _), res in zip(live, results):
        if res:
            out[idx] = res
    return out
