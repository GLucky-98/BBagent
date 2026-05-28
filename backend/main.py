from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.api import api_router

app = FastAPI(title="BBagent API", version="0.1.0")

# CORS: 开发模式允许所有来源
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API 路由
app.include_router(api_router, prefix="/api")

# 健康检查
@app.get("/health")
async def health():
    return {"status": "ok"}

# 生产模式：托管前端构建产物
dist_path = Path(__file__).parent.parent / "frontend" / "dist"
if dist_path.exists():
    # 静态资源目录
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
        # API 路径不走这里
        if full_path.startswith("api/") or full_path == "health":
            return {"error": "Not found"}
        index_file = dist_path / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
        return {"error": "Frontend not built"}
