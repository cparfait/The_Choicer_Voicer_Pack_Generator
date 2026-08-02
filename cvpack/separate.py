"""Separation voix / musique par Demucs (optionnel).

Sert a fabriquer la piste d'ambiance d'un pack Dub : la bande son d'origine
sans les voix, pour que le joueur double par-dessus. Demucs tire PyTorch avec
lui, donc l'installation reste facultative — sans lui, l'emplacement
`_backing_track` se remplit a la main comme avant.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from . import media, settings

_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

MODEL = "htdemucs"


def available() -> bool:
    try:
        import demucs  # noqa: F401
        return True
    except Exception:  # noqa: BLE001 - une installation a moitie cassee ne doit
        return False   # pas empecher le reste de l'outil de demarrer


def status() -> dict:
    version = ""
    if available():
        try:
            from importlib.metadata import version as _version
            version = _version("demucs")
        except Exception:  # noqa: BLE001 - la version n'est qu'un confort
            version = ""
    return {"available": available(), "version": version, "model": MODEL}


_PERCENT = re.compile(r"(\d+)%")


def backing_track(source: Path, destination: Path, progress_cb=None) -> Path:
    """Ecrit `destination` : la source sans les voix.

    Demucs travaille dans un dossier temporaire, on ne garde que la piste
    « no_vocals » qu'on reencode au format du pack.
    """
    if not available():
        raise RuntimeError(
            "demucs n'est pas installe. Lance : pip install demucs"
        )
    source = Path(source)
    with tempfile.TemporaryDirectory(prefix="cvpack-demucs-") as tmp:
        out = Path(tmp)
        command = [sys.executable, "-m", "demucs", "--two-stems=vocals",
                   "-n", MODEL, "-o", str(out), str(source)]
        ffmpeg = Path(settings.binary("ffmpeg"))
        env = None
        if ffmpeg.parent.name:
            import os
            env = dict(os.environ)
            env["PATH"] = str(ffmpeg.parent) + os.pathsep + env.get("PATH", "")

        process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            creationflags=_NO_WINDOW, text=True, encoding="utf-8",
            errors="replace", env=env,
        )
        tail: list[str] = []
        assert process.stdout is not None
        for line in process.stdout:
            tail.append(line)
            del tail[:-15]
            match = _PERCENT.search(line)
            if match and progress_cb:
                progress_cb(min(0.98, int(match.group(1)) / 100.0))
        process.wait()
        if process.returncode != 0:
            raise RuntimeError("".join(tail)[-600:] or "demucs a echoue.")

        found = next(out.rglob("no_vocals.*"), None)
        if not found:
            raise RuntimeError("demucs n'a pas produit de piste sans voix.")
        media.convert_audio(found, destination, fmt=destination.suffix.lstrip("."),
                            normalize=False)
    if progress_cb:
        progress_cb(1.0)
    return destination


def install_hint() -> str:
    return "pip install demucs" if not shutil.which("demucs") else ""
