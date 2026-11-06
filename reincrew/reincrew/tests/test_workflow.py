"""End-to-end data workflow (no UI, network mocked): profile -> selection -> session -> answers -> evaluation -> report."""
import unittest
from unittest import mock

from reincrew import api_ai, engine
from reincrew.report import build_report
from reincrew.selector import select_questions
from tests.helpers import fresh_db, profile

ANSWERS = [
    "Machine learning is where computers learn patterns from data to make predictions without being explicitly programmed.",
    "",  # skipped
    "I do not know.",
]


class WorkflowTests(unittest.TestCase):
    def _run(self, mode, api_chat=None):
        db = fresh_db()
        p = profile()
        cid = db.upsert_candidate(p["name"], p["email"])
        qs = select_questions(db, p, n=3, seed=11)["questions"]
        sid = db.create_session(cid, p, mode, qs)
        sqs = db.session_questions(sid)
        with mock.patch("requests.post", side_effect=ConnectionError("no ollama")):  # local model unavailable
            ctx = mock.patch.object(api_ai, "chat", return_value=api_chat) if api_chat else mock.patch.object(api_ai, "chat", side_effect=AssertionError("API must not be called"))
            with ctx as chat:
                for sq, q, a in zip(sqs, qs, ANSWERS):
                    ev = engine.evaluate_answer(mode, q, a, db=db, api_key="k")
                    db.save_answer(sq["id"], a, not a, ev)
                if mode == "Hybrid Mode":
                    rows = [r for r in db.get_answers(sid) if r["evaluation"]]
                    items = [dict(question=next(q for q in qs if q["id"] == r["question_id"]), transcript=r["transcript"] or "", evaluation=r["evaluation"]) for r in rows]
                    up = engine.finalize_hybrid(items, db=db, api_key="k")
                    for r, ev in zip(rows, up):
                        db.save_answer(r["sqid"], r["transcript"] or "", bool(r["skipped"]), ev)
        rep = build_report(db.get_session(sid), db.get_answers(sid), {q["id"]: q for q in qs})
        return rep, chat

    def test_local_mode_end_to_end_zero_api_calls(self):
        rep, chat = self._run("Local AI Mode")
        chat.assert_not_called()
        self.assertEqual(rep["summary"]["total_questions"], 3)
        self.assertEqual(rep["summary"]["skipped"], 1)
        self.assertEqual(rep["candidate"]["mode"], "Local AI Mode")

    def test_hybrid_end_to_end_one_api_call(self):
        # 2 non-skipped answers -> one batch call
        batch = '{"results": [{"n":1,"correctness_score":95,"knowledge_depth_score":80,"completeness_score":90,"status":"complete"},{"n":2,"correctness_score":0,"knowledge_depth_score":0,"completeness_score":5,"status":"incorrect"}]}'
        rep, chat = self._run("Hybrid Mode", api_chat=batch)
        self.assertEqual(chat.call_count, 1)
        scored = [r for r in rep["per_question"] if not r["skipped"]]
        self.assertTrue(all(r["scoring_mode"] == "hybrid_api_batch" for r in scored))

    def test_incomplete_session_counts_unanswered_as_zero(self):
        db = fresh_db()
        p = profile()
        cid = db.upsert_candidate(p["name"], p["email"])
        qs = select_questions(db, p, n=4, seed=1)["questions"]
        sid = db.create_session(cid, p, "Local AI Mode", qs)
        rep = build_report(db.get_session(sid), db.get_answers(sid), {q["id"]: q for q in qs})
        self.assertEqual((rep["summary"]["answered"], rep["summary"]["final_score"]), (0, 0.0))


if __name__ == "__main__":
    unittest.main()
