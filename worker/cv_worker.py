"""Ouvrier des fonctions IA, execute par un Python exterieur a l'outil.

L'executable ne peut pas embarquer PyTorch : plus de 1,5 Go, et PyInstaller s'y
casse les dents. Il delegue donc a un interpreteur qui possede ces
bibliotheques, en lui passant ce fichier — volontairement autonome : il
n'importe rien de `cvpack`, seulement la bibliotheque de la tache demandee.

    python cv_worker.py status
    python cv_worker.py whisper '{"source": "...", "ranges": [...]}'

Le dialogue passe par la sortie standard, une ligne JSON a la fois :

    {"progress": 0.4, "message": "3/8"}
    {"result": ...}          en cas de succes
    {"error": "..."}         sinon

Ainsi l'appelant suit l'avancement sans attendre la fin, et rien n'est perdu si
la bibliotheque affiche ses propres messages sur la sortie d'erreur.
"""

from __future__ import annotations

import json
import sys


def emit(**payload) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _importable(module: str) -> bool:
    try:
        __import__(module)
        return True
    except Exception:  # noqa: BLE001 - une dependance cassee vaut une absente
        return False


# --------------------------------------------------------------------------
# Taches
# --------------------------------------------------------------------------

def task_status(_payload: dict) -> dict:
    """Ce que cet interpreteur sait faire."""
    versions = {}
    for nom, module in (("torch", "torch"), ("demucs", "demucs"),
                        ("faster_whisper", "faster_whisper"),
                        ("pyannote", "pyannote.audio"), ("rembg", "rembg"),
                        ("cv2", "cv2")):
        try:
            from importlib.metadata import version
            versions[nom] = version(module.split(".")[0]) if _importable(module) else ""
        except Exception:  # noqa: BLE001
            versions[nom] = "?" if _importable(module) else ""
    return {
        "python": sys.version.split()[0],
        "executable": sys.executable,
        "whisper": _importable("faster_whisper"),
        "demucs": _importable("demucs"),
        "diarize": _importable("pyannote.audio"),
        "cutout": _importable("rembg"),
        "face": _importable("cv2"),
        "versions": versions,
    }


def task_whisper(payload: dict) -> dict:
    """Transcrit une liste de fichiers, modele charge une seule fois.

    La decoupe est faite par l'appelant, qui a ffmpeg : l'ouvrier ne recoit que
    des extraits deja prets, et le modele n'est pas recharge a chaque clip.
    """
    from faster_whisper import WhisperModel

    fichiers = payload.get("files") or []
    langue = payload.get("language") or "fr"
    emit(progress=0.02, message="Chargement du modele")
    model = WhisperModel(payload.get("model") or "small",
                         device=payload.get("device") or "auto",
                         compute_type=payload.get("compute_type") or "default")

    textes = {}
    total = max(1, len(fichiers))
    for index, item in enumerate(fichiers, start=1):
        segments, _info = model.transcribe(
            item["path"], language=langue, vad_filter=True, beam_size=5,
            condition_on_previous_text=False,
        )
        texte = " ".join(s.text.strip() for s in segments).strip()
        textes[item["id"]] = texte
        emit(progress=index / total, message=f"{index}/{total} — {texte[:50]}")
    return {"captions": textes}


def task_diarize(payload: dict) -> dict:
    """Regroupe les passages parlants par voix."""
    from pyannote.audio import Pipeline

    token = payload.get("token") or ""
    refus = []
    pipeline = None
    for modele in payload.get("models") or []:
        try:
            try:
                pipeline = Pipeline.from_pretrained(modele, token=token)
            except TypeError:
                pipeline = Pipeline.from_pretrained(modele, use_auth_token=token)
        except Exception as exc:  # noqa: BLE001
            refus.append(f"{modele} ({str(exc).splitlines()[0][:100]})")
            continue
        if pipeline is not None:
            emit(progress=0.3, message="Modele charge")
            break
        refus.append(f"{modele} (conditions non acceptees avec ce compte)")
    if pipeline is None:
        raise RuntimeError("Aucun modele chargeable. " + " ; ".join(refus))

    options = {"num_speakers": payload["speakers"]} if payload.get("speakers") else {}
    sortie = pipeline(payload["source"], **options)
    for nom in ("exclusive_speaker_diarization", "speaker_diarization"):
        piste = getattr(sortie, nom, None)
        if piste is not None and hasattr(piste, "itertracks"):
            sortie = piste
            break
    turns = [{"start": round(float(t.start), 3), "end": round(float(t.end), 3),
              "label": str(label)}
             for t, _, label in sortie.itertracks(yield_label=True)]
    return {"turns": sorted(turns, key=lambda t: t["start"])}


def task_cutout(payload: dict) -> dict:
    """Enleve le fond d'une image. Le recadrage reste a l'appelant (ffmpeg)."""
    from pathlib import Path

    from rembg import remove, new_session

    session = None
    modele = (payload.get("model") or "").strip()
    if modele:
        session = new_session(modele)
    donnees = Path(payload["source"]).read_bytes()
    resultat = remove(donnees, session=session) if session else remove(donnees)
    Path(payload["destination"]).write_bytes(resultat)
    return {"destination": payload["destination"]}


def task_faces(payload: dict) -> dict:
    """Visages detectes dans une serie d'images.

    Une seule invocation pour toutes les images : demarrer Python et charger
    OpenCV coute plus cher que la detection elle-meme.
    """
    import cv2

    cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    resultats = []
    sources = payload.get("sources") or []
    for index, chemin in enumerate(sources, start=1):
        image = cv2.imread(chemin)
        if image is None:
            resultats.append({"source": chemin, "faces": []})
            continue
        grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        faces = cascade.detectMultiScale(grey, scaleFactor=1.15, minNeighbors=5,
                                        minSize=(40, 40))
        resultats.append({
            "source": chemin,
            "width": int(image.shape[1]), "height": int(image.shape[0]),
            "faces": [{"x": int(x), "y": int(y), "w": int(w), "h": int(h)}
                      for (x, y, w, h) in faces],
        })
        emit(progress=index / max(1, len(sources)), message=f"{index}/{len(sources)}")
    return {"images": resultats}


TASKS = {
    "status": task_status,
    "whisper": task_whisper,
    "diarize": task_diarize,
    "cutout": task_cutout,
    "faces": task_faces,
}


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] not in TASKS:
        emit(error=f"Tache attendue parmi : {', '.join(sorted(TASKS))}")
        return 2
    payload = {}
    if len(sys.argv) > 2:
        try:
            payload = json.loads(sys.argv[2])
        except json.JSONDecodeError as exc:
            emit(error=f"Parametres illisibles : {exc}")
            return 2
    try:
        emit(result=TASKS[sys.argv[1]](payload))
    except Exception as exc:  # noqa: BLE001 - tout remonte a l'appelant
        emit(error=f"{type(exc).__name__} : {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
