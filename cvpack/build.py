"""Generation des packs sur disque, installation dans le jeu et validation."""

from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path

from . import inifmt, media, settings
from .project import Project, safe_name
from .specs import IMAGE_EXTS, PLAYER_AUDIO_SLOTS, SPECS

MAX_CLIP_SECONDS = 60.0
MAX_DUB_CLIP_SECONDS = 6.0


class BuildError(RuntimeError):
    pass


def _noop(fraction: float, message: str = "") -> None:
    return None


# --------------------------------------------------------------------------
# Configs JSON
# --------------------------------------------------------------------------

def _set_path(target: dict, dotted: str, value) -> None:
    parts = dotted.split(".")
    node = target
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    node[parts[-1]] = value


def _coerce(field: dict, value):
    if value is None:
        value = field.get("default")
    kind = field["type"]
    if kind == "bool":
        return bool(value)
    if kind == "number":
        try:
            number = float(value)
        except (TypeError, ValueError):
            number = float(field.get("default") or 0)
        return int(number) if number.is_integer() and abs(number) < 1e9 and \
            isinstance(field.get("default"), int) else number
    if kind == "select":
        options = [o["value"] for o in field.get("options", [])]
        return value if value in options else field.get("default")
    if kind in ("color", "color8"):
        text = str(value or field.get("default") or "").lstrip("#")
        return text.lower()
    return "" if value is None else str(value)


def build_config(project: Project) -> dict:
    """Construit le dict JSON de config a partir des champs de la spec."""
    spec = SPECS[project.type]
    values = project.data.get("config", {})
    config: dict = {}
    for field in spec.get("fields", []):
        _set_path(config, field["key"], _coerce(field, values.get(field["key"])))

    if project.type == "player":
        assignment = {}
        for key, _label in PLAYER_AUDIO_SLOTS:
            asset = project.asset(f"audio_{key}")
            assignment[key] = Path(asset).stem if asset else ""
        config["audio_assignment"] = assignment

    if project.type == "host":
        dialog = project.data.get("host_dialog", {}) or {}
        config = {
            "host_type": dialog.get("host_type", "basic"),
            "name": values.get("name") or dialog.get("name") or "Animateur",
        }
        for section in ("match_singleplayer", "match_multiplayer", "twitch_standard"):
            if section in dialog:
                config[section] = dialog[section]

    if project.type == "studio":
        config.setdefault("audio", {})["music_studio_loop_start_README"] = (
            "For WAV, the start must be the SAMPLE. For MP3 and OGG, it must be the TIME, in seconds."
        )
    if project.type == "menu":
        config.setdefault("audio", {})["music_menu_loop_start_README"] = (
            "For WAV, the start must be the SAMPLE. For MP3 and OGG, it must be the TIME, in seconds."
        )
    return config


# --------------------------------------------------------------------------
# Noms de clips
# --------------------------------------------------------------------------

def clip_filenames(project: Project) -> dict[str, str]:
    """Nom de fichier final (sans extension) pour chaque clip actif."""
    clips = [c for c in project.data.get("clips", []) if c.get("enabled", True)]
    numbering = project.data.get("options", {}).get("numbering", True)
    is_dub = bool(project.data.get("dub", {}).get("enabled"))
    width = max(2, len(str(len(clips))))
    used: set[str] = set()
    names: dict[str, str] = {}
    for index, clip in enumerate(clips, start=1):
        base = safe_name(clip.get("name") or f"clip{index}", f"clip{index}")
        if numbering:
            base = f"{index:0{width}d}_{base}"
        if is_dub and project.data.get("options", {}).get("timestamp_suffix", False):
            stamp = f"{float(clip.get('start', 0)):.3f}".replace(".", "-")
            base = f"{base}_{stamp}"
        candidate = base
        suffix = 2
        while candidate.lower() in used:
            candidate = f"{base}_{suffix}"
            suffix += 1
        used.add(candidate.lower())
        names[clip["id"]] = candidate
    return names


# --------------------------------------------------------------------------
# Construction
# --------------------------------------------------------------------------

def output_dir(project: Project) -> Path:
    return project.build_dir / safe_name(project.data.get("name") or "Pack")


def build(project: Project, progress=_noop) -> dict:
    target = output_dir(project)
    if target.exists():
        shutil.rmtree(target, ignore_errors=True)
    target.mkdir(parents=True, exist_ok=True)

    warnings: list[str] = []
    written: list[str] = []

    if project.type == "voice":
        _build_voice(project, target, warnings, written, progress)
    elif project.type == "chatter":
        _build_chatter(project, target, warnings, written, progress)
    else:
        _build_simple(project, target, warnings, written, progress)

    report = {
        "path": str(target),
        "files": written,
        "warnings": warnings,
        "file_count": len(written),
    }
    project.data["build"] = {
        "path": str(target),
        "file_count": len(written),
        "warnings": warnings,
    }
    project.save()
    progress(1.0, "Termine")
    return report


def _copy_asset(project: Project, slot: str, target: Path, base_name: str,
                written: list[str], warnings: list[str],
                force_ext: str | None = None) -> str | None:
    source = project.asset(slot)
    if not source:
        return None
    ext = force_ext or source.suffix.lower()
    destination = target / f"{base_name}{ext}"
    try:
        media.copy_media(source, destination)
    except OSError as exc:
        warnings.append(f"Impossible de copier {slot} : {exc}")
        return None
    written.append(destination.name)
    return destination.name


def _build_voice(project: Project, target: Path, warnings: list[str],
                 written: list[str], progress) -> None:
    source = project.master_audio if project.master_audio.exists() else project.source_path()
    clips = [c for c in project.data.get("clips", []) if c.get("enabled", True)]
    if clips and not (source and Path(source).exists()):
        raise BuildError("Le fichier source est introuvable : reimporte-le avant de generer.")

    names = clip_filenames(project)
    fmt = project.data.get("options", {}).get("clip_format") or settings.get("clip_format")
    normalize = project.data.get("options", {}).get("normalize")
    if normalize is None:
        normalize = settings.get("normalize")
    target_lufs = float(settings.get("target_lufs"))
    is_dub = bool(project.data.get("dub", {}).get("enabled"))

    total_steps = max(1, len(clips) + 3)
    step = 0

    for clip in clips:
        step += 1
        base = names[clip["id"]]
        progress(step / total_steps, f"Clip {base}")
        length = float(clip["end"]) - float(clip["start"])
        limit = MAX_DUB_CLIP_SECONDS if is_dub else MAX_CLIP_SECONDS
        if length > limit:
            warnings.append(
                f"{base} dure {length:.1f} s (limite conseillee : {limit:.0f} s)."
            )
        try:
            media.export_clip(
                Path(source), target / f"{base}.{fmt}",
                float(clip["start"]), float(clip["end"]),
                fmt=fmt, normalize=bool(normalize), target_lufs=target_lufs,
                gain_db=float(clip.get("gain_db") or 0.0),
            )
        except media.MediaError as exc:
            warnings.append(f"Echec de l'export de {base} : {exc}")
            continue
        written.append(f"{base}.{fmt}")

        image = project.clip_image(clip["id"])
        image_name = ""
        if image:
            destination = target / f"{base}{image.suffix.lower()}"
            media.copy_media(image, destination)
            written.append(destination.name)
            # Le jeu cherche ce nom dans le pack : c'est celui du fichier
            # copie, pas celui du fichier de travail.
            image_name = destination.name

        caption = (clip.get("caption") or "").strip()
        timestamps = clip.get("dub_timestamps") or ([round(float(clip["start"]), 3)] if is_dub else [])
        characters = [c for c in (clip.get("characters") or []) if c]
        needs_ini = bool(timestamps or characters or clip.get("dub_only"))
        if needs_ini:
            content = inifmt.clip_metadata(
                caption=caption,
                image=image_name,
                dub_timestamps=timestamps,
                dub_characters=characters,
                dub_only=bool(clip.get("dub_only")),
            )
            (target / f"{base}.ini").write_text(content, encoding="utf-8")
            written.append(f"{base}.ini")
        elif caption:
            # Un .txt seul a cote d'un clip = sous-titre en clair.
            (target / f"{base}.txt").write_text(caption, encoding="utf-8")
            written.append(f"{base}.txt")

    step += 1
    progress(step / total_steps, "Metadonnees du pack")
    meta = project.data.get("meta", {})
    icon_name = _copy_asset(project, "_icon", target, "_icon", written, warnings)
    _copy_asset(project, "_pack_filler_image", target, "_pack_filler_image", written, warnings)

    info = inifmt.pack_info(
        title=meta.get("title") or project.data.get("name", ""),
        subtitle=meta.get("subtitle", ""),
        icon=icon_name or "",
        authors=meta.get("authors") or [],
        readme=meta.get("readme", ""),
    )
    (target / "_pack_info.ini").write_text(info, encoding="utf-8")
    written.append("_pack_info.ini")

    # Fichiers redondants mais lus par toutes les versions du jeu.
    authors = [a for a in (meta.get("authors") or []) if a]
    if authors:
        (target / "_author.txt").write_text(", ".join(authors), encoding="utf-8")
        written.append("_author.txt")
    if meta.get("subtitle"):
        (target / "_subtitle.txt").write_text(meta["subtitle"], encoding="utf-8")
        written.append("_subtitle.txt")
    if meta.get("readme"):
        (target / "_readme.txt").write_text(meta["readme"], encoding="utf-8")
        written.append("_readme.txt")

    step += 1
    progress(step / total_steps, "Piste d'ambiance")
    backing = project.asset("_backing_track")
    if backing:
        destination = target / f"_backing_track.{fmt}"
        try:
            media.convert_audio(backing, destination, fmt=fmt, normalize=False)
            written.append(destination.name)
        except media.MediaError as exc:
            warnings.append(f"Piste d'ambiance non convertie : {exc}")

    step += 1
    if is_dub:
        progress(step / total_steps, "Conversion de la video (OGV)")
        video = _dub_video_source(project)
        if not video:
            warnings.append(
                "Mode Dub actif mais aucune video source : le pack ne sera pas reconnu "
                "comme pack Dub tant que dub_video.ogv est absent."
            )
        else:
            destination = target / "dub_video.ogv"
            try:
                if video.suffix.lower() == ".ogv":
                    media.copy_media(video, destination)
                else:
                    media.to_ogv(
                        video, destination,
                        quality=int(project.data.get("options", {}).get("ogv_quality", 7)),
                        max_height=int(project.data.get("options", {}).get("ogv_height", 720)),
                        progress_cb=lambda f: progress(
                            (step - 1 + f) / total_steps, f"Conversion OGV {int(f * 100)} %"
                        ),
                    )
                written.append("dub_video.ogv")
            except media.MediaError as exc:
                warnings.append(f"Conversion OGV impossible : {exc}")

        # Feuille de route des timestamps, a saisir dans l'editeur du jeu si besoin.
        lines = ["# Timestamps du pack Dub (secondes sur la timeline video)", ""]
        for clip in clips:
            base = names[clip["id"]]
            stamps = clip.get("dub_timestamps") or [round(float(clip["start"]), 3)]
            lines.append(f"{base}\t" + ", ".join(f"{float(s):.3f}" for s in stamps))
        (target / "_dub_timestamps.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        written.append("_dub_timestamps.md")


def _dub_video_source(project: Project) -> Path | None:
    explicit = project.asset("dub_video")
    if explicit:
        return explicit
    source = project.source_path()
    if source and project.data.get("source", {}).get("has_video"):
        return source
    return None


def _build_simple(project: Project, target: Path, warnings: list[str],
                  written: list[str], progress) -> None:
    spec = SPECS[project.type]
    slots = spec.get("slots", [])
    total = max(1, len(slots) + 1)

    for index, slot in enumerate(slots, start=1):
        progress(index / total, slot["label"])
        source = project.asset(slot["name"])
        if not source:
            if slot.get("required"):
                warnings.append(f"Fichier requis manquant : {slot['label']}.")
            continue
        name = slot["name"]
        # Les emplacements audio du candidat gardent leur nom de fichier d'origine.
        if project.type == "player" and name.startswith("audio_"):
            name = safe_name(Path(source).stem)
        extension = Path(source).suffix.lower()
        if slot["kind"] == "video" and extension != ".ogv":
            destination = target / f"{name}.ogv"
            try:
                media.to_ogv(Path(source), destination,
                             progress_cb=lambda f, i=index: progress(
                                 (i - 1 + f) / total, f"Conversion OGV {int(f * 100)} %"))
                written.append(destination.name)
            except media.MediaError as exc:
                warnings.append(f"{slot['label']} : conversion OGV impossible ({exc})")
            continue
        destination = target / f"{name}{extension}"
        media.copy_media(Path(source), destination)
        written.append(destination.name)

    progress(1.0, "Configuration")
    config_name = spec.get("config_file")
    if config_name:
        config = build_config(project)
        (target / config_name).write_text(
            json.dumps(config, indent="\t", ensure_ascii=False), encoding="utf-8"
        )
        written.append(config_name)

    authors = [a for a in (project.data.get("meta", {}).get("authors") or []) if a]
    if authors:
        (target / "_author.txt").write_text(", ".join(authors), encoding="utf-8")
        written.append("_author.txt")


def _build_chatter(project: Project, target: Path, warnings: list[str],
                   written: list[str], progress) -> None:
    entries = project.data.get("chatter", [])
    fmt = project.data.get("options", {}).get("clip_format") or "ogg"
    exact: dict[str, list[str]] = {}
    broad: dict[str, list[str]] = {}
    total = max(1, len(entries) + 1)

    for index, entry in enumerate(entries, start=1):
        progress(index / total, entry.get("name", ""))
        source = project.assets_dir / entry["stored"]
        if not source.exists():
            warnings.append(f"Fichier introuvable : {entry.get('name')}")
            continue
        base = safe_name(Path(entry.get("name") or source.stem).stem)
        destination = target / f"{base}.{fmt}"
        try:
            media.convert_audio(source, destination, fmt=fmt, normalize=False)
        except media.MediaError as exc:
            warnings.append(f"{base} : conversion impossible ({exc})")
            continue
        written.append(destination.name)
        keywords = [k for k in (entry.get("keywords") or []) if k]
        if not keywords:
            warnings.append(f"{base} n'a aucun mot-cle : il ne se declenchera jamais.")
            continue
        bucket = exact if entry.get("mode") == "exact" else broad
        bucket[destination.name] = keywords

    progress(1.0, "Configuration")
    icon_name = _copy_asset(project, "_icon", target, "_icon", written, warnings)
    meta = project.data.get("meta", {})
    content = inifmt.chatter_config(
        title=meta.get("title") or project.data.get("name", ""),
        icon=icon_name or "",
        authors=meta.get("authors") or [],
        volume=float(project.data.get("config", {}).get("volume") or 1.0),
        exact=exact, broad=broad,
    )
    (target / "config_chatter.ini").write_text(content, encoding="utf-8")
    written.append("config_chatter.ini")


# --------------------------------------------------------------------------
# Installation et export
# --------------------------------------------------------------------------

def install_target(project: Project) -> Path:
    folder = SPECS[project.type]["folder"]
    return settings.game_dir() / folder / safe_name(project.data.get("name") or "Pack")


def install(project: Project, overwrite: bool = False) -> dict:
    source = output_dir(project)
    if not source.is_dir():
        raise BuildError("Genere le pack avant de l'installer.")
    destination = install_target(project)
    if destination.exists():
        if not overwrite:
            return {"installed": False, "exists": True, "path": str(destination)}
        shutil.rmtree(destination, ignore_errors=True)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination)
    return {"installed": True, "exists": False, "path": str(destination)}


def zip_pack(project: Project) -> Path:
    source = output_dir(project)
    if not source.is_dir():
        raise BuildError("Genere le pack avant de l'exporter.")
    folder = SPECS[project.type]["folder"]
    archive = project.build_dir / f"{safe_name(project.data.get('name') or 'pack')}.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(source.rglob("*")):
            if path.is_file():
                arcname = Path(folder) / source.name / path.relative_to(source)
                zf.write(path, arcname.as_posix())
    return archive


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------

def validate(project: Project) -> list[dict]:
    issues: list[dict] = []

    def add(level: str, message: str) -> None:
        issues.append({"level": level, "message": message})

    name = project.data.get("name", "").strip()
    if not name:
        add("error", "Le pack n'a pas de nom : c'est le nom du dossier dans le jeu.")
    elif safe_name(name) != name:
        add("warning", f"Le nom sera assaini en « {safe_name(name)} » pour le dossier.")

    if project.type == "voice":
        clips = [c for c in project.data.get("clips", []) if c.get("enabled", True)]
        if not clips:
            add("error", "Aucun clip actif : le pack serait vide.")
        is_dub = bool(project.data.get("dub", {}).get("enabled"))
        limit = MAX_DUB_CLIP_SECONDS if is_dub else MAX_CLIP_SECONDS
        too_long = [c for c in clips if float(c["end"]) - float(c["start"]) > limit]
        if too_long:
            add("warning" if not is_dub else "error",
                f"{len(too_long)} clip(s) depassent {limit:.0f} s.")
        very_short = [c for c in clips if float(c["end"]) - float(c["start"]) < 0.4]
        if very_short:
            add("warning", f"{len(very_short)} clip(s) durent moins de 0,4 s.")
        if is_dub and not _dub_video_source(project):
            add("error", "Mode Dub actif mais aucune video source (dub_video.ogv requis).")
        if not project.data.get("meta", {}).get("authors"):
            add("info", "Aucun auteur renseigne — recommande par la documentation du jeu.")
    elif project.type == "chatter":
        entries = project.data.get("chatter", [])
        if not entries:
            add("error", "Aucun son dans le pack chatter.")
        if any(not e.get("keywords") for e in entries):
            add("warning", "Certains sons n'ont aucun mot-cle.")
    else:
        for slot in SPECS[project.type].get("slots", []):
            if slot.get("required") and not project.asset(slot["name"]):
                add("error", f"Fichier requis manquant : {slot['label']}.")
        if project.type == "judges":
            missing = [i for i in range(1, 6) if not project.asset(f"judge{i}")]
            if missing:
                add("warning", "Juges sans image : " + ", ".join(map(str, missing)))
            success = project.asset("success")
            if success and success.suffix.lower() not in IMAGE_EXTS:
                add("warning", "Le panneau de vote doit etre une image PNG ou JPG.")
        if project.type == "player" and not project.data.get("config", {}).get("name"):
            add("warning", "Le candidat n'a pas de nom : le jeu affichera « Player ».")

    status = settings.game_dir_status()
    if not status["looks_valid"]:
        add("info", f"Dossier de jeu introuvable ({status['path']}) : "
                    "l'installation directe sera indisponible.")
    return issues
