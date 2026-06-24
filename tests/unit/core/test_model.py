from bbagent.core.message import ImageBlock, ModelMessage, TextBlock, ToolUseBlock
from bbagent.core.model import AnthropicModel, OpenAIModel


def test_openai_model_message_to_payload_preserves_thinking_as_reasoning_content():
    model = OpenAIModel(model="test-model", api_key="test-key")
    message = ModelMessage(
        id="msg-1",
        content="answer",
        thinking="reasoning",
        stop_reason="end_turn",
        usage_data={},
    )

    payload = model.model_message_to_payload(message)

    assert payload["role"] == "assistant"
    assert payload["content"] == [{"type": "text", "text": "answer"}]
    assert payload["reasoning_content"] == "reasoning"
    assert "origin" not in payload["content"][0]


def test_openai_model_message_to_payload_reuses_content_block_parse():
    model = OpenAIModel(model="test-model", api_key="test-key")
    message = ModelMessage(
        id="msg-1",
        content=[TextBlock(text="answer"), ImageBlock(data="abc123", image_type="png")],
        stop_reason="end_turn",
        usage_data={},
    )

    payload = model.model_message_to_payload(message)

    assert payload["content"] == [
        {"type": "text", "text": "answer"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc123"}},
    ]


def test_openai_model_response_parse_keeps_reasoning_content_on_model_message():
    model = OpenAIModel(model="test-model", api_key="test-key")
    response = {
        "id": "chatcmpl-1",
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "answer",
                    "reasoning_content": "reasoning",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 3, "completion_tokens": 5},
    }

    message = model.model_response_parse(response)

    assert isinstance(message.content[0], TextBlock)
    assert message.content[0].text == "answer"
    assert message.content[0].origin == "model"
    assert message.thinking == "reasoning"
    assert message.stop_reason == "end_turn"
    assert message.input_tokens == 3
    assert message.output_tokens == 5


def test_anthropic_model_message_to_payload_reuses_content_block_parse():
    model = AnthropicModel(model="test-model", api_key="test-key")
    message = ModelMessage(
        id="msg-1",
        content=[TextBlock(text="answer"), ImageBlock(data="abc123", image_type="image/png")],
        thinking="reasoning",
        thinking_signature="sig",
        tool_calls=[ToolUseBlock(id="tool-1", name="read", input={"path": "README.md"})],
        stop_reason="tool_use",
        usage_data={},
    )

    payload = model.model_message_to_payload(message)

    assert payload == {
        "role": "assistant",
        "content": [
            {"type": "thinking", "thinking": "reasoning", "signature": "sig"},
            {"type": "text", "text": "answer"},
            {
                "type": "image",
                "source": {"type": "base64", "data": "abc123", "media_type": "image/png"},
            },
            {
                "type": "tool_use",
                "id": "tool-1",
                "name": "read",
                "input": {"path": "README.md"},
            },
        ],
    }
    assert "origin" not in payload["content"][1]
    assert "origin" not in payload["content"][2]
    assert "source" in payload["content"][2]


def test_provider_payloads_do_not_leak_content_origin():
    openai = OpenAIModel(model="test-model", api_key="test-key")
    anthropic = AnthropicModel(model="test-model", api_key="test-key")
    blocks = [TextBlock(text="user text", origin="system"), ImageBlock(data="abc123", image_type="png", origin="user")]

    openai_parts = openai.content_block_parse(blocks)
    anthropic_parts = anthropic.content_block_parse(blocks)

    assert openai_parts == [
        {"type": "text", "text": "user text"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc123"}},
    ]
    assert anthropic_parts == [
        {"type": "text", "text": "user text"},
        {"type": "image", "source": {"type": "base64", "data": "abc123", "media_type": "png"}},
    ]
