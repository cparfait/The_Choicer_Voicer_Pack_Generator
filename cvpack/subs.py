"""Lecture des fichiers de sous-titres (SRT, WebVTT, JSON3 de YouTube).

Un « cue » est un dict {start, end, text} en secondes.

Les sous-titres automatiques defilent : une replique reste affichee pendant
que les suivantes s'ecrivent sous elle. Les durees annoncees se recouvrent
donc largement, et la meme ligne est reecrite a chaque nouvelle. Sans
nettoyage, les clips decoupes dessus se recouvrent a leur tour et chacun
recupere le texte du voisin.
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path

from . import media

_TIME_RE = re.compile(
    r"(?:(\d+):)?(\d{1,2}):(\d{2})[.,](\d{1,3})\s*-->\s*(?:(\d+):)?(\d{1,2}):(\d{2})[.,](\d{1,3})"
)
_TAG_RE = re.compile(r"<[^>]+>")

_MIN_CUE = 0.15    # duree plancher d'une replique une fois recadree
_WORD_TAIL = 0.8   # marge laissee apres le dernier mot chronometre
_SHORT_GAP = 1.0   # ecart tolere pour rattacher une replique trop courte


def _seconds(hours, minutes, seconds, millis) -> float:
    return (int(hours or 0) * 3600 + int(minutes) * 60 + int(seconds)
            + int(str(millis).ljust(3, "0")) / 1000.0)


def parse_vtt(text: str) -> list[dict]:
    """WebVTT et SRT partagent la meme structure de blocs."""
    cues: list[dict] = []
    block: list[str] = []

    def flush():
        if not block:
            return
        timing = next((line for line in block if "-->" in line), None)
        if not timing:
            block.clear()
            return
        match = _TIME_RE.search(timing)
        if not match:
            block.clear()
            return
        start = _seconds(*match.groups()[0:4])
        end = _seconds(*match.groups()[4:8])
        lines = block[block.index(timing) + 1:]
        content = " ".join(_TAG_RE.sub("", line).strip() for line in lines)
        content = html.unescape(content).strip()
        if content:
            cues.append({"start": start, "end": end, "text": content})
        block.clear()

    for raw in text.splitlines():
        line = raw.strip("﻿").rstrip()
        if not line.strip():
            flush()
        else:
            block.append(line)
    flush()
    return _clean(cues)


def parse_json3(text: str) -> list[dict]:
    """Format json3 de YouTube (celui des sous-titres automatiques)."""
    data = json.loads(text)
    cues: list[dict] = []
    for event in data.get("events", []):
        segments = event.get("segs") or []
        content = "".join(seg.get("utf8", "") for seg in segments)
        content = " ".join(content.split())
        if not content:
            # Marqueur de defilement : un evenement « aAppend » qui ne
            # contient qu'un saut de ligne.
            continue
        start = float(event.get("tStartMs", 0)) / 1000.0
        end = start + max(0.1, float(event.get("dDurationMs", 0)) / 1000.0)
        offsets = [float(seg["tOffsetMs"]) for seg in segments
                   if seg.get("tOffsetMs") is not None and (seg.get("utf8") or "").strip()]
        if offsets:
            # Sous-titres automatiques : chaque mot est date, la fin reelle
            # de la parole est donc connue — la duree annoncee, elle, court
            # jusqu'a ce que la ligne sorte de l'ecran.
            spoken = start + max(offsets) / 1000.0 + _WORD_TAIL
            end = min(end, max(spoken, start + _MIN_CUE))
        cues.append({"start": start, "end": end, "text": content})
    return _clean(cues)


def parse_file(path: Path) -> list[dict]:
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    if path.suffix.lower() in (".json3", ".json") or text.lstrip().startswith("{"):
        try:
            return parse_json3(text)
        except (json.JSONDecodeError, KeyError):
            pass
    return parse_vtt(text)


def _without_repeat(previous: list[str], words: list[str]) -> list[str]:
    """Retire de `words` la fin de `previous` qu'elle reprend telle quelle."""
    limit = min(len(previous), len(words))
    for size in range(limit, 1, -1):
        if previous[-size:] == words[:size]:
            return words[size:]
    if len(words) <= len(previous) and previous[-len(words):] == words:
        return []
    return words


def _clean(cues: list[dict]) -> list[dict]:
    """Deduplique le defilement, puis empeche les repliques de se recouvrir."""
    cleaned: list[dict] = []
    for cue in sorted(cues, key=lambda c: (c["start"], c["end"])):
        words = cue["text"].split()
        if not words:
            continue
        start, end = float(cue["start"]), float(cue["end"])
        if cleaned:
            previous = cleaned[-1]
            if words == previous["words"]:
                previous["end"] = max(previous["end"], end)
                continue
            # Le defilement se reconnait a ceci : la replique suivante
            # commence avant que la precedente ne soit finie — ou juste au
            # moment ou elle s'arrete — et elle en reprend la fin mot pour
            # mot. Deux repliques separees par un silence ne sont jamais
            # rabotees, meme si elles se repetent.
            if start <= previous["end"] + 0.05:
                words = _without_repeat(previous["words"], words)
                if not words:
                    previous["end"] = max(previous["end"], end)
                    continue
                previous["end"] = max(previous["start"] + _MIN_CUE,
                                      min(previous["end"], start))
        cleaned.append({"start": start, "end": end, "words": words})

    return [{"start": round(cue["start"], 3),
             "end": round(max(cue["end"], cue["start"] + _MIN_CUE), 3),
             "text": " ".join(cue["words"])}
            for cue in cleaned]


# --------------------------------------------------------------------------
# Exploitation
# --------------------------------------------------------------------------

def _split_long(start: float, end: float, text: str, max_len: float,
                pauses: list[tuple[float, float]] | None = None) -> list[dict]:
    """Coupe une replique trop longue, dans ses silences quand on les connait.

    Le texte suit le decoupage au prorata du temps : on ne sait pas quel mot
    est prononce quand, mais une replique lue a peu pres regulierement tombe
    juste a quelques mots pres.
    """
    length = end - start
    if max_len <= 0 or length <= max_len:
        return [{"start": start, "end": end, "text": text}]

    edges = [start] + media.split_points(start, end, max_len, pauses) + [end]
    words = text.split()
    parts = []
    for left, right in zip(edges, edges[1:]):
        first = round(len(words) * (left - start) / length)
        last = round(len(words) * (right - start) / length)
        parts.append({"start": left, "end": right,
                      "text": " ".join(words[first:last])})
    return parts


def segments_from_cues(cues: list[dict], min_len: float = 0.7, max_len: float = 6.0,
                       merge_gap: float = 0.35, pad: float = 0.05,
                       duration: float | None = None,
                       pauses: list[tuple[float, float]] | None = None) -> list[dict]:
    """Un clip par replique, en fusionnant les cues trop courtes ou collees."""
    groups: list[dict] = []
    for cue in cues:
        if groups:
            last = groups[-1]
            gap = cue["start"] - last["end"]
            merged_length = cue["end"] - last["start"]
            too_short = (last["end"] - last["start"]) < min_len
            # Une phrase finie est une replique : on ne lui colle pas la
            # suivante. Une replique trop courte, elle, se rattache a la
            # precedente — mais pas par-dessus un silence, ce serait
            # rapprocher deux repliques sans rapport.
            finished = last["text"][-1:] in ".?!…"
            close_enough = ((gap <= merge_gap and not finished)
                            or (too_short and gap <= _SHORT_GAP))
            if merged_length <= max_len and close_enough:
                last["end"] = max(last["end"], cue["end"])
                last["text"] = (last["text"] + " " + cue["text"]).strip()
                continue
        groups.append(dict(cue))

    segments: list[dict] = []
    for group in groups:
        start = max(0.0, group["start"] - pad)
        end = group["end"] + pad
        if duration:
            end = min(end, duration)
        if end - start < 0.25:
            continue
        segments.extend(_split_long(start, end, group["text"], max_len, pauses))

    # La marge ajoutee de chaque cote peut faire mordre un clip sur le
    # suivant : le meme son se retrouverait dans deux fichiers.
    for current, following in zip(segments, segments[1:]):
        if current["end"] > following["start"]:
            current["end"] = max(current["start"] + 0.25, following["start"])

    return [{"start": round(s["start"], 3), "end": round(s["end"], 3),
             "text": s["text"]} for s in segments]


def _stamp(seconds: float) -> str:
    millis = int(round(max(0.0, seconds) * 1000))
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    secondes, millis = divmod(millis, 1000)
    return f"{hours:02d}:{minutes:02d}:{secondes:02d},{millis:03d}"


def to_srt(cues: list[dict]) -> str:
    """Repliques {start, end, text} vers un fichier SRT."""
    blocks = []
    for cue in sorted(cues, key=lambda c: float(c["start"])):
        text = " ".join((cue.get("text") or "").split())
        if not text:
            continue
        blocks.append(f"{len(blocks) + 1}\n"
                      f"{_stamp(float(cue['start']))} --> {_stamp(float(cue['end']))}\n"
                      f"{text}\n")
    return "\n".join(blocks)


def text_for_range(cues: list[dict], start: float, end: float) -> str:
    """Texte des cues qui recouvrent l'intervalle demande."""
    parts = []
    for cue in cues:
        overlap = min(end, cue["end"]) - max(start, cue["start"])
        if overlap > 0 and overlap > 0.35 * min(cue["end"] - cue["start"], end - start):
            parts.append(cue["text"])
    return " ".join(parts).strip()
