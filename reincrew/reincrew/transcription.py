"""Speech-to-text with Faster-Whisper (lazy loaded). Model files download once on first use."""
import os
import tempfile
from functools import lru_cache

from . import config


class TranscriptionError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def _model():
    try:
        from faster_whisper import WhisperModel
    except ImportError as e:
        raise TranscriptionError("faster-whisper is not installed. Run: pip install faster-whisper") from e
    return WhisperModel(config.ASR_MODEL, device="cpu", compute_type="int8")


def transcribe_bytes(audio: bytes, suffix: str = ".wav") -> str:
    if not audio:
        raise TranscriptionError("No audio received.")

    temp_path = None
    try:
        # On Windows, NamedTemporaryFile with delete=True keeps an open handle that
        # prevents other processes/libraries from opening the file (causing Errno 13).
        # We explicitly close the file before transcription and clean it up in finally.
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            f.write(audio)
            f.flush()
            temp_path = f.name

        segments, _ = _model().transcribe(temp_path, beam_size=1, vad_filter=True)
        return " ".join(s.text.strip() for s in segments).strip()

    except TranscriptionError:
        raise
    except Exception as e:
        raise TranscriptionError(f"Transcription failed: {e}") from e
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass
