
from sentence_transformers import SentenceTransformer, util

# Load a model from the local disk.
# No external AI API is called during inference.
model = SentenceTransformer(
    "./models/all-MiniLM-L6-v2"
)


def evaluate_answer(question, answer, reference_answer):

    # Convert answers into numerical vectors.
    candidate_vector = model.encode(answer)
    reference_vector = model.encode(reference_answer)

    # Compare semantic meaning.
    similarity = util.cos_sim(
        candidate_vector,
        reference_vector
    ).item()

    # Initial similarity-based correctness estimate.
    # These thresholds MUST be calibrated using test data.
    correctness = max(0, min(100, similarity * 100))

    # Simple preliminary completeness estimate.
    # Replace this with rubric-based coverage.
    completeness = min(
        100,
        max(0, correctness)
    )

    # Placeholder depth estimate.
    # A real version must evaluate reasoning and detail.
    depth = correctness

    final_score = (
        correctness * 0.60
        + depth * 0.25
        + completeness * 0.15
    )

    return {
        "question": question,
        "answer": answer,
        "correctness": round(correctness, 2),
        "depth": round(depth, 2),
        "completeness": round(completeness, 2),
        "explanation": (
            "Preliminary semantic similarity evaluation. "
            "Human or reference-rubric validation is required."
        ),
        "final_score": round(final_score, 2),
        "confidence": None
    }
