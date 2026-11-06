
import json
import sqlite3
import logging

logging.basicConfig(
    filename="api_calls.log",
    level=logging.INFO,
    format="%(asctime)s %(message)s"
)


def get_cached_result(interview_id):

    conn = sqlite3.connect("reincrew.db")

    row = conn.execute(
        "SELECT result FROM hybrid_cache WHERE interview_id = ?",
        (interview_id,)
    ).fetchone()

    conn.close()

    if row:
        return json.loads(row[0])

    return None


def save_result(interview_id, result):

    conn = sqlite3.connect("reincrew.db")

    conn.execute("""
        INSERT OR IGNORE INTO hybrid_cache
        (interview_id, result)
        VALUES (?, ?)
    """, (interview_id, json.dumps(result)))

    conn.commit()
    conn.close()


def hybrid_score(interview_id, interview_data):

    # First check whether this interview was scored.
    cached = get_cached_result(interview_id)

    if cached is not None:
        logging.info("CACHE HIT: %s", interview_id)
        return cached

    logging.info("CACHE MISS: %s", interview_id)

    # One consolidated external scoring request.
    result = call_existing_api_once(interview_data)

    save_result(interview_id, result)

    logging.info("EXTERNAL API CALL: %s", interview_id)

    return result
