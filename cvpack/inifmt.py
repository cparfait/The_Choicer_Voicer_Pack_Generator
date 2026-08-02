"""Lecture/ecriture du format INI "a la Godot" utilise par les packs.

Format observe dans les packs reels :

    [data]

    caption="Attends, c'etait pas prevu."
    image="narrateur_surpris.png"
    dub_timestamps=[1.866]
    dub_characters=["Narrateur"]

Les valeurs sont des litteraux Godot : chaines entre guillemets droits,
tableaux entre crochets. Les guillemets internes sont echappes avec \\".
"""

from __future__ import annotations

import re

CRLF = "\r\n"


def quote(value: str) -> str:
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
    escaped = escaped.replace("\r\n", "\\n").replace("\n", "\\n").replace("\r", "\\n")
    return '"' + escaped + '"'


def _fmt_value(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int,)):
        return str(value)
    if isinstance(value, float):
        return f"{value:.3f}"
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_fmt_value(v) for v in value) + "]"
    return quote(value)


def dumps(sections: dict[str, dict]) -> str:
    """Serialise {section: {cle: valeur}} vers le format du jeu (CRLF)."""
    out: list[str] = []
    for section, values in sections.items():
        if not values:
            continue
        out.append(f"[{section}]")
        out.append("")
        for key, value in values.items():
            out.append(f"{key}={_fmt_value(value)}")
        out.append("")
    return CRLF.join(out).rstrip(CRLF) + CRLF


_KV_RE = re.compile(r"^(?P<key>[^\s=\[\]]+)\s*=\s*(?P<value>.*)$")
_SECTION_RE = re.compile(r"^\[(?P<name>[^\]]+)\]$")


def loads(text: str) -> dict[str, dict]:
    """Parse un fichier INI de pack. Tolerant : guillemets courbes, .txt, etc."""
    result: dict[str, dict] = {}
    section = "data"
    result[section] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith(";") or line.startswith("#"):
            continue
        match = _SECTION_RE.match(line)
        if match:
            section = match.group("name")
            result.setdefault(section, {})
            continue
        match = _KV_RE.match(line)
        if not match:
            continue
        result.setdefault(section, {})[match.group("key").strip()] = _parse_value(
            match.group("value").strip()
        )
    return {k: v for k, v in result.items() if v or k != "data"}


def _parse_value(value: str):
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        items = [_parse_value(item) for item in _split_list(inner)]
        return items
    if len(value) >= 2 and value[0] in '"\u201c' and value[-1] in '"\u201d':
        body = value[1:-1]
        return body.replace('\\"', '"').replace("\\n", "\n").replace("\\\\", "\\")
    low = value.lower()
    if low in ("true", "false"):
        return low == "true"
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def _split_list(inner: str) -> list[str]:
    items: list[str] = []
    current: list[str] = []
    in_string = False
    escape = False
    for ch in inner:
        if escape:
            current.append(ch)
            escape = False
            continue
        if ch == "\\":
            current.append(ch)
            escape = True
            continue
        if ch in '"\u201c\u201d':
            in_string = not in_string
            current.append(ch)
        elif ch == "," and not in_string:
            items.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
    if current:
        items.append("".join(current).strip())
    return [i for i in items if i]


# --------------------------------------------------------------------------
# Helpers specifiques aux fichiers du jeu
# --------------------------------------------------------------------------

def clip_metadata(caption: str = "", image: str = "",
                  dub_timestamps: list[float] | None = None,
                  dub_characters: list[str] | None = None,
                  dub_only: bool = False) -> str:
    data: dict = {}
    if caption:
        data["caption"] = caption
    if image:
        data["image"] = image
    if dub_timestamps:
        data["dub_timestamps"] = [round(float(t), 3) for t in sorted(dub_timestamps)]
    if dub_characters:
        data["dub_characters"] = list(dub_characters)
    if dub_only:
        data["dub_only"] = True
    return dumps({"data": data})


def pack_info(title: str = "", subtitle: str = "", icon: str = "",
              authors: list[str] | None = None, readme: str = "") -> str:
    data: dict = {}
    if title:
        data["title"] = title
    if subtitle:
        data["subtitle"] = subtitle
    if icon:
        data["icon"] = icon
    if authors:
        data["authors"] = [a for a in authors if a]
    if readme:
        data["readme"] = readme
    return dumps({"data": data})


def chatter_config(title: str = "", icon: str = "", authors: list[str] | None = None,
                   volume: float = 1.0,
                   exact: dict[str, list[str]] | None = None,
                   broad: dict[str, list[str]] | None = None) -> str:
    data: dict = {}
    if title:
        data["title"] = title
    if icon:
        data["icon"] = icon
    if authors:
        data["authors"] = [a for a in authors if a]
    if volume is not None and abs(float(volume) - 1.0) > 1e-6:
        data["volume"] = float(volume)
    sections = {"data": data}
    if exact:
        sections["exact_keywords"] = {k: v for k, v in exact.items() if v}
    if broad:
        sections["broad_keywords"] = {k: v for k, v in broad.items() if v}
    return dumps(sections)
