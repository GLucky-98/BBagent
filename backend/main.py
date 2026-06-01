from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.logging import setup_backend_logging, get_backend_logger
from backend.errors import AppError, app_error_handler, unhandled_exception_handler

setup_backend_logging()

from backend.api import api_router
from backend.state import state_manager

logger = get_backend_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await state_manager.load_all()
    loaded = len(state_manager.agents)
    logger.info("Starting BBagent API with %d agent(s) loaded", loaded)
    await state_manager.start_all_agents()
    running = sum(
        1 for name in state_manager.agents
        if state_manager.get_agent_state(name).get("state") not in ("unknown", "ready")
    )
    logger.info("Startup complete — %d/%d agent(s) running", running, loaded)
    yield
    logger.info("BBagent API shutting down")


app = FastAPI(title="BBagent API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")

app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)


@app.get("/health")
async def health():
    return {"status": "ok"}


dist_path = Path(__file__).parent.parent / "frontend" / "dist"
if dist_path.exists():
    assets_path = dist_path / "assets"
    if assets_path.exists():
        app.mount("/assets", StaticFiles(directory=assets_path), name="assets")
    icons_path = dist_path / "icons"
    if icons_path.exists():
        app.mount("/icons", StaticFiles(directory=icons_path), name="icons")
    public_path = dist_path / "public"
    if public_path.exists():
        app.mount("/public", StaticFiles(directory=public_path), name="public")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        if full_path.startswith("api/") or full_path == "health":
            return {"error": "Not found"}
        index_file = dist_path / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        return {"error": "Frontend not built"}
