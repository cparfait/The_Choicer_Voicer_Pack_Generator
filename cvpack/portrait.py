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
    """Ce qui est possible, ici ou via un Python exterieur."""
    from . import helper
    aide = helper.status()
    return {"cutout": _has("rembg") or bool(aide.get("cutout")),
            "face": _has("cv2") or bool(aide.get("face")),
            "local": {"cutout": _has("rembg"), "face": _has("cv2")}}


# --------------------------------------------------------------------------
# Detourage
# --------------------------------------------------------------------------

def cutout(source: Path, destination: Path, height: int = STAGE_HEIGHT) -> None:
    """Enleve le fond, rogne les marges vides, met a la hauteur du plateau.

    Le detourage lui-meme part chez un Python exterieur quand rembg n'est pas
    la ; le rognage et la mise a l'echelle restent ici, ou vit ffmpeg.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    cut = destination.with_suffix(".cut.png")
    if _has("rembg"):
        from rembg import remove  # import tardif : le modele se charge a la demande
        cut.write_bytes(remove(Path(source).read_bytes()))
    else:
        from . import helper
        helper.run("cutout", {"source": str(source), "destination": str(cut)})
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


def _detect_faces(video: Path, duration: float,
                  samples: int) -> list[tuple[float, int, list[dict]]]:
    """Visages trouves dans quelques images de la video : (instant, largeur, visages).

    OpenCV ici s'il est la, sinon un Python exterieur — en une seule invocation
    pour toutes les images, car demarrer Python coute plus cher que la
    detection. Sans aide du tout, la liste est vide et l'appelant se rabat sur
    un recadrage centre.
    """
    import tempfile

    with tempfile.TemporaryDirectory(prefix="cvpack-faces-") as tmp:
        images: list[tuple[float, Path]] = []
        for index in range(samples):
            at = duration * (index + 0.5) / samples
            cible = Path(tmp) / f"{index:02d}.jpg"
            try:
                media.extract_frame(video, at, cible, width=640)
            except media.MediaError:
                continue
            images.append((at, cible))
        if not images:
            return []

        if _has("cv2"):
            import cv2

            cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
            sortie = []
            for at, chemin in images:
                image = cv2.imread(str(chemin))
                if image is None:
                    continue
                grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
                faces = cascade.detectMultiScale(grey, scaleFactor=1.15,
                                                 minNeighbors=5, minSize=(40, 40))
                sortie.append((at, int(image.shape[1]),
                               [{"x": int(x), "y": int(y), "w": int(w), "h": int(h)}
                                for (x, y, w, h) in faces]))
            return sortie

        from . import helper
        if not helper.status().get("face"):
            return []
        try:
            resultat = helper.run("faces", {"sources": [str(p) for _at, p in images]})
        except helper.HelperError:
            return []
        par_chemin = {item["source"]: item for item in resultat.get("images", [])}
        return [(at, par_chemin.get(str(p), {}).get("width", 0),
                 par_chemin.get(str(p), {}).get("faces", []))
                for at, p in images]


def frame_with_face(video: Path, destination: Path, samples: int = 12) -> float:
    """Image de la video ou le visage est le plus grand, recadree en personnage.

    Retourne l'instant retenu. Sans OpenCV, prend le milieu de la video et
    recadre au centre : approximatif, mais utilisable — mieux qu'un refus.
    """
    duration = media.duration_of(video)
    if duration <= 0:
        raise RuntimeError("Duree de la video inconnue.")

    best_time, best_face, best_area = duration / 2, None, 0
    detection = _detect_faces(video, duration, samples)
    for at, largeur, faces in detection:
        echelle = media.probe(video)["width"] / largeur if largeur else 1
        for face in faces:
            aire = face["w"] * face["h"]
            if aire > best_area:
                best_time, best_area = at, aire
                best_face = (face["x"] * echelle, face["y"] * echelle,
                             face["w"] * echelle, face["h"] * echelle)

    full = destination.with_suffix(".full.png")
    try:
        media.extract_frame(video, best_time, full, width=media.probe(video)["width"])
        info = media.probe(full)
        box = _portrait_box(info["width"], info["height"], best_face)
        media.fit_stage_image(full, destination, STAGE_HEIGHT, box)
    finally:
        full.unlink(missing_ok=True)
    return best_time
