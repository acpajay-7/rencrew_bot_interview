"""Final score + report generation (JSON / CSV / Markdown). Pure functions over saved answers."""
import csv
import io
from datetime import datetime, timezone


def _avg(xs):
    return round(sum(xs) / len(xs), 1) if xs else 0.0


def build_report(session: dict, answers: list, questions_meta: dict = None) -> dict:
    """session: row from db.get_session. answers: db.get_answers rows. questions_meta: {question_id: question dict}."""
    questions_meta = questions_meta or {}
    rows, evs = [], []
    for a in answers:
        ev = a.get("evaluation") or {}
        meta = questions_meta.get(a.get("question_id")) or {}
        skipped = bool(a.get("skipped")) or not (a.get("transcript") or "").strip()
        if not ev:
            ev = { "final_score": 0, "status": "not_answered", "correctness_score": 0, "knowledge_depth_score": 0,
                  "completeness_score": 0, "explanation": "Not answered. Zero points; confidence is not applicable.",
                  "unsupported_claims": [], "contradictions": [], "confidence": "none"}
        rows.append({
            "number": a["position"], "question": a["question_text"], "topic": meta.get("topic"),
            "candidate_answer": a.get("transcript") or "", "transcribed_answer": a.get("transcript") or "",
            "skipped": skipped, "correctness_score": ev.get("correctness_score", 0),
            "knowledge_depth_score": ev.get("knowledge_depth_score", 0), "completeness_score": ev.get("completeness_score", 0),
            "final_question_score": ev.get("final_score", 0), "status": ev.get("status", "incorrect"),
            "explanation": ev.get("explanation", ""), "unsupported_claims": ev.get("unsupported_claims", []),
            "contradictions": ev.get("contradictions", []), "confidence": ev.get("confidence", "low"),
            "scoring_mode": ev.get("scoring_mode"), "expected_answer": meta.get("reference"),
            "key_concepts": list((meta.get("concepts") or {}).keys()),
        })
        evs.append(ev)
    total = len(rows)
    answered = [r for r in rows if not r["skipped"]]
    final = _avg([r["final_question_score"] for r in rows])  # unanswered count as 0
    perf = "Excellent" if final >= 80 else "Good" if final >= 65 else "Fair" if final >= 45 else "Needs Improvement"
    strengths = [r["topic"] or r["question"] for r in rows if r["status"] == "complete"]
    weak = [r for r in rows if r["status"] != "complete"]
    return {
        "candidate": {"name": session["name"], "email": session["email"], "stream": session["stream"],
                      "specialization": session["specialization"], "experience_level": session["experience_level"],
                      "skills": session["skills_json"], "mode": session["mode"], "date": session["started_at"]},
        "summary": {"total_questions": total, "answered": len(answered), "skipped": total - len(answered),
                    "final_score": final, "overall_performance": perf,
                    "complete": sum(r["status"] == "complete" for r in rows),
                    "partial": sum(r["status"] == "partial" for r in rows),
                    "incorrect": sum(r["status"] == "incorrect" for r in rows),
                    "not_answered": sum(r["status"] == "not_answered" for r in rows),
                    "avg_correctness": _avg([r["correctness_score"] for r in rows]),
                    "avg_depth": _avg([r["knowledge_depth_score"] for r in rows]),
                    "avg_completeness": _avg([r["completeness_score"] for r in rows])},
        "per_question": rows,
        "feedback": {
            "strengths": strengths or ["No fully correct answers yet."],
            "weaknesses": [r["question"] for r in weak] or ["None identified."],
            "topics_to_revise": sorted({r["topic"] for r in weak if r["topic"]}),
            "improvement_suggestions": [f"Q{r['number']}: review key concepts - {', '.join(r['key_concepts'])}" for r in weak if r["key_concepts"]],
        },
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def to_csv(report: dict) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["number", "question", "answer", "correctness", "depth", "completeness", "final", "status", "explanation"])
    for r in report["per_question"]:
        w.writerow([r["number"], r["question"], r["candidate_answer"], r["correctness_score"], r["knowledge_depth_score"],
                    r["completeness_score"], r["final_question_score"], r["status"], r["explanation"]])
    return buf.getvalue()


def to_markdown(report: dict) -> str:
    c, s = report["candidate"], report["summary"]
    L = [f"# ReinCrew Interview Report", "",
         f"**Candidate:** {c['name']} ({c['email']})  ", f"**Stream:** {c['stream']} / {c['specialization']}  ",
         f"**Experience:** {c['experience_level']}  ", f"**Mode:** {c['mode']}  ", f"**Date:** {c['date']}", "",
         f"## Result: {s['final_score']}/100 - {s['overall_performance']}", "",
         f"Questions: {s['total_questions']} | Answered: {s['answered']} | Skipped: {s['skipped']} | "
         f"Complete: {s['complete']} | Partial: {s['partial']} | Incorrect: {s['incorrect']} | Not answered: {s.get('not_answered', 0)}", "",
         f"Avg correctness {s['avg_correctness']} | Avg depth {s['avg_depth']} | Avg completeness {s['avg_completeness']}", "", "## Per-question"]
    for r in report["per_question"]:
        L += [f"### Q{r['number']}. {r['question']}", f"- Answer: {r['candidate_answer'] or '(none)'}",
              f"- Scores: correctness {r['correctness_score']}, depth {r['knowledge_depth_score']}, completeness {r['completeness_score']} -> **{r['final_question_score']}** ({r['status']})",
              f"- Explanation: {r['explanation']}", f"- Key concepts: {', '.join(r['key_concepts'])}", ""]
    f = report["feedback"]
    L += ["## Feedback", "**Strengths:** " + "; ".join(map(str, f["strengths"])), "**Weaknesses:** " + "; ".join(f["weaknesses"]),
          "**Topics to revise:** " + (", ".join(f["topics_to_revise"]) or "-")]
    return "\n".join(L)
