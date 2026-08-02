"""Preparation des images de personnages (optionnel).

Le jeu pose les juges et le candidat sur le sol du plateau, sans les
redimensionner et sans rien detourer : une photo rectangulaire s'affiche en
entier, fond compris, et le personnage se retrouve trop bas. Ce module fait
les deux gestes qui manquent :

  - `cutout()` enleve le fond (rembg) et rogne au ras du personnage ;
  - `frame_with_face()` va chercher, dans une video, une image ou un visage
    est visible (OpenCV).

Les deux dependances sont facultatives : sans elles, l'outil se contente de
signaler le probleme dans « Verifier ».
"""

from __future__ import annotations

from pathlib import Path

from . import media
from .specs import STAGE_HEIGHT


def _has(module: str) -> bool:
    try:
        __import__(module)
        return True
    except Exception:  # noqa: BLE001 - une dependance cassee vaut une absente
        return False


def status() -> dict:
    return {"cutout": _has("rembg"), "face": _has("cv2")}


# --------------------------------------------------------------------------
# Detourage
# --------------------------------------------------------------------------

def cutout(source: Path, destination: Path, height: int = STAGE_HEIGHT) -> None:
    """Enleve le fond, rogne les marges vides, met a la hauteur du plateau."""
    if not _has("rembg"):
        raise RuntimeError(
            "rembg n'est pas installe. Lance : pip install rembg onnxruntime"
        )
    from rembg import remove  # import tardif : le modele se charge a la demande

    destination.parent.mkdir(parents=True, exist_ok=True)
    cut = destination.with_suffix(".cut.png")
    cut.write_bytes(remove(Path(source).read_bytes()))
    try:
        alpha = media.alpha_info(cut)
        media.fit_stage_image(cut, destination, height, alpha["bounds"])
    finally:
        cut.unlink(missing_ok=True)


# --------------------------------------------------------------------------
# Image tiree d'une video
# --------------------------------------------------------------------------

def _portrait_box(width: int, height: int, face=None) -> tuple[int, int, int, int]:
    """Cadre 1:2 (les proportions d'un personnage) dans une image de film.

    Centre sur le visage quand on l'a trouve, sinon au milieu de l'image. Le
    cadre descend toujours jusqu'en bas : le personnage doit toucher le sol.
    """
    box_width = min(width, max(1, height // 2))
    if face is None:
        left = (width - box_width) // 2
    else:
        face_x, _face_y, face_w, _face_h = face
        left = int(face_x + face_w / 2 - box_width / 2)
    left = max(0, min(left, width - box_width))
    return left, 0, box_width, height


def frame_with_face(video: Path, destination: Path, samples: int = 12) -> float:
    """Image de la video ou le visage est le plus grand, recadree en personnage.

    Retourne l'instant retenu. Sans OpenCV, prend le milieu de la video et
    recadre au centre : approximatif, mais utilisable — mieux qu'un refus.
    """
    duration = media.duration_of(video)
    if duration <= 0:
        raise RuntimeError("Duree de la video inconnue.")

    best_time, best_face, best_area = duration / 2, None, 0
    probe = destination.with_suffix(".probe.jpg")
    if _has("cv2"):
        import cv2

        cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        try:
            for index in range(samples):
                at = duration * (index + 0.5) / samples
                try:
                    media.extract_frame(video, at, probe, width=640)
                except media.MediaError:
                    continue
                image = cv2.imread(str(probe))
                if image is None:
                    continue
                scale = media.probe(video)["width"] / image.shape[1] if image.shape[1] else 1
                grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                faces = cascade.detectMultiScale(grey, scaleFactor=1.15, minNeighbors=5,
                                                 minSize=(40, 40))
                for (x, y, width, height) in faces:
                    if width * height > best_area:
                        best_time, best_area = at, width * height
                        best_face = (x * scale, y * scale, width * scale, height * scale)
        finally:
            probe.unlink(missing_ok=True)

    full = destination.with_suffix(".full.png")
    try:
        media.extract_frame(video, best_time, full, width=media.probe(video)["width"])
        info = media.probe(full)
        box = _portrait_box(info["width"], info["height"], best_face)
        media.fit_stage_image(full, destination, STAGE_HEIGHT, box)
    finally:
        full.unlink(missing_ok=True)
    return best_time
