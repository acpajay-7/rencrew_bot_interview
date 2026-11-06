import os, tempfile
from reincrew.db import Database
from reincrew.question_bank import seed_if_empty


def fresh_db():
    d = tempfile.mkdtemp()
    db = Database(os.path.join(d, "t.db"))
    seed_if_empty(db)
    return db


def profile(**kw):
    p = dict(name="Rahul Sharma", email="rahul@example.com", stream="Data Science", specialization="Machine Learning",
             experience_level="Fresher", skills=["Python", "SQL", "Scikit-learn"], interview_type="Technical Interview")
    p.update(kw)
    return p
