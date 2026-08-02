"""Transcription francaise des clips via faster-whisper (optionnel)."""

from __future__ import annotations

import tempfile
from pathlib import Path

from . import media, settings

_model = None
_model_key: tuple | None = None


def available() -> bool:
    try:
        import faster_whisper  # noqa: F401
        return True
    except ImportError:
        return False


def _pick_device() -> tuple[str, str]:
    choice = (settings.get("whisper_device") or "auto").lower()
    if choice == "cuda":
        return "cuda", "float16"
    if choice == "cpu":
        return "cpu", "int8"
    try:
        import ctranslate2
        if ctranslate2.get_cuda_device_count() > 0:
            return "cuda", "float16"
    except Exception:  # pragma: no cover - depend du materiel
        pass
    return "cpu", "int8"


def get_model():
    global _model, _model_key
    if not available():
        raise RuntimeError(
            "faster-whisper n'est pas installe. Lance : pip install faster-whisper"
        )
    from faster_whisper import WhisperModel

    name = settings.get("whisper_model") or "small"
    device, compute = _pick_device()
    key = (name, device, compute)
    if _model is None or _model_key != key:
        _model = WhisperModel(name, device=device, compute_type=compute)
        _model_key = key
    return _model


def transcribe_file(path: Path, language: str = "fr") -> str:
    model = get_model()
    segments, _info = model.transcribe(
        str(path), language=language, vad_filter=True,
        beam_size=5, condition_on_previous_text=False,
    )
    return " ".join(segment.text.strip() for segment in segments).strip()


def transcribe_range(source: Path, start: float, end: float, language: str = "fr") -> str:
    """Transcrit un intervalle de la source en passant par un WAV temporaire."""
    with tempfile.TemporaryDirectory() as tmp:
        clip = Path(tmp) / "clip.wav"
        media.export_clip(source, clip, start, end, fmt="wav",
                          normalize=False, fade_ms=0)
        return transcribe_file(clip, language=language)


def status() -> dict:
    device, compute = _pick_device() if available() else ("", "")
    return {
        "available": available(),
        "model": settings.get("whisper_model"),
        "device": device,
        "compute_type": compute,
        "loaded": _model is not None,
    }
