
import json
import unittest

from reincrew.config import SEED_PATH
from reincrew.scorer import score_answer


# Load questions from the existing seed question bank.
QUESTIONS = json.loads(SEED_PATH.read_text(encoding="utf-8"))

Q = {q["question"]: q for q in QUESTIONS}

SUP = Q["What is the difference between supervised and unsupervised learning?"]
OVER = Q["What is overfitting in Machine Learning?"]


class ScorerTests(unittest.TestCase):

    # --------------------------------------------------
    # 1. CORRECT ANSWER
    # --------------------------------------------------

    def test_correct_answer_is_complete(self):
        answer = (
            "Supervised learning uses labeled data with known target labels "
            "to predict outputs such as classification or regression, "
            "while unsupervised learning works with unlabeled data and "
            "finds clusters or structure without labels."
        )

        result = score_answer(SUP, answer)

        self.assertEqual(result["status"], "complete")
        self.assertGreaterEqual(result["final_score"], 60)
        self.assertEqual(result["answer_status"], "answered")

    # --------------------------------------------------
    # 2. PARTIAL ANSWER
    # --------------------------------------------------

    def test_partial_answer(self):
        result = score_answer(
            SUP,
            "Supervised learning uses labeled data to predict things."
        )

        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["answer_status"], "answered")

    # --------------------------------------------------
    # 3. INCORRECT ANSWER
    # --------------------------------------------------

    def test_incorrect_answer(self):
        result = score_answer(
            OVER,
            "It is when a computer gets too hot and slows down."
        )

        self.assertEqual(result["status"], "incorrect")
        self.assertEqual(result["correctness_score"], 0)

    # --------------------------------------------------
    # 4. EQUIVALENT WORDING
    # --------------------------------------------------

    def test_equivalent_wording_credited(self):
        answer = (
            "The model memorises training data including noise "
            "so it does not generalize to new data."
        )

        result = score_answer(OVER, answer)

        self.assertEqual(result["status"], "complete")
        self.assertGreater(result["correctness_score"], 0)

    # --------------------------------------------------
    # 5. EMPTY ANSWER
    # --------------------------------------------------

    def test_empty_answer(self):
        result = score_answer(OVER, "   ")

        self.assertEqual(result["final_score"], 0)
        self.assertEqual(result["correctness_score"], 0)
        self.assertEqual(result["knowledge_depth_score"], 0)
        self.assertEqual(result["completeness_score"], 0)

        self.assertEqual(result["status"], "not_answered")
        self.assertEqual(result["answer_status"], "not_answered")
        self.assertEqual(result["confidence"], "none")

    # --------------------------------------------------
    # 6. VERY SHORT ANSWER
    # --------------------------------------------------

    def test_very_short_answer_low_confidence(self):
        result = score_answer(OVER, "overfitting")

        self.assertEqual(result["confidence"], "low")
        self.assertEqual(result["answer_status"], "answered")

    def test_single_character_answer(self):
        result = score_answer(OVER, "a")

        self.assertEqual(result["final_score"], 0)
        self.assertEqual(result["status"], "insufficient_input")
        self.assertEqual(result["confidence"], "none")

    # --------------------------------------------------
    # 7. WHITESPACE ANSWER
    # --------------------------------------------------

    def test_whitespace_answer(self):
        result = score_answer(OVER, "       ")

        self.assertEqual(result["final_score"], 0)
        self.assertEqual(result["status"], "not_answered")
        self.assertEqual(result["confidence"], "none")

    # --------------------------------------------------
    # 8. TRANSCRIPTION FAILURE
    # --------------------------------------------------

    def test_transcription_failure(self):
        result = score_answer(
            OVER,
            "",
            input_status="transcription_failed"
        )

        self.assertEqual(result["final_score"], 0)
        self.assertEqual(result["status"], "transcription_failed")
        self.assertEqual(result["confidence"], "none")

    # --------------------------------------------------
    # 9. ORIGINAL SCORING WEIGHTS
    # --------------------------------------------------

    def test_original_weights_unchanged(self):
        answer = (
            "memorizes training data and does not generalize "
            "to unseen data; fix with regularization, "
            "cross-validation, early stopping"
        )

        result = score_answer(OVER, answer)

        expected_score = round(
            result["correctness_score"] * 0.60
            + result["knowledge_depth_score"] * 0.25
            + result["completeness_score"] * 0.15
        )

        self.assertEqual(result["final_score"], expected_score)

    # --------------------------------------------------
    # 10. RULE-BASED LIMITATIONS
    # --------------------------------------------------

    def test_rule_mode_reports_no_detected_claims(self):
        result = score_answer(
            OVER,
            "overfitting is when the model memorizes training "
            "data and fails on unseen data"
        )

        self.assertEqual(result["unsupported_claims"], [])
        self.assertEqual(result["contradictions"], [])
        self.assertEqual(result["scoring_mode"], "rule_based")

    # --------------------------------------------------
    # 11. RESULT STRUCTURE
    # --------------------------------------------------

    def test_result_contains_required_fields(self):
        result = score_answer(
            OVER,
            "The model memorizes training data."
        )

        required_fields = [
            "correctness_score",
            "knowledge_depth_score",
            "completeness_score",
            "final_score",
            "status",
            "answer_status",
            "explanation",
            "confidence",
            "unsupported_claims",
            "contradictions",
            "matched_concepts",
            "scoring_mode",
        ]

        for field in required_fields:
            with self.subTest(field=field):
                self.assertIn(field, result)

    # --------------------------------------------------
    # 12. SCORE RANGE
    # --------------------------------------------------

    def test_all_scores_are_within_valid_range(self):
        result = score_answer(
            OVER,
            "The model memorizes training data "
            "and fails to generalize to unseen data."
        )

        score_fields = [
            "correctness_score",
            "knowledge_depth_score",
            "completeness_score",
            "final_score",
        ]

        for field in score_fields:
            with self.subTest(field=field):
                self.assertGreaterEqual(result[field], 0)
                self.assertLessEqual(result[field], 100)


if __name__ == "__main__":
    unittest.main(verbosity=2)
