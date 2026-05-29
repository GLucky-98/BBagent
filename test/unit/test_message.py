#!/usr/bin/env python3
"""
test_message.py - Message component tests

Test for BBagent.core.message module.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "BBagent"))

from core.message import (
    HumanMessage,
    ModelMessage,
    ToolMessage,
    TextBlock,
    ImageBlock,
    ToolUseBlock,
    ContentBlock,
    Message,
    Session,
)


def test_text_block_creation():
    """Test TextBlock creation."""
    print("[TEST] test_text_block_creation")
    try:
        block = TextBlock(text="Hello, world!")
        assert block.text == "Hello, world!"
        assert block.type == "text"

        d = block.to_dict()
        assert d["type"] == "text"
        assert d["text"] == "Hello, world!"
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_image_block_creation():
    """Test ImageBlock creation."""
    print("[TEST] test_image_block_creation")
    try:
        block = ImageBlock(data="base64data123", image_type="base64")
        assert block.data == "base64data123"

        d = block.to_dict()
        assert d["type"] == "image"
        assert d["data"] == "base64data123"
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_tool_use_block_creation():
    """Test ToolUseBlock creation."""
    print("[TEST] test_tool_use_block_creation")
    try:
        block = ToolUseBlock(id="tool_123", name="read_file", input={"path": "/test"})
        assert block.id == "tool_123"
        assert block.name == "read_file"
        assert block.input["path"] == "/test"

        d = block.to_dict()
        assert d["type"] == "tooluse"
        assert d["id"] == "tool_123"
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_human_message_creation():
    """Test HumanMessage creation with string content."""
    print("[TEST] test_human_message_creation")
    try:
        msg = HumanMessage(content="Hello, agent!")
        assert msg.role == "user"
        assert msg.content == "Hello, agent!"

        d = msg.to_dict()
        assert d["role"] == "user"
        assert d["content"] == "Hello, agent!"
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_human_message_with_blocks():
    """Test HumanMessage creation with content blocks."""
    print("[TEST] test_human_message_with_blocks")
    try:
        blocks = [TextBlock(text="Hello"), TextBlock(text="World")]
        msg = HumanMessage(content=blocks)
        assert len(msg.content) == 2

        d = msg.to_dict()
        assert isinstance(d["content"], list)
        assert len(d["content"]) == 2
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_tool_message_creation():
    """Test ToolMessage creation."""
    print("[TEST] test_tool_message_creation")
    try:
        msg = ToolMessage(
            id="tool_result_1",
            name="read_file",
            content="File content here"
        )
        assert msg.id == "tool_result_1"
        assert msg.name == "read_file"
        assert msg.content == "File content here"

        d = msg.to_dict()
        assert d["role"] == "tool"
        assert d["id"] == "tool_result_1"
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_content_block_from_dict():
    """Test ContentBlock deserialization from dict."""
    print("[TEST] test_content_block_from_dict")
    try:
        data = {"type": "text", "text": "Test content"}
        block = ContentBlock.from_dict(data)
        assert isinstance(block, TextBlock)
        assert block.text == "Test content"
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def test_message_from_dict():
    """Test Message deserialization from dict."""
    print("[TEST] test_message_from_dict")
    try:
        data = {
            "role": "user",
            "content": "Test message"
        }
        msg = Message.from_dict(data)
        assert isinstance(msg, HumanMessage)
        print("[PASS]")
        return True
    except Exception as e:
        print(f"[FAIL] {e}")
        return False


def main():
    tests = [
        test_text_block_creation,
        test_image_block_creation,
        test_tool_use_block_creation,
        test_human_message_creation,
        test_human_message_with_blocks,
        test_tool_message_creation,
        test_content_block_from_dict,
        test_message_from_dict,
    ]
    passed = 0
    failed = 0
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"[ERROR] {test.__name__}: {e}")
            failed += 1

    print(f"\nResults: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    sys.exit(0 if main() else 1)