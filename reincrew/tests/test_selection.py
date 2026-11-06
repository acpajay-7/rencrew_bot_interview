import unittest
from reincrew.selector import select_questions
from reincrew.streams import family_streams
from tests.helpers import fresh_db, profile


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.db = fresh_db()

    def test_original_questions_preserved(self):
        orig = [q for q in self.db.list_questions() if q["source"] == "original"]
        self.assertEqual(len(orig), 5)
        texts = {q["question"] for q in orig}
        self.assertIn("What is Machine Learning?", texts)
        self.assertIn("What is the purpose of a confusion matrix?", texts)

    def test_no_unrelated_streams(self):
        for stream in ["Data Science", "Web Development", "Cybersecurity", "Mechanical Engineering"]:
            res = select_questions(self.db, profile(stream=stream, specialization=""), n=8, seed=1)
            allowed = family_streams(stream)
            for q in res["questions"]:
                self.assertIn(q["stream"], allowed, f"{stream} got {q['stream']}")

    def test_data_science_never_gets_mechanical(self):
        res = select_questions(self.db, profile(), n=10, seed=2)
        self.assertTrue(all(q["stream"] != "Mechanical Engineering" for q in res["questions"]))

    def test_no_repeats(self):
        res = select_questions(self.db, profile(), n=10, seed=3)
        ids = [q["id"] for q in res["questions"]]
        self.assertEqual(len(ids), len(set(ids)))

    def test_difficulty_progression_non_decreasing(self):
        res = select_questions(self.db, profile(experience_level="Intermediate"), n=8, seed=4)
        order = {"Beginner": 0, "Intermediate": 1, "Advanced": 2}
        d = [order[q["difficulty"]] for q in res["questions"]]
        self.assertEqual(d, sorted(d))

    def test_experience_level_changes_difficulty(self):
        student = select_questions(self.db, profile(experience_level="Student"), n=5, seed=5)["questions"]
        pro = select_questions(self.db, profile(experience_level="Experienced Professional"), n=5, seed=5)["questions"]
        self.assertTrue(all(q["difficulty"] == "Beginner" for q in student))
        self.assertTrue(any(q["difficulty"] == "Advanced" for q in pro))

    def test_skills_boost_relevance(self):
        res = select_questions(self.db, profile(specialization="", skills=["SQL"]), n=1, seed=6)
        self.assertIn("SQL", res["questions"][0]["question"] + (res["questions"][0]["specialization"] or ""))

    def test_shortage_reported_not_hidden(self):
        res = select_questions(self.db, profile(stream="Mechanical Engineering", specialization=""), n=5, seed=7)
        self.assertGreater(res["shortage"], 0)
        self.assertTrue(res["notes"])

    def test_custom_stream_does_not_borrow_other_streams(self):
        res = select_questions(self.db, profile(stream="Astrophysics"), n=5, seed=8)
        self.assertEqual(res["questions"], [])


if __name__ == "__main__":
    unittest.main()
