import unittest
from unittest.mock import patch
from reincrew.scorer import score_answer
from reincrew.engine import evaluate_answer
from reincrew.report import build_report
from tests.helpers import fresh_db, profile

QUESTION = {"question": "What is Python?", "concepts": {"language": ["programming language"]},
            "depth": ["interpreted"], "reference": "Python is a programming language."}

class CandidateFixTests(unittest.TestCase):
    def test_empty_answer_has_zero_score_and_no_confidence(self):
        result = score_answer(QUESTION, "   ")
        self.assertEqual(result["final_score"], 0)
        self.assertEqual(result["correctness_score"], 0)
        self.assertEqual(result["knowledge_depth_score"], 0)
        self.assertEqual(result["completeness_score"], 0)
        self.assertEqual(result["status"], "not_answered")
        self.assertEqual(result["confidence"], "none")

    def test_empty_answer_does_not_call_external_api(self):
        with patch("reincrew.engine.api_ai.score_with_api") as api_call:
            result = evaluate_answer("API Mode", QUESTION, "")
        api_call.assert_not_called()
        self.assertEqual(result["final_score"], 0)
        self.assertEqual(result["confidence"], "none")

    def test_candidate_history_persists_by_normalized_email(self):
        db = fresh_db()
        cid = db.upsert_candidate("Candidate One", "CANDIDATE@example.com")
        sid = db.create_session(cid, profile(email="candidate@example.com"), "Local AI Mode", [QUESTION])
        self.assertEqual(len(db.history(" candidate@EXAMPLE.com ")), 1)
        self.assertEqual(db.history("candidate@example.com")[0]["id"], sid)

    def test_unanswered_report_is_separate_from_incorrect(self):
        db = fresh_db()
        cid = db.upsert_candidate("Candidate One", "candidate@example.com")
        sid = db.create_session(cid, profile(), "Local AI Mode", [QUESTION])
        sq = db.session_questions(sid)[0]
        db.save_answer(sq["id"], "", True, score_answer(QUESTION, ""))
        rep = build_report(db.get_session(sid), db.get_answers(sid), {})
        self.assertEqual(rep["summary"]["final_score"], 0)
        self.assertEqual(rep["summary"]["not_answered"], 1)
        self.assertEqual(rep["per_question"][0]["confidence"], "none")

if __name__ == "__main__":
    unittest.main()
