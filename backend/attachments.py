import re
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._() -]+")
_SAFE_SEGMENT_RE = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass(frozen=True)
class StoredFile:
    id: str
    original_name: str
    stored_name: str
    path: str
    content_type: str
    size: int

    def to_api_dict(self) -> dict:
        return {
            "id": self.id,
            "originalName": self.original_name,
            "storedName": self.stored_name,
            "path": self.path,
            "contentType": self.content_type,
            "size": self.size,
        }


def safe_path_segment(value: str) -> str:
    segment = _SAFE_SEGMENT_RE.sub("_", value.strip()).strip("._-")
    return segment or "unknown"


def safe_upload_name(filename: str | None) -> str:
    original = Path(filename or "file").name
    cleaned = _SAFE_NAME_RE.sub("_", original).strip(" ._")
    if cleaned:
        return cleaned
    suffix = Path(original).suffix
    return f"file{suffix}" if suffix else "file"


class FileStore:
    def __init__(self, root: Path):
        self.root = root

    async def save(self, owner_id: str, upload) -> StoredFile:
        file_id = uuid4().hex
        original_name = Path(upload.filename or "file").name
        stored_name = safe_upload_name(original_name)
        target_dir = self.root / safe_path_segment(owner_id) / file_id
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / stored_name

        size = 0
        with target_path.open("wb") as f:
            while True:
                chunk = await upload.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                f.write(chunk)

        return StoredFile(
            id=file_id,
            original_name=original_name,
            stored_name=stored_name,
            path=str(target_path.resolve()),
            content_type=getattr(upload, "content_type", None) or "application/octet-stream",
            size=size,
        )

    def is_owned_file(self, owner_id: str, path: str) -> bool:
        try:
            target = Path(path).expanduser().resolve()
            owner_root = (self.root / safe_path_segment(owner_id)).resolve()
        except OSError:
            return False
        return target.is_file() and target.is_relative_to(owner_root)

    def resolve_owned_file_id(self, owner_id: str, file_id: str) -> Path | None:
        safe_owner = safe_path_segment(owner_id)
        safe_file_id = safe_path_segment(file_id)
        file_dir = (self.root / safe_owner / safe_file_id).resolve()
        owner_root = (self.root / safe_owner).resolve()
        try:
            if not file_dir.is_dir() or not file_dir.is_relative_to(owner_root):
                return None
            files = [item for item in file_dir.iterdir() if item.is_file()]
        except OSError:
            return None
        if len(files) != 1:
            return None
        return files[0].resolve()


# Backwards-compatible aliases while the API/frontend migrate from
# "attachment" wording to "file" wording.
StoredAttachment = StoredFile
AttachmentStore = FileStore
