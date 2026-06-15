from fastapi import APIRouter

from . import (
    agents,
    chat,
    file_watch,
    files,
    hooks,
    mcps,
    models,
    prompts,
    sessions,
    skills,
    state,
    team_ws,
    teams,
    tools,
)

api_router = APIRouter()
api_router.include_router(models.router, prefix="/models", tags=["models"])
api_router.include_router(mcps.router, prefix="/mcps", tags=["mcps"])
api_router.include_router(prompts.router, prefix="/prompts", tags=["prompts"])
api_router.include_router(skills.router, prefix="/skills", tags=["skills"])
api_router.include_router(agents.router, prefix="/agents", tags=["agents"])
api_router.include_router(teams.router, prefix="/teams", tags=["teams"])
api_router.include_router(chat.router, prefix="/ws", tags=["chat"])
api_router.include_router(file_watch.router, prefix="/ws", tags=["file_watch"])
api_router.include_router(team_ws.router, prefix="/ws", tags=["team_chat"])
api_router.include_router(files.router, prefix="/files", tags=["files"])
api_router.include_router(state.router, prefix="/state", tags=["state"])
api_router.include_router(tools.router, prefix="/tools", tags=["tools"])
api_router.include_router(hooks.router, prefix="/hooks", tags=["hooks"])
api_router.include_router(sessions.router, prefix="/sessions", tags=["sessions"])
