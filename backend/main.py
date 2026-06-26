from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.errors import AppError, app_error_handler, unhandled_exception_handler
from backend.logging import get_backend_logger, setup_backend_logging

setup_backend_logging()

from backend.api import api_router
from backend.state import state_manager

logger = get_backend_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await state_manager.load_all()
    loaded = len(state_manager.agent_factory.agents)
    logger.info("BBagent API started — %d agent(s) loaded (ready)", loaded)
    yield
    # persist metadata for all active sessions on shutdown
    logger.info("BBagent API shutting down — saving sessions")
    agent_factory = state_manager.agent_factory
    for _agent_id, agent in list(agent_factory.agents.items()):
        if agent.session is None or agent.session.dir is None:
            continue
        try:
            agent.session.save()
            logger.debug("Saved session '%s' for agent '%s' on shutdown",
                         agent.session.id, agent.name)
        except Exception as e:
            logger.warning(
                "Failed to save session for agent '%s' on shutdown: %s",
                agent.name, e,
            )
    logger.info("BBagent API shut down")


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
