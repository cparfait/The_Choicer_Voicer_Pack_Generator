"""Delegation des fonctions IA a un Python exterieur.

Les bibliotheques d'IA pesent plus de 1,5 Go : la version .exe ne les embarque
pas. Plutot que de priver l'utilisateur de ces fonctions, on lui demande un
interpreteur qui les possede, et on lui confie le travail dans un
sous-processus (voir `worker/cv_worker.py`).

Deux benefices en plus du poids : le serveur demarre sans charger PyTorch, et
une bibliotheque cassee ne fait plus tomber l'outil entier.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from . import settings

_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

# Une detection reussie est gardee : chercher un interpreteur coute quelques
# lancements de processus, et la reponse ne change pas en cours de session.
_cache: dict[str, dict] = {}


def script() -> Path:
    """Chemin de l'ouvrier, embarque dans le paquet ou pose a cote du code."""
    for base in (settings.BUNDLE, settings.ROOT):
        candidate = base / "worker" / "cv_worker.py"
        if candidate.is_file():
            return candidate
    return settings.ROOT / "worker" / "cv_worker.py"


def _candidates() -> list[str]:
    """Interpreteurs a essayer, du plus explicite au plus devine."""
    found: list[str] = []
    configured = (settings.get("python_ai") or "").strip().strip('"')
    if configured:
        path = Path(configured)
        if path.is_dir():  # un dossier : on cherche l'executable dedans
            for name in ("python.exe", "Scripts/python.exe", "bin/python"):
                if (path / name).is_file():
                    found.append(str(path / name))
                    break
        else:
            found.append(str(path))

    # Environnement pose a cote de l'outil par le bouton d'installation.
    for relative in ("extras/Scripts/python.exe", "extras/bin/python"):
        local = settings.ROOT / relative
        if local.is_file():
            found.append(str(local))

    if not settings.FROZEN:
        found.append(sys.executable)  # version Python : on est deja dedans
    for name in ("python", "python3"):
        which = shutil.which(name)
        if which:
            found.append(which)
    return [f for i, f in enumerate(found) if f and f not in found[:i]]


def interpreter() -> str | None:
    """Premier interpreteur exterieur qui repond, ou None."""
    if "interpreter" in _cache:
        return _cache["interpreter"].get("path")
    for candidate in _candidates():
        if Path(candidate).resolve() == Path(sys.executable).resolve() and settings.FROZEN:
            continue  # l'executable lui-meme ne sait pas jouer l'ouvrier
        state = _probe(candidate)
        if state:
            _cache["interpreter"] = {"path": candidate, "status": state}
            return candidate
    _cache["interpreter"] = {}
    return None


def _probe(python: str) -> dict | None:
    try:
        proc = subprocess.run([python, str(script()), "status"],
                              capture_output=True, text=True, timeout=120,
                              creationflags=_NO_WINDOW, encoding="utf-8",
                              errors="replace")
    except (OSError, subprocess.SubprocessError):
        return None
    for line in reversed((proc.stdout or "").splitlines()):
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "result" in payload:
            return payload["result"]
    return None


def status() -> dict:
    """Ce que l'aide exterieure permet, pour l'affichage des Reglages."""
    python = interpreter()
    state = _cache.get("interpreter", {}).get("status") or {}
    return {
        "python": python or "",
        "configured": bool((settings.get("python_ai") or "").strip()),
        "whisper": bool(state.get("whisper")),
        "demucs": bool(state.get("demucs")),
        "diarize": bool(state.get("diarize")),
        "cutout": bool(state.get("cutout")),
        "face": bool(state.get("face")),
        "versions": state.get("versions") or {},
    }


def forget() -> None:
    """Oublie la detection : a appeler quand le reglage change."""
    _cache.clear()


class HelperError(RuntimeError):
    pass


def run(task: str, payload: dict | None = None, progress_cb=None,
        timeout: int = 3600) -> dict:
    """Execute une tache chez l'interpreteur exterieur et retourne son resultat."""
    python = interpreter()
    if not python:
        raise HelperError(
            "Aucun Python capable des fonctions IA n'a ete trouve. Indique-en "
            "un dans les Reglages, ou utilise la version Python de l'outil."
        )
    command = [python, str(script()), task, json.dumps(payload or {}, ensure_ascii=False)]
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, encoding="utf-8", errors="replace",
                               creationflags=_NO_WINDOW, env=env)
    resultat: dict | None = None
    erreur: str | None = None
    assert process.stdout is not None
    for line in process.stdout:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue  # la bibliotheque bavarde : ce n'est pas pour nous
        if "progress" in message and progress_cb:
            progress_cb(float(message["progress"]), message.get("message", ""))
        if "result" in message:
            resultat = message["result"]
        if "error" in message:
            erreur = message["error"]
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        raise HelperError("La tache a depasse le temps imparti.") from None

    if erreur:
        raise HelperError(erreur)
    if resultat is None:
        details = (process.stderr.read() if process.stderr else "")[-400:]
        raise HelperError(f"L'aide exterieure n'a rien renvoye. {details}".strip())
    return resultat
