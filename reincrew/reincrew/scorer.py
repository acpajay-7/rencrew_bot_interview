
import json, unittest
from reincrew.config import SEED_PATH
from reincrew.scorer import score_answer

Q = {q["question"]: q for q in json.loads(SEED_PATH.read_text())}
SUP = Q["What is the difference between supervised and unsupervised learning?"]
OVER = Q["What is overfitting in Machine Learning?"]


class ScorerTests(unittest.TestCase):
    def test_correct_answer_is_complete(self):
        a = ("Supervised learning uses labeled data with known target labels to predict outputs such as classification or regression, "
             "while unsupervised learning works with unlabeled data and finds clusters or structure without labels.")
        r = score_answer(SUP, a)
        self.assertEqual(r["status"], "complete")
        self.assertGreaterEqual(r["final_score"], 60)

    def test_partial_answer(self):
        r = score_answer(SUP, "Supervised learning uses labeled data to predict things.")
        self.assertEqual(r["status"], "partial")

    def test_incorrect_answer(self):
        r = score_answer(OVER, "It is when a computer gets too hot and slows down.")
        self.assertEqual(r["status"], "incorrect")
        self.assertEqual(r["correctness_score"], 0)

    def test_equivalent_wording_credited(self):
        r = score_answer(OVER, "The model memorises training data including noise so it does not generalize to new data.")
        self.assertEqual(r["status"], "complete")

    def test_empty_answer(self):
        r = score_answer(OVER, "   ")
        self.assertEqual(r["final_score"], 0)
        self.assertEqual(r["status"], "not_answered")
        self.assertEqual(r["confidence"], "none")

    def test_very_short_answer_low_confidence(self):
        self.assertEqual(score_answer(OVER, "overfitting")["confidence"], "low")

    def test_original_weights_unchanged(self):
        # original formula: 60% correctness + 25% depth + 15% completeness
        a = "memorizes training data and does not generalize to unseen data; fix with regularization, cross-validation, early stopping"
        r = score_answer(OVER, a)
        exp = round(r["correctness_score"] * .6 + r["knowledge_depth_score"] * .25 + r["completeness_score"] * .15)
        self.assertEqual(r["final_score"], exp)

    def test_rule_mode_reports_no_detected_claims(self):
        # documented limitation: rule scorer does not detect unsupported claims/contradictions
        r = score_answer(OVER, "overfitting is when the model memorizes training data and fails on unseen data")
        self.assertEqual(r["unsupported_claims"], [])
        self.assertEqual(r["contradictions"], [])


if __name__ == "__main__":
    unittest.main()

