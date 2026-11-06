
import hmac
import json
import os

import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="ReinCrew AI Interview", page_icon="🎙️", layout="wide")

# Bridge Streamlit Cloud secrets -> env vars BEFORE importing config (keys are never hard-coded).
try:
    for _k in ("OPENROUTER_API_KEY", "OPENROUTER_MODEL", "OLLAMA_MODEL", "ADMIN_PASSWORD", "ASR_MODEL"):
        if _k in st.secrets:
            os.environ.setdefault(_k, str(st.secrets[_k]))
except Exception:
    pass

from reincrew import api_ai, config, engine, local_ai, transcription  # noqa: E402
from reincrew.db import Database  # noqa: E402
from reincrew.profile import parse_skills, validate_profile  # noqa: E402
from reincrew.question_bank import save_generated, seed_if_empty  # noqa: E402
from reincrew.report import build_report, to_csv, to_markdown  # noqa: E402
from reincrew.selector import select_questions  # noqa: E402
from reincrew.streams import DIFFICULTIES, EXPERIENCE_LEVELS, INTERVIEW_TYPES, STREAMS  # noqa: E402

CSS = """
<style>
.block-container{max-width:1200px;padding-top:1.5rem}
.rc-brand{font-size:1.6rem;font-weight:700;letter-spacing:-.5px}
.rc-brand span{color:#4f46e5}
.rc-card{border:1px solid rgba(128,128,128,.25);border-radius:14px;padding:1.1rem 1.3rem;margin-bottom:1rem}
.rc-avatar{width:92px;height:92px;border-radius:50%;background:linear-gradient(135deg,#4f46e5,#06b6d4);color:#fff;
 display:flex;align-items:center;justify-content:center;font-size:2rem;font-weight:700;margin:0 auto .5rem}
.rc-badge{display:inline-block;padding:.2rem .7rem;border-radius:999px;font-size:.8rem;font-weight:600;background:rgba(79,70,229,.12);color:#4f46e5}
.rc-q{font-size:1.25rem;line-height:1.5;font-weight:600}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


@st.cache_resource
def get_db() -> Database:
    db = Database(config.DB_PATH)
    seed_if_empty(db)
    return db


db = get_db()
S = st.session_state
for k, v in dict(stage="register", profile=None, mode="Local AI Mode", questions=[], notes=[], sid=None, idx=0, report=None).items():
    S.setdefault(k, v)


def brand():
    st.markdown('<div class="rc-brand">Rein<span>Crew</span> · AI Interview Platform</div>', unsafe_allow_html=True)


# ------------------------------------------------------------------ browser components
def tts_component(text: str):
    safe = json.dumps(text).replace("</", "<\\/")
    components.html(f"""
<div style="font-family:sans-serif">
<button id="b" style="padding:6px 12px;border-radius:8px;border:1px solid #888;cursor:pointer">🔊 Repeat question</button>
<span id="s" style="margin-left:10px;font-size:13px;color:#666">ready</span></div>
<script>
const t={safe}, s=document.getElementById('s');
function speak(){{ if(!('speechSynthesis' in window)){{s.textContent='speech not supported';return}}
 speechSynthesis.cancel(); const u=new SpeechSynthesisUtterance(t);
 u.onstart=()=>s.textContent='AI speaking...'; u.onend=()=>s.textContent='finished'; u.onerror=()=>s.textContent='click Repeat (browser blocked autoplay)';
 speechSynthesis.speak(u);}}
document.getElementById('b').onclick=speak; setTimeout(speak,300);
</script>""", height=48)


def webcam_component():
    components.html("""
<div style="font-family:sans-serif">
<video id="v" autoplay muted playsinline style="width:100%;border-radius:12px;background:#111"></video>
<div id="m" style="font-size:13px;margin-top:4px">requesting camera and microphone...</div></div>
<script>
navigator.mediaDevices.getUserMedia({video:true,audio:true}).then(st=>{
 document.getElementById('v').srcObject=st;
 document.getElementById('m').textContent='📷 camera on · 🎙️ microphone available (preview only, video is not recorded)';
}).catch(e=>{document.getElementById('m').textContent='⚠️ '+e.name+': allow camera/microphone (needs HTTPS or localhost)';});
</script>""", height=290)


# ------------------------------------------------------------------ pages
def page_register():
    brand()
    st.subheader("Candidate registration")
    c1, c2 = st.columns(2)
    name = c1.text_input("Full name")
    email = c2.text_input("Email address")
    stream = c1.selectbox("Educational / professional stream", list(STREAMS.keys()), index=list(STREAMS).index("Data Science"))
    if stream == "Other":
        stream = c1.text_input("Enter your stream").strip()
    specs = STREAMS.get(stream, [])
    spec = c2.selectbox("Specialization / subject", specs + ["Other (type below)"]) if specs else ""
    if spec == "Other (type below)" or not specs:
        spec = c2.text_input("Specialization (type)").strip()
    exp = c1.selectbox("Experience level", EXPERIENCE_LEVELS, index=1)
    itype = c2.selectbox("Interview type", INTERVIEW_TYPES)
    skills = st.text_input("Skills / technologies (comma separated)", placeholder="Python, SQL, Machine Learning")
    st.markdown("##### AI mode")
    mode = st.radio("Mode", engine.MODES, index=1, horizontal=True, label_visibility="collapsed")
    st.caption(engine.MODE_NOTES[mode])
    n = st.slider("Number of questions", 3, 10, 5)
    if st.button("Continue", type="primary"):
        prof = dict(name=name, email=email, stream=stream, specialization=spec, experience_level=exp,
                    interview_type=itype, skills=parse_skills(skills))
        errs = validate_profile(prof)
        if errs:
            for e in errs:
                st.error(e)
            return
        sel = select_questions(db, prof, n=n)
        S.update(profile=prof, mode=mode, questions=sel["questions"], notes=sel["notes"], stage="config", n_requested=n)
        st.rerun()


def page_config():
    brand()
    p = S.profile
    st.subheader("Review your interview")
    st.markdown(f'<div class="rc-card"><b>{p["name"]}</b> · {p["stream"]} / {p["specialization"] or "-"} · {p["experience_level"]}<br>'
                f'Skills: {", ".join(p["skills"]) or "-"} · {p["interview_type"]}<br>'
                f'Mode: <span class="rc-badge">{S.mode}</span> · Questions: {len(S.questions)}</div>', unsafe_allow_html=True)
    topics = sorted({q.get("topic") or q["specialization"] or "" for q in S.questions} - {""})
    st.write("**Topics:** " + (", ".join(topics) or "-"))
    for note in S.notes:
        st.warning(note)
    if not S.questions:
        st.error("No approved questions exist for this stream yet, so an interview can't start. Add some in the Admin page.")
    if S.mode in ("Local AI Mode", "Hybrid Mode"):
        stt = local_ai.ollama_status()
        (st.success if stt["model_available"] else st.warning)(
            f"Local model ({config.OLLAMA_MODEL}): {stt['message']}" + ("" if stt["model_available"] else " — the rule-based scorer will be used instead."))
    if S.mode in ("API Mode", "Hybrid Mode"):
        if config.openrouter_key():
            st.info("OpenRouter key found. Answers will be sent to an external API in this mode.")
        else:
            st.warning("OPENROUTER_API_KEY is not set — the rule-based scorer will be used instead.")
        if S.get("questions") is not None and getattr(S, "n_requested", 0) > len(S.questions) and config.openrouter_key():
            if st.button("Generate extra questions (saved as PENDING for admin review)"):
                try:
                    cands = api_ai.generate_questions(p, [q["question"] for q in db.list_questions(status=None)], k=3)
                    results = [save_generated(db, c)[1] for c in cands]
                    st.write(results)
                except Exception as e:
                    st.error(f"Generation failed: {e}")
    consent = st.checkbox("I agree to the use of my camera preview and microphone for this interview and understand how my answers are processed in the selected mode.")
    c1, c2 = st.columns(2)
    if c1.button("← Edit details"):
        S.stage = "register"; st.rerun()
    if c2.button("Start interview", type="primary", disabled=not (consent and S.questions)):
        cid = db.upsert_candidate(p["name"], p["email"])
        S.sid = db.create_session(cid, p, S.mode, S.questions)
        S.sqs = db.session_questions(S.sid)
        S.idx = 0
        S.stage = "interview"
        st.rerun()


def do_transcribe(i: int):
    f = S.get(f"aud_{i}")
    if f is None:
        S[f"err_{i}"] = "Record your answer first."
        return
    try:
        S[f"txa_{i}"] = transcription.transcribe_bytes(f.getvalue())
        S[f"err_{i}"] = "" if S[f"txa_{i}"] else "No speech detected. Please record again or type your answer."
    except Exception as e:
        S[f"err_{i}"] = f"{e}"


def finish(status: str):
    answers = db.get_answers(S.sid)
    if S.mode == "Hybrid Mode":
        items = [dict(question=next((q for q in S.questions if q["id"] == a["question_id"]), {"question": a["question_text"]}),
                      transcript=a["transcript"] or "", evaluation=a["evaluation"] or {}) for a in answers if a["evaluation"]]
        with st.spinner("Final evaluation (one API call)..."):
            upgraded = engine.finalize_hybrid(items, db=db)
        for a, ev in zip([a for a in answers if a["evaluation"]], upgraded):
            db.save_answer(a["sqid"], a["transcript"] or "", bool(a["skipped"]), ev)
        answers = db.get_answers(S.sid)
    rep = build_report(db.get_session(S.sid), answers, {q["id"]: q for q in S.questions})
    db.finish_session(S.sid, status, rep["summary"]["final_score"], rep)
    S.report, S.stage = rep, "report"


def submit(i: int, transcript: str, skipped: bool):
    q, sq = S.questions[i], S.sqs[i]
    with st.spinner("Evaluating answer..."):
        ev = engine.evaluate_answer(S.mode, q, transcript, db=db)
    db.save_answer(sq["id"], transcript, skipped, ev)
    S.idx = i + 1
    if S.idx >= len(S.questions):
        finish("completed")


def page_interview():
    i = S.idx
    q = S.questions[i]
    brand()
    st.progress(i / len(S.questions), text=f"Question {i + 1} of {len(S.questions)}")
    left, right = st.columns([1.1, 1])
    with left:
        st.markdown('<div class="rc-card"><div class="rc-avatar">R</div><div style="text-align:center"><b>Rein</b> · AI Interviewer<br>'
                    f'<span class="rc-badge">{"Candidate answering" if S.get(f"aud_{i}") else "Waiting for candidate"}</span></div></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="rc-card"><div class="rc-q">{q["question"]}</div></div>', unsafe_allow_html=True)
        tts_component(q["question"])
    with right:
        webcam_component()
        st.audio_input("🎙️ Record your answer (press, speak, press again to stop)", key=f"aud_{i}")
        st.button("Transcribe recording", on_click=do_transcribe, args=(i,))
        if S.get(f"err_{i}"):
            st.error(S[f"err_{i}"])
        ans = st.text_area("Your answer (edit the transcript, or type it)", key=f"txa_{i}", height=140)
        a, b, c = st.columns(3)
        if a.button("Submit answer", type="primary", disabled=not ans.strip()):
            submit(i, ans.strip(), False); st.rerun()
        if b.button("Skip question"):
            submit(i, "", True); st.rerun()
        if c.button("End interview"):
            finish("incomplete"); st.rerun()


def page_report():
    rep = S.report
    brand()
    s, c = rep["summary"], rep["candidate"]
    st.subheader(f"Result for {c['name']}")
    m = st.columns(4)
    m[0].metric("Final score", f"{s['final_score']}/100")
    m[1].metric("Performance", s["overall_performance"])
    m[2].metric("Answered", f"{s['answered']}/{s['total_questions']}")
    m[3].metric("Mode", c["mode"].replace(" Mode", ""))
    st.caption(f"{c['stream']} / {c['specialization']} · {c['experience_level']} · complete {s['complete']} · partial {s['partial']} · incorrect {s['incorrect']}")
    for r in rep["per_question"]:
        with st.expander(f"Q{r['number']} · {r['final_question_score']}/100 · {r['status']} — {r['question']}"):
            st.write("**Answer:**", r["candidate_answer"] or "(skipped)")
            st.write(f"Correctness {r['correctness_score']} · Depth {r['knowledge_depth_score']} · Completeness {r['completeness_score']} · Confidence {r['confidence']}")
            st.write("**Explanation:**", r["explanation"])
            st.write("**Key concepts:**", ", ".join(r["key_concepts"]))
            if r["unsupported_claims"]:
                st.write("**Unsupported claims:**", r["unsupported_claims"])
            if r["contradictions"]:
                st.write("**Contradictions:**", r["contradictions"])
            st.caption(f"Scored by: {r['scoring_mode']}")
    f = rep["feedback"]
    st.markdown("**Strengths:** " + "; ".join(map(str, f["strengths"])))
    st.markdown("**Topics to revise:** " + (", ".join(f["topics_to_revise"]) or "-"))
    d = st.columns(3)
    d[0].download_button("Download JSON", json.dumps(rep, indent=2), "reincrew_report.json", "application/json")
    d[1].download_button("Download CSV", to_csv(rep), "reincrew_report.csv", "text/csv")
    d[2].download_button("Download Markdown", to_markdown(rep), "reincrew_report.md", "text/markdown")
    st.divider()
    x, y = st.columns(2)
    if x.button("New interview"):
        for k in list(S.keys()):
            del S[k]
        st.rerun()
    if y.button("Delete my data"):
        db.delete_candidate(c["email"])
        for k in list(S.keys()):
            del S[k]
        st.success("Your profile, answers and reports were deleted."); 


def page_history():
    brand()
    st.subheader("My interview history")
    if not S.get("profile"):
        st.info("Register for an interview in this browser session first. History is shown only for the email used in this session, so other candidates' results are never exposed.")
        return
    rows = db.history(S.profile["email"])
    st.dataframe(rows, use_container_width=True) if rows else st.write("No interviews yet.")


def page_admin():
    brand()
    st.subheader("Question bank admin")
    if not config.ADMIN_PASSWORD:
        st.warning("Admin is disabled. Set ADMIN_PASSWORD in .env or Streamlit secrets to enable it."); return
    if not hmac.compare_digest(st.text_input("Admin password", type="password"), config.ADMIN_PASSWORD):
        st.info("Enter the admin password."); return
    status = st.selectbox("Show", ["pending", "approved", "rejected"])
    for q in db.list_questions(status=status):
        with st.expander(f"#{q['id']} [{q['stream']} / {q['topic']}] {q['question']}  ({q['source']})"):
            txt = st.text_area("Question", q["question"], key=f"qt{q['id']}")
            ref = st.text_area("Reference answer", q["reference"] or "", key=f"qr{q['id']}")
            diff = st.selectbox("Difficulty", DIFFICULTIES, index=DIFFICULTIES.index(q["difficulty"]), key=f"qd{q['id']}")
            a, b, c = st.columns(3)
            if a.button("Save & approve", key=f"ap{q['id']}"):
                db.update_question(q["id"], question=txt, reference=ref, difficulty=diff, status="approved"); st.rerun()
            if b.button("Reject", key=f"rj{q['id']}"):
                db.update_question(q["id"], status="rejected"); st.rerun()
            if c.button("Delete", key=f"dl{q['id']}"):
                db.delete_question(q["id"]); st.rerun()
    st.markdown("##### Add a question")
    with st.form("addq"):
        stream = st.selectbox("Stream", list(STREAMS)); topic = st.text_input("Topic"); spec = st.text_input("Specialization")
        text = st.text_input("Question"); ref = st.text_area("Reference answer")
        concepts = st.text_area("Key concepts, one per line, format  name: phrase1, phrase2")
        diff = st.selectbox("Difficulty", DIFFICULTIES)
        if st.form_submit_button("Add (approved, source=admin)"):
            groups = {}
            for line in concepts.splitlines():
                if ":" in line:
                    n, ph = line.split(":", 1); groups[n.strip()] = [p.strip() for p in ph.split(",") if p.strip()]
            qid, msg = db.add_question(dict(stream=stream, topic=topic, specialization=spec, question=text, reference=ref,
                                            concepts=groups, difficulty=diff, source="admin", status="approved"))
            (st.success if qid else st.error)(msg)
    if st.button("Purge interviews older than 90 days"):
        st.write(f"Deleted data for {db.purge_older_than(90)} candidate(s).")


# ------------------------------------------------------------------ router
page = st.sidebar.radio("ReinCrew", ["Interview", "My history", "Admin"])
if page == "My history":
    page_history()
elif page == "Admin":
    page_admin()
else:
    {"register": page_register, "config": page_config, "interview": page_interview, "report": page_report}[S.stage]()
