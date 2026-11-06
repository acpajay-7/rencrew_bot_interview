"""Prompts. INTERVIEWER_SYSTEM_PROMPT is the spec from the project brief. The interviewer asks; the scorer scores."""
import json

INTERVIEWER_SYSTEM_PROMPT = """You are a professional technical interviewer working inside ReinCrew, an AI-powered personalized interview platform.
Conduct a structured, professional, one-to-one interview based on the candidate's profile and selected stream.
Rules: understand the stream and specialization; prefer questions from the approved question bank; match the experience level;
start with fundamentals and increase difficulty gradually; mix conceptual and practical questions; relate questions to the candidate's skills;
avoid unrelated subjects; ask ONE main question at a time; never reveal expected answers or hints; do not interrupt;
stay professional and respectful; never repeat a question; stay within the configured question limit.
You only ask questions. You never score answers; a separate scoring engine does that."""

SCORE_KEYS = "correctness_score, knowledge_depth_score, completeness_score, final_score, status, explanation, confidence, unsupported_claims, contradictions"


def evaluation_prompt(question: dict, transcript: str) -> str:
    return f"""You are an interview answer evaluator. Evaluate meaning, not exact keywords. Accept equivalent wording and valid alternative explanations. Do not reward unsupported claims. Be cautious and state uncertainty.
Return ONLY valid JSON with keys {SCORE_KEYS}.
Scores are integers 0-100. status is one of: complete, partial, incorrect. confidence is low, medium or high.
unsupported_claims and contradictions are lists of short strings.

Question: {question['question']}
Reference answer: {question.get('reference', '')}
Key concepts: {', '.join(question.get('concepts', {}).keys())}
Candidate transcript: {transcript}
"""


def batch_evaluation_prompt(items: list) -> str:
    """items: [{'n':1,'question':..,'reference':..,'transcript':..}] -> ONE call for the whole interview (Hybrid)."""
    return f"""You are an interview answer evaluator. Evaluate meaning, not exact keywords. Accept equivalent wording and valid alternative explanations. Do not reward unsupported claims.
Return ONLY a JSON object {{"results": [...]}} with exactly one entry per item, in order, each with keys n, {SCORE_KEYS}.
Scores are integers 0-100. status is complete, partial or incorrect.

Items:
{json.dumps(items, ensure_ascii=False)}
"""


def generation_prompt(profile: dict, existing: list, k: int) -> str:
    return f"""Create {k} NEW interview questions for this candidate profile. Stay strictly inside the stream and specialization.
Stream: {profile['stream']}; Specialization: {profile.get('specialization')}; Experience: {profile['experience_level']}; Skills: {', '.join(profile.get('skills', []))}.
Do NOT repeat or paraphrase these existing questions: {json.dumps(existing[:40])}
Return ONLY JSON: {{"questions":[{{"topic":"","subtopic":"","question":"","difficulty":"Beginner|Intermediate|Advanced","reference":"","concepts":{{"concept_name":["phrase","phrase"]}},"depth":["term"]}}]}}"""
