"""Candidate profile validation."""
import re
from .streams import EXPERIENCE_LEVELS, INTERVIEW_TYPES

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
NAME_RE = re.compile(r"^[A-Za-z][A-Za-z .'\-]{1,59}$")


def parse_skills(text: str) -> list:
    seen, out = set(), []
    for s in re.split(r"[,;\n]", text or ""):
        s = s.strip()
        if s and s.lower() not in seen:
            seen.add(s.lower()); out.append(s)
    return out[:25]


def validate_profile(p: dict) -> list:
    errors = []
    if not NAME_RE.match((p.get("name") or "").strip()):
        errors.append("Enter a valid full name (letters, spaces, . ' - only).")
    if not EMAIL_RE.match((p.get("email") or "").strip()):
        errors.append("Enter a valid email address.")
    if not (p.get("stream") or "").strip():
        errors.append("Stream is required.")
    if p.get("experience_level") not in EXPERIENCE_LEVELS:
        errors.append("Choose an experience level.")
    if p.get("interview_type") not in INTERVIEW_TYPES:
        errors.append("Choose an interview type.")
    return errors
