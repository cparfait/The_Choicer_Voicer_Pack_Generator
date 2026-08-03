"""Operations sur la liste de clips d'un projet voix."""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher

# En dessous, deux repliques ne se ressemblent pas assez pour n'en faire qu'une.
SIMILARITY = 0.92
# Une replique d'un seul mot revient trop souvent pour etre fusionnee sans
# risque : « oui » dit par deux personnes n'est pas le meme son.
MIN_WORDS = 2
# Ecart de duree tolere : le meme texte dit deux fois dure a peu pres pareil.
LENGTH_RATIO = 0.5


def _key(text: str) -> str:
    """Texte compare : sans accents, sans ponctuation, sans casse."""
    folded = unicodedata.normalize("NFKD", text or "")
    folded = "".join(c for c in folded if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9 ]+", " ", folded.lower()).strip()


def rename_character(clips: list[dict], before: str, after: str) -> int:
    """Renomme un personnage dans tous les clips. Retourne le nombre touche.

    La diarisation sort « Locuteur 1 », « Locuteur 2 » : sans ce renommage en
    bloc, mettre les vrais prenoms demanderait de reprendre chaque clip.
    """
    before, after = (before or "").strip(), (after or "").strip()
    if not before or before == after:
        return 0
    touched = 0
    for clip in clips:
        names = clip.get("characters") or []
        if before not in names:
            continue
        if after:
            clip["characters"] = [after if n == before else n for n in names]
        else:
            clip["characters"] = [n for n in names if n != before]
        touched += 1
    return touched


def merge_repeated(clips: list[dict], similarity: float = SIMILARITY) -> int:
    """Regroupe les repliques repetees en un clip a plusieurs timestamps.

    Le jeu accepte une liste dans `dub_timestamps` : une replique qui revient
    cinq fois dans la video n'a pas besoin de cinq clips identiques, un seul
    suffit s'il porte les cinq instants. Retourne le nombre de clips absorbes.
    """
    kept: list[dict] = []
    merged = 0
    for clip in clips:
        text = _key(clip.get("caption", ""))
        length = float(clip["end"]) - float(clip["start"])
        twin = None
        if len(text.split()) >= MIN_WORDS:
            for candidate in kept:
                if candidate.get("dub_only"):
                    continue
                other = float(candidate["end"]) - float(candidate["start"])
                if min(length, other) < max(length, other) * LENGTH_RATIO:
                    continue
                if SequenceMatcher(None, text, _key(candidate.get("caption", ""))) \
                        .ratio() >= similarity:
                    twin = candidate
                    break
        if twin is None:
            clip.setdefault("dub_timestamps", [])
            if not clip["dub_timestamps"]:
                clip["dub_timestamps"] = [round(float(clip["start"]), 3)]
            kept.append(clip)
            continue
        stamps = twin.setdefault("dub_timestamps", [])
        stamps.append(round(float(clip["start"]), 3))
        twin["dub_timestamps"] = sorted(set(stamps))
        merged += 1

    clips[:] = kept
    return merged
