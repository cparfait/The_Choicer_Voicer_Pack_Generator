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

# pyannote 4 recommande « community-1 », nettement meilleur au comptage des
# voix ; « 3.1 » reste le repli, et c'est celui que la plupart des comptes ont
# deja autorise. Chaque modele demande d'accepter ses conditions a part, donc
# on essaie dans l'ordre et on garde le premier qui se charge.
MODELS = [
    "pyannote/speaker-diarization-community-1",
    "pyannote/speaker-diarization-3.1",
]
MODEL = MODELS[-1]

_pipeline = None
_pipeline_token: str | None = None
_pipeline_model: str = ""


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


def _open(model: str, token: str):
    """Charge un modele. pyannote 4 attend « token », la 3 « use_auth_token »."""
    from pyannote.audio import Pipeline
    try:
        return Pipeline.from_pretrained(model, token=token)
    except TypeError:
        return Pipeline.from_pretrained(model, use_auth_token=token)


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
        pipeline, model, refus = None, "", []
        for candidate in MODELS:
            try:
                pipeline = _open(candidate, token)
            except Exception as exc:  # noqa: BLE001 - modele refuse, absent, hors ligne
                refus.append(f"{candidate} ({str(exc).splitlines()[0][:120]})")
                continue
            if pipeline is not None:
                model = candidate
                break
            refus.append(f"{candidate} (conditions non acceptees avec ce compte)")
        if pipeline is None:
            raise RuntimeError(
                "Aucun modele de diarisation n'a pu etre charge. Accepte leurs "
                "conditions sur huggingface.co avec le compte du jeton, puis "
                "reessaie. Detail : " + " ; ".join(refus)
            )
        globals()["_pipeline"] = pipeline
        globals()["_pipeline_token"] = token
        globals()["_pipeline_model"] = model
    return _pipeline


def _annotation(result):
    """La sortie de pyannote 4 porte plusieurs pistes ; la 3 en renvoyait une.

    On prefere la version « exclusive », sans chevauchement : pour attribuer un
    personnage a un clip, deux voix superposees ne rendent pas service.
    """
    for name in ("exclusive_speaker_diarization", "speaker_diarization"):
        track = getattr(result, name, None)
        if track is not None and hasattr(track, "itertracks"):
            return track
    return result


def speakers(audio: Path, count: int | None = None) -> list[dict]:
    """Passages parlants, avec l'etiquette de voix : [{start, end, label}]."""
    pipeline = _load()
    options = {"num_speakers": count} if count else {}
    result = _annotation(pipeline(str(audio), **options))
    turns = [
        {"start": round(float(turn.start), 3), "end": round(float(turn.end), 3),
         "label": str(label)}
        for turn, _, label in result.itertracks(yield_label=True)
    ]
    return sorted(turns, key=lambda t: t["start"])


def loaded_model() -> str:
    """Modele reellement charge — celui des MODELS que le compte a autorise."""
    return _pipeline_model


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
