"""Import d'une video en ligne via yt-dlp.

Fonctionne avec le module Python `yt_dlp` s'il est installe, sinon avec
l'executable `yt-dlp` present dans le PATH.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from . import settings

_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0

VIDEO_FORMAT = "bestvideo[height<=?1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=?1080]+bestaudio/best"
AUDIO_FORMAT = "bestaudio/best"


class DownloadError(RuntimeError):
    pass


def _module():
    try:
        import yt_dlp
        return yt_dlp
    except ImportError:
        return None


def _binary() -> str | None:
    return shutil.which("yt-dlp") or shutil.which("yt-dlp.exe")


def status() -> dict:
    module = _module()
    version = ""
    if module is not None:
        version = getattr(module, "version", None)
        version = getattr(version, "__version__", "") if version else ""
    return {
        "available": module is not None or _binary() is not None,
        "module": module is not None,
        "binary": _binary() or "",
        "version": version,
    }


def _ffmpeg_dir() -> str:
    path = Path(settings.binary("ffmpeg"))
    return str(path.parent) if path.parent.name else ""


# --------------------------------------------------------------------------
# Informations
# --------------------------------------------------------------------------

def probe_url(url: str) -> dict:
    module = _module()
    if module is not None:
        options = {"quiet": True, "no_warnings": True, "noplaylist": True,
                   "skip_download": True}
        try:
            with module.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception as exc:  # noqa: BLE001 - yt-dlp remonte des erreurs variees
            raise DownloadError(str(exc)) from exc
    else:
        binary = _binary()
        if not binary:
            raise DownloadError(
                "yt-dlp n'est pas installe. Lance : pip install yt-dlp"
            )
        proc = subprocess.run(
            [binary, "--dump-single-json", "--no-playlist", url],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            creationflags=_NO_WINDOW, check=False,
        )
        if proc.returncode != 0:
            raise DownloadError(proc.stderr.decode("utf-8", "replace")[-500:])
        info = json.loads(proc.stdout.decode("utf-8", "replace"))

    if info.get("_type") == "playlist":
        entries = info.get("entries") or []
        if not entries:
            raise DownloadError("Cette URL ne contient aucune video.")
        info = entries[0]

    return {
        "id": info.get("id", ""),
        "title": info.get("title", ""),
        "uploader": info.get("uploader") or info.get("channel") or "",
        "duration": float(info.get("duration") or 0),
        "thumbnail": info.get("thumbnail", ""),
        "webpage_url": info.get("webpage_url", url),
        "is_live": bool(info.get("is_live")),
    }


# --------------------------------------------------------------------------
# Telechargement
# --------------------------------------------------------------------------

def download(url: str, destination: Path, mode: str = "video",
             progress_cb=None) -> Path:
    """Telecharge dans destination sous le nom source.<ext>. Retourne le chemin."""
    destination.mkdir(parents=True, exist_ok=True)
    for old in destination.glob("source.*"):
        old.unlink(missing_ok=True)

    fmt = AUDIO_FORMAT if mode == "audio" else VIDEO_FORMAT
    template = str(destination / "source.%(ext)s")

    module = _module()
    if module is not None:
        _download_with_module(module, url, fmt, template, mode, progress_cb)
    else:
        _download_with_binary(url, fmt, template, mode, progress_cb)

    files = sorted(destination.glob("source.*"))
    files = [f for f in files if f.suffix.lower() not in (".part", ".ytdl")]
    if not files:
        raise DownloadError("Le telechargement n'a produit aucun fichier.")
    return files[0]


def _download_with_module(module, url, fmt, template, mode, progress_cb) -> None:
    def hook(status_dict):
        if not progress_cb:
            return
        if status_dict.get("status") == "downloading":
            total = status_dict.get("total_bytes") or status_dict.get("total_bytes_estimate")
            done = status_dict.get("downloaded_bytes") or 0
            if total:
                progress_cb(min(0.99, done / total), "Telechargement")
        elif status_dict.get("status") == "finished":
            progress_cb(1.0, "Assemblage")

    options = {
        "format": fmt,
        "outtmpl": template,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [hook],
        "retries": 3,
        "overwrites": True,
    }
    if mode != "audio":
        options["merge_output_format"] = "mp4"
    ffmpeg_dir = _ffmpeg_dir()
    if ffmpeg_dir:
        options["ffmpeg_location"] = ffmpeg_dir

    try:
        with module.YoutubeDL(options) as ydl:
            ydl.download([url])
    except Exception as exc:  # noqa: BLE001
        raise DownloadError(str(exc)) from exc


SUBTITLE_LANGS = ["fr", "fr-FR", "fr-orig", "fr-ca", "en", "en-orig"]


def find_subtitles(destination: Path, langs: list[str] | None = None) -> dict | None:
    """Meilleur fichier de sous-titres deja present dans un dossier.

    Retourne {"lang", "path"} ou None. La langue voulue passe avant, puis le
    format le plus riche.
    """
    langs = langs or SUBTITLE_LANGS
    files = [f for f in Path(destination).glob("subs.*")
             if f.suffix.lower() in (".json3", ".vtt", ".srt", ".json")]
    if not files:
        return None

    def rank(path: Path) -> tuple:
        # subs.fr.json3 -> parties = ['subs', 'fr', 'json3']
        parts = path.name.split(".")
        lang = parts[1] if len(parts) > 2 else ""
        try:
            language_rank = langs.index(lang)
        except ValueError:
            language_rank = len(langs)
        format_rank = {".json3": 0, ".vtt": 1, ".srt": 2}.get(path.suffix.lower(), 3)
        return (language_rank, format_rank)

    best = sorted(files, key=rank)[0]
    parts = best.name.split(".")
    return {"lang": parts[1] if len(parts) > 2 else "", "path": str(best)}


def fetch_subtitles(url: str, destination: Path,
                    langs: list[str] | None = None) -> dict | None:
    """Recupere les sous-titres (officiels d'abord, sinon automatiques).

    Retourne {"lang", "path"} ou None si la video n'en a pas.
    """
    langs = langs or SUBTITLE_LANGS
    destination.mkdir(parents=True, exist_ok=True)
    for old in destination.glob("subs.*"):
        old.unlink(missing_ok=True)
    template = str(destination / "subs.%(ext)s")

    module = _module()
    options = {
        "skip_download": True,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": langs,
        "subtitlesformat": "json3/vtt/srt/best",
        "outtmpl": template,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
    }
    # yt-dlp ecrit les fichiers langue par langue, puis peut echouer sur la
    # suivante — ou sur la video elle-meme. L'erreur ne dit donc rien de ce
    # qui est deja sur le disque : on regarde le dossier dans tous les cas.
    try:
        if module is not None:
            with module.YoutubeDL(options) as ydl:
                ydl.download([url])
        else:
            binary = _binary()
            if not binary:
                return None
            command = [binary, "--skip-download", "--write-subs", "--write-auto-subs",
                       "--sub-langs", ",".join(langs), "--sub-format", "json3/vtt/srt/best",
                       "--no-playlist", "-o", template, url]
            subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           creationflags=_NO_WINDOW, check=False)
    except Exception:  # noqa: BLE001 - l'absence de sous-titres ne doit rien casser
        pass

    return find_subtitles(destination, langs)


_PERCENT_RE = re.compile(r"\[download\]\s+([\d.]+)%")


def _download_with_binary(url, fmt, template, mode, progress_cb) -> None:
    binary = _binary()
    if not binary:
        raise DownloadError("yt-dlp n'est pas installe. Lance : pip install yt-dlp")
    command = [binary, "-f", fmt, "--no-playlist", "--force-overwrites",
               "-o", template, "--newline"]
    if mode != "audio":
        command += ["--merge-output-format", "mp4"]
    ffmpeg_dir = _ffmpeg_dir()
    if ffmpeg_dir:
        command += ["--ffmpeg-location", ffmpeg_dir]
    command.append(url)

    process = subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        creationflags=_NO_WINDOW, text=True, encoding="utf-8", errors="replace",
    )
    tail: list[str] = []
    assert process.stdout is not None
    for line in process.stdout:
        tail.append(line)
        del tail[:-15]
        match = _PERCENT_RE.search(line)
        if match and progress_cb:
            progress_cb(min(0.99, float(match.group(1)) / 100.0), "Telechargement")
    process.wait()
    if process.returncode != 0:
        raise DownloadError("".join(tail)[-600:] or "yt-dlp a echoue.")
