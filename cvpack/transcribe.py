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


def transcribe_ranges(source: Path, ranges: list[dict], language: str = "fr",
                      progress_cb=None, cancelled=None) -> dict[str, str]:
    """Transcrit plusieurs intervalles : {identifiant du clip -> texte}.

    Quand la bibliotheque manque — la version .exe ne l'embarque pas — le
    travail part chez un Python exterieur. La decoupe reste ici, puisque c'est
    nous qui avons ffmpeg, et le modele n'est charge qu'une fois de l'autre cote.
    """
    if available():
        textes: dict[str, str] = {}
        total = max(1, len(ranges))
        for index, item in enumerate(ranges, start=1):
            if cancelled and cancelled():
                break
            texte = transcribe_range(source, float(item["start"]), float(item["end"]),
                                     language=language)
            textes[item["id"]] = texte
            if progress_cb:
                progress_cb(index / total, f"{index}/{total} — {texte[:60]}")
        return textes

    from . import helper

    with tempfile.TemporaryDirectory(prefix="cvpack-whisper-") as tmp:
        fichiers = []
        for index, item in enumerate(ranges, start=1):
            clip = Path(tmp) / f"{index:04d}.wav"
            media.export_clip(source, clip, float(item["start"]), float(item["end"]),
                              fmt="wav", normalize=False, fade_ms=0)
            fichiers.append({"id": item["id"], "path": str(clip)})
            if progress_cb:
                progress_cb(0.05 * index / max(1, len(ranges)), "Preparation des extraits")
        suivi = (lambda f, m: progress_cb(0.05 + 0.95 * f, m)) if progress_cb else None
        resultat = helper.run("whisper", {
            "files": fichiers,
            "language": language,
            "model": settings.get("whisper_model") or "small",
            "device": settings.get("whisper_device") or "auto",
            "compute_type": "default",
        }, progress_cb=suivi)
    return resultat.get("captions") or {}


def status() -> dict:
    device, compute = _pick_device() if available() else ("", "")
    return {
        "available": available(),
        "model": settings.get("whisper_model"),
        "device": device,
        "compute_type": compute,
        "loaded": _model is not None,
    }
