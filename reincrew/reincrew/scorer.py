"""ReinCrew Rule-based & Heuristic Response Scorer"""
from typing import Any, Dict, List, Optional, Set
import re
import unicodedata

WEIGHTS = {
    "correctness": 0.60,
    "knowledge_depth": 0.25,
    "completeness": 0.15,
}

def normalize(text: str) -> str:
    """Normalize text: lowercase, remove diacritics/accents, strip punctuation."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode("utf-8")
    text = re.sub(r"[^\w\s]", " ", text.lower())
    return re.sub(r"\s+", " ", text).strip()

def _tokenize(text: str) -> List[str]:
    """Tokenize normalized text into unique word elements."""
    cleaned = normalize(text)
    return cleaned.split() if cleaned else []

def _concept_matched(concept_keywords: List[str], candidate_tokens: Set[str], candidate_raw: str) -> bool:
    """Check if any keyword or phrase for a concept appears in candidate answer."""
    cand_lower = candidate_raw.lower()
    for kw in concept_keywords:
        kw_clean = kw.strip().lower()
        if not kw_clean:
            continue
        if " " in kw_clean:
            if kw_clean in cand_lower:
                return True
        else:
            if kw_clean in candidate_tokens:
                return True
    return False

def score_answer(question: Dict[str, Any], candidate_answer: str) -> Dict[str, Any]:
    """Evaluate candidate answer and generate structured diagnostic scores."""
    raw = (candidate_answer or "").strip()
    tokens = _tokenize(raw)
    token_set = set(tokens)
    words = len(tokens)

    if not raw or words == 0:
        return {
            "final_score": 0,
            "status": "not_answered",
            "correctness_score": 0,
            "knowledge_depth_score": 0,
            "completeness_score": 0,
            "confidence": "none",
            "key_concepts": [],
            "explanation": "No response provided.",
            "unsupported_claims": [],
            "contradictions": [],
            "scoring_mode": "rule_based",
        }

    concepts_dict = question.get("concepts") or {}
    if isinstance(concepts_dict, str):
        try:
            import json
            concepts_dict = json.loads(concepts_dict)
        except Exception:
            concepts_dict = {}

    total_concepts = len(concepts_dict)
    matched_concepts: List[str] = []

    if total_concepts > 0:
        for cname, kws in concepts_dict.items():
            kw_list = kws if isinstance(kws, list) else [str(kws)]
            if _concept_matched(kw_list, token_set, raw):
                matched_concepts.append(cname)
        concept_coverage = len(matched_concepts) / total_concepts
    else:
        ref_tokens = set(_tokenize(question.get("reference") or ""))
        if ref_tokens:
            overlap = token_set.intersection(ref_tokens)
            concept_coverage = min(1.0, len(overlap) / max(3, len(ref_tokens) * 0.4))
        else:
            concept_coverage = 0.5 if words >= 15 else 0.2

    correctness = int(round(concept_coverage * 100))

    if words < 5:
        depth = 10
    elif words < 15:
        depth = 40
    elif words < 30:
        depth = 70
    else:
        depth = min(100, 75 + int(concept_coverage * 25))

    if concept_coverage >= 0.75 and words >= 20:
        completeness = 95
    elif concept_coverage >= 0.45 and words >= 10:
        completeness = 65
    elif concept_coverage > 0:
        completeness = 35
    else:
        completeness = 0

    final = int(
        round(
            correctness * WEIGHTS["correctness"]
            + depth * WEIGHTS["knowledge_depth"]
            + completeness * WEIGHTS["completeness"]
        )
    )

    if final >= 60 and concept_coverage >= 0.5:
        status = "complete"
    elif final >= 30 or concept_coverage > 0:
        status = "partial"
    else:
        status = "incorrect"
        correctness = 0
        final = min(final, 25)

    confidence = "high" if words >= 15 else "medium" if words >= 5 else "low"

    explanation = (
        f"Solid answer covering key points: {', '.join(matched_concepts) if matched_concepts else 'core definitions'}."
        if status == "complete"
        else f"Partially accurate answer. Touched upon: {', '.join(matched_concepts) if matched_concepts else 'basics'}."
        if status == "partial"
        else "Response did not address the required technical concepts accurately."
    )

    return {
        "final_score": final,
        "status": status,
        "correctness_score": correctness,
        "knowledge_depth_score": depth,
        "completeness_score": completeness,
        "confidence": confidence,
        "key_concepts": matched_concepts,
        "explanation": explanation,
        "unsupported_claims": [],
        "contradictions": [],
        "scoring_mode": "rule_based",
    }
