"""SQLite data layer. Plain SQL + one Database class, so a PostgreSQL swap only touches this file."""
import hashlib
import json
import re
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS questions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  stream TEXT NOT NULL, specialization TEXT, topic TEXT, subtopic TEXT,
  question TEXT NOT NULL, norm_hash TEXT NOT NULL,
  difficulty TEXT NOT NULL, experience_level TEXT, interview_type TEXT,
  reference TEXT, concepts_json TEXT, depth_json TEXT, evaluation_criteria TEXT,
  status TEXT NOT NULL DEFAULT 'approved',        -- approved | pending | rejected
  source TEXT NOT NULL DEFAULT 'seed',            -- original | seed | admin | ai_generated
  created_at TEXT NOT NULL,
  UNIQUE(stream, norm_hash)
);
CREATE TABLE IF NOT EXISTS candidates (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY, candidate_id TEXT NOT NULL REFERENCES candidates(id),
  stream TEXT, specialization TEXT, experience_level TEXT, interview_type TEXT,
  skills_json TEXT, mode TEXT, status TEXT NOT NULL DEFAULT 'in_progress',
  started_at TEXT NOT NULL, finished_at TEXT, final_score REAL
);
CREATE TABLE IF NOT EXISTS session_questions (
  id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL REFERENCES sessions(id),
  position INTEGER NOT NULL, question_id INTEGER, question_text TEXT NOT NULL,
  UNIQUE(session_id, position)
);
CREATE TABLE IF NOT EXISTS answers (
  id INTEGER PRIMARY KEY AUTOINCREMENT, session_question_id INTEGER NOT NULL UNIQUE REFERENCES session_questions(id),
  transcript TEXT, skipped INTEGER NOT NULL DEFAULT 0, evaluation_json TEXT, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reports (session_id TEXT PRIMARY KEY REFERENCES sessions(id), report_json TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS eval_cache (key TEXT PRIMARY KEY, result_json TEXT NOT NULL, created_at TEXT NOT NULL);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def norm_text(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", text.lower())).strip()


def text_hash(text: str) -> str:
    return hashlib.sha256(norm_text(text).encode()).hexdigest()[:32]


def similarity(a: str, b: str) -> float:
    ta, tb = set(norm_text(a).split()), set(norm_text(b).split())
    return len(ta & tb) / len(ta | tb) if ta and tb else 0.0


class Database:
    def __init__(self, path: str = "data/reincrew.db"):
        self.path = path
        with self.conn() as c:
            c.executescript(SCHEMA)

    @contextmanager
    def conn(self):
        c = sqlite3.connect(self.path)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys = ON")
        try:
            yield c
            c.commit()
        finally:
            c.close()

    # ---------- questions ----------
    @staticmethod
    def _q(row) -> dict:
        d = dict(row)
        d["concepts"] = json.loads(d.pop("concepts_json") or "{}")
        d["depth"] = json.loads(d.pop("depth_json") or "[]")
        return d

    def add_question(self, q: dict, check_duplicates: bool = True) -> tuple:
        """Returns (question_id | None, message). Never raises on duplicates."""
        if check_duplicates:
            dup = self.find_duplicate(q["stream"], q["question"])
            if dup:
                return None, f"duplicate of question #{dup}"
        try:
            with self.conn() as c:
                cur = c.execute(
                    """INSERT INTO questions (stream,specialization,topic,subtopic,question,norm_hash,difficulty,
                       experience_level,interview_type,reference,concepts_json,depth_json,evaluation_criteria,status,source,created_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (q["stream"], q.get("specialization"), q.get("topic"), q.get("subtopic"), q["question"],
                     text_hash(q["question"]), q.get("difficulty", "Beginner"), q.get("experience_level"),
                     q.get("interview_type", "Technical Interview"), q.get("reference"),
                     json.dumps(q.get("concepts", {})), json.dumps(q.get("depth", [])),
                     q.get("evaluation_criteria", "Judge meaning against the reference answer and key concepts."),
                     q.get("status", "approved"), q.get("source", "admin"), now()))
                return cur.lastrowid, "saved"
        except sqlite3.IntegrityError:
            return None, "duplicate (exact text already in this stream)"

    def find_duplicate(self, stream: str, text: str, threshold: float = 0.8):
        with self.conn() as c:
            for r in c.execute("SELECT id, question FROM questions WHERE stream=? AND status!='rejected'", (stream,)):
                if text_hash(r["question"]) == text_hash(text) or similarity(r["question"], text) >= threshold:
                    return r["id"]
        return None

    def list_questions(self, status="approved", streams=None) -> list:
        sql, args = "SELECT * FROM questions WHERE 1=1", []
        if status:
            sql += " AND status=?"; args.append(status)
        if streams:
            sql += f" AND stream IN ({','.join('?' * len(streams))})"; args += list(streams)
        with self.conn() as c:
            return [self._q(r) for r in c.execute(sql + " ORDER BY id", args)]

    def get_question(self, qid: int):
        with self.conn() as c:
            r = c.execute("SELECT * FROM questions WHERE id=?", (qid,)).fetchone()
            return self._q(r) if r else None

    def update_question(self, qid: int, **fields):
        allowed = {"stream", "specialization", "topic", "subtopic", "question", "difficulty", "experience_level",
                   "interview_type", "reference", "evaluation_criteria", "status"}
        sets = {k: v for k, v in fields.items() if k in allowed}
        if "question" in sets:
            sets["norm_hash"] = text_hash(sets["question"])
        if not sets:
            return
        with self.conn() as c:
            c.execute(f"UPDATE questions SET {', '.join(k + '=?' for k in sets)} WHERE id=?", (*sets.values(), qid))

    def delete_question(self, qid: int):
        with self.conn() as c:
            c.execute("DELETE FROM questions WHERE id=?", (qid,))

    # ---------- candidates & sessions ----------
    def upsert_candidate(self, name: str, email: str) -> str:
        email = email.strip().lower()
        with self.conn() as c:
            r = c.execute("SELECT id FROM candidates WHERE email=?", (email,)).fetchone()
            if r:
                c.execute("UPDATE candidates SET name=? WHERE id=?", (name.strip(), r["id"]))
                return r["id"]
            cid = uuid.uuid4().hex
            c.execute("INSERT INTO candidates VALUES (?,?,?,?)", (cid, name.strip(), email, now()))
            return cid

    def create_session(self, candidate_id: str, profile: dict, mode: str, questions: list) -> str:
        sid = uuid.uuid4().hex
        with self.conn() as c:
            c.execute("INSERT INTO sessions (id,candidate_id,stream,specialization,experience_level,interview_type,skills_json,mode,started_at) VALUES (?,?,?,?,?,?,?,?,?)",
                      (sid, candidate_id, profile["stream"], profile.get("specialization"), profile["experience_level"],
                       profile["interview_type"], json.dumps(profile.get("skills", [])), mode, now()))
            for i, q in enumerate(questions, 1):
                c.execute("INSERT INTO session_questions (session_id,position,question_id,question_text) VALUES (?,?,?,?)",
                          (sid, i, q.get("id"), q["question"]))
        return sid

    def session_questions(self, sid: str) -> list:
        with self.conn() as c:
            return [dict(r) for r in c.execute("SELECT * FROM session_questions WHERE session_id=? ORDER BY position", (sid,))]

    def save_answer(self, session_question_id: int, transcript: str, skipped: bool, evaluation: dict):
        with self.conn() as c:
            c.execute("""INSERT INTO answers (session_question_id,transcript,skipped,evaluation_json,created_at) VALUES (?,?,?,?,?)
                         ON CONFLICT(session_question_id) DO UPDATE SET transcript=excluded.transcript,
                         skipped=excluded.skipped, evaluation_json=excluded.evaluation_json""",
                      (session_question_id, transcript, int(skipped), json.dumps(evaluation), now()))

    def get_answers(self, sid: str) -> list:
        with self.conn() as c:
            rows = c.execute("""SELECT sq.id AS sqid, sq.position, sq.question_id, sq.question_text, a.transcript, a.skipped, a.evaluation_json
                                FROM session_questions sq LEFT JOIN answers a ON a.session_question_id=sq.id
                                WHERE sq.session_id=? ORDER BY sq.position""", (sid,)).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["evaluation"] = json.loads(d.pop("evaluation_json")) if d.get("evaluation_json") else None
            out.append(d)
        return out

    def finish_session(self, sid: str, status: str, final_score, report: dict):
        with self.conn() as c:
            c.execute("UPDATE sessions SET status=?, finished_at=?, final_score=? WHERE id=?", (status, now(), final_score, sid))
            c.execute("INSERT OR REPLACE INTO reports VALUES (?,?,?)", (sid, json.dumps(report), now()))

    def get_session(self, sid: str):
        with self.conn() as c:
            r = c.execute("""SELECT s.*, c.name, c.email FROM sessions s JOIN candidates c ON c.id=s.candidate_id WHERE s.id=?""", (sid,)).fetchone()
            return dict(r) if r else None

    def history(self, email: str) -> list:
        """Only returns sessions belonging to this exact email."""
        with self.conn() as c:
            return [dict(r) for r in c.execute("""SELECT s.id, s.started_at, s.stream, s.specialization, s.mode, s.status, s.final_score
                FROM sessions s JOIN candidates c ON c.id=s.candidate_id WHERE c.email=? ORDER BY s.started_at DESC""", (email.strip().lower(),))]

    def get_report(self, sid: str):
        with self.conn() as c:
            r = c.execute("SELECT report_json FROM reports WHERE session_id=?", (sid,)).fetchone()
            return json.loads(r["report_json"]) if r else None

    # ---------- cache ----------
    def cache_get(self, key: str):
        with self.conn() as c:
            r = c.execute("SELECT result_json FROM eval_cache WHERE key=?", (key,)).fetchone()
            return json.loads(r["result_json"]) if r else None

    def cache_set(self, key: str, value: dict):
        with self.conn() as c:
            c.execute("INSERT OR REPLACE INTO eval_cache VALUES (?,?,?)", (key, json.dumps(value), now()))

    # ---------- privacy ----------
    def delete_candidate(self, email: str) -> bool:
        """Deletes the candidate and ALL their sessions, answers and reports. Question bank untouched."""
        email = email.strip().lower()
        with self.conn() as c:
            r = c.execute("SELECT id FROM candidates WHERE email=?", (email,)).fetchone()
            if not r:
                return False
            cid = r["id"]
            sids = [x["id"] for x in c.execute("SELECT id FROM sessions WHERE candidate_id=?", (cid,))]
            for sid in sids:
                c.execute("DELETE FROM answers WHERE session_question_id IN (SELECT id FROM session_questions WHERE session_id=?)", (sid,))
                c.execute("DELETE FROM session_questions WHERE session_id=?", (sid,))
                c.execute("DELETE FROM reports WHERE session_id=?", (sid,))
                c.execute("DELETE FROM sessions WHERE id=?", (sid,))
            c.execute("DELETE FROM candidates WHERE id=?", (cid,))
            return True

    def purge_older_than(self, days: int) -> int:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat(timespec="seconds")
        with self.conn() as c:
            emails = [r["email"] for r in c.execute(
                "SELECT DISTINCT c.email FROM candidates c JOIN sessions s ON s.candidate_id=c.id WHERE s.started_at<?", (cutoff,))]
        for e in emails:
            self.delete_candidate(e)
        return len(emails)
