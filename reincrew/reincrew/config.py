"""Settings from environment variables."""
import os
from pathlib import Path

try:  # optional .env support
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = os.getenv("REINCREW_DB", str(BASE_DIR / "data" / "reincrew.db"))
SEED_PATH = BASE_DIR / "data" / "seed_questions.json"
OPENROUTER_URL = os.getenv("OPENROUTER_URL", "https://openrouter.ai/api/v1/chat/completions")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "deepseek/deepseek-chat")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://127.0.0.1:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3:0.6b")
ASR_MODEL = os.getenv("ASR_MODEL", "base.en")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "")  # empty = admin page disabled


def openrouter_key() -> str:
    return os.getenv("OPENROUTER_API_KEY", "")
