"""Stockage des projets sur disque."""

from __future__ import annotations

import json
import re
import shutil
import time
import uuid
from pathlib import Path

from . import settings
from .specs import SPECS

INVALID_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)),
            *(f"LPT{i}" for i in range(1, 10))}


def safe_name(name: str, fallback: str = "sans_nom") -> str:
    """Nom de fichier/dossier valide sous Windows, accents conserves."""
    cleaned = INVALID_CHARS.sub("_", (name or "").strip())
    cleaned = cleaned.strip(" .")
    if not cleaned:
        return fallback
    if cleaned.upper().split(".")[0] in RESERVED:
        cleaned = "_" + cleaned
    return cleaned[:120]


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


class Project:
    def __init__(self, data: dict, directory: Path):
        self.data = data
        self.dir = directory

    # -- chemins -----------------------------------------------------------
    @property
    def id(self) -> str:
        return self.data["id"]

    @property
    def type(self) -> str:
        return self.data["type"]

    @property
    def source_dir(self) -> Path:
        return self.dir / "source"

    @property
    def assets_dir(self) -> Path:
        return self.dir / "assets"

    @property
    def clip_images_dir(self) -> Path:
        return self.dir / "clip_images"

    @property
    def frames_dir(self) -> Path:
        return self.dir / "frames"

    @property
    def build_dir(self) -> Path:
        return self.dir / "build"

    @property
    def master_audio(self) -> Path:
        return self.source_dir / "master.wav"

    @property
    def preview_audio(self) -> Path:
        return self.source_dir / "preview.ogg"

    @property
    def peaks_file(self) -> Path:
        return self.source_dir / "peaks.json"

    def source_path(self) -> Path | None:
        """Fichier source : copie locale si importee, sinon chemin externe."""
        source = self.data.get("source", {})
        stored = source.get("stored")
        if stored:
            path = self.source_dir / stored
            if path.exists():
                return path
        external = source.get("external")
        if external:
            path = Path(external)
            if path.exists():
                return path
        return None

    # -- persistance -------------------------------------------------------
    def save(self) -> "Project":
        self.data["updated"] = _now()
        self.dir.mkdir(parents=True, exist_ok=True)
        (self.dir / "project.json").write_text(
            json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return self

    def patch(self, patch: dict) -> "Project":
        for key, value in patch.items():
            if key in ("id", "type", "created"):
                continue
            self.data[key] = value
        return self.save()

    # -- clips -------------------------------------------------------------
    def clip(self, clip_id: str) -> dict | None:
        return next((c for c in self.data.get("clips", []) if c["id"] == clip_id), None)

    def clip_image(self, clip_id: str) -> Path | None:
        stored = (self.clip(clip_id) or {}).get("image")
        if not stored:
            return None
        path = self.clip_images_dir / stored
        return path if path.exists() else None

    def asset(self, slot: str) -> Path | None:
        stored = self.data.get("assets", {}).get(slot)
        if not stored:
            return None
        path = self.assets_dir / stored
        return path if path.exists() else None

    def summary(self) -> dict:
        spec = SPECS.get(self.type, {})
        clips = self.data.get("clips", [])
        return {
            "id": self.id,
            "type": self.type,
            "type_label": spec.get("label", self.type),
            "name": self.data.get("name", ""),
            "created": self.data.get("created", ""),
            "updated": self.data.get("updated", ""),
            "clip_count": len([c for c in clips if c.get("enabled", True)]),
            "is_dub": bool(self.data.get("dub", {}).get("enabled")),
            "has_source": self.source_path() is not None,
        }


# --------------------------------------------------------------------------
# Depot
# --------------------------------------------------------------------------

def _root() -> Path:
    settings.PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    return settings.PROJECTS_DIR


def new_project(name: str, type_: str) -> Project:
    if type_ not in SPECS:
        raise ValueError(f"Type de pack inconnu : {type_}")
    project_id = uuid.uuid4().hex[:12]
    directory = _root() / project_id
    directory.mkdir(parents=True, exist_ok=True)
    data = {
        "id": project_id,
        "type": type_,
        "name": name or "Nouveau pack",
        "created": _now(),
        "updated": _now(),
        "meta": {
            "title": name or "",
            "subtitle": "",
            "readme": "",
            "authors": [a for a in [settings.get("author")] if a],
        },
        "config": {f["key"]: f["default"] for f in SPECS[type_].get("fields", [])},
        "assets": {},
        "clips": [],
        "chatter": [],
        "source": {},
        "dub": {"enabled": False, "characters": []},
        "build": {},
    }
    if type_ == "host":
        from .specs import HOST_TEMPLATE_FR
        data["host_dialog"] = json.loads(json.dumps(HOST_TEMPLATE_FR))
    if type_ == "player":
        data["config"].setdefault("name", name or "Candidat")
    return Project(data, directory).save()


def load(project_id: str) -> Project | None:
    directory = _root() / project_id
    file = directory / "project.json"
    if not file.exists():
        return None
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return Project(data, directory)


def list_projects() -> list[dict]:
    projects = []
    for directory in _root().iterdir():
        if not directory.is_dir():
            continue
        project = load(directory.name)
        if project:
            projects.append(project.summary())
    projects.sort(key=lambda p: p["updated"], reverse=True)
    return projects


def delete(project_id: str) -> bool:
    directory = _root() / project_id
    if not directory.is_dir():
        return False
    shutil.rmtree(directory, ignore_errors=True)
    return True


def duplicate(project_id: str, new_name: str) -> Project | None:
    source = load(project_id)
    if not source:
        return None
    clone_id = uuid.uuid4().hex[:12]
    target = _root() / clone_id
    shutil.copytree(source.dir, target)
    project = load(clone_id)
    if not project:
        return None
    project.data["id"] = clone_id
    project.data["name"] = new_name or (source.data.get("name", "") + " (copie)")
    project.data["created"] = _now()
    return project.save()
