import contextlib
import mimetypes
import os
import platform
import subprocess
from pathlib import Path
from typing import Any, cast

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from backend.schemas import FileNode

router = APIRouter()


def _build_tree(path: Path, max_depth: int | None = None) -> FileNode:
    if not path.is_dir():
        stat = None
        with contextlib.suppress(OSError):
            stat = path.stat()
        return FileNode(
            name=path.name,
            path=str(path),
            type="file",
            size=stat.st_size if stat else None,
            extension=path.suffix.lstrip(".") if path.suffix else None,
            modifiedAt=int(stat.st_mtime) if stat else None,
        )
    children = []
    if max_depth is None or max_depth > 0:
        next_depth = max_depth - 1 if max_depth is not None else None
        try:
            entries = sorted(
                (c for c in path.iterdir() if not c.name.startswith(".")),
                key=lambda x: (not x.is_dir(), x.name.lower()),
            )
            for child in entries:
                with contextlib.suppress(PermissionError, OSError):
                    children.append(_build_tree(child, next_depth))
        except (PermissionError, OSError):
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
async def get_tree(path: str = Query(...), depth: int | None = Query(default=None)):
    target = Path(path).expanduser().resolve()
    if not target.exists():
        raise HTTPException(status_code=404, detail="Path not found")
    return _build_tree(target, depth).model_dump(mode="json")


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
        text_content = target.read_text(encoding="utf-8")
        return Response(content=text_content, media_type=content_type)
    else:
        bytes_content = target.read_bytes()
        return Response(content=bytes_content, media_type=content_type)


@router.post("/write")
async def write_file(payload: dict):
    path = Path(payload["path"]).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload["content"], encoding="utf-8")
    return {"success": True}


@router.post("/open")
async def open_file_dir(payload: dict):
    path = Path(payload["path"]).expanduser().resolve()
    if not path.exists():
        raise HTTPException(status_code=404, detail="Path not found")
    try:
        system = platform.system()
        if system == "Darwin":
            subprocess.run(["open", str(path)], check=True)
        elif system == "Linux":
            subprocess.run(["xdg-open", str(path)], check=True)
        elif system == "Windows":
            cast(Any, os).startfile(str(path))
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to open path: {e}") from None


@router.post("/dirs")
async def create_dir(payload: dict):
    """Create a new directory. Idempotent if it already exists as a dir."""
    path = Path(payload["path"]).expanduser().resolve()
    if path.exists():
        if path.is_dir():
            return {"success": True, "path": str(path)}
        raise HTTPException(status_code=409, detail="Path already exists and is not a directory")
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Failed to create directory: {e}") from None
    return {"success": True, "path": str(path)}


@router.put("/dirs")
async def rename_dir(payload: dict):
    """Rename/move a directory."""
    old_path = Path(payload["oldPath"]).expanduser().resolve()
    new_path = Path(payload["newPath"]).expanduser().resolve()
    if not old_path.exists() or not old_path.is_dir():
        raise HTTPException(status_code=404, detail="Source directory not found")
    if new_path.exists():
        raise HTTPException(status_code=409, detail="Destination already exists")
    try:
        old_path.rename(new_path)
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Failed to rename directory: {e}") from None
    return {"success": True, "path": str(new_path)}


@router.delete("/dirs")
async def delete_dir(path: str = Query(...), recursive: bool = Query(default=False)):
    """Delete a directory. Requires recursive=true for non-empty dirs."""
    target = Path(path).expanduser().resolve()
    if not target.exists() or not target.is_dir():
        raise HTTPException(status_code=404, detail="Directory not found")
    try:
        if recursive:
            import shutil
            shutil.rmtree(target)
        else:
            target.rmdir()
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete directory: {e}") from None
    return {"success": True}
