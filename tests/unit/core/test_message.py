import json

import pytest

from bbagent.core.message import (
    ContentBlock,
    HumanMessage,
    ImageBlock,
    ModelMessage,
    Session,
    TextBlock,
    ToolMessage,
    ToolUseBlock,
)


def test_message_round_trip_preserves_structured_content():
    original = ModelMessage(
        id="msg-1",
        content=[TextBlock(text="I will call a tool.")],
        stop_reason="tool_use",
        usage_data={"input_tokens": 10, "output_tokens": 4},
        tool_calls=[ToolUseBlock(id="tool-1", name="read", input={"path": "README.md"})],
        input_tokens=10,
        output_tokens=4,
        timestamp=123,
    )

    restored = ModelMessage._from_dict(json.loads(json.dumps(original.to_dict())))

    assert restored.id == "msg-1"
    assert restored.stop_reason == "tool_use"
    assert restored.usage_data == {"input_tokens": 10, "output_tokens": 4}
    assert restored.input_tokens == 10
    assert restored.output_tokens == 4
    assert isinstance(restored.content[0], TextBlock)
    assert restored.content[0].text == "I will call a tool."
    assert restored.tool_calls[0].name == "read"
    assert restored.tool_calls[0].input == {"path": "README.md"}
    assert restored.content[0].origin == "model"
    assert restored.tool_calls[0].origin == "model"


def test_message_content_is_normalized_to_origin_blocks():
    human = HumanMessage(content="hi")
    model = ModelMessage(id="m1", content="hello", stop_reason="end_turn", usage_data={})
    tool = ToolMessage(id="t1", name="read", content="ok")

    assert isinstance(human.content, list)
    assert human.content[0].origin == "user"
    assert model.content[0].origin == "model"
    assert tool.content[0].origin == "tool"


def test_content_block_serialization_includes_origin():
    assert TextBlock(text="hello", origin="system").to_dict() == {
        "type": "text",
        "text": "hello",
        "origin": "system",
    }
    assert ImageBlock(data="abc", image_type="png", origin="user").to_dict() == {
        "type": "image",
        "data": "abc",
        "image_type": "png",
        "origin": "user",
    }


def test_unknown_content_block_type_is_rejected():
    with pytest.raises(ValueError, match="Unknown content block type"):
        ContentBlock.from_dict({"type": "video", "url": "x"})


def test_session_persists_and_loads_completed_turn(tmp_path):
    session = Session.create(tmp_path)
    session.add_message(HumanMessage(content="Please inspect README.", timestamp=1))
    session.add_message(
        ModelMessage(
            id="m1",
            content="I need the file.",
            stop_reason="tool_use",
            usage_data={},
            tool_calls=[ToolUseBlock(id="call-1", name="read", input={"path": "README.md"})],
            input_tokens=8,
            output_tokens=3,
            timestamp=2,
        )
    )
    session.add_message(ToolMessage(id="call-1", name="read", content="content", timestamp=3))
    session.add_message(
        ModelMessage(
            id="m2",
            content="Done.",
            stop_reason="end_turn",
            usage_data={},
            input_tokens=12,
            output_tokens=5,
            timestamp=4,
        )
    )
    session.save()

    loaded = Session.load(session.id, session.dir)
    jsonl_text = (session.dir / f"{session.id}.jsonl").read_text(encoding="utf-8")

    assert loaded.id == session.id
    assert loaded.turn_count == 1
    assert loaded.turns[0].is_complete
    assert [type(msg).__name__ for msg in loaded.messages] == [
        "HumanMessage",
        "ModelMessage",
        "ToolMessage",
        "ModelMessage",
    ]
    assert loaded.ever_used_tools == ["read"]
    assert loaded.total_input_cost_tokens == 20
    assert loaded.total_output_cost_tokens == 8
    assert '"origin": "user"' in jsonl_text
    assert '"origin": "tool"' in jsonl_text
    assert '"origin": "model"' in jsonl_text


def test_session_load_restores_turn_metadata(tmp_path):
    session = Session.create(tmp_path)
    session.add_message(HumanMessage(content="Remember my preference.", timestamp=1))
    session.add_message(
        ModelMessage(
            id="m1",
            content="Done.",
            stop_reason="end_turn",
            usage_data={},
            timestamp=2,
        )
    )
    session.turns[0].memory_extracted = True
    session.turns[0].key_content = ["preference"]
    session.save()

    loaded = Session.load(session.id, session.dir)

    assert loaded.turns[0].memory_extracted is True
    assert loaded.turns[0].key_content == ["preference"]


def test_session_merges_incomplete_turn_into_next_user_message():
    session = Session()
    session.add_message(HumanMessage(content="First request", timestamp=1))
    session.add_message(ModelMessage(id="m1", content="Partial answer", stop_reason="max_tokens", usage_data={}))

    session.add_message(HumanMessage(content="Second request", timestamp=2))

    assert session.turn_count == 1
    merged = session.turns[0].messages[0]
    assert isinstance(merged.content, list)
    texts = [block.text for block in merged.content if isinstance(block, TextBlock)]
    assert any("Context from an incomplete previous turn" in text for text in texts)
    assert any("[User] First request" in text for text in texts)
    assert any("[Assistant] Partial answer" in text for text in texts)
    assert any("Current request" in text for text in texts)
    assert any(text == "Second request" for text in texts)


def test_session_fork_copies_turns_without_sharing_objects(tmp_path):
    session = Session.create(tmp_path / "sessions")
    session.add_message(HumanMessage(content="Hi", timestamp=1))
    session.add_message(
        ModelMessage(
            id="m1",
            content="Hello",
            stop_reason="end_turn",
            usage_data={},
            input_tokens=5,
            output_tokens=2,
            timestamp=2,
        )
    )

    forked = session.fork(session_root=tmp_path / "forks")
    forked.turns[0].messages[0].content = "Changed in fork"

    assert forked.id != session.id
    assert forked.turn_count == 1
    assert session.turns[0].messages[0].content != "Changed in fork"
    assert (forked.dir / f"{forked.id}.jsonl").exists()
    assert (forked.dir / f"{forked.id}.md").exists()
