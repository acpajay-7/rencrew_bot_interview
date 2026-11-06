import unittest
from reincrew.profile import parse_skills, validate_profile
from reincrew.report import build_report, to_csv, to_markdown
from reincrew.selector import select_questions
from reincrew.scorer import score_answer
from tests.helpers import fresh_db, profile


class ProfileTests(unittest.TestCase):
    def test_valid_profile(self):
        self.assertEqual(validate_profile(profile()), [])

    def test_bad_name_email_stream(self):
        errs = validate_profile(profile(name="1", email="nope", stream=""))
        self.assertEqual(len(errs), 3)

    def test_skills_parsing_dedupes(self):
        self.assertEqual(parse_skills("Python, sql;Python\n NLP"), ["Python", "sql", "NLP"])

    def test_candidates_isolated_and_deletable(self):
        db = fresh_db()
        a = db.upsert_candidate("A One", "a@x.com"); b = db.upsert_candidate("B Two", "b@x.com")
        qs = select_questions(db, profile(), n=2, seed=1)["questions"]
        sa = db.create_session(a, profile(), "Local AI Mode", qs)
        db.create_session(b, profile(), "Local AI Mode", qs)
        self.assertEqual(len(db.history("a@x.com")), 1)
        self.assertEqual(db.history("a@x.com")[0]["id"], sa)
        self.assertTrue(db.delete_candidate("a@x.com"))
        self.assertEqual(db.history("a@x.com"), [])
        self.assertEqual(len(db.history("b@x.com")), 1)  # other candidate untouched
        self.assertGreater(len(db.list_questions()), 0)   # question bank untouched


class ReportTests(unittest.TestCase):
    def _run(self, answers):
        db = fresh_db()
        cid = db.upsert_candidate("Rahul Sharma", "rahul@example.com")
        qs = select_questions(db, profile(), n=len(answers), seed=1)["questions"]
        sid = db.create_session(cid, profile(), "Local AI Mode", qs)
        for sq, q, ans in zip(db.session_questions(sid), qs, answers):
            ev = score_answer(q, ans or "")
            db.save_answer(sq["id"], ans or "", not ans, ev)
        meta = {q["id"]: q for q in qs}
        return build_report(db.get_session(sid), db.get_answers(sid), meta)

    def test_report_counts_and_score(self):
        rep = self._run(["", "", ""])
        s = rep["summary"]
        self.assertEqual((s["total_questions"], s["answered"], s["skipped"], s["final_score"]), (3, 0, 3, 0.0))
        self.assertEqual(s["not_answered"], 3)

    def test_report_exports(self):
        rep = self._run(["Machine learning is where computers learn patterns from data to make predictions without being explicitly programmed", ""])
        self.assertIn("ReinCrew Interview Report", to_markdown(rep))
        self.assertEqual(to_csv(rep).count("\n"), 3)  # header + 2 rows
        self.assertEqual(rep["candidate"]["email"], "rahul@example.com")
        self.assertEqual(rep["summary"]["answered"], 1)


if __name__ == "__main__":
    unittest.main()
