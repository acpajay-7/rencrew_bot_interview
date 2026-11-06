import os, tempfile, unittest
from reincrew.db import Database
from reincrew.question_bank import save_generated, seed_if_empty, validate_generated
from reincrew.selector import select_questions
from tests.helpers import fresh_db, profile

GOOD = dict(stream="Data Science", specialization="Machine Learning", topic="Feature Engineering", subtopic="Encoding",
            question="What is one-hot encoding and when would you use it?", difficulty="Beginner",
            reference="One-hot encoding turns categorical values into binary columns, used for nominal categories.",
            concepts={"binary_columns": ["binary", "0 and 1"], "categorical": ["categorical", "category"]})


class QuestionBankTests(unittest.TestCase):
    def test_persistence_across_restart(self):
        d = tempfile.mkdtemp(); path = os.path.join(d, "x.db")
        db1 = Database(path); seed_if_empty(db1); n = len(db1.list_questions())
        db2 = Database(path)  # simulated restart
        self.assertEqual(len(db2.list_questions()), n)
        self.assertEqual(seed_if_empty(db2), 0)  # no re-seeding / duplication

    def test_duplicate_detection_exact_and_near(self):
        db = fresh_db()
        qid, msg = db.add_question({**GOOD, "question": "What is Machine Learning?"})
        self.assertIsNone(qid); self.assertIn("duplicate", msg)
        qid, msg = db.add_question({**GOOD, "question": "what is machine learning"})
        self.assertIsNone(qid)

    def test_ai_question_saved_as_pending_and_not_used(self):
        db = fresh_db()
        qid, msg = save_generated(db, GOOD)
        self.assertIsNotNone(qid)
        q = db.get_question(qid)
        self.assertEqual((q["status"], q["source"]), ("pending", "ai_generated"))
        res = select_questions(db, profile(), n=30, seed=1)
        self.assertNotIn(qid, [x["id"] for x in res["questions"]])
        db.update_question(qid, status="approved")  # admin approval
        res = select_questions(db, profile(), n=30, seed=1)
        self.assertIn(qid, [x["id"] for x in res["questions"]])

    def test_invalid_generated_question_rejected(self):
        db = fresh_db()
        bad = {**GOOD, "reference": "", "concepts": {}}
        self.assertTrue(validate_generated(bad))
        qid, msg = save_generated(db, bad)
        self.assertIsNone(qid); self.assertIn("rejected", msg)

    def test_admin_edit_and_delete(self):
        db = fresh_db()
        qid, _ = db.add_question(GOOD)
        db.update_question(qid, difficulty="Advanced")
        self.assertEqual(db.get_question(qid)["difficulty"], "Advanced")
        db.delete_question(qid)
        self.assertIsNone(db.get_question(qid))


if __name__ == "__main__":
    unittest.main()
