from pathlib import Path

import pytest

from backend.api import chat
from backend.attachments import FileStore, safe_path_segment, safe_upload_name
from bbagent.core.message import ImageBlock, TextBlock


class FakeUpload:
    def __init__(self, filename: str, content: bytes, content_type: str = "text/plain"):
        self.filename = filename
        self.content_type = content_type
        self._content = content
        self._sent = False

    async def read(self, _size: int) -> bytes:
        if self._sent:
            return b""
        self._sent = True
        return self._content


def test_safe_upload_name_strips_path_and_unsafe_characters():
    assert safe_upload_name("../résumé final.txt") == "r_sum_ final.txt"
    assert safe_upload_name("../../") == "file"


@pytest.mark.asyncio
async def test_file_store_saves_copy_under_owner_directory(tmp_path: Path):
    store = FileStore(tmp_path)

    uploaded_file = await store.save(
        "agent/one",
        FakeUpload("../report.txt", b"hello", "text/plain"),
    )

    stored_path = Path(uploaded_file.path)
    assert stored_path.read_bytes() == b"hello"
    assert stored_path.name == "report.txt"
    assert stored_path.parent.parent == tmp_path / safe_path_segment("agent/one")
    assert uploaded_file.original_name == "report.txt"
    assert uploaded_file.content_type == "text/plain"
    assert uploaded_file.size == 5
    assert store.is_owned_file("agent/one", uploaded_file.path)
    assert store.resolve_owned_file_id("agent/one", uploaded_file.id) == stored_path


def test_file_store_rejects_external_paths(tmp_path: Path):
    store = FileStore(tmp_path)
    external = tmp_path / "outside.txt"
    external.write_text("not an uploaded copy", encoding="utf-8")

    assert not store.is_owned_file("agent-1", str(external))


def test_chat_formatter_includes_only_owned_files(monkeypatch):
    class DummyStore:
        def is_owned_file(self, owner_id: str, path: str) -> bool:
            return owner_id == "agent-1" and path == "/managed/file.txt"

    monkeypatch.setattr(chat, "_file_store", DummyStore())

    formatted = chat._format_user_message(
        "agent-1",
        "Please inspect this.",
        [
            {
                "originalName": "file.txt",
                "id": "file-1",
                "path": "/managed/file.txt",
                "contentType": "text/plain",
                "size": 4,
            },
            {
                "originalName": "secret.txt",
                "id": "file-2",
                "path": "/etc/passwd",
                "contentType": "text/plain",
                "size": 10,
            },
        ],
    )

    assert "file_id=file-1" in formatted
    assert "/managed/file.txt" not in formatted
    assert "/etc/passwd" not in formatted
    assert "copied into managed local storage" in formatted


def test_chat_build_user_content_embeds_owned_images(monkeypatch, tmp_path: Path):
    image_path = tmp_path / "photo.png"
    image_path.write_bytes(b"fake-png-bytes")

    class DummyStore:
        def is_owned_file(self, owner_id: str, path: str) -> bool:
            return owner_id == "agent-1" and path == str(image_path)

    monkeypatch.setattr(chat, "_file_store", DummyStore())

    content = chat._build_user_content(
        "agent-1",
        "What is in this image?",
        [
            {
                "originalName": "photo.png",
                "id": "image-1",
                "path": str(image_path),
                "contentType": "image/png",
                "size": len(b"fake-png-bytes"),
            },
        ],
    )

    assert isinstance(content, list)
    assert isinstance(content[0], TextBlock)
    assert "included directly" in content[0].text
    assert "read_file" not in content[0].text
    assert "file_id=image-1" in content[0].text
    assert isinstance(content[1], ImageBlock)
    assert content[1].data == "ZmFrZS1wbmctYnl0ZXM="
    assert content[1].image_type == "image/png"


def test_chat_build_user_content_keeps_non_images_as_paths(monkeypatch, tmp_path: Path):
    doc_path = tmp_path / "notes.txt"
    doc_path.write_text("hello", encoding="utf-8")

    class DummyStore:
        def is_owned_file(self, owner_id: str, path: str) -> bool:
            return owner_id == "agent-1" and path == str(doc_path)

    monkeypatch.setattr(chat, "_file_store", DummyStore())

    content = chat._build_user_content(
        "agent-1",
        "",
        [
            {
                "originalName": "notes.txt",
                "id": "doc-1",
                "path": str(doc_path),
                "contentType": "text/plain",
                "size": 5,
            },
        ],
    )

    assert isinstance(content, str)
    assert "Please review the uploaded file(s)." in content
    assert str(doc_path) not in content
    assert "file_id=doc-1" in content
    assert "read_file" in content
