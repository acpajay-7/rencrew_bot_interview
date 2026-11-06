"""Stream-based personalised question selection. Never pulls from outside the candidate's stream family."""
import random
from .db import Database
from .streams import DIFFICULTIES, EXPERIENCE_TO_DIFFICULTY, family_streams
from .scorer import normalize


def _relevance(q: dict, profile: dict) -> int:
    score = 3 if q["stream"] == profile["stream"] else 0
    spec = normalize(profile.get("specialization") or "")
    if spec and spec in normalize(" ".join(filter(None, [q.get("specialization"), q.get("topic"), q.get("subtopic")]))):
        score += 3
    hay = normalize(" ".join(filter(None, [q.get("specialization"), q.get("topic"), q.get("subtopic"), q["question"]])))
    for skill in profile.get("skills", []):
        s = normalize(skill)
        if s and s in hay:
            score += 2
    if profile["interview_type"] != "Mixed Interview" and q.get("interview_type") == profile["interview_type"]:
        score += 1
    return score


def select_questions(db: Database, profile: dict, n: int = 5, seed=None) -> dict:
    """Returns {'questions': [...], 'shortage': int, 'notes': [...]}. Questions are approved only, no repeats."""
    rng = random.Random(seed)
    pool = db.list_questions(status="approved", streams=family_streams(profile["stream"]))
    notes = []
    allowed = EXPERIENCE_TO_DIFFICULTY.get(profile["experience_level"], DIFFICULTIES)
    primary = [q for q in pool if q["difficulty"] in allowed]
    chosen, seen = [], set()

    def take(candidates):
        ranked = sorted(candidates, key=lambda q: (-_relevance(q, profile), rng.random()))
        for q in ranked:
            if len(chosen) >= n:
                return
            if q["id"] not in seen:
                seen.add(q["id"]); chosen.append(q)

    take(primary)
    if len(chosen) < n:
        rest = [q for q in pool if q["id"] not in seen]
        if rest:
            notes.append("Not enough questions at the matching difficulty; added nearby difficulty from the same stream.")
        take(rest)
    # difficulty progression: easy -> hard, relevance as tie-break
    chosen.sort(key=lambda q: (DIFFICULTIES.index(q["difficulty"]), -_relevance(q, profile)))
    shortage = max(0, n - len(chosen))
    if shortage:
        notes.append(f"Only {len(chosen)} approved questions exist for this stream; {shortage} short. "
                     "Add questions in Admin or use API/Hybrid mode to generate pending ones.")
    return {"questions": chosen, "shortage": shortage, "notes": notes}
