"""Seeding, validation of AI-generated questions, and saving them as PENDING (never auto-approved)."""
import json
from .config import SEED_PATH
from .db import Database
from .streams import DIFFICULTIES


def seed_if_empty(db: Database) -> int:
    with db.conn() as c:
        if c.execute("SELECT COUNT(*) n FROM questions").fetchone()["n"] > 0:
            return 0
    n = 0
    for q in json.loads(SEED_PATH.read_text(encoding="utf-8")):
        qid, _ = db.add_question(q, check_duplicates=False)
        n += 1 if qid else 0
    return n


def validate_generated(q: dict) -> list:
    """Returns a list of problems; empty list means the question may be saved as pending."""
    problems = []
    text = (q.get("question") or "").strip()
    if len(text) < 15 or len(text) > 400:
        problems.append("question text must be 15-400 characters")
    if not text.endswith("?") and not text.lower().startswith(("explain", "describe", "define", "compare", "list", "state")):
        problems.append("question should be a question or an instruction like Explain/Describe")
    if not (q.get("reference") or "").strip():
        problems.append("missing reference answer")
    if not q.get("concepts") or not isinstance(q["concepts"], dict):
        problems.append("missing concept groups")
    if q.get("difficulty") not in DIFFICULTIES:
        problems.append("difficulty must be Beginner/Intermediate/Advanced")
    if not q.get("stream"):
        problems.append("missing stream")
    return problems


def save_generated(db: Database, q: dict) -> tuple:
    """Validate -> duplicate check -> save as status='pending', source='ai_generated'. Admin must approve."""
    problems = validate_generated(q)
    if problems:
        return None, "rejected: " + "; ".join(problems)
    q = {**q, "status": "pending", "source": "ai_generated"}
    return db.add_question(q)
