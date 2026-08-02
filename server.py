"""Point d'entree : sert l'interface web et l'API.

    python server.py            demarre sur http://127.0.0.1:8730
    python server.py --port 9000 --no-browser
"""

from __future__ import annotations

import argparse
import threading
import webbrowser
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from cvpack import settings
from cvpack.api import router

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "web"

app = FastAPI(title="Choicer Voicer Pack Maker", docs_url="/api/docs", redoc_url=None)
app.include_router(router)
app.mount("/static", StaticFiles(directory=WEB), name="static")


@app.get("/")
def index():
    return FileResponse(WEB / "index.html")


def main() -> None:
    parser = argparse.ArgumentParser(description="Createur de packs The Choicer Voicer")
    parser.add_argument("--port", type=int, default=8730)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
    settings.PROJECTS_DIR.mkdir(parents=True, exist_ok=True)

    url = f"http://{args.host}:{args.port}/"
    print(f"\n  Createur de packs The Choicer Voicer")
    print(f"  Interface : {url}")
    print(f"  Packs du jeu : {settings.get('game_dir')}")
    print(f"  Ctrl+C pour arreter.\n")

    if not args.no_browser:
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()

    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
