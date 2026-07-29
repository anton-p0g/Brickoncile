import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.routers import minifigs, missing_parts, parts, sets
from app.application.use_cases.sync_themes import SyncThemesUseCase
from app.infrastructure.cache.local_image_cache import LocalImageCache
from app.infrastructure.db.session import create_db_and_tables, engine
from app.infrastructure.db.sqlite_theme_repository import SqliteThemeRepository
from app.infrastructure.external.brickognize_client import BrickognizeClient
from app.infrastructure.external.rebrickable_client import RebrickableClient
from app.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


async def _prime_theme_cache(catalog: RebrickableClient) -> None:
    """Pull the theme tree once so the dashboard can group sets by theme. Best-effort: an
    unreachable Rebrickable must not stop the app from starting, since everything else in it works
    offline against the local cache. The sets simply show up ungrouped until the next attempt."""
    try:
        with Session(engine) as session:
            await SyncThemesUseCase(SqliteThemeRepository(session), catalog).ensure_populated()
    except Exception:
        logger.warning("could not prime the theme cache; sets will show without a theme", exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.images_dir.mkdir(parents=True, exist_ok=True)
    create_db_and_tables()

    app.state.catalog_client = RebrickableClient(settings.rebrickable_api_key)
    app.state.image_cache = LocalImageCache(settings.images_dir)
    app.state.minifig_recognizer = BrickognizeClient(settings.brickognize_base_url)

    await _prime_theme_cache(app.state.catalog_client)

    yield

    await app.state.catalog_client.aclose()
    await app.state.image_cache.aclose()
    await app.state.minifig_recognizer.aclose()


app = FastAPI(title="Brickoncile", lifespan=lifespan)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(sets.router)
app.include_router(minifigs.router)
app.include_router(missing_parts.router)
app.include_router(parts.router)

app.mount("/static/images", StaticFiles(directory=settings.images_dir, check_dir=False), name="images")

if settings.frontend_dist_dir.is_dir():
    app.mount("/", StaticFiles(directory=settings.frontend_dist_dir, html=True), name="frontend")

    @app.exception_handler(StarletteHTTPException)
    async def spa_fallback(request: Request, exc: StarletteHTTPException):
        # React Router owns client-side routes (e.g. /minifigs, /sets/75192-1) — on a direct
        # navigation or refresh there's no matching static file, so serve index.html and let
        # the client-side router take over instead of a real 404.
        is_app_route = exc.status_code == 404 and not request.url.path.startswith(("/api", "/static"))
        if is_app_route:
            return FileResponse(settings.frontend_dist_dir / "index.html")
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
