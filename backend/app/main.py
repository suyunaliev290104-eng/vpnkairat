import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api import routes, sub, webhooks
from app.config import get_settings
from app.payments import registry

log = logging.getLogger(__name__)
WEBAPP_DIST = Path(__file__).resolve().parents[2] / "webapp" / "dist"


def create_app(background: bool = True) -> FastAPI:
    registry.load_builtin()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        tasks = []
        if background:
            from app.runtime import start_runtime, stop_runtime
            tasks = await start_runtime()
        yield
        if background:
            await stop_runtime(tasks)

    app = FastAPI(title=get_settings().brand_name, lifespan=lifespan)
    app.include_router(routes.router)
    app.include_router(webhooks.router)
    app.include_router(sub.router)

    @app.get("/health")
    async def health():
        return {"ok": True}

    if WEBAPP_DIST.is_dir():
        app.mount("/", StaticFiles(directory=WEBAPP_DIST, html=True), name="webapp")
    return app


app = create_app()
