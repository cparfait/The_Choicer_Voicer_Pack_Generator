"""Detection des locuteurs par pyannote.audio (optionnel).

En mode Dub, chaque clip peut porter le nom du personnage qui parle. Le faire
a la main sur cent clips est penible ; pyannote regroupe les passages par voix
et l'outil n'a plus qu'a proposer une correspondance « Locuteur 1 -> Nom ».

Le modele est sous conditions : il faut les accepter sur Hugging Face, sur les
deux pages pyannote/segmentation-3.0 et pyannote/speaker-diarization-3.1, puis
coller un jeton d'acces dans les Reglages. Sans jeton, la fonction reste
indisponible et le champ Personnage se remplit a la main, comme avant.
"""

from __future__ import annotations

from pathlib import Path

from . import settings

MODEL = "pyannote/speaker-diarization-3.1"

_pipeline = None
_pipeline_token: str | None = None


def _has_pyannote() -> bool:
    try:
        import pyannote.audio  # noqa: F401
        return True
    except Exception:  # noqa: BLE001 - dependance lourde, souvent a moitie installee
        return False


def status() -> dict:
    return {
        "available": _has_pyannote(),
        "token": bool((settings.get("hf_token") or "").strip()),
        "model": MODEL,
    }


def _load():
    global _pipeline, _pipeline_token
    if not _has_pyannote():
        raise RuntimeError(
            "pyannote.audio n'est pas installe. Lance : pip install pyannote.audio"
        )
    token = (settings.get("hf_token") or "").strip()
    if not token:
        raise RuntimeError(
            "Aucun jeton Hugging Face dans les Reglages : le modele de "
            "diarisation en demande un, apres acceptation de ses conditions."
        )
    if _pipeline is None or _pipeline_token != token:
        from pyannote.audio import Pipeline
        # pyannote 4 attend « token », la 3 attendait « use_auth_token » : on
        # essaie le nom recent d'abord et on retombe sur l'ancien.
        try:
            pipeline = Pipeline.from_pretrained(MODEL, token=token)
        except TypeError:
            pipeline = Pipeline.from_pretrained(MODEL, use_auth_token=token)
        if pipeline is None:
            raise RuntimeError(
                "Le modele n'a pas pu etre charge : les conditions doivent etre "
                "acceptees avec ce compte sur les deux pages, "
                f"pyannote/segmentation-3.0 et {MODEL}."
            )
        globals()["_pipeline"] = pipeline
        globals()["_pipeline_token"] = token
    return _pipeline


def speakers(audio: Path, count: int | None = None) -> list[dict]:
    """Passages parlants, avec l'etiquette de voix : [{start, end, label}]."""
    pipeline = _load()
    options = {"num_speakers": count} if count else {}
    result = pipeline(str(audio), **options)
    turns = [
        {"start": round(float(turn.start), 3), "end": round(float(turn.end), 3),
         "label": str(label)}
        for turn, _, label in result.itertracks(yield_label=True)
    ]
    return sorted(turns, key=lambda t: t["start"])


def label_for_range(turns: list[dict], start: float, end: float) -> str | None:
    """Voix qui occupe le plus l'intervalle d'un clip."""
    scores: dict[str, float] = {}
    for turn in turns:
        overlap = min(end, turn["end"]) - max(start, turn["start"])
        if overlap > 0:
            scores[turn["label"]] = scores.get(turn["label"], 0.0) + overlap
    if not scores:
        return None
    return max(scores.items(), key=lambda item: item[1])[0]


def friendly_names(turns: list[dict]) -> dict[str, str]:
    """Etiquettes brutes (SPEAKER_00...) -> noms lisibles, dans l'ordre d'entree."""
    names: dict[str, str] = {}
    for turn in turns:
        if turn["label"] not in names:
            names[turn["label"]] = f"Locuteur {len(names) + 1}"
    return names
