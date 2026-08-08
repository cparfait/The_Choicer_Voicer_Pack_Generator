"""Fabrique l'executable Windows de l'outil.

    .venv\\Scripts\\python build_exe.py                  avec ffmpeg si on le trouve
    .venv\\Scripts\\python build_exe.py --no-ffmpeg      sans, plus leger
    .venv\\Scripts\\python build_exe.py --ffmpeg C:\\...\\bin

Le resultat est un dossier `dist/ChoicerVoicerPackMaker/` a copier tel quel :
l'executable, l'interface embarquee, et — au choix — ffmpeg a cote.

Les fonctions qui reposent sur PyTorch (transcription, separation des voix,
detection des locuteurs, detourage) ne sont volontairement PAS embarquees :
elles pesent plus de 1,5 Go et PyInstaller s'en sort mal. L'interface le dit
clairement quand elle tourne en version .exe.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NAME = "ChoicerVoicerPackMaker"

# Ces modules ne doivent jamais entrer dans le paquet : soit ils sont enormes,
# soit PyInstaller les embarque « au cas ou » alors que rien ne les importe.
EXCLUDES = [
    "torch", "torchaudio", "torchvision", "torchcodec", "demucs", "pyannote",
    "pyannote.audio", "lightning", "pytorch_lightning", "rembg", "onnxruntime",
    "cv2", "faster_whisper", "ctranslate2", "transformers", "scipy",
    "sklearn", "matplotlib", "pandas", "optuna", "tkinter", "test",
]


def find_ffmpeg(explicit: str | None) -> Path | None:
    """Dossier contenant ffmpeg.exe : argument, puis reglages, puis PATH."""
    if explicit:
        folder = Path(explicit)
        return folder if (folder / "ffmpeg.exe").is_file() else None

    candidats: list[Path] = [ROOT / "ffmpeg"]
    reglages = ROOT / "data" / "settings.json"
    if reglages.is_file():
        try:
            configure = json.loads(reglages.read_text(encoding="utf-8")).get("ffmpeg", "")
        except (json.JSONDecodeError, OSError):
            configure = ""
        if configure:
            chemin = Path(configure.strip().strip('"'))
            candidats.append(chemin if chemin.is_dir() else chemin.parent)
    trouve = shutil.which("ffmpeg")
    if trouve:
        candidats.append(Path(trouve).parent)

    for dossier in candidats:
        if (dossier / "ffmpeg.exe").is_file() and (dossier / "ffprobe.exe").is_file():
            return dossier
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Construit l'executable")
    parser.add_argument("--ffmpeg", help="dossier contenant ffmpeg.exe et ffprobe.exe")
    parser.add_argument("--no-ffmpeg", action="store_true",
                        help="ne pas embarquer ffmpeg (l'utilisateur le reglera)")
    args = parser.parse_args()

    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("PyInstaller manque. Lance : pip install pyinstaller")
        return 1

    separateur = ';' if sys.platform == 'win32' else ':'
    commande = [
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
        "--name", NAME,
        "--add-data", f"{ROOT / 'web'}{separateur}web",
        # L'ouvrier des fonctions IA voyage comme donnee : il sera execute par
        # un Python exterieur, pas par l'executable.
        "--add-data", f"{ROOT / 'worker'}{separateur}worker",
        # uvicorn charge ses implementations par leur nom : sans ces imports
        # declares, le paquet demarre puis echoue au premier reglage.
        "--hidden-import", "uvicorn.logging",
        "--hidden-import", "uvicorn.protocols.http.h11_impl",
        "--hidden-import", "uvicorn.protocols.websockets.websockets_impl",
        "--hidden-import", "uvicorn.lifespan.on",
        "--console",
    ]
    for module in EXCLUDES:
        commande += ["--exclude-module", module]

    ffmpeg = None if args.no_ffmpeg else find_ffmpeg(args.ffmpeg)

    commande.append(str(ROOT / "server.py"))
    print("\n" + " ".join(commande[:8]) + " ...\n")
    resultat = subprocess.run(commande, cwd=ROOT)
    if resultat.returncode != 0:
        return resultat.returncode

    cible = ROOT / "dist" / NAME
    if ffmpeg:
        # ffmpeg est copie a cote de l'executable, pas dans le paquet : passe en
        # --add-data ou --add-binary, PyInstaller analyse les DLL et les recopie
        # aussi a la racine, soit 130 Mo en double. L'outil sait deja chercher
        # un dossier `ffmpeg/` voisin — et l'utilisateur peut y mettre le sien.
        # ffplay reste dehors : c'est un lecteur video, inutile ici.
        dossier = cible / "ffmpeg"
        dossier.mkdir(parents=True, exist_ok=True)
        garde = 0
        for fichier in sorted(ffmpeg.glob("*")):
            if not fichier.is_file():
                continue
            if (fichier.name.lower() in ("ffmpeg.exe", "ffprobe.exe")
                    or fichier.suffix.lower() == ".dll"):
                shutil.copy2(fichier, dossier / fichier.name)
                garde += fichier.stat().st_size
        print(f"ffmpeg copie depuis {ffmpeg} ({garde / 1024 / 1024:.0f} Mo)")
    else:
        print("ffmpeg non embarque : l'utilisateur devra indiquer son chemin dans Reglages.")
    poids = sum(f.stat().st_size for f in cible.rglob("*") if f.is_file())
    print(f"\n  Termine : {cible}")
    print(f"  Poids : {poids / 1024 / 1024:.0f} Mo")
    print(f"  Lance {NAME}.exe ; les projets iront dans data/, a cote de lui.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
