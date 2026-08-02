"""Routes HTTP de l'outil."""

from __future__ import annotations

import json
import mimetypes
import os
import re
import string
import subprocess
import sys
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse

from . import build as builder
from . import clips as cliptools
from . import diarize, inifmt, jobs, media, portrait, project as projects
from . import separate, settings, subs, transcribe, ytdl
from .specs import (SOURCE_AUDIO_EXTS, SOURCE_VIDEO_EXTS, SPECS, public_specs)

router = APIRouter(prefix="/api")

CHUNK = 512 * 1024

# Seuil de detection des respirations : trop fin pour separer deux repliques,
# assez fin pour couper un passage trop long sans trancher un mot.
FINE_SILENCE = 0.12


# --------------------------------------------------------------------------
# Utilitaires
# --------------------------------------------------------------------------

def _project(project_id: str) -> projects.Project:
    found = projects.load(project_id)
    if not found:
        raise HTTPException(404, "Projet introuvable")
    return found


def _ranged_file(path: Path, request: Request, media_type: str | None = None) -> Response:
    """FileResponse avec gestion des requetes Range (seek dans <audio>/<video>)."""
    if not path.exists():
        raise HTTPException(404, "Fichier introuvable")
    size = path.stat().st_size
    media_type = media_type or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    range_header = request.headers.get("range")
    if not range_header:
        return FileResponse(path, media_type=media_type,
                            headers={"Accept-Ranges": "bytes", "Cache-Control": "no-store"})

    match = re.match(r"bytes=(\d*)-(\d*)", range_header)
    if not match:
        raise HTTPException(416, "Range invalide")
    start_text, end_text = match.groups()
    start = int(start_text) if start_text else 0
    end = int(end_text) if end_text else size - 1
    start = max(0, min(start, size - 1))
    end = max(start, min(end, size - 1))
    length = end - start + 1

    def stream():
        with path.open("rb") as handle:
            handle.seek(start)
            remaining = length
            while remaining > 0:
                block = handle.read(min(CHUNK, remaining))
                if not block:
                    break
                remaining -= len(block)
                yield block

    return StreamingResponse(
        stream(), status_code=206, media_type=media_type,
        headers={
            "Content-Range": f"bytes {start}-{end}/{size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(length),
            "Cache-Control": "no-store",
        },
    )


def _safe_ext(filename: str, allowed: list[str] | None = None) -> str:
    ext = Path(filename or "").suffix.lower()
    if allowed and ext not in allowed:
        raise HTTPException(400, f"Extension non acceptee : {ext or '(aucune)'}. "
                                 f"Attendu : {', '.join(allowed)}")
    return ext or ".bin"


async def _store_upload(upload: UploadFile, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as handle:
        while True:
            block = await upload.read(1024 * 1024)
            if not block:
                break
            handle.write(block)


# --------------------------------------------------------------------------
# Demarrage / reglages
# --------------------------------------------------------------------------

@router.get("/bootstrap")
def bootstrap():
    return {
        "settings": settings.load(),
        "specs": public_specs(),
        "game": settings.game_dir_status(),
        "tools": media.check_tools(),
        "whisper": transcribe.status(),
        "ytdl": ytdl.status(),
        "demucs": separate.status(),
        "portrait": portrait.status(),
        "diarize": diarize.status(),
        "platform": sys.platform,
    }


@router.post("/settings")
async def update_settings(request: Request):
    patch = await request.json()
    return {"settings": settings.save(patch), "game": settings.game_dir_status(),
            "tools": media.check_tools(), "whisper": transcribe.status(),
            "demucs": separate.status(), "portrait": portrait.status(),
            "diarize": diarize.status()}


@router.post("/gamedata/ensure")
def ensure_game_folders():
    created = settings.ensure_pack_folders()
    return {"created": created, "game": settings.game_dir_status()}


@router.get("/gamedata/packs")
def installed_packs():
    root = settings.game_dir()
    result = {}
    for type_id, spec in SPECS.items():
        folder = root / spec["folder"]
        entries = []
        if folder.is_dir():
            for item in sorted(folder.iterdir()):
                if item.is_dir():
                    files = [f for f in item.rglob("*") if f.is_file()]
                    entries.append({
                        "name": item.name,
                        "path": str(item),
                        "file_count": len(files),
                        "is_dub": (item / "dub_video.ogv").exists(),
                    })
        result[type_id] = {"folder": str(folder), "exists": folder.is_dir(), "packs": entries}
    return result


@router.post("/open-folder")
async def open_folder(request: Request):
    payload = await request.json()
    path = Path(payload.get("path", ""))
    if not path.exists():
        raise HTTPException(404, "Dossier introuvable")
    target = path if path.is_dir() else path.parent
    if sys.platform == "win32":
        os.startfile(str(target))  # noqa: S606
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(target)])
    else:
        subprocess.Popen(["xdg-open", str(target)])
    return {"opened": str(target)}


# --------------------------------------------------------------------------
# Explorateur de fichiers cote serveur
# --------------------------------------------------------------------------

@router.get("/fs/list")
def list_files(path: str = "", kind: str = "media"):
    allowed = {
        "media": SOURCE_AUDIO_EXTS + SOURCE_VIDEO_EXTS,
        "image": [".png", ".jpg", ".jpeg", ".webp", ".bmp"],
        "audio": SOURCE_AUDIO_EXTS,
        "video": SOURCE_VIDEO_EXTS,
        "model": [".glb", ".gltf"],
        "all": [],
    }.get(kind, [])

    if not path:
        if sys.platform == "win32":
            drives = [f"{letter}:\\" for letter in string.ascii_uppercase
                      if Path(f"{letter}:\\").exists()]
            shortcuts = [str(Path.home() / n) for n in ("Downloads", "Videos", "Music", "Desktop")]
            return {
                "path": "", "parent": None,
                "dirs": [{"name": d, "path": d} for d in drives]
                        + [{"name": Path(s).name, "path": s} for s in shortcuts if Path(s).exists()],
                "files": [],
            }
        path = str(Path.home())

    current = Path(path)
    if not current.is_dir():
        raise HTTPException(400, "Ce chemin n'est pas un dossier")
    dirs, files = [], []
    try:
        for item in sorted(current.iterdir(), key=lambda p: p.name.lower()):
            if item.name.startswith("."):
                continue
            try:
                if item.is_dir():
                    dirs.append({"name": item.name, "path": str(item)})
                elif not allowed or item.suffix.lower() in allowed:
                    files.append({"name": item.name, "path": str(item),
                                  "size": item.stat().st_size})
            except OSError:
                continue
    except PermissionError:
        raise HTTPException(403, "Acces refuse a ce dossier")
    parent = str(current.parent) if current.parent != current else ""
    return {"path": str(current), "parent": parent, "dirs": dirs, "files": files}


# --------------------------------------------------------------------------
# Projets
# --------------------------------------------------------------------------

@router.get("/projects")
def list_projects():
    return {"projects": projects.list_projects()}


@router.post("/projects")
async def create_project(request: Request):
    payload = await request.json()
    name = (payload.get("name") or "").strip()
    type_ = payload.get("type")
    if type_ not in SPECS:
        raise HTTPException(400, "Type de pack inconnu")
    created = projects.new_project(name, type_)
    return created.data


@router.get("/projects/{project_id}")
def get_project(project_id: str):
    return _project(project_id).data


@router.patch("/projects/{project_id}")
async def patch_project(project_id: str, request: Request):
    found = _project(project_id)
    patch = await request.json()
    return found.patch(patch).data


@router.delete("/projects/{project_id}")
def delete_project(project_id: str):
    return {"deleted": projects.delete(project_id)}


@router.post("/projects/{project_id}/duplicate")
async def duplicate_project(project_id: str, request: Request):
    payload = await request.json()
    clone = projects.duplicate(project_id, (payload.get("name") or "").strip())
    if not clone:
        raise HTTPException(404, "Projet introuvable")
    return clone.data


@router.get("/projects/{project_id}/validate")
def validate_project(project_id: str):
    found = _project(project_id)
    return {"issues": builder.validate(found),
            "install_path": str(builder.install_target(found))}


# --------------------------------------------------------------------------
# Source audio/video d'un pack voix
# --------------------------------------------------------------------------

def _process_source(job, found: projects.Project, source: Path,
                    start: float = 0.0, span: float = 1.0) -> dict:
    """Analyse, extraction audio, apercu et forme d'onde d'une source."""
    def step(fraction, message):
        job.progress(start + fraction * span, message)

    step(0.05, "Analyse du fichier")
    info = media.probe(source)
    if not info["has_audio"]:
        raise RuntimeError(
            "Ce fichier ne contient aucune piste audio : impossible d'en tirer des clips."
        )

    step(0.2, "Extraction de la piste audio")
    media.extract_master_audio(source, found.master_audio)

    step(0.6, "Generation de l'apercu")
    media.make_preview(found.master_audio, found.preview_audio)

    step(0.8, "Calcul de la forme d'onde")
    peaks = media.compute_peaks(found.master_audio)
    found.peaks_file.write_text(json.dumps({"peaks": peaks, "duration": info["duration"]}),
                                encoding="utf-8")

    if info["has_video"] and info["duration"] > 0:
        step(0.9, "Extraction d'images candidates")
        _extract_candidate_frames(found, source, info["duration"])

    found.data.setdefault("source", {}).update({
        "duration": info["duration"],
        "has_video": info["has_video"],
        "has_audio": info["has_audio"],
        "width": info["width"],
        "height": info["height"],
        "ready": True,
    })
    # Une source qui a une piste video donne un pack Dub : la video tourne
    # pendant que le clip est joue, comme dans les packs de la communaute.
    # Sans piste video, le mode Dub est impossible — le pack se resume alors
    # a des sons et leurs images.
    dub = found.data.setdefault("dub", {})
    dub.setdefault("characters", [])
    if not dub.get("chosen"):
        dub["enabled"] = bool(info["has_video"])
    elif not info["has_video"]:
        dub["enabled"] = False
    found.save()
    step(1.0, "Pret")
    return {"source": found.data["source"]}


def _extract_candidate_frames(found: projects.Project, source: Path,
                              duration: float, count: int = 12) -> list[str]:
    """Images reparties dans la video, proposees comme icone du pack."""
    found.frames_dir.mkdir(parents=True, exist_ok=True)
    for old in found.frames_dir.glob("frame_[0-9]*"):
        if not old.name.startswith("frame_00"):
            old.unlink(missing_ok=True)
    made = []
    for index in range(count):
        at = duration * (index + 0.5) / count
        target = found.frames_dir / f"frame_{index + 1:02d}.jpg"
        try:
            media.extract_frame(source, at, target)
            made.append(target.name)
        except media.MediaError:
            continue
    return made


def _prepare_source(job, project_id: str) -> dict:
    found = _project(project_id)
    source = found.source_path()
    if not source:
        raise RuntimeError("Fichier source introuvable")
    return _process_source(job, found, source)


@router.post("/projects/{project_id}/source/upload")
async def upload_source(project_id: str, file: UploadFile = File(...)):
    found = _project(project_id)
    ext = _safe_ext(file.filename, SOURCE_AUDIO_EXTS + SOURCE_VIDEO_EXTS)
    stored = f"source{ext}"
    for old in found.source_dir.glob("source.*"):
        old.unlink(missing_ok=True)
    await _store_upload(file, found.source_dir / stored)
    found.data["source"] = {"filename": file.filename, "stored": stored, "ready": False}
    found.save()
    return {"job": jobs.submit("Import de la source", _prepare_source, project_id)}


@router.post("/projects/{project_id}/source/path")
async def link_source(project_id: str, request: Request):
    found = _project(project_id)
    payload = await request.json()
    path = Path(payload.get("path", ""))
    if not path.is_file():
        raise HTTPException(400, "Fichier introuvable")
    _safe_ext(path.name, SOURCE_AUDIO_EXTS + SOURCE_VIDEO_EXTS)
    for old in found.source_dir.glob("source.*"):
        old.unlink(missing_ok=True)
    found.data["source"] = {"filename": path.name, "external": str(path), "ready": False}
    found.save()
    return {"job": jobs.submit("Import de la source", _prepare_source, project_id)}


def _download_source(job, project_id: str, url: str, mode: str) -> dict:
    found = _project(project_id)
    job.progress(0.02, "Lecture des informations")
    info = ytdl.probe_url(url)
    if info["is_live"]:
        raise RuntimeError("Les directs ne peuvent pas etre importes.")

    def report(fraction, message):
        job.progress(0.05 + fraction * 0.55, message)

    path = ytdl.download(url, found.source_dir, mode=mode, progress_cb=report)
    found.data["source"] = {
        "filename": info["title"] or path.name,
        "stored": path.name,
        "ready": False,
        "origin": {"url": info["webpage_url"], "title": info["title"],
                   "uploader": info["uploader"], "id": info["id"]},
    }
    if not (found.data.get("meta", {}).get("subtitle") or "").strip() and info["uploader"]:
        found.data.setdefault("meta", {})["subtitle"] = info["uploader"]
    found.data.setdefault("options", {}).setdefault(
        "base_name", projects.safe_name(info["title"] or found.data.get("name", "clip"))
    )
    _save_remote_thumbnail(found, info.get("thumbnail") or "")

    job.progress(0.61, "Recherche des sous-titres")
    found_subs = ytdl.fetch_subtitles(url, found.source_dir)
    if found_subs:
        try:
            cues = subs.parse_file(Path(found_subs["path"]))
        except (OSError, ValueError):
            cues = []
        if cues:
            found.data["transcript"] = {
                "source": "sous-titres de la video",
                "lang": found_subs.get("lang", ""),
                "cues": cues,
            }
    found.save()

    result = _process_source(job, found, path, start=0.6, span=0.4)
    return {**result, "info": info}


def _save_remote_thumbnail(found: projects.Project, url: str) -> None:
    """Miniature de la video, proposee comme candidate d'icone du pack."""
    if not url.startswith(("http://", "https://")):
        return
    try:
        import urllib.request
        with urllib.request.urlopen(url, timeout=20) as response:
            data = response.read(8 * 1024 * 1024)
    except Exception:  # noqa: BLE001 - la miniature est un bonus, jamais bloquant
        return
    found.frames_dir.mkdir(parents=True, exist_ok=True)
    suffix = ".webp" if url.lower().split("?")[0].endswith(".webp") else ".jpg"
    (found.frames_dir / f"frame_00_miniature{suffix}").write_bytes(data)


@router.post("/projects/{project_id}/source/youtube/probe")
async def probe_youtube(project_id: str, request: Request):
    payload = await request.json()
    url = (payload.get("url") or "").strip()
    if not url:
        raise HTTPException(400, "Adresse manquante")
    try:
        return ytdl.probe_url(url)
    except ytdl.DownloadError as exc:
        raise HTTPException(400, str(exc))


@router.post("/projects/{project_id}/source/youtube")
async def import_youtube(project_id: str, request: Request):
    _project(project_id)
    if not ytdl.status()["available"]:
        raise HTTPException(400, "yt-dlp n'est pas installe. Lance : pip install yt-dlp")
    payload = await request.json()
    url = (payload.get("url") or "").strip()
    if not url:
        raise HTTPException(400, "Adresse manquante")
    mode = payload.get("mode") or "video"
    return {"job": jobs.submit("Import depuis le web", _download_source,
                               project_id, url, mode)}


@router.get("/projects/{project_id}/audio")
def stream_audio(project_id: str, request: Request):
    found = _project(project_id)
    return _ranged_file(found.preview_audio, request, "audio/ogg")


@router.get("/projects/{project_id}/video")
def stream_video(project_id: str, request: Request):
    found = _project(project_id)
    source = found.source_path()
    if not source or not found.data.get("source", {}).get("has_video"):
        raise HTTPException(404, "Pas de video")
    return _ranged_file(source, request)


@router.get("/projects/{project_id}/peaks")
def get_peaks(project_id: str):
    found = _project(project_id)
    if not found.peaks_file.exists():
        return {"peaks": [], "duration": found.data.get("source", {}).get("duration", 0)}
    return json.loads(found.peaks_file.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# Decoupe automatique
# --------------------------------------------------------------------------

def _merge_repeats(found: projects.Project, new_clips: list[dict],
                   params: dict) -> int:
    """En mode Dub, une replique repetee devient un clip a plusieurs instants.

    Hors mode Dub les timestamps ne servent a rien : chaque replique garde
    son clip.
    """
    if not params.get("merge_repeats", True):
        return 0
    if not found.data.get("dub", {}).get("enabled"):
        return 0
    return cliptools.merge_repeated(new_clips)


def _autosplit(job, project_id: str, params: dict) -> dict:
    found = _project(project_id)
    source = found.master_audio if found.master_audio.exists() else found.source_path()
    if not source:
        raise RuntimeError("Aucune source a analyser")

    job.progress(0.15, "Detection des silences")
    minimum = float(params.get("min_silence", 0.35))
    # Une seule passe ffmpeg, avec le seuil le plus fin : les silences longs
    # decoupent les prises de parole, les courts servent a couper proprement
    # un passage qui depasse la duree maxi.
    pauses = media.detect_silences(
        Path(source),
        noise_db=float(params.get("noise_db", -32.0)),
        min_silence=min(FINE_SILENCE, minimum),
    )
    silences = [p for p in pauses if p[1] - p[0] >= minimum]
    duration = float(found.data.get("source", {}).get("duration") or media.duration_of(source))

    job.progress(0.7, "Construction des segments")
    segments = media.segments_from_silences(
        duration, silences,
        min_len=float(params.get("min_len", 0.7)),
        max_len=float(params.get("max_len", 6.0)),
        pad=float(params.get("pad", 0.08)),
        pauses=pauses,
    )

    # Decouper sur les silences n'empeche pas d'avoir les sous-titres : quand
    # la source en a, chaque clip prend le texte qui tombe dans son intervalle.
    cues = _transcript(found).get("cues") or []

    base = (params.get("base_name") or found.data.get("name") or "clip").strip()
    clips = []
    for index, segment in enumerate(segments, start=1):
        clips.append({
            "id": uuid.uuid4().hex[:8],
            "name": f"{projects.safe_name(base)}_{index:03d}",
            "start": segment["start"],
            "end": segment["end"],
            "caption": subs.text_for_range(cues, segment["start"], segment["end"])
                       if cues else "",
            "image": None,
            "characters": [],
            "dub_only": False,
            "dub_timestamps": [],
            "gain_db": 0.0,
            "enabled": True,
        })
    merged = _merge_repeats(found, clips, params)
    if params.get("replace", True):
        for old in found.clip_images_dir.glob("*"):
            old.unlink(missing_ok=True)
        found.data["clips"] = clips
    else:
        found.data.setdefault("clips", []).extend(clips)
    found.save()

    # Une image par clip, prise au milieu : chaque son est accompagne de
    # l'image de la video a cet instant.
    with_images = params.get("clip_images", True)
    video = found.source_path()  # master.wav n'a pas d'image : on relit l'original
    if with_images and video and found.data.get("source", {}).get("has_video"):
        found.clip_images_dir.mkdir(parents=True, exist_ok=True)
        total = max(1, len(clips))
        for index, clip in enumerate(clips, start=1):
            if job.cancelled():
                break
            destination = found.clip_images_dir / f"{clip['id']}.png"
            middle = (clip["start"] + clip["end"]) / 2
            try:
                media.extract_frame(video, middle, destination, width=800)
                clip["image"] = destination.name
            except media.MediaError:
                continue
            job.progress(0.7 + 0.3 * index / total, f"Image {index}/{total}")
        found.save()

    job.progress(1.0, f"{len(clips)} clips")
    return {"clips": found.data["clips"], "count": len(clips), "merged": merged}


@router.post("/projects/{project_id}/autosplit")
async def autosplit(project_id: str, request: Request):
    _project(project_id)
    params = await request.json()
    return {"job": jobs.submit("Decoupe automatique", _autosplit, project_id, params)}


# --------------------------------------------------------------------------
# Transcript (sous-titres de la video ou fichier importe)
# --------------------------------------------------------------------------

def _recover_transcript(found: projects.Project) -> dict:
    """Sous-titres telecharges par un import qui ne les a pas enregistres.

    Le fichier est dans le dossier du projet : autant le relire plutot que de
    demander un reimport.
    """
    best = ytdl.find_subtitles(found.source_dir)
    if not best:
        return {}
    try:
        cues = subs.parse_file(Path(best["path"]))
    except (OSError, ValueError):
        return {}
    if not cues:
        return {}
    transcript = {"source": "sous-titres de la video",
                  "lang": best.get("lang", ""), "cues": cues}
    found.data["transcript"] = transcript
    found.save()
    return transcript


def _transcript(found: projects.Project) -> dict:
    transcript = found.data.get("transcript") or {}
    if not transcript.get("cues") and not transcript.get("cleared"):
        transcript = _recover_transcript(found) or transcript
    return transcript


@router.get("/projects/{project_id}/transcript")
def get_transcript(project_id: str):
    found = _project(project_id)
    transcript = _transcript(found)
    return {
        "source": transcript.get("source", ""),
        "lang": transcript.get("lang", ""),
        "count": len(transcript.get("cues", [])),
        "cues": transcript.get("cues", [])[:2000],
    }


@router.delete("/projects/{project_id}/transcript")
def clear_transcript(project_id: str):
    found = _project(project_id)
    # Marque le refus : sans quoi le fichier reste dans le dossier du projet
    # et serait repris a la prochaine lecture.
    found.data["transcript"] = {"cleared": True, "cues": []}
    found.save()
    return {"ok": True}


@router.post("/projects/{project_id}/transcript/upload")
async def upload_transcript(project_id: str, file: UploadFile = File(...)):
    found = _project(project_id)
    _safe_ext(file.filename, [".srt", ".vtt", ".json3", ".json", ".txt"])
    target = found.source_dir / f"imported{Path(file.filename).suffix.lower()}"
    await _store_upload(file, target)
    try:
        cues = subs.parse_file(target)
    except (OSError, ValueError) as exc:
        raise HTTPException(400, f"Fichier de sous-titres illisible : {exc}")
    if not cues:
        raise HTTPException(400, "Aucun sous-titre exploitable dans ce fichier.")
    found.data["transcript"] = {"source": file.filename, "lang": "", "cues": cues}
    found.save()
    return {"count": len(cues)}


def _segment_from_transcript(job, project_id: str, params: dict) -> dict:
    found = _project(project_id)
    cues = _transcript(found).get("cues") or []
    if not cues:
        raise RuntimeError("Aucun transcript disponible pour ce projet.")

    duration = float(found.data.get("source", {}).get("duration") or 0) or None

    # Une replique plus longue que la duree maxi doit etre coupee : autant le
    # faire dans une respiration plutot qu'au milieu d'un mot.
    pauses: list[tuple[float, float]] = []
    audio = found.master_audio if found.master_audio.exists() else found.source_path()
    if audio:
        job.progress(0.1, "Detection des silences")
        try:
            pauses = media.detect_silences(
                Path(audio), noise_db=float(params.get("noise_db", -32.0)),
                min_silence=FINE_SILENCE)
        except media.MediaError:
            pauses = []

    job.progress(0.2, "Construction des clips")
    segments = subs.segments_from_cues(
        cues,
        min_len=float(params.get("min_len", 0.7)),
        max_len=float(params.get("max_len", 6.0)),
        merge_gap=float(params.get("merge_gap", 0.35)),
        pad=float(params.get("pad", 0.05)),
        duration=duration,
        pauses=pauses,
    )

    base = projects.safe_name(params.get("base_name") or found.data.get("name") or "clip")
    clips = []
    for index, segment in enumerate(segments, start=1):
        clips.append({
            "id": uuid.uuid4().hex[:8],
            "name": f"{base}_{index:03d}",
            "start": segment["start"],
            "end": segment["end"],
            "caption": segment["text"],
            "image": None,
            "characters": [],
            "dub_only": False,
            "dub_timestamps": [],
            "gain_db": 0.0,
            "enabled": True,
        })
    merged = _merge_repeats(found, clips, params)
    if params.get("replace", True):
        for old in found.clip_images_dir.glob("*"):
            old.unlink(missing_ok=True)
        found.data["clips"] = clips
    else:
        found.data.setdefault("clips", []).extend(clips)
    found.save()

    video = found.source_path()
    if params.get("clip_images", True) and video and found.data.get("source", {}).get("has_video"):
        found.clip_images_dir.mkdir(parents=True, exist_ok=True)
        total = max(1, len(clips))
        for index, clip in enumerate(clips, start=1):
            if job.cancelled():
                break
            destination = found.clip_images_dir / f"{clip['id']}.png"
            middle = (clip["start"] + clip["end"]) / 2
            try:
                media.extract_frame(video, middle, destination, width=800)
                clip["image"] = destination.name
            except media.MediaError:
                continue
            job.progress(0.4 + 0.6 * index / total, f"Image {index}/{total}")
        found.save()

    job.progress(1.0, f"{len(clips)} clips")
    return {"clips": found.data["clips"], "count": len(clips), "merged": merged}


@router.post("/projects/{project_id}/transcript/segment")
async def segment_from_transcript(project_id: str, request: Request):
    _project(project_id)
    params = await request.json() if await request.body() else {}
    return {"job": jobs.submit("Decoupe sur les sous-titres",
                               _segment_from_transcript, project_id, params)}


@router.post("/projects/{project_id}/transcript/apply")
async def apply_transcript(project_id: str, request: Request):
    """Remplit les sous-titres des clips existants a partir du transcript."""
    found = _project(project_id)
    payload = await request.json() if await request.body() else {}
    cues = _transcript(found).get("cues") or []
    if not cues:
        raise HTTPException(400, "Aucun transcript disponible.")
    overwrite = bool(payload.get("overwrite"))
    filled = 0
    for clip in found.data.get("clips", []):
        if not overwrite and (clip.get("caption") or "").strip():
            continue
        text = subs.text_for_range(cues, float(clip["start"]), float(clip["end"]))
        if text:
            clip["caption"] = text
            filled += 1
    found.save()
    return {"filled": filled, "clips": found.data.get("clips", [])}


# --------------------------------------------------------------------------
# Transcription automatique (Whisper)
# --------------------------------------------------------------------------

def _transcribe(job, project_id: str, params: dict) -> dict:
    found = _project(project_id)
    source = found.master_audio if found.master_audio.exists() else found.source_path()
    if not source:
        raise RuntimeError("Aucune source a transcrire")

    ids = params.get("clip_ids")
    clips = [c for c in found.data.get("clips", []) if c.get("enabled", True)]
    if ids:
        clips = [c for c in clips if c["id"] in ids]
    if not params.get("overwrite", False):
        clips = [c for c in clips if not (c.get("caption") or "").strip()]

    total = max(1, len(clips))
    language = params.get("language", "fr")
    job.progress(0.02, "Chargement du modele")
    transcribe.get_model()

    done = 0
    for clip in clips:
        if job.cancelled():
            break
        text = transcribe.transcribe_range(Path(source), float(clip["start"]),
                                           float(clip["end"]), language=language)
        target = found.clip(clip["id"])
        if target is not None:
            target["caption"] = text
        done += 1
        job.progress(done / total, f"{done}/{total} — {text[:60]}")
        found.save()
    return {"clips": found.data.get("clips", []), "transcribed": done}


@router.post("/projects/{project_id}/transcribe")
async def start_transcription(project_id: str, request: Request):
    _project(project_id)
    if not transcribe.available():
        raise HTTPException(400, "faster-whisper n'est pas installe. "
                                 "Lance : pip install faster-whisper")
    params = await request.json()
    return {"job": jobs.submit("Transcription", _transcribe, project_id, params)}


# --------------------------------------------------------------------------
# Detection des locuteurs (pyannote)
# --------------------------------------------------------------------------

def _diarize(job, project_id: str, params: dict) -> dict:
    found = _project(project_id)
    source = found.master_audio if found.master_audio.exists() else found.source_path()
    if not source:
        raise RuntimeError("Aucune source a analyser")

    job.progress(0.05, "Chargement du modele")
    turns = diarize.speakers(Path(source), count=params.get("speakers") or None)
    if not turns:
        raise RuntimeError("Aucune voix distinguee dans cette source.")

    job.progress(0.85, "Attribution des personnages")
    names = diarize.friendly_names(turns)
    overwrite = bool(params.get("overwrite"))
    filled = 0
    for clip in found.data.get("clips", []):
        if not overwrite and (clip.get("characters") or []):
            continue
        label = diarize.label_for_range(turns, float(clip["start"]), float(clip["end"]))
        if not label:
            continue
        clip["characters"] = [names[label]]
        filled += 1

    # Les noms proposes alimentent la liste du mode Dub : l'utilisateur les
    # renomme une fois, la correspondance suit dans tous les clips.
    dub = found.data.setdefault("dub", {})
    known = list(dub.get("characters") or [])
    for name in names.values():
        if name not in known:
            known.append(name)
    dub["characters"] = known
    found.save()
    job.progress(1.0, f"{len(names)} voix")
    return {"clips": found.data.get("clips", []), "speakers": len(names),
            "filled": filled, "names": list(names.values())}


@router.post("/projects/{project_id}/diarize")
async def start_diarization(project_id: str, request: Request):
    _project(project_id)
    state = diarize.status()
    if not state["available"]:
        raise HTTPException(400, "pyannote.audio n'est pas installe. "
                                 "Lance : pip install pyannote.audio")
    if not state["token"]:
        raise HTTPException(400, "Aucun jeton Hugging Face dans les Reglages : le "
                                 "modele de diarisation en demande un.")
    params = await request.json() if await request.body() else {}
    return {"job": jobs.submit("Detection des locuteurs", _diarize, project_id, params)}


# --------------------------------------------------------------------------
# Piste d'ambiance (Demucs)
# --------------------------------------------------------------------------

def _backing_track(job, project_id: str, params: dict) -> dict:
    found = _project(project_id)
    source = found.master_audio if found.master_audio.exists() else found.source_path()
    if not source:
        raise RuntimeError("Aucune source a separer")

    job.progress(0.05, "Separation des voix")
    fmt = settings.get("clip_format") or "ogg"
    stored = f"_backing_track.{fmt}"
    destination = found.assets_dir / stored
    for old in found.assets_dir.glob("_backing_track.*"):
        old.unlink(missing_ok=True)
    separate.backing_track(Path(source), destination,
                           progress_cb=lambda f: job.progress(0.05 + 0.9 * f,
                                                              "Separation des voix"))
    found.data.setdefault("assets", {})["_backing_track"] = stored
    found.data.setdefault("asset_names", {})["_backing_track"] = stored
    found.save()
    job.progress(1.0, "Piste d'ambiance prete")
    return {"assets": found.data["assets"], "asset_names": found.data.get("asset_names", {})}


@router.post("/projects/{project_id}/backing-track")
async def start_backing_track(project_id: str, request: Request):
    _project(project_id)
    if not separate.available():
        raise HTTPException(400, "demucs n'est pas installe. Lance : pip install demucs")
    params = await request.json() if await request.body() else {}
    return {"job": jobs.submit("Piste d'ambiance", _backing_track, project_id, params)}


# --------------------------------------------------------------------------
# Assets (emplacements de fichiers)
# --------------------------------------------------------------------------

def _slot_exts(type_: str, slot: str) -> list[str]:
    for definition in SPECS[type_].get("slots", []):
        if definition["name"] == slot:
            kind = definition["kind"]
            if kind == "image":
                return [".png", ".jpg", ".jpeg"]
            if kind == "audio":
                return SOURCE_AUDIO_EXTS
            if kind == "video":
                return SOURCE_VIDEO_EXTS
            if kind == "model":
                return [".glb", ".gltf"]
    return []


@router.post("/projects/{project_id}/assets/{slot}")
async def upload_asset(project_id: str, slot: str, file: UploadFile = File(...)):
    found = _project(project_id)
    allowed = _slot_exts(found.type, slot)
    ext = _safe_ext(file.filename, allowed or None)
    for old in found.assets_dir.glob(f"{slot}.*"):
        old.unlink(missing_ok=True)
    stored = f"{slot}{ext}"
    await _store_upload(file, found.assets_dir / stored)
    found.data.setdefault("assets", {})[slot] = stored
    found.data.setdefault("asset_names", {})[slot] = file.filename
    found.save()
    return {"assets": found.data["assets"], "asset_names": found.data.get("asset_names", {})}


@router.delete("/projects/{project_id}/assets/{slot}")
def delete_asset(project_id: str, slot: str):
    found = _project(project_id)
    for old in found.assets_dir.glob(f"{slot}.*"):
        old.unlink(missing_ok=True)
    found.data.get("assets", {}).pop(slot, None)
    found.data.get("asset_names", {}).pop(slot, None)
    found.save()
    return {"assets": found.data.get("assets", {})}


@router.get("/projects/{project_id}/assets/{slot}/file")
def get_asset(project_id: str, slot: str, request: Request):
    found = _project(project_id)
    path = found.asset(slot)
    if not path:
        raise HTTPException(404, "Aucun fichier pour cet emplacement")
    return _ranged_file(path, request)


def _stage_slot(type_: str, slot: str) -> dict:
    definition = next((s for s in SPECS[type_].get("slots", []) if s["name"] == slot), None)
    if not definition or not definition.get("stage"):
        raise HTTPException(400, "Cet emplacement n'est pas un personnage du plateau.")
    return definition


def _cutout(job, project_id: str, slot: str) -> dict:
    found = _project(project_id)
    source = found.asset(slot)
    if not source:
        raise RuntimeError("Aucune image pour cet emplacement.")
    job.progress(0.1, "Detourage du personnage")
    # L'original est garde a cote : le detourage automatique se rate parfois,
    # et repartir de la photo evite de la reimporter.
    backup = found.assets_dir / f"{slot}.original{source.suffix.lower()}"
    if not backup.exists():
        backup.write_bytes(source.read_bytes())
    stored = f"{slot}.png"
    portrait.cutout(source, found.assets_dir / stored)
    if source.name != stored:
        source.unlink(missing_ok=True)
    found.data.setdefault("assets", {})[slot] = stored
    found.save()
    job.progress(1.0, "Personnage detoure")
    return {"assets": found.data["assets"], "asset_names": found.data.get("asset_names", {})}


@router.post("/projects/{project_id}/assets/{slot}/cutout")
async def cutout_asset(project_id: str, slot: str):
    found = _project(project_id)
    _stage_slot(found.type, slot)
    if not portrait.status()["cutout"]:
        raise HTTPException(400, "rembg n'est pas installe. "
                                 "Lance : pip install rembg onnxruntime")
    return {"job": jobs.submit("Detourage", _cutout, project_id, slot)}


@router.post("/projects/{project_id}/assets/{slot}/restore")
def restore_asset(project_id: str, slot: str):
    """Revient a l'image d'avant detourage."""
    found = _project(project_id)
    _stage_slot(found.type, slot)
    backup = next(found.assets_dir.glob(f"{slot}.original.*"), None)
    if not backup:
        raise HTTPException(404, "Aucune image d'origine conservee.")
    stored = f"{slot}{backup.suffix.lower()}"
    for old in found.assets_dir.glob(f"{slot}.*"):
        if old != backup:
            old.unlink(missing_ok=True)
    (found.assets_dir / stored).write_bytes(backup.read_bytes())
    backup.unlink(missing_ok=True)
    found.data.setdefault("assets", {})[slot] = stored
    found.save()
    return {"assets": found.data["assets"], "asset_names": found.data.get("asset_names", {})}


def _portrait_from_video(job, project_id: str, slot: str, path: str) -> dict:
    found = _project(project_id)
    video = Path(path)
    if not video.is_file():
        raise RuntimeError("Fichier video introuvable.")
    job.progress(0.1, "Recherche d'un visage")
    target = found.assets_dir / f"{slot}.png"
    for old in found.assets_dir.glob(f"{slot}.*"):
        old.unlink(missing_ok=True)
    at = portrait.frame_with_face(video, target)
    if portrait.status()["cutout"]:
        job.progress(0.7, "Detourage du personnage")
        try:
            portrait.cutout(target, target)
        except RuntimeError:
            pass
    found.data.setdefault("assets", {})[slot] = target.name
    found.data.setdefault("asset_names", {})[slot] = f"{video.name} @ {at:.1f}s"
    found.save()
    job.progress(1.0, "Image prete")
    return {"assets": found.data["assets"], "asset_names": found.data.get("asset_names", {})}


@router.post("/projects/{project_id}/assets/{slot}/from-video")
async def portrait_from_video(project_id: str, slot: str, request: Request):
    found = _project(project_id)
    _stage_slot(found.type, slot)
    payload = await request.json()
    path = (payload.get("path") or "").strip()
    if not path:
        raise HTTPException(400, "Chemin de la video manquant")
    return {"job": jobs.submit("Image depuis une video", _portrait_from_video,
                               project_id, slot, path)}


# --------------------------------------------------------------------------
# Propositions d'images extraites de la video
# --------------------------------------------------------------------------

def _frame_list(found: projects.Project) -> list[dict]:
    if not found.frames_dir.is_dir():
        return []
    frames = []
    for path in sorted(found.frames_dir.iterdir()):
        if path.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
            frames.append({"name": path.name, "size": path.stat().st_size})
    return frames


@router.get("/projects/{project_id}/frames")
def list_frames(project_id: str):
    return {"frames": _frame_list(_project(project_id))}


@router.post("/projects/{project_id}/frames")
async def make_frames(project_id: str, request: Request):
    """Extrait des images reparties dans la video, comme candidates d'icone."""
    found = _project(project_id)
    payload = await request.json() if await request.body() else {}
    source = found.source_path()
    if not source:
        raise HTTPException(400, "Aucune source importee.")
    if not found.data.get("source", {}).get("has_video"):
        raise HTTPException(400, "La source n'a pas de piste video : aucune image a extraire.")

    duration = float(found.data.get("source", {}).get("duration") or 0)
    if duration <= 0:
        raise HTTPException(400, "Duree de la source inconnue.")

    count = max(1, min(24, int(payload.get("count") or 12)))
    keep_existing = bool(payload.get("keep"))
    found.frames_dir.mkdir(parents=True, exist_ok=True)
    if not keep_existing:
        for old in found.frames_dir.glob("frame_*"):
            old.unlink(missing_ok=True)

    # Reparties sur la video, en evitant les tout premiers et derniers instants.
    times = [duration * (index + 0.5) / count for index in range(count)]
    made = []
    for index, time in enumerate(times, start=1):
        target = found.frames_dir / f"frame_{index:02d}.jpg"
        try:
            media.extract_frame(source, time, target)
            made.append({"name": target.name, "time": round(time, 2)})
        except media.MediaError:
            continue
    if not made:
        raise HTTPException(500, "Aucune image n'a pu etre extraite.")
    return {"frames": _frame_list(found), "made": made}


@router.post("/projects/{project_id}/frames/at")
async def make_frame_at(project_id: str, request: Request):
    """Une image a un instant precis (milieu d'un clip, position de lecture...)."""
    found = _project(project_id)
    payload = await request.json()
    source = found.source_path()
    if not source or not found.data.get("source", {}).get("has_video"):
        raise HTTPException(400, "La source n'a pas de piste video.")
    time = float(payload.get("at") or 0)
    target = found.frames_dir / f"frame_at_{int(time * 1000):09d}.jpg"
    try:
        media.extract_frame(source, time, target)
    except media.MediaError as exc:
        raise HTTPException(500, str(exc))
    return {"frame": target.name, "frames": _frame_list(found)}


@router.get("/projects/{project_id}/frames/{name}")
def get_frame(project_id: str, name: str, request: Request):
    found = _project(project_id)
    path = found.frames_dir / Path(name).name
    if not path.is_file():
        raise HTTPException(404, "Image introuvable")
    return _ranged_file(path, request)


@router.post("/projects/{project_id}/assets/{slot}/from-frame")
async def asset_from_frame(project_id: str, slot: str, request: Request):
    """Utilise une image extraite comme fichier d'un emplacement (icone, etc.)."""
    found = _project(project_id)
    payload = await request.json()
    frame = found.frames_dir / Path(payload.get("frame", "")).name
    if not frame.is_file():
        raise HTTPException(404, "Image introuvable")
    for old in found.assets_dir.glob(f"{slot}.*"):
        old.unlink(missing_ok=True)
    stored = f"{slot}.png"
    try:
        media.convert_image(frame, found.assets_dir / stored)
    except media.MediaError as exc:
        raise HTTPException(500, str(exc))
    found.data.setdefault("assets", {})[slot] = stored
    found.data.setdefault("asset_names", {})[slot] = frame.name
    found.save()
    return {"assets": found.data["assets"], "asset_names": found.data.get("asset_names", {})}


@router.post("/projects/{project_id}/clips/{clip_id}/image/from-frame")
async def clip_image_from_frame(project_id: str, clip_id: str, request: Request):
    """Image du clip prise dans la video (par defaut au milieu du clip)."""
    found = _project(project_id)
    clip = found.clip(clip_id)
    if not clip:
        raise HTTPException(404, "Clip introuvable")
    source = found.source_path()
    if not source or not found.data.get("source", {}).get("has_video"):
        raise HTTPException(400, "La source n'a pas de piste video.")
    payload = await request.json() if await request.body() else {}
    frame_name = payload.get("frame")
    for old in found.clip_images_dir.glob(f"{clip_id}.*"):
        old.unlink(missing_ok=True)
    destination = found.clip_images_dir / f"{clip_id}.png"
    try:
        if frame_name:
            frame = found.frames_dir / Path(frame_name).name
            if not frame.is_file():
                raise HTTPException(404, "Image introuvable")
            media.convert_image(frame, destination)
        else:
            at = float(payload.get("at") if payload.get("at") is not None
                       else (float(clip["start"]) + float(clip["end"])) / 2)
            media.extract_frame(source, at, destination)
    except media.MediaError as exc:
        raise HTTPException(500, str(exc))
    clip["image"] = destination.name
    found.save()
    return {"clip": clip}


@router.post("/projects/{project_id}/clips/images/from-video")
def all_clip_images(project_id: str):
    """Une image par clip, prise au milieu de chacun."""
    found = _project(project_id)
    source = found.source_path()
    if not source or not found.data.get("source", {}).get("has_video"):
        raise HTTPException(400, "La source n'a pas de piste video.")

    def worker(job, project_id: str) -> dict:
        project = _project(project_id)
        clips = [c for c in project.data.get("clips", []) if c.get("enabled", True)]
        total = max(1, len(clips))
        for index, clip in enumerate(clips, start=1):
            for old in project.clip_images_dir.glob(f"{clip['id']}.*"):
                old.unlink(missing_ok=True)
            destination = project.clip_images_dir / f"{clip['id']}.png"
            middle = (float(clip["start"]) + float(clip["end"])) / 2
            try:
                media.extract_frame(project.source_path(), middle, destination)
                target = project.clip(clip["id"])
                if target is not None:
                    target["image"] = destination.name
            except media.MediaError:
                pass
            job.progress(index / total, f"{index}/{total}")
        project.save()
        return {"clips": project.data.get("clips", [])}

    return {"job": jobs.submit("Images des clips", worker, project_id)}


# --------------------------------------------------------------------------
# Images de clips
# --------------------------------------------------------------------------

@router.post("/projects/{project_id}/clips/{clip_id}/image")
async def upload_clip_image(project_id: str, clip_id: str, file: UploadFile = File(...)):
    found = _project(project_id)
    clip = found.clip(clip_id)
    if not clip:
        raise HTTPException(404, "Clip introuvable")
    ext = _safe_ext(file.filename, [".png", ".jpg", ".jpeg"])
    for old in found.clip_images_dir.glob(f"{clip_id}.*"):
        old.unlink(missing_ok=True)
    stored = f"{clip_id}{ext}"
    await _store_upload(file, found.clip_images_dir / stored)
    clip["image"] = stored
    found.save()
    return {"clip": clip}


@router.delete("/projects/{project_id}/clips/{clip_id}/image")
def delete_clip_image(project_id: str, clip_id: str):
    found = _project(project_id)
    clip = found.clip(clip_id)
    if not clip:
        raise HTTPException(404, "Clip introuvable")
    for old in found.clip_images_dir.glob(f"{clip_id}.*"):
        old.unlink(missing_ok=True)
    clip["image"] = None
    found.save()
    return {"clip": clip}


@router.get("/projects/{project_id}/clips/{clip_id}/image")
def get_clip_image(project_id: str, clip_id: str, request: Request):
    found = _project(project_id)
    path = found.clip_image(clip_id)
    if not path:
        raise HTTPException(404, "Pas d'image")
    return _ranged_file(path, request)


# --------------------------------------------------------------------------
# Pack chatter : fichiers audio libres
# --------------------------------------------------------------------------

@router.post("/projects/{project_id}/chatter")
async def upload_chatter(project_id: str, file: UploadFile = File(...)):
    found = _project(project_id)
    ext = _safe_ext(file.filename, SOURCE_AUDIO_EXTS)
    entry_id = uuid.uuid4().hex[:8]
    stored = f"chatter_{entry_id}{ext}"
    await _store_upload(file, found.assets_dir / stored)
    entry = {"id": entry_id, "name": Path(file.filename).stem, "stored": stored,
             "keywords": [], "mode": "broad"}
    found.data.setdefault("chatter", []).append(entry)
    found.save()
    return {"chatter": found.data["chatter"]}


@router.delete("/projects/{project_id}/chatter/{entry_id}")
def delete_chatter(project_id: str, entry_id: str):
    found = _project(project_id)
    entries = found.data.get("chatter", [])
    entry = next((e for e in entries if e["id"] == entry_id), None)
    if entry:
        (found.assets_dir / entry["stored"]).unlink(missing_ok=True)
        found.data["chatter"] = [e for e in entries if e["id"] != entry_id]
        found.save()
    return {"chatter": found.data.get("chatter", [])}


@router.get("/projects/{project_id}/chatter/{entry_id}/file")
def get_chatter_file(project_id: str, entry_id: str, request: Request):
    found = _project(project_id)
    entry = next((e for e in found.data.get("chatter", []) if e["id"] == entry_id), None)
    if not entry:
        raise HTTPException(404, "Son introuvable")
    return _ranged_file(found.assets_dir / entry["stored"], request)


# --------------------------------------------------------------------------
# Generation / installation
# --------------------------------------------------------------------------

def _build(job, project_id: str) -> dict:
    found = _project(project_id)
    return builder.build(found, progress=lambda f, m="": job.progress(f, m))


@router.post("/projects/{project_id}/build")
def start_build(project_id: str):
    _project(project_id)
    return {"job": jobs.submit("Generation du pack", _build, project_id)}


@router.post("/projects/{project_id}/install")
async def install_pack(project_id: str, request: Request):
    found = _project(project_id)
    payload = await request.json() if await request.body() else {}
    try:
        return builder.install(found, overwrite=bool(payload.get("overwrite")))
    except builder.BuildError as exc:
        raise HTTPException(400, str(exc))


@router.get("/projects/{project_id}/zip")
def download_zip(project_id: str):
    found = _project(project_id)
    try:
        archive = builder.zip_pack(found)
    except builder.BuildError as exc:
        raise HTTPException(400, str(exc))
    return FileResponse(archive, filename=archive.name, media_type="application/zip")


@router.get("/projects/{project_id}/preview-config")
def preview_config(project_id: str):
    """Apercu du fichier de config qui sera ecrit."""
    found = _project(project_id)
    spec = SPECS[found.type]
    if found.type == "chatter":
        meta = found.data.get("meta", {})
        exact, broad = {}, {}
        for entry in found.data.get("chatter", []):
            keywords = [k for k in entry.get("keywords", []) if k]
            if not keywords:
                continue
            name = projects.safe_name(entry.get("name") or entry["stored"]) + ".ogg"
            (exact if entry.get("mode") == "exact" else broad)[name] = keywords
        text = inifmt.chatter_config(
            title=meta.get("title") or found.data.get("name", ""),
            authors=meta.get("authors") or [],
            volume=float(found.data.get("config", {}).get("volume") or 1.0),
            exact=exact, broad=broad,
        )
        return {"filename": "config_chatter.ini", "content": text}
    if found.type == "voice":
        meta = found.data.get("meta", {})
        text = inifmt.pack_info(
            title=meta.get("title") or found.data.get("name", ""),
            subtitle=meta.get("subtitle", ""),
            authors=meta.get("authors") or [],
            readme=meta.get("readme", ""),
        )
        return {"filename": "_pack_info.ini", "content": text}
    return {
        "filename": spec.get("config_file") or "",
        "content": json.dumps(builder.build_config(found), indent="\t", ensure_ascii=False),
    }


# --------------------------------------------------------------------------
# Taches de fond
# --------------------------------------------------------------------------

@router.get("/jobs/{job_id}")
def job_status(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Tache inconnue")
    jobs.prune()
    return job


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str):
    return {"cancelled": jobs.cancel(job_id)}
