"""FastAPI entry. Every module in radar/routes exposing `router` is included automatically."""
import importlib
import pkgutil
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from radar import routes

ROOT = Path(__file__).resolve().parent
app = FastAPI(title="Ocean Opportunity Radar")
app.mount("/static", StaticFiles(directory=ROOT / "radar" / "static"), name="static")


@app.get("/healthz")
def healthz():
    return {"ok": True}


def include_routes(target: FastAPI) -> list[str]:
    names = []
    for m in sorted(pkgutil.iter_modules(routes.__path__), key=lambda m: m.name):
        mod = importlib.import_module(f"radar.routes.{m.name}")
        router = getattr(mod, "router", None)
        if router is not None:
            target.include_router(router)
            names.append(m.name)
    return names


LOADED_ROUTES = include_routes(app)
