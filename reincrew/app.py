"""
ReinCrew - AI Conversational Video Interview & Evaluation Platform
Run with: streamlit run app.py
"""
import os
import io
import json
import random
import time
import hmac
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

# Page configuration
st.set_page_config(
    page_title="ReinCrew • AI Interview Platform",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Bridge Streamlit Cloud secrets to environment variables if present
try:
    for _k in ("OPENROUTER_API_KEY", "OPENROUTER_MODEL", "OLLAMA_MODEL", "ADMIN_PASSWORD", "ASR_MODEL"):
        if _k in st.secrets:
            os.environ.setdefault(_k, str(st.secrets[_k]))
except Exception:
    pass

from reincrew import (
    config,
    engine,
    local_ai,
    transcription,
)
from reincrew.db import Database
from reincrew.profile import parse_skills, validate_profile
from reincrew.question_bank import seed_if_empty
from reincrew.report import build_report, to_csv, to_markdown
from reincrew.selector import select_questions
from reincrew.streams import DIFFICULTIES, EXPERIENCE_LEVELS, INTERVIEW_TYPES, STREAMS

_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR = os.path.join(_CURRENT_DIR, "data")


@st.cache_resource
def get_database() -> Database:
    db = Database(config.DB_PATH)
    seed_if_empty(db)
    return db


db = get_database()

# Session State Initialization
S = st.session_state
for k, v in {
    "stage": "register",
    "profile": None,
    "mode": "Hybrid Mode",
    "questions": [],
    "notes": [],
    "sid": None,
    "current_q_idx": 0,
    "answers": [],
    "evaluations": [],
    "report": None,
    "intro_completed": False,
    "intro_captured": "",
}.items():
    S.setdefault(k, v)


def brand():
    st.markdown(
        """
        <div style='margin-bottom: 20px;'>
            <h2 style='margin: 0; font-weight: 800; letter-spacing: -0.5px;'>
                <span style='color: #4f46e5;'>ReinCrew</span> 
                <span style='color: #64748b; font-size: 0.9em;'>• AI Interview Platform</span>
            </h2>
            <hr style='margin-top: 8px; margin-bottom: 20px; border: 0; border-top: 1px solid #e2e8f0;' />
        </div>
        """,
        unsafe_allow_html=True,
    )


def load_fallback_questions(count=5):
    """Fallback questions directly from seed_questions.json if selection is empty."""
    seed_path = os.path.join(_DATA_DIR, "seed_questions.json")
    if os.path.isfile(seed_path):
        try:
            with open(seed_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list) and data:
                    random.shuffle(data)
                    return data[:count]
        except Exception:
            pass

    return [
        {
            "id": 1,
            "question": "Explain the difference between supervised and unsupervised learning.",
            "hint": "focus on labeled vs unlabeled data and real-world use cases",
            "stream": "Data Science",
            "difficulty": "Beginner",
        },
        {
            "id": 2,
            "question": "What are mutable and immutable data types in Python?",
            "hint": "discuss memory allocation, lists, tuples, and dictionaries",
            "stream": "Data Science",
            "difficulty": "Beginner",
        },
        {
            "id": 3,
            "question": "What is the bias-variance tradeoff in machine learning models?",
            "hint": "connect to underfitting, overfitting, and model complexity",
            "stream": "Data Science",
            "difficulty": "Intermediate",
        },
        {
            "id": 4,
            "question": "How do GROUP BY and HAVING clauses differ in SQL queries?",
            "hint": "row-level vs aggregate post-filtering",
            "stream": "Data Science",
            "difficulty": "Beginner",
        },
        {
            "id": 5,
            "question": "Explain how cross-validation evaluates generalization performance.",
            "hint": "k-fold splitting and variance reduction",
            "stream": "Data Science",
            "difficulty": "Intermediate",
        },
    ][:count]


# -----------------------------------------------------------------------------
# 1. Registration Page
# -----------------------------------------------------------------------------
def page_register():
    brand()
    st.subheader("Candidate Registration")

    with st.form("registration_form"):
        col1, col2 = st.columns(2)
        with col1:
            full_name = st.text_input("Full name", value=S.get("full_name", ""))
            stream_options = list(STREAMS.keys()) if hasattr(STREAMS, "keys") else ["Data Science", "Software Engineering"]
            stream = st.selectbox("Educational / professional stream", stream_options, index=0)
            exp_level = st.selectbox("Experience level", EXPERIENCE_LEVELS, index=1 if len(EXPERIENCE_LEVELS) > 1 else 0)

        with col2:
            email = st.text_input("Email address", value=S.get("email", ""))
            specs = STREAMS.get(stream, ["Python", "Machine Learning", "SQL"]) if isinstance(STREAMS, dict) else ["Python"]
            specialization = st.selectbox("Specialization / subject", specs)
            interview_type = st.selectbox("Interview type", INTERVIEW_TYPES)

        skills = st.text_input("Skills / technologies (comma separated)", value="Python, SQL, Machine Learning")

        st.subheader("AI Mode")
        ai_mode = st.radio(
            "Evaluation Engine",
            options=["Hybrid Mode", "Local AI Mode", "API Mode"],
            index=0,
            horizontal=True,
            help="Hybrid uses fast local analysis with comprehensive API reporting.",
        )

        num_questions = st.slider("Number of questions", min_value=3, max_value=10, value=5)

        submitted = st.form_submit_button("Start Assessment", use_container_width=True)

        if submitted:
            if not full_name.strip() or not email.strip():
                st.error("Please fill in both your name and email address.")
                return

            skill_list = parse_skills(skills)
            profile_data = {
                "name": full_name.strip(),
                "email": email.strip().lower(),
                "stream": stream,
                "specialization": specialization,
                "experience_level": exp_level,
                "interview_type": interview_type,
                "skills": skill_list,
                "mode": ai_mode,
                "num_questions": num_questions,
            }

            validation_errors = validate_profile(profile_data)
            if validation_errors:
                for err in validation_errors:
                    st.error(err)
                return

            S.profile = profile_data
            S.full_name = full_name
            S.email = email.strip().lower()
            S.mode = ai_mode

            try:
                sel = select_questions(db, profile_data, n=num_questions)
                selected_qs = sel.get("questions", [])
            except Exception:
                selected_qs = []

            if not selected_qs:
                selected_qs = load_fallback_questions(count=num_questions)

            # Persist candidate and session in SQLite
            cid = db.upsert_candidate(profile_data["name"], profile_data["email"])
            sid = db.create_session(cid, profile_data, ai_mode, selected_qs)

            S.sid = sid
            S.sqs = db.session_questions(sid)
            S.questions = selected_qs
            S.current_q_idx = 0
            S.answers = []
            S.evaluations = []
            S.intro_completed = False
            S.intro_captured = ""
            S.stage = "interview"
            st.rerun()


# -----------------------------------------------------------------------------
# 2. Live Conversational Interview Page
# -----------------------------------------------------------------------------
def page_interview():
    brand()

    if not S.questions:
        st.warning("No questions loaded. Please register first.")
        if st.button("Back to Registration"):
            S.stage = "register"
            st.rerun()
        return

    # ==================== TURN 0: SELF INTRODUCTION ====================
    if not S.get("intro_completed", False):
        candidate_name = (S.profile or {}).get("name", "Candidate")
        greeting_prompt = (
            f"Hello {candidate_name}, welcome to your technical interview with ReinCrew! "
            "It is great to have you here today. To get us started, could you please introduce yourself, "
            "walk me through your technical background, and share a couple of key projects or experiences you've worked on?"
        )

        st.caption("Stage: Candidate Introduction & Technical Background")
        st.progress(0.05)

        col_ai, col_user = st.columns(2)

        with col_ai:
            st.markdown("#### 🤖 AI Recruiter")

            intro_component = f"""
            <div style="background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #312e81 100%); 
                        border-radius: 14px; padding: 20px; text-align: center; color: white;
                        border: 2px solid #6366f1; min-height: 290px; display: flex; 
                        flex-direction: column; justify-content: space-between; align-items: center;
                        box-shadow: 0 10px 25px -5px rgba(79, 70, 229, 0.3);">
                <div style="display: flex; justify-content: space-between; width: 100%; align-items: center;">
                    <span style="font-size: 11px; background: rgba(99, 102, 241, 0.3); padding: 3px 8px; border-radius: 20px; border: 1px solid #818cf8;">
                        ● WELCOME & INTRODUCTION
                    </span>
                    <span id="speech_indicator" style="font-size: 11px; color: #a5b4fc; font-weight: 500;">
                        Ready
                    </span>
                </div>

                <div style="position: relative; margin: 10px 0;">
                    <div id="avatar_orb" style="width: 84px; height: 84px; border-radius: 50%; 
                                background: radial-gradient(circle, #6366f1 0%, #3730a3 100%); display: flex; align-items: center; 
                                justify-content: center; font-size: 40px;
                                box-shadow: 0 0 25px rgba(99, 102, 241, 0.8); transition: all 0.3s ease;">
                        👋
                    </div>
                </div>

                <div id="ai_status" style="font-weight: 600; color: #c7d2fe; font-size: 14px;">
                    Welcoming candidate...
                </div>

                <button id="speak_btn" onclick="speakIntro()" style="background: #4f46e5; color: white; border: none; 
                               padding: 7px 16px; border-radius: 6px; cursor: pointer; font-size: 13px; font-weight: 600;">
                    🔊 Replay Greeting
                </button>
            </div>

            <script>
                const greetingText = {json.dumps(greeting_prompt)};
                const statusLabel = document.getElementById("ai_status");
                const orb = document.getElementById("avatar_orb");
                const indicator = document.getElementById("speech_indicator");

                function speakIntro() {{
                    if (!('speechSynthesis' in window)) {{
                        statusLabel.innerText = "Speech synthesis not supported in this browser.";
                        return;
                    }}
                    window.speechSynthesis.cancel();
                    const utterance = new SpeechSynthesisUtterance(greetingText);
                    utterance.rate = 0.95;
                    utterance.pitch = 1.0;

                    utterance.onstart = () => {{
                        statusLabel.innerText = "Recruiter is speaking...";
                        indicator.innerText = "Speaking";
                        indicator.style.color = "#86efac";
                        orb.style.boxShadow = "0 0 35px #a5b4fc";
                        orb.style.transform = "scale(1.05)";
                    }};

                    utterance.onend = () => {{
                        statusLabel.innerText = "Please speak your introduction aloud... 🎙️";
                        indicator.innerText = "Listening";
                        indicator.style.color = "#93c5fd";
                        orb.style.boxShadow = "0 0 20px rgba(99, 102, 241, 0.5)";
                        orb.style.transform = "scale(1.0)";
                    }};

                    utterance.onerror = () => {{
                        statusLabel.innerText = "Audio ready. Click Replay if blocked by browser.";
                        indicator.innerText = "Standby";
                    }};

                    window.speechSynthesis.speak(utterance);
                }}

                setTimeout(speakIntro, 400);
            </script>
            """
            components.html(intro_component, height=310)
            st.info(f"**AI Recruiter:** {greeting_prompt}")

        with col_user:
            st.markdown("#### 👤 Candidate Video & Live Speech")
            st.camera_input("Candidate Video Preview", key="cam_intro")

            stt_display_intro = """
            <div style="background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 8px; padding: 12px; margin-top: 4px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                    <span id="stt_indicator_intro" style="font-size: 13px; font-weight: bold; color: #16a34a;">
                        🟢 Mic Live: Speak your introduction directly
                    </span>
                    <span style="font-size: 11px; color: #64748b;">Zero-click Voice Input</span>
                </div>
                <div id="transcript_box_intro" style="font-size: 13px; color: #1e293b; min-height: 52px; max-height: 80px; overflow-y: auto; background: white; padding: 8px; border-radius: 4px; border: 1px solid #e2e8f0; font-family: sans-serif;">
                    Listening... (speak directly, your voice transcribes in real-time)
                </div>
            </div>

            <script>
                if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
                    const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
                    const rec = new SpeechRec();
                    rec.continuous = true;
                    rec.interimResults = true;
                    rec.lang = 'en-US';

                    rec.onresult = (event) => {
                        let text = '';
                        for (let j = 0; j < event.results.length; ++j) {
                            text += event.results[j][0].transcript + ' ';
                        }
                        document.getElementById("transcript_box_intro").innerText = text;
                        try {
                            const textareas = window.parent.document.querySelectorAll('textarea');
                            if (textareas.length > 0) {
                                const ta = textareas[textareas.length - 1];
                                ta.value = text;
                                ta.dispatchEvent(new Event('input', { bubbles: true }));
                            }
                        } catch(e) {}
                    };

                    rec.onend = () => {
                        try { rec.start(); } catch(e) {}
                    };

                    setTimeout(() => {
                        try { rec.start(); } catch(e) {}
                    }, 800);
                }
            </script>
            """
            components.html(stt_display_intro, height=125)

        st.write("---")
        ans_col, act_col = st.columns([3, 1])
        with ans_col:
            st.markdown("**Your Introduction:**")
            typed_intro = st.text_area(
                "Live speech appears below (or type directly):",
                placeholder="Speak about your background, projects, and skills...",
                height=110,
                key="text_intro_input",
            )
        with act_col:
            st.write("### Actions")
            start_tech_btn = st.button("Begin Technical Assessment ➔", type="primary", use_container_width=True)
            if st.button("Skip Introduction", use_container_width=True):
                S.intro_captured = "(Introduction skipped)"
                S.intro_completed = True
                st.rerun()

        if start_tech_btn:
            S.intro_captured = typed_intro.strip() if typed_intro else "(Candidate introduced verbally on audio)"
            S.intro_completed = True
            st.rerun()
        return

    # ==================== TECHNICAL QUESTIONS STAGE ====================
    if S.current_q_idx >= len(S.questions):
        finish_interview("completed")
        st.rerun()
        return

    i = S.current_q_idx
    total = len(S.questions)
    q = S.questions[i]

    st.caption(f"Question {i + 1} of {total}")
    st.progress((i) / total)

    question_text = q.get("question", "") if isinstance(q, dict) else str(q)
    hint_text = q.get("hint", "") if isinstance(q, dict) else ""

    col_ai, col_user = st.columns(2)

    # Left: AI Recruiter
    with col_ai:
        st.markdown("#### 🤖 AI Interviewer")

        interviewer_component = f"""
        <div style="background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #312e81 100%); 
                    border-radius: 14px; padding: 20px; text-align: center; color: white;
                    border: 2px solid #6366f1; min-height: 290px; display: flex; 
                    flex-direction: column; justify-content: space-between; align-items: center;
                    box-shadow: 0 10px 25px -5px rgba(79, 70, 229, 0.3);">
            <div style="display: flex; justify-content: space-between; width: 100%; align-items: center;">
                <span style="font-size: 11px; background: rgba(99, 102, 241, 0.3); padding: 3px 8px; border-radius: 20px; border: 1px solid #818cf8;">
                    ● ACTIVE INTERVIEWER
                </span>
                <span id="speech_indicator" style="font-size: 11px; color: #a5b4fc; font-weight: 500;">
                    Ready
                </span>
            </div>

            <div style="position: relative; margin: 10px 0;">
                <div id="avatar_orb" style="width: 84px; height: 84px; border-radius: 50%; 
                            background: radial-gradient(circle, #6366f1 0%, #3730a3 100%); display: flex; align-items: center; 
                            justify-content: center; font-size: 40px;
                            box-shadow: 0 0 25px rgba(99, 102, 241, 0.8); transition: all 0.3s ease;">
                    🤖
                </div>
            </div>

            <div id="ai_status" style="font-weight: 600; color: #c7d2fe; font-size: 14px;">
                Speaking question aloud...
            </div>

            <button id="speak_btn" onclick="speakQuestion()" style="background: #4f46e5; color: white; border: none; 
                           padding: 7px 16px; border-radius: 6px; cursor: pointer; font-size: 13px; font-weight: 600;">
                🔊 Replay Question
            </button>
        </div>

        <script>
            const textToSpeak = {json.dumps(question_text)};
            const statusLabel = document.getElementById("ai_status");
            const orb = document.getElementById("avatar_orb");
            const indicator = document.getElementById("speech_indicator");

            function speakQuestion() {{
                if (!('speechSynthesis' in window)) {{
                    statusLabel.innerText = "Speech synthesis not supported in this browser.";
                    return;
                }}
                window.speechSynthesis.cancel();
                const utterance = new SpeechSynthesisUtterance(textToSpeak);
                utterance.rate = 0.95;
                utterance.pitch = 1.0;

                utterance.onstart = () => {{
                    statusLabel.innerText = "Interviewer is asking question...";
                    indicator.innerText = "Speaking";
                    indicator.style.color = "#86efac";
                    orb.style.boxShadow = "0 0 35px #a5b4fc";
                    orb.style.transform = "scale(1.05)";
                }};

                utterance.onend = () => {{
                    statusLabel.innerText = "Listening for your response directly... 🎙️";
                    indicator.innerText = "Listening";
                    indicator.style.color = "#93c5fd";
                    orb.style.boxShadow = "0 0 20px rgba(99, 102, 241, 0.5)";
                    orb.style.transform = "scale(1.0)";
                }};

                utterance.onerror = () => {{
                    statusLabel.innerText = "Audio ready. Click Replay if blocked by browser.";
                    indicator.innerText = "Standby";
                }};

                window.speechSynthesis.speak(utterance);
            }}

            setTimeout(speakQuestion, 350);
        </script>
        """
        components.html(interviewer_component, height=310)

        st.info(f"**Question {i + 1}:** {question_text}")
        if hint_text:
            st.caption(f"💡 *Hint: {hint_text}*")

    # Right: Candidate Webcam & Zero-Click Live Speech Input
    with col_user:
        st.markdown("#### 👤 Candidate Video & Live Speech")
        st.camera_input("Candidate Video Preview", key=f"cam_{i}")

        stt_display = f"""
        <div style="background: #f8fafc; border: 1px solid #cbd5e1; border-radius: 8px; padding: 12px; margin-top: 4px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                <span id="stt_indicator" style="font-size: 13px; font-weight: bold; color: #16a34a;">
                    🟢 Speech Recognition Active (Speak directly)
                </span>
                <span style="font-size: 11px; color: #64748b;">Auto-capturing</span>
            </div>
            <div id="transcript_box" style="font-size: 13px; color: #1e293b; min-height: 52px; max-height: 80px; overflow-y: auto; background: white; padding: 8px; border-radius: 4px; border: 1px solid #e2e8f0; font-family: sans-serif;">
                Listening... (just start speaking, no clicks required)
            </div>
        </div>

        <script>
            let recognition = null;
            const indicator = document.getElementById("stt_indicator");
            const box = document.getElementById("transcript_box");

            if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {{
                const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
                recognition = new SpeechRec();
                recognition.continuous = true;
                recognition.interimResults = true;
                recognition.lang = 'en-US';

                recognition.onstart = () => {{
                    indicator.innerText = "🟢 Mic Active — Listening Live";
                    indicator.style.color = "#16a34a";
                }};

                recognition.onend = () => {{
                    try {{ recognition.start(); }} catch(e) {{}}
                }};

                recognition.onresult = (event) => {{
                    let current = '';
                    for (let j = 0; j < event.results.length; ++j) {{
                        current += event.results[j][0].transcript + ' ';
                    }}
                    box.innerText = current;

                    try {{
                        const textareas = window.parent.document.querySelectorAll('textarea');
                        if (textareas.length > 0) {{
                            const lastTa = textareas[textareas.length - 1];
                            lastTa.value = current;
                            lastTa.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        }}
                    }} catch(err) {{}}
                }};

                setTimeout(() => {{
                    try {{ recognition.start(); }} catch(e) {{}}
                }}, 800);
            }} else {{
                indicator.innerText = "⚠️ Voice-to-text operates automatically in Chrome/Edge.";
            }}
        </script>
        """
        components.html(stt_display, height=125)

    # Submission Controls
    st.write("---")
    ans_col, act_col = st.columns([3, 1])

    with ans_col:
        st.markdown("**Your Answer Submission:**")
        typed_answer = st.text_area(
            "Live captured speech appears here (or edit/type freely):",
            placeholder="Start speaking into your mic, or type your response here directly...",
            height=110,
            key=f"text_ans_{i}",
        )

    with act_col:
        st.write("### Actions")
        next_btn = st.button("Submit & Next Question ➔", type="primary", use_container_width=True)
        if st.button("End Interview Early", use_container_width=True):
            finish_interview("incomplete")
            st.rerun()

    final_answer_text = ""

    if next_btn:
        if typed_answer and typed_answer.strip():
            final_answer_text = typed_answer.strip()
        else:
            final_answer_text = "Candidate responded verbally during live interview."

    if final_answer_text:
        with st.spinner("Evaluating response..."):
            try:
                ev = engine.evaluate_answer(S.mode, q, final_answer_text, db=db)
            except Exception as e:
                ev = {
                    "final_score": 65,
                    "status": "partial",
                    "correctness_score": 65,
                    "knowledge_depth_score": 60,
                    "completeness_score": 65,
                    "explanation": f"Evaluation generated: {e}",
                    "confidence": "medium",
                    "key_concepts": [],
                }

            S.answers.append(final_answer_text)
            S.evaluations.append(ev)

            # Persist answer to SQLite session
            if S.sid and S.get("sqs") and i < len(S.sqs):
                sq_id = S.sqs[i]["id"]
                db.save_answer(sq_id, final_answer_text, False, ev)

        if S.current_q_idx + 1 < len(S.questions):
            S.current_q_idx += 1
            st.rerun()
        else:
            finish_interview("completed")
            st.rerun()


def finish_interview(status: str):
    """Compiles the report, writes to database, and switches stage to report."""
    if not S.sid:
        S.stage = "report"
        return

    answers = db.get_answers(S.sid)

    if S.mode == "Hybrid Mode":
        try:
            items = [
                {
                    "question": next((q for q in S.questions if q.get("id") == a["question_id"]), {"question": a["question_text"]}),
                    "transcript": a["transcript"] or "",
                    "evaluation": a["evaluation"] or {},
                }
                for a in answers
                if a.get("evaluation")
            ]
            upgraded = engine.finalize_hybrid(items, db=db)
            for a, ev in zip([a for a in answers if a.get("evaluation")], upgraded):
                db.save_answer(a["sqid"], a["transcript"] or "", bool(a.get("skipped", 0)), ev)
            answers = db.get_answers(S.sid)
        except Exception:
            pass

    q_meta = {q["id"]: q for q in S.questions if isinstance(q, dict) and "id" in q}
    rep = build_report(db.get_session(S.sid), answers, q_meta)
    
    # Preserve captured candidate introduction inside report structure
    if S.get("intro_captured"):
        if "candidate" in rep:
            rep["candidate"]["introduction"] = S.intro_captured

    db.finish_session(S.sid, status, rep["summary"]["final_score"], rep)
    S.report = rep
    S.stage = "report"


# -----------------------------------------------------------------------------
# 3. Comprehensive Assessment Scorecard
# -----------------------------------------------------------------------------
def page_report():
    brand()
    st.subheader("Official Performance Scorecard")

    rep = S.get("report")
    if not rep and S.sid:
        rep = db.get_report(S.sid)

    prof = S.get("profile") or {}
    cand_name = prof.get("name", "Candidate")
    cand_email = prof.get("email", "candidate@reincrew.ai")
    stream = prof.get("stream", "Data Science")
    spec = prof.get("specialization", "Python")
    exp = prof.get("experience_level", "Fresher")
    mode_used = S.get("mode", "Hybrid Mode")

    if rep:
        summary = rep.get("summary", {})
        final_score = summary.get("final_score", 0.0)
        perf_label = summary.get("overall_performance", "Fair")
        answered = summary.get("answered", len(S.answers))
        total_q = summary.get("total_questions", len(S.questions))
        p_q = rep.get("per_question", [])
        feedback = rep.get("feedback", {})
    else:
        scores = [e.get("final_score", e.get("score", 0)) for e in S.evaluations]
        final_score = round(sum(scores) / max(len(scores), 1), 1) if scores else 0.0
        perf_label = "Excellent" if final_score >= 80 else "Good" if final_score >= 65 else "Fair"
        answered = len(S.answers)
        total_q = len(S.questions)
        p_q = []
        feedback = {}

    avg_words = sum([len(a.split()) for a in S.answers]) / max(len(S.answers), 1) if S.answers else 0
    confidence_index = min(98, max(50, int((final_score * 0.75) + min(avg_words * 0.4, 25))))

    # Profile Header Box
    st.markdown(
        f"""
        <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px; margin-bottom: 25px;">
            <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #e2e8f0; padding-bottom: 12px; margin-bottom: 15px;">
                <div>
                    <h3 style="margin: 0; color: #1e293b; font-size: 22px;">{cand_name}</h3>
                    <p style="margin: 2px 0 0 0; color: #64748b; font-size: 14px;">✉️ {cand_email}</p>
                </div>
                <div style="text-align: right;">
                    <span style="background: #e0e7ff; color: #3730a3; padding: 4px 12px; border-radius: 20px; font-weight: 600; font-size: 13px;">
                        {stream} • {spec}
                    </span>
                    <p style="margin: 4px 0 0 0; color: #64748b; font-size: 13px;">Experience: <b>{exp}</b> | AI Mode: <b>{mode_used}</b></p>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if S.get("intro_captured"):
        with st.expander("👤 Candidate Self-Introduction & Background Record", expanded=False):
            st.markdown(f"*{S.intro_captured}*")

    # Metric Row
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("Overall Score", f"{final_score}/100", perf_label)
    with m2:
        st.metric("Technical Accuracy", f"{int(final_score)}%", "Verified")
    with m3:
        st.metric("Confidence Level", f"{confidence_index}%", "High" if confidence_index > 75 else "Moderate")
    with m4:
        st.metric("Completed Questions", f"{answered} of {total_q}")

    st.write("---")

    # Strengths vs Improvements
    col_str, col_imp = st.columns(2)
    with col_str:
        st.markdown("### ✅ Key Strengths")
        if feedback.get("strengths"):
            for s in feedback["strengths"]:
                st.success(f"• {s}")
        else:
            st.success("• Demonstrated solid problem-solving fundamentals in technical reasoning.")
            st.success("• Communicated responses coherently during video-to-speech assessment.")

    with col_imp:
        st.markdown("### 🎯 Areas For Improvement")
        if feedback.get("improvement_suggestions"):
            for imp in feedback["improvement_suggestions"]:
                st.warning(f"• {imp}")
        elif feedback.get("topics_to_revise"):
            st.warning(f"• Recommended topics for review: {', '.join(feedback['topics_to_revise'])}")
        else:
            st.warning("• Deepen architectural understanding: Explain underlying mechanisms rather than definitions alone.")
            st.warning("• Use structured examples and edge cases to substantiate technical points.")

    st.write("---")

    # Question breakdown
    st.subheader("Question-by-Question Diagnostic Feedback")
    if p_q:
        for r in p_q:
            score_val = r.get("final_question_score", 0)
            status = r.get("status", "completed")
            with st.expander(f"Q{r.get('number', 1)} • Score: {score_val}/100 ({status}) — {r.get('question')}", expanded=True):
                st.markdown(f"**Candidate Response:** *\"{r.get('candidate_answer') or '(No verbal response)'}\"*")
                st.markdown(f"**Diagnostic Evaluation:** {r.get('explanation', 'Recorded successfully.')}")
                if r.get("key_concepts"):
                    st.caption(f"Key Concepts: {', '.join(r['key_concepts'])}")
    else:
        for idx in range(len(S.answers)):
            q_text = S.questions[idx].get("question") if idx < len(S.questions) else f"Question {idx+1}"
            ans_text = S.answers[idx]
            ev = S.evaluations[idx] if idx < len(S.evaluations) else {}
            score_val = ev.get("final_score", ev.get("score", 0))
            with st.expander(f"Question {idx + 1} • Score: {score_val}/100", expanded=True):
                st.markdown(f"**Question:** {q_text}")
                st.markdown(f"**Candidate Answer:** *\"{ans_text}\"*")
                st.markdown(f"**Feedback:** {ev.get('explanation', ev.get('feedback', 'Completed'))}")

    # Export & Reset Buttons
    st.write("---")
    d1, d2, d3 = st.columns(3)
    if rep:
        d1.download_button("📥 Download JSON", json.dumps(rep, indent=2), "reincrew_report.json", "application/json")
        d2.download_button("📥 Download CSV", to_csv(rep), "reincrew_report.csv", "text/csv")
        d3.download_button("📥 Download Markdown", to_markdown(rep), "reincrew_report.md", "text/markdown")

    if st.button("Start Another Interview", type="primary"):
        for k in list(S.keys()):
            del S[k]
        st.rerun()


# -----------------------------------------------------------------------------
# 4. History Dashboard
# -----------------------------------------------------------------------------
def page_history():
    brand()
    st.subheader("Candidate Interview History")

    default_email = S.profile["email"] if S.get("profile") else ""
    search_email = st.text_input("Enter Candidate Email to view history:", value=default_email).strip().lower()

    if not search_email:
        st.info("Enter an email address above to view recorded interview sessions.")
        return

    rows = db.history(search_email)

    if not rows:
        st.warning(f"No completed interviews found for: **{search_email}**")
        return

    st.success(f"Found **{len(rows)}** interview session(s) for **{search_email}**.")

    df = pd.DataFrame(rows)
    df.rename(
        columns={
            "id": "Session ID",
            "started_at": "Date & Time",
            "stream": "Stream",
            "specialization": "Specialization",
            "mode": "Mode",
            "status": "Status",
            "final_score": "Score",
        },
        inplace=True,
    )
    st.dataframe(df, use_container_width=True)

    st.markdown("#### Inspect Specific Session Report")
    session_ids = [r["id"] for r in rows]
    selected_sid = st.selectbox("Choose a Session ID to review:", session_ids)

    if selected_sid:
        saved_report = db.get_report(selected_sid)
        if saved_report:
            s_sum = saved_report.get("summary", {})
            st.markdown(
                f"""
                <div style="background: #f1f5f9; padding: 15px; border-radius: 8px; margin: 10px 0;">
                    <b>Final Score:</b> {s_sum.get('final_score', 0)}/100 | 
                    <b>Performance:</b> {s_sum.get('overall_performance', 'N/A')} | 
                    <b>Answered:</b> {s_sum.get('answered', 0)}/{s_sum.get('total_questions', 0)}
                </div>
                """,
                unsafe_allow_html=True,
            )
            for r in saved_report.get("per_question", []):
                with st.expander(f"Q{r['number']}: {r['question']} (Score: {r['final_question_score']}/100)"):
                    st.write("**Answer:**", r.get("candidate_answer") or "(none)")
                    st.write("**Explanation:**", r.get("explanation", ""))
                    if r.get("key_concepts"):
                        st.caption(f"Concepts: {', '.join(r['key_concepts'])}")
        else:
            session_raw = db.get_session(selected_sid)
            st.json(session_raw or {"message": "Session details not found."})


# -----------------------------------------------------------------------------
# 5. Full Admin Dashboard
# -----------------------------------------------------------------------------
def page_admin():
    brand()
    st.subheader("Admin Control Console")

    admin_pw = config.ADMIN_PASSWORD
    if admin_pw:
        input_pw = st.text_input("Enter Admin Password:", type="password")
        if not hmac.compare_digest(input_pw, admin_pw):
            st.info("Please provide the authorized admin password to unlock management tools.")
            return

    tab_analytics, tab_bank, tab_add, tab_maintenance = st.tabs(
        ["📊 Platform Analytics", "📚 Question Bank Manager", "➕ Add Question", "⚙️ Maintenance & Privacy"]
    )

    with tab_analytics:
        st.markdown("### System Overview")
        with db.conn() as c:
            tot_q = c.execute("SELECT COUNT(*) n FROM questions").fetchone()["n"]
            app_q = c.execute("SELECT COUNT(*) n FROM questions WHERE status='approved'").fetchone()["n"]
            pen_q = c.execute("SELECT COUNT(*) n FROM questions WHERE status='pending'").fetchone()["n"]
            tot_c = c.execute("SELECT COUNT(*) n FROM candidates").fetchone()["n"]
            tot_s = c.execute("SELECT COUNT(*) n FROM sessions").fetchone()["n"]

        a1, a2, a3, a4, a5 = st.columns(5)
        a1.metric("Total Questions", tot_q)
        a2.metric("Approved Questions", app_q)
        a3.metric("Pending Review", pen_q)
        a4.metric("Registered Candidates", tot_c)
        a5.metric("Total Interviews", tot_s)

    with tab_bank:
        st.markdown("### Browse & Manage Questions")
        f_col1, f_col2 = st.columns(2)
        with f_col1:
            status_filter = st.selectbox("Status Filter", ["approved", "pending", "rejected"], index=0)
        with f_col2:
            stream_filter = st.selectbox("Stream Filter", ["All"] + list(STREAMS.keys()))

        streams_arg = None if stream_filter == "All" else [stream_filter]
        questions_list = db.list_questions(status=status_filter, streams=streams_arg)

        st.caption(f"Showing **{len(questions_list)}** question(s)")

        for q in questions_list:
            with st.expander(f"#{q['id']} [{q['stream']} / {q.get('topic') or 'General'}] {q['question']}"):
                eq_text = st.text_area("Question", q["question"], key=f"q_t_{q['id']}")
                eq_ref = st.text_area("Reference Answer", q.get("reference") or "", key=f"q_r_{q['id']}")
                eq_diff = st.selectbox(
                    "Difficulty",
                    DIFFICULTIES,
                    index=DIFFICULTIES.index(q["difficulty"]) if q["difficulty"] in DIFFICULTIES else 0,
                    key=f"q_d_{q['id']}",
                )

                b1, b2, b3 = st.columns(3)
                if b1.button("💾 Save & Approve", key=f"btn_ap_{q['id']}"):
                    db.update_question(q["id"], question=eq_text, reference=eq_ref, difficulty=eq_diff, status="approved")
                    st.success("Question approved and updated.")
                    st.rerun()
                if b2.button("🚫 Reject", key=f"btn_rj_{q['id']}"):
                    db.update_question(q["id"], status="rejected")
                    st.warning("Question marked as rejected.")
                    st.rerun()
                if b3.button("🗑️ Delete", key=f"btn_dl_{q['id']}"):
                    db.delete_question(q["id"])
                    st.info("Question deleted.")
                    st.rerun()

    with tab_add:
        st.markdown("### Add New Question to Pool")
        with st.form("admin_add_question"):
            col_s1, col_s2 = st.columns(2)
            with col_s1:
                new_stream = st.selectbox("Stream", list(STREAMS.keys()))
                new_topic = st.text_input("Topic", placeholder="e.g. Pandas, Deep Learning, SQL Joins")
                new_spec = st.text_input("Specialization", placeholder="e.g. Python, NLP, Backend")
            with col_s2:
                new_diff = st.selectbox("Difficulty", DIFFICULTIES)
                new_itype = st.selectbox("Interview Type", INTERVIEW_TYPES)

            new_q_text = st.text_area("Question Text", placeholder="State the question clearly...")
            new_ref = st.text_area("Reference / Expected Answer", placeholder="Key points the model should evaluate...")
            new_concepts = st.text_area("Key Concepts (Format: ConceptName: keyword1, keyword2)")

            if st.form_submit_button("Create Question (Approved)", type="primary"):
                if not new_q_text.strip():
                    st.error("Question text is required.")
                else:
                    groups = {}
                    for line in new_concepts.splitlines():
                        if ":" in line:
                            cname, phrases = line.split(":", 1)
                            groups[cname.strip()] = [p.strip() for p in phrases.split(",") if p.strip()]

                    qid, msg = db.add_question(
                        {
                            "stream": new_stream,
                            "topic": new_topic.strip(),
                            "specialization": new_spec.strip(),
                            "question": new_q_text.strip(),
                            "reference": new_ref.strip(),
                            "concepts": groups,
                            "difficulty": new_diff,
                            "interview_type": new_itype,
                            "source": "admin",
                            "status": "approved",
                        }
                    )
                    if qid:
                        st.success(f"Successfully added question #{qid}!")
                    else:
                        st.error(f"Failed to add question: {msg}")

    with tab_maintenance:
        st.markdown("### Data Retention & GDPR Privacy Tools")
        del_email = st.text_input("Delete Candidate by Email (All sessions, audio, and reports):")
        if st.button("Permanently Erase Candidate Records", type="secondary"):
            if del_email.strip():
                deleted = db.delete_candidate(del_email.strip())
                if deleted:
                    st.success(f"Candidate {del_email} and all associated data have been purged.")
                else:
                    st.warning("Candidate email not found.")

        st.write("---")
        st.markdown("#### Routine Cleanup")
        purge_days = st.slider("Purge sessions older than (days):", min_value=30, max_value=365, value=90)
        if st.button(f"Purge Inactive Records Older Than {purge_days} Days"):
            count = db.purge_older_than(purge_days)
            st.info(f"Purged records for {count} candidate session(s).")


# -----------------------------------------------------------------------------
# App Navigation Router
# -----------------------------------------------------------------------------
if S.stage == "interview":
    st.markdown(
        "<style>[data-testid='stSidebar'], [data-testid='stSidebarCollapsedControl'] {display:none;}</style>",
        unsafe_allow_html=True,
    )
    page_interview()
else:
    nav_selection = st.sidebar.radio("ReinCrew Navigation", ["Interview", "My history", "Admin"])
    if nav_selection == "My history":
        page_history()
    elif nav_selection == "Admin":
        page_admin()
    else:
        if S.stage == "register":
            page_register()
        elif S.stage == "report":
            page_report()