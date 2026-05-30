import mimetypes
import os
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from backend.schemas import FileNode

router = APIRouter()


def _build_tree(path: Path) -> FileNode:
    if path.is_file():
        stat = path.stat()
        return FileNode(
            name=path.name,
            path=str(path),
            type="file",
            size=stat.st_size,
            extension=path.suffix.lstrip(".") if path.suffix else None,
            modifiedAt=int(stat.st_mtime),
        )
    children = []
    try:
        for child in sorted(path.iterdir(), key=lambda x: (x.is_file(), x.name.lower())):
            children.append(_build_tree(child))
    except PermissionError:
        pass
    return FileNode(
        name=path.name,
        path=str(path),
        type="directory",
        children=children,
    )


@router.get("/dirs")
async def list_dirs(path: str = Query(default="~")):
    target = Path(path).expanduser().resolve()
    if not target.exists():
        raise HTTPException(status_code=404, detail="Path not found")
    if not target.is_dir():
        raise HTTPException(status_code=400, detail="Path is not a directory")

    parent = str(target.parent) if target.parent != target else None
    dirs = []
    try:
        for child in sorted(target.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
            if child.is_dir() and not child.name.startswith("."):
                dirs.append(child.name)
    except PermissionError:
        pass

    return {
        "current": str(target),
        "parent": parent,
        "separator": os.sep,
        "directories": dirs,
    }


@router.get("/tree")
async def get_tree(path: str = Query(...)):
    target = Path(path).expanduser().resolve()
    if not target.exists():
        raise HTTPException(status_code=404, detail="Path not found")
    return _build_tree(target).model_dump(mode="json")


@router.get("/read")
async def read_file(path: str = Query(...)):
    target = Path(path).expanduser().resolve()
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    mime, _ = mimetypes.guess_type(str(target))
    content = target.read_text(encoding="utf-8")
    return {"content": content, "mimeType": mime or "text/plain", "name": target.name, "path": str(target)}


@router.get("/raw")
async def raw_file(path: str = Query(...)):
    target = Path(path).expanduser().resolve()
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    mime, _ = mimetypes.guess_type(str(target))
    content_type = mime or "application/octet-stream"

    text_mimes = {"text/", "application/json", "application/javascript", "application/xml", "image/svg"}
    is_text = any(content_type.startswith(prefix) for prefix in text_mimes)

    if is_text:
        content = target.read_text(encoding="utf-8")
        return Response(content=content, media_type=content_type)
    else:
        content = target.read_bytes()
        return Response(content=content, media_type=content_type)


@router.post("/write")
async def write_file(payload: dict):
    path = Path(payload["path"]).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload["content"], encoding="utf-8")
    return {"success": True}
