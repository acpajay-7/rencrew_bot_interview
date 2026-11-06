import json
import re


def extract_json(raw: str):
    """Parse JSON from model output; strips <think> blocks and code fences. Raises ValueError if none found."""
    raw = re.sub(r"<think>.*?</think>", "", raw or "", flags=re.S).strip()
    raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.M).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", raw, flags=re.S)
        if m:
            return json.loads(m.group(0))
    raise ValueError("model did not return valid JSON")
