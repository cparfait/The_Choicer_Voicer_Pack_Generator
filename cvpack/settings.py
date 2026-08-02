"""Reglages persistants + localisation du dossier de donnees du jeu."""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

# Racine du projet (le dossier qui contient server.py)
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
PROJECTS_DIR = DATA_DIR / "projects"
SETTINGS_FILE = DATA_DIR / "settings.json"

PACK_FOLDERS = [
    "packs_voice",
    "packs_judges",
    "packs_player",
    "packs_host",
    "packs_studio",
    "packs_menu",
    "packs_chatter",
]


def default_game_dir() -> str:
    """Emplacement standard des packs selon l'OS.

    Confirme sur cette machine : %APPDATA%\\YeahMaybe\\ChoicerVoicer\\game
    """
    if sys.platform == "win32":
        base = os.environ.get("APPDATA")
        if base:
            return str(Path(base) / "YeahMaybe" / "ChoicerVoicer" / "game")
    elif sys.platform == "darwin":
        return str(Path.home() / "Library" / "Application Support" / "YeahMaybe" / "ChoicerVoicer" / "game")
    return str(Path.home() / ".local" / "share" / "YeahMaybe" / "ChoicerVoicer" / "game")


DEFAULTS = {
    "game_dir": default_game_dir(),
    "author": "",
    "ffmpeg": "",          # vide = cherche dans le PATH
    "ffprobe": "",
    "whisper_model": "small",
    "whisper_device": "auto",
    "clip_format": "ogg",  # ogg | wav | mp3
    "normalize": True,
    "target_lufs": -16.0,
}


def _load_raw() -> dict:
    if SETTINGS_FILE.exists():
        try:
            return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def load() -> dict:
    settings = dict(DEFAULTS)
    settings.update(_load_raw())
    return settings


def save(patch: dict) -> dict:
    settings = load()
    for key, value in patch.items():
        if key in DEFAULTS:
            settings[key] = value
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8")
    return settings


def get(key: str):
    return load().get(key, DEFAULTS.get(key))


def binary(name: str) -> str:
    """Chemin vers ffmpeg/ffprobe : reglage explicite, sinon PATH.

    Le reglage accepte aussi bien l'executable que le dossier qui le contient
    (c'est ce qu'on a naturellement envie de coller depuis l'explorateur).
    """
    configured = (get(name) or "").strip().strip('"')
    if configured:
        path = Path(configured)
        if path.is_dir():
            for candidate in (path / f"{name}.exe", path / name):
                if candidate.is_file():
                    return str(candidate)
        elif path.is_file():
            return str(path)
        else:
            with_exe = path.with_suffix(".exe")
            if with_exe.is_file():
                return str(with_exe)
        # Reglage inexploitable : on retombe sur le PATH plutot que d'echouer.
    found = shutil.which(name)
    return found or name


def game_dir() -> Path:
    return Path(get("game_dir"))


def game_dir_status() -> dict:
    path = game_dir()
    present = [f for f in PACK_FOLDERS if (path / f).is_dir()]
    return {
        "path": str(path),
        "exists": path.is_dir(),
        "pack_folders": present,
        # Le jeu ne cree pas packs_host tout seul dans toutes les versions ;
        # on considere l'emplacement valide des qu'un dossier packs_* existe.
        "looks_valid": bool(present),
    }


def ensure_pack_folders() -> list[str]:
    """Cree les dossiers packs_* manquants. Retourne ceux qui ont ete crees."""
    created = []
    root = game_dir()
    for folder in PACK_FOLDERS:
        target = root / folder
        if not target.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            created.append(folder)
    return created
