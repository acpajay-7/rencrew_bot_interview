"""Local Ollama evaluator (extends the original local_ai.py). Local mode may ONLY talk to a loopback address.
Rule: if OLLAMA_URL is not 127.0.0.1/localhost/::1 this module refuses to send anything."""
import os
from urllib.parse import urlparse

import requests

from . import config
from .jsonutil import extract_json
from .prompts import evaluation_prompt
from .scorer import WEIGHTS

LOOPBACK = {"127.0.0.1", "localhost", "::1"}


class NonLocalEndpointError(RuntimeError):
    pass


def assert_loopback(url: str):
    host = urlparse(url).hostname
    if host not in LOOPBACK:
        raise NonLocalEndpointError(f"Local mode refuses non-local endpoint: {host}")


def clamp_result(result: dict, mode: str) -> dict:
    for key in ("correctness_score", "knowledge_depth_score", "completeness_score"):
        try:
            result[key] = max(0, min(100, int(result.get(key, 0))))
        except (TypeError, ValueError):
            result[key] = 0
    # final score recomputed with the original 60/25/15 weights so it is consistent across modes
    result["final_score"] = round(result["correctness_score"] * WEIGHTS["correctness"]
                                  + result["knowledge_depth_score"] * WEIGHTS["depth"]
                                  + result["completeness_score"] * WEIGHTS["completeness"])
    if result.get("status") not in ("complete", "partial", "incorrect"):
        result["status"] = "partial"
    result.setdefault("explanation", "The model returned no explanation.")
    result.setdefault("confidence", "low")
    result.setdefault("unsupported_claims", [])
    result.setdefault("contradictions", [])
    result["scoring_mode"] = mode
    return result


def ollama_status(url: str = None, model: str = None) -> dict:
    """Used by the UI to show model availability. Loopback only."""
    url = url or config.OLLAMA_URL
    model = model or config.OLLAMA_MODEL
    try:
        assert_loopback(url)
        tags = url.rsplit("/api/", 1)[0] + "/api/tags"
        r = requests.get(tags, timeout=3)
        r.raise_for_status()
        names = [m.get("name") for m in r.json().get("models", [])]
        ok = any(n and n.split(":")[0] == model.split(":")[0] and (":" not in model or n == model) for n in names)
        return {"running": True, "model_available": ok, "models": names,
                "message": "Ready" if ok else f"Ollama is running but model '{model}' is not pulled. Run: ollama pull {model}"}
    except NonLocalEndpointError as e:
        return {"running": False, "model_available": False, "models": [], "message": str(e)}
    except Exception as e:
        return {"running": False, "model_available": False, "models": [], "message": f"Ollama not reachable: {e.__class__.__name__}"}


def score_with_ollama(question: dict, transcript: str, url: str = None, model: str = None) -> dict:
    url = url or config.OLLAMA_URL
    model = model or config.OLLAMA_MODEL
    assert_loopback(url)
    response = requests.post(url, json={"model": model, "prompt": evaluation_prompt(question, transcript),
                                        "stream": False, "format": "json"}, timeout=180)
    response.raise_for_status()
    return clamp_result(extract_json(response.json().get("response", "{}")), "local_ollama")
