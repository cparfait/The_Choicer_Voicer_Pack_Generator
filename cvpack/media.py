"""Toutes les operations ffmpeg : analyse, decoupe, normalisation, conversion."""

from __future__ import annotations

import array
import json
import re
import subprocess
import sys
from pathlib import Path

from . import settings

_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


class MediaError(RuntimeError):
    pass


def _run(cmd: list[str], capture_stderr=True) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE if capture_stderr else None,
            creationflags=_NO_WINDOW,
            check=False,
        )
    except OSError as exc:
        raise MediaError(
            f"Impossible de lancer « {cmd[0]} » ({exc.strerror or exc}). "
            f"Verifie le chemin de ffmpeg dans les Reglages : il doit pointer vers "
            f"l'executable ou vers le dossier qui le contient."
        ) from exc


def check_tools() -> dict:
    result = {}
    for name in ("ffmpeg", "ffprobe"):
        path = settings.binary(name)
        ok, version = False, ""
        try:
            proc = _run([path, "-version"])
            ok = proc.returncode == 0
            if ok:
                first = proc.stdout.decode("utf-8", "replace").splitlines()
                version = first[0] if first else ""
            else:
                version = proc.stderr.decode("utf-8", "replace")[-200:]
        except (MediaError, OSError) as exc:
            version = str(exc)
        result[name] = {"path": path, "ok": ok, "version": version}
    return result


def probe(path: Path | str) -> dict:
    """Metadonnees d'un fichier media."""
    proc = _run([
        settings.binary("ffprobe"), "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", str(path),
    ])
    if proc.returncode != 0:
        raise MediaError(proc.stderr.decode("utf-8", "replace")[-600:] or "ffprobe a echoue")
    data = json.loads(proc.stdout.decode("utf-8", "replace") or "{}")
    streams = data.get("streams", [])
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    duration = 0.0
    for candidate in (data.get("format", {}).get("duration"),
                      (audio or {}).get("duration"), (video or {}).get("duration")):
        try:
            duration = float(candidate)
            break
        except (TypeError, ValueError):
            continue
    return {
        "duration": duration,
        "has_audio": audio is not None,
        "has_video": video is not None and (video.get("disposition", {}).get("attached_pic") != 1),
        "audio_codec": (audio or {}).get("codec_name", ""),
        "video_codec": (video or {}).get("codec_name", ""),
        "sample_rate": int((audio or {}).get("sample_rate") or 0),
        "channels": int((audio or {}).get("channels") or 0),
        "width": int((video or {}).get("width") or 0),
        "height": int((video or {}).get("height") or 0),
        "size": int(data.get("format", {}).get("size") or 0),
    }


def duration_of(path: Path | str) -> float:
    return probe(path)["duration"]


# --------------------------------------------------------------------------
# Preparation de la source
# --------------------------------------------------------------------------

def extract_master_audio(src: Path, dst: Path) -> None:
    """Piste audio de travail : WAV 48 kHz mono, sans perte supplementaire."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    proc = _run([
        settings.binary("ffmpeg"), "-y", "-i", str(src), "-vn",
        "-ac", "1", "-ar", "48000", "-c:a", "pcm_s16le", str(dst),
    ])
    if proc.returncode != 0:
        raise MediaError(proc.stderr.decode("utf-8", "replace")[-800:])


def make_preview(src: Path, dst: Path) -> None:
    """Version compressee pour la lecture dans le navigateur."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    proc = _run([
        settings.binary("ffmpeg"), "-y", "-i", str(src), "-vn",
        "-ac", "1", "-ar", "44100", "-c:a", "libvorbis", "-q:a", "3", str(dst),
    ])
    if proc.returncode != 0:
        raise MediaError(proc.stderr.decode("utf-8", "replace")[-800:])


def compute_peaks(src: Path, buckets: int = 4000) -> list[float]:
    """Enveloppe de la forme d'onde, normalisee entre 0 et 1."""
    rate = 8000
    proc = _run([
        settings.binary("ffmpeg"), "-v", "error", "-i", str(src), "-vn",
        "-ac", "1", "-ar", str(rate), "-f", "s16le", "-",
    ])
    if proc.returncode != 0:
        raise MediaError(proc.stderr.decode("utf-8", "replace")[-800:])
    samples = array.array("h")
    raw = proc.stdout
    samples.frombytes(raw[: len(raw) - (len(raw) % 2)])
    if not samples:
        return []
    buckets = max(1, min(buckets, len(samples)))
    step = len(samples) / buckets
    peaks = []
    for i in range(buckets):
        start = int(i * step)
        end = max(start + 1, int((i + 1) * step))
        window = samples[start:end]
        peaks.append(max(abs(min(window)), abs(max(window))) / 32768.0)
    return [round(p, 4) for p in peaks]


# --------------------------------------------------------------------------
# Detection de silences et decoupage
# --------------------------------------------------------------------------

_SILENCE_START = re.compile(r"silence_start:\s*(-?[\d.]+)")
_SILENCE_END = re.compile(r"silence_end:\s*(-?[\d.]+)")


def detect_silences(src: Path, noise_db: float = -32.0,
                    min_silence: float = 0.35) -> list[tuple[float, float]]:
    proc = _run([
        settings.binary("ffmpeg"), "-i", str(src),
        "-af", f"silencedetect=noise={noise_db}dB:d={min_silence}",
        "-f", "null", "-",
    ])
    text = proc.stderr.decode("utf-8", "replace")
    silences: list[tuple[float, float]] = []
    pending: float | None = None
    for line in text.splitlines():
        start = _SILENCE_START.search(line)
        if start:
            pending = max(0.0, float(start.group(1)))
        end = _SILENCE_END.search(line)
        if end and pending is not None:
            silences.append((pending, float(end.group(1))))
            pending = None
    return silences


def split_points(start: float, end: float, max_len: float,
                 pauses: list[tuple[float, float]] | None = None,
                 floor: float = 0.4) -> list[float]:
    """Ou couper un passage trop long, du silence le plus large vers le moins.

    Couper en parts egales tombe au milieu d'un mot une fois sur deux. Quand
    on connait les silences de la source, on coupe dedans : le clip commence
    et finit sur une respiration.
    """
    if max_len <= 0 or end - start <= max_len:
        return []
    cut = _widest_pause(start, end, pauses or [], floor)
    if cut is None:
        # Aucun silence exploitable : parts egales, faute de mieux.
        pieces = int((end - start) // max_len) + (1 if (end - start) % max_len else 0)
        step = (end - start) / pieces
        return [start + i * step for i in range(1, pieces)]
    return sorted(split_points(start, cut, max_len, pauses, floor)
                  + [cut]
                  + split_points(cut, end, max_len, pauses, floor))


def _widest_pause(start: float, end: float, pauses: list[tuple[float, float]],
                  floor: float) -> float | None:
    """Milieu du plus large silence utilisable dans [start, end]."""
    best, best_width = None, 0.0
    for pause_start, pause_end in pauses:
        left = max(pause_start, start + floor)
        right = min(pause_end, end - floor)
        if right - left <= 0:
            continue
        width = right - left
        # A largeur egale, le silence le plus central partage le mieux.
        score = width - abs((left + right) / 2 - (start + end) / 2) / 100.0
        if score > best_width:
            best, best_width = (left + right) / 2, score
    return best


def segments_from_silences(duration: float, silences: list[tuple[float, float]],
                           min_len: float = 0.7, max_len: float = 6.0,
                           pad: float = 0.08,
                           pauses: list[tuple[float, float]] | None = None) -> list[dict]:
    """Transforme les zones de silence en segments parlants exploitables."""
    speech: list[list[float]] = []
    cursor = 0.0
    for start, end in silences:
        if start > cursor:
            speech.append([cursor, min(start, duration)])
        cursor = max(cursor, end)
    if cursor < duration:
        speech.append([cursor, duration])

    segments: list[dict] = []
    for start, end in speech:
        start = max(0.0, start - pad)
        end = min(duration, end + pad)
        length = end - start
        if length < min_len:
            continue
        if length <= max_len:
            segments.append({"start": start, "end": end})
            continue
        # Segment trop long : on le coupe dans ses silences internes.
        edges = [start] + split_points(start, end, max_len, pauses) + [end]
        for left, right in zip(edges, edges[1:]):
            segments.append({"start": round(left, 3), "end": round(right, 3)})
    return [{"start": round(s["start"], 3), "end": round(s["end"], 3)} for s in segments]


# --------------------------------------------------------------------------
# Export
# --------------------------------------------------------------------------

def _encode_args(fmt: str) -> list[str]:
    if fmt == "wav":
        return ["-c:a", "pcm_s16le"]
    if fmt == "mp3":
        return ["-c:a", "libmp3lame", "-q:a", "2"]
    return ["-c:a", "libvorbis", "-q:a", "5"]


def export_clip(src: Path, dst: Path, start: float, end: float,
                fmt: str = "ogg", normalize: bool = True,
                target_lufs: float = -16.0, fade_ms: int = 8,
                gain_db: float = 0.0) -> None:
    """Extrait [start, end] de src vers dst, normalise et fondu aux extremites."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    length = max(0.05, end - start)
    filters = []
    if abs(gain_db) > 0.01:
        filters.append(f"volume={gain_db}dB")
    if normalize:
        filters.append(f"loudnorm=I={target_lufs}:TP=-1.0:LRA=11")
    if fade_ms > 0:
        fade = fade_ms / 1000.0
        filters.append(f"afade=t=in:st=0:d={fade}")
        filters.append(f"afade=t=out:st={max(0.0, length - fade):.3f}:d={fade}")
    cmd = [
        settings.binary("ffmpeg"), "-y",
        "-ss", f"{start:.3f}", "-t", f"{length:.3f}", "-i", str(src), "-vn",
    ]
    if filters:
        cmd += ["-af", ",".join(filters)]
    cmd += ["-ar", "48000", "-ac", "1"] + _encode_args(fmt) + [str(dst)]
    proc = _run(cmd)
    if proc.returncode != 0:
        raise MediaError(proc.stderr.decode("utf-8", "replace")[-800:])


def convert_audio(src: Path, dst: Path, fmt: str = "ogg",
                  normalize: bool = False, target_lufs: float = -16.0) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = [settings.binary("ffmpeg"), "-y", "-i", str(src), "-vn"]
    if normalize:
        cmd += ["-af", f"loudnorm=I={target_lufs}:TP=-1.0:LRA=11"]
    cmd += _encode_args(fmt) + [str(dst)]
    proc = _run(cmd)
    if proc.returncode != 0:
        raise MediaError(proc.stderr.decode("utf-8", "replace")[-800:])


def convert_image(src: Path, dst: Path, max_size: int | None = None) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = [settings.binary("ffmpeg"), "-y", "-i", str(src)]
    if max_size:
        cmd += ["-vf", f"scale='min({max_size},iw)':-1"]
    cmd += ["-frames:v", "1", str(dst)]
    proc = _run(cmd)
    if proc.returncode != 0:
        raise MediaError(proc.stderr.decode("utf-8", "replace")[-800:])


def alpha_info(src: Path) -> dict:
    """Ce que la couche alpha d'une image raconte.

    Retourne {"bounds", "transparent", "height"} : le rectangle reellement
    dessine (None s'il occupe tout le cadre), la part de pixels vides, et la
    hauteur de ce rectangle. Sert a poser un personnage sur le sol du plateau.
    """
    info = probe(src)
    width, height = info["width"], info["height"]
    empty = {"bounds": None, "transparent": 0.0, "height": height}
    if not width or not height:
        return empty
    proc = _run([
        settings.binary("ffmpeg"), "-v", "error", "-i", str(src),
        "-vf", "alphaextract,format=gray", "-f", "rawvideo", "-",
    ])
    raw = proc.stdout
    if proc.returncode != 0 or len(raw) < width * height:
        return empty

    opaque = 8  # en dessous, le pixel est considere comme vide
    rows = [y for y in range(height) if max(raw[y * width:(y + 1) * width]) > opaque]
    if not rows:
        return empty
    columns = [x for x in range(width) if max(raw[x::width]) > opaque]
    left, right, top, bottom = columns[0], columns[-1], rows[0], rows[-1]
    transparent = sum(1 for value in raw[:width * height] if value <= opaque)
    full_frame = (left, top, right, bottom) == (0, 0, width - 1, height - 1)
    return {
        "bounds": None if full_frame else (left, top, right - left + 1, bottom - top + 1),
        "transparent": transparent / (width * height),
        "height": bottom - top + 1,
    }


def fit_stage_image(src: Path, dst: Path, height: int,
                    bounds: tuple[int, int, int, int] | None = None) -> None:
    """Rogne les marges transparentes, puis met a la hauteur voulue.

    Le jeu pose le bas de l'image sur le sol du plateau : une marge
    transparente sous les pieds ferait flotter le personnage, et une image
    trop courte le laisserait derriere le pupitre.
    """
    dst.parent.mkdir(parents=True, exist_ok=True)
    filters = []
    if bounds:
        x, y, w, h = bounds
        filters.append(f"crop={w}:{h}:{x}:{y}")
    filters.append(f"scale=-1:{height}:flags=lanczos")
    proc = _run([
        settings.binary("ffmpeg"), "-y", "-i", str(src),
        "-vf", ",".join(filters), "-frames:v", "1", str(dst),
    ])
    if proc.returncode != 0:
        raise MediaError(proc.stderr.decode("utf-8", "replace")[-800:])


def extract_frame(src: Path, time: float, dst: Path, width: int = 640) -> None:
    """Une image fixe prise a `time` secondes."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    proc = _run([
        settings.binary("ffmpeg"), "-y", "-ss", f"{max(0.0, time):.3f}", "-i", str(src),
        "-frames:v", "1", "-vf", f"scale={width}:-2", "-q:v", "3", str(dst),
    ])
    if proc.returncode != 0:
        raise MediaError(proc.stderr.decode("utf-8", "replace")[-500:])


def to_ogv(src: Path, dst: Path, quality: int = 7, max_height: int = 720,
           mute: bool = True, progress_cb=None) -> None:
    """Conversion en OGV/Theora — le seul format video lu par Godot."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    total = 0.0
    try:
        total = probe(src)["duration"]
    except MediaError:
        pass
    cmd = [
        settings.binary("ffmpeg"), "-y", "-i", str(src),
        "-c:v", "libtheora", "-q:v", str(quality),
        "-vf", f"scale=-2:'min({max_height},ih)'",
    ]
    cmd += ["-an"] if mute else ["-c:a", "libvorbis", "-q:a", "4"]
    cmd += ["-progress", "pipe:1", "-nostats", str(dst)]

    process = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        creationflags=_NO_WINDOW, text=True, encoding="utf-8", errors="replace",
    )
    assert process.stdout is not None
    for line in process.stdout:
        if progress_cb and line.startswith("out_time_ms=") and total > 0:
            try:
                done = int(line.split("=", 1)[1]) / 1_000_000.0
                progress_cb(min(0.99, done / total))
            except ValueError:
                pass
    process.wait()
    if process.returncode != 0:
        err = process.stderr.read() if process.stderr else ""
        raise MediaError(err[-800:] or "La conversion OGV a echoue.")
    if progress_cb:
        progress_cb(1.0)


def copy_media(src: Path, dst: Path) -> None:
    """Copie brute quand le format est deja accepte par le jeu."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(Path(src).read_bytes())
