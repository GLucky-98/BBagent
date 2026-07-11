import asyncio
import json
import os
import re
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, cast

import httpx

from .message import (
    ContentBlock,
    HumanMessage,
    ImageBlock,
    Message,
    ModelMessage,
    TextBlock,
    ToolMessage,
    ToolUseBlock,
)
from .tool import Tool


@dataclass
class Model_Input:  # noqa: N801
    prompt: str = ''
    tools: list[Tool] = field(default_factory=list)
    messages: list[Message] = field(default_factory=list)


PROVIDER_REGISTRY: dict[str, type["Model"]] = {}


class Model(ABC):
    _DEFAULT_TIMEOUT = httpx.Timeout(60.0, read=300.0)
    _DEFAULT_LIMITS = httpx.Limits(max_connections=100, max_keepalive_connections=20, keepalive_expiry=30)
    provider: str
    headers: dict[str, str]
    max_completion_tokens: int
    temperature: float
    top_p: float
    thinking: bool
    extra_args: dict[str, Any]

    def __init__(self, model: str, api_key: str, base_url: str, max_context_tokens: int = 200000, max_concurrent: int = 5):
        self.model = model
        self.api_key = api_key
        self.base_url_raw = base_url
        self.max_context_tokens = max_context_tokens
        self.max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._async_client: httpx.AsyncClient | None = None
        self._active_requests: int = 0

    @property
    def async_client(self) -> httpx.AsyncClient:
        if self._async_client is None or self._async_client.is_closed:
            self._async_client = httpx.AsyncClient(
                timeout=self._DEFAULT_TIMEOUT,
                limits=self._DEFAULT_LIMITS,
                headers=self.headers,
            )
        return self._async_client

    @property
    def active_requests(self) -> int:
        return self._active_requests

    async def aclose(self):
        if self._async_client is not None and not self._async_client.is_closed:
            await self._async_client.aclose()

    @abstractmethod
    def invoke(self, model_input: Model_Input) -> ModelMessage | str:
        pass

    @abstractmethod
    async def async_invoke(self, model_input: Model_Input)-> ModelMessage | str:
        pass

    @abstractmethod
    def async_stream_invoke(self, model_input: Model_Input) -> AsyncIterator[dict[str, Any]]:
        pass

    @abstractmethod
    def payload_construct(self, model_input: Model_Input) -> dict:
        pass

    @abstractmethod
    def model_response_parse(self, response: dict) -> ModelMessage | str:
        pass

    def to_config_dict(self) -> dict:
        """Subclass must set self.provider, self.max_completion_tokens, self.temperature, self.top_p, self.thinking, self.extra_args"""
        config = {
            "provider": self.provider,
            "model": self.model,
            "api_key": self.api_key,
            "base_url": self.base_url_raw,
            "max_completion_tokens": self.max_completion_tokens,
            "max_context_tokens": self.max_context_tokens,
            "max_concurrent": self.max_concurrent,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "thinking": self.thinking,
        }
        config.update(self.extra_args)
        return config

    @staticmethod
    def _resolve_env_vars(value: str) -> str:
        if not isinstance(value, str):
            return value
        pattern = re.compile(r'\$\{(\w+)\}')
        def _replacer(match):
            var_name = match.group(1)
            return os.environ.get(var_name, match.group(0))
        return pattern.sub(_replacer, value)

    @staticmethod
    def from_config_dict(config: dict) -> 'Model':
        provider = config.get("provider", "")
        provider_cls = PROVIDER_REGISTRY.get(provider)
        if provider_cls is None:
            raise ValueError(f"Unknown model provider: '{provider}'. Registered providers: {list(PROVIDER_REGISTRY.keys())}")
        params = {k: v for k, v in config.items() if k != "provider"}
        for key in list(params.keys()):
            if isinstance(params[key], str):
                params[key] = Model._resolve_env_vars(params[key])
        return cast(Model, provider_cls(**params))

    @staticmethod
    def _is_retryable(status_code: int) -> bool:
        if status_code == 429:
            return True
        return status_code >= 500

    @staticmethod
    def _classify_error(e: httpx.HTTPStatusError) -> str:
        status = e.response.status_code
        if status == 429:
            return f"Rate limited (429): {e}"
        if status >= 500:
            return f"Server error ({status}): {e}"
        if status in (401, 403):
            return f"Authentication error ({status}): {e}"
        return f"Client error ({status}): {e}"
#----------------------------------------------------------------------------
# Anthropic Model
##---------------------------------------------------------------------------
class AnthropicModel(Model):
    """Anthropic Claude API https://platform.claude.com/docs/en/api/messages/create"""

    def __init__(self,
                 model: str,
                 api_key: str,
                 base_url: str = "https://api.anthropic.com",
                 max_completion_tokens: int = 65536,
                 max_context_tokens: int = 200000,
                 max_concurrent: int = 5,
                 temperature: float = 1,
                 top_p: float = 1,
                 thinking: bool = True,
                 **kwargs):

        self.provider = "anthropic"
        self.base_url_raw = base_url
        self.base_url = base_url + '/v1/messages'

        super().__init__(model, api_key, base_url, max_context_tokens=max_context_tokens, max_concurrent=max_concurrent)

        self.max_completion_tokens = max_completion_tokens
        self.temperature = temperature
        self.top_p = top_p
        self.thinking = thinking
        self.extra_args = kwargs if kwargs else {}

        self.headers = {
                    "Content-Type": "application/json",
                    "anthropic-version": "2023-06-01",
                    "X-Api-Key": api_key,
                    }

        self.payload = {
                    "max_tokens": self.max_completion_tokens,
                    "model": self.model,
                    "temperature": self.temperature,
                    "top_p": self.top_p
                    }
        if thinking:
            self.payload["thinking"] = {"type": "adaptive"}
        else:
            self.payload["thinking"] = {"type": "disabled"}

        self.payload.update(self.extra_args)
        self._base_payload = dict(self.payload)

    def invoke(self, model_input: Model_Input, max_retries: int = 3, retry_delay: float = 1.0) -> ModelMessage | str:
        payload = self.payload_construct(model_input)
        timeout = httpx.Timeout(60.0, read=300.0)

        for attempt in range(max_retries):
            with httpx.Client(timeout=timeout) as client:
                try:
                    response = client.post(self.base_url, headers=self.headers, json=payload)
                    response.raise_for_status()
                    return self.model_response_parse(response.json())
                except httpx.HTTPStatusError as e:
                    if self._is_retryable(e.response.status_code) and attempt < max_retries - 1:
                        import time
                        time.sleep(retry_delay * (2 ** attempt))
                        continue
                    raise RuntimeError(f"{self._classify_error(e)} (after {max_retries} attempts)") from e
                except httpx.RequestError as e:
                    if attempt < max_retries - 1:
                        import time
                        time.sleep(retry_delay * (2 ** attempt))
                        continue
                    raise RuntimeError(f"Network error after {max_retries} attempts: {e}") from e
        raise RuntimeError(f"Anthropic request failed after {max_retries} attempts")

    async def async_invoke(self, model_input: Model_Input, max_retries: int = 3, retry_delay: float = 1.0) -> ModelMessage | str:
        payload = self.payload_construct(model_input)
        client = self.async_client
        await self._semaphore.acquire()
        self._active_requests += 1
        try:
            for attempt in range(max_retries):
                try:
                    response = await client.post(self.base_url, json=payload)
                    response.raise_for_status()
                    return self.model_response_parse(response.json())
                except httpx.HTTPStatusError as e:
                    if self._is_retryable(e.response.status_code) and attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay * (2 ** attempt))
                        continue
                    raise RuntimeError(f"{self._classify_error(e)} (after {max_retries} attempts)") from e
                except httpx.RequestError as e:
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay * (2 ** attempt))
                        continue
                    raise RuntimeError(f"Network error after {max_retries} attempts: {e}") from e
            raise RuntimeError(f"Anthropic request failed after {max_retries} attempts")
        finally:
            self._active_requests -= 1
            self._semaphore.release()

    async def async_stream_invoke(
        self,
        model_input: Model_Input,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ) -> AsyncIterator[dict[str, Any]]:
        payload = {**self.payload_construct(model_input), 'stream': True}
        client = self.async_client
        await self._semaphore.acquire()
        self._active_requests += 1

        accumulated_message: dict[str, Any] = {"content": [], "usage": {}}
        accumulated_block: list[dict[str, Any] | None] = []

        try:
            for attempt in range(max_retries):
                try:
                    async with client.stream('POST', self.base_url, json=payload) as response:
                        response.raise_for_status()
                        async for line in response.aiter_lines():
                            if line.startswith('data: '):
                                data = line[6:]
                                if data == '[DONE]':
                                    continue
                                try:
                                    event = json.loads(data)
                                    event_type = event.get('type','')
                                    if event_type == 'ping':
                                        continue
                                    if event_type == 'error':
                                        error_info = event.get('error', {})
                                        raise Exception(f"Stream error: {error_info.get('type')} - {error_info.get('message')}")
                                    if event_type == 'message_start':
                                        accumulated_message.update(event.get('message',{}))
                                        accumulated_message.setdefault('content', [])
                                        accumulated_message.setdefault('usage', {})
                                        continue
                                    if event_type == 'content_block_start':
                                        index = int(event.get('index', 0))
                                        while len(accumulated_block) <= index:
                                            accumulated_block.append(None)
                                        accumulated_block[index] = event.get('content_block',{})
                                        continue
                                    if event_type == 'content_block_delta':
                                        index = int(event.get('index', 0))
                                        delta = event.get('delta',{})
                                        delta_type = delta.get('type','')
                                        block = accumulated_block[index] if index < len(accumulated_block) else None
                                        if block:
                                            if delta_type == 'text_delta':
                                                if block.get('type') == 'text':
                                                    block['text'] = block.get('text', '') + delta.get('text', '')
                                                    yield {'type':'text','content':delta.get('text', '')}
                                            elif delta_type == 'input_json_delta':
                                                if block.get('type') == 'tool_use':
                                                    block['partial_json'] = block.get('partial_json', '') + delta.get('partial_json', '')
                                                    continue
                                            elif delta_type == 'thinking_delta':
                                                if block.get('type') == 'thinking':
                                                    block['thinking'] = block.get('thinking', '') + delta.get('thinking', '')
                                                    yield {'type':'thinking','content':delta.get('thinking', '')}
                                            elif delta_type == 'signature_delta' and block.get('type') == 'thinking':
                                                block['signature'] = delta.get('signature', '')
                                    if event_type == 'content_block_stop':
                                        index = int(event.get('index', 0))
                                        block = accumulated_block[index] if index < len(accumulated_block) else None
                                        if block is None:
                                            continue
                                        if block.get('type','') == 'tool_use':
                                            block['input'] = json.loads(block['partial_json'])
                                            tool_use = ToolUseBlock(block['id'], block['name'], block['input'])
                                            yield {'type':'completed_tool_use','content':tool_use}
                                        accumulated_message.setdefault('content', []).append(block)
                                        continue
                                    if event_type == 'message_delta':
                                        if 'delta' in event:
                                            accumulated_message.update(event.get('delta',{}))
                                        if 'usage' in event:
                                            accumulated_message.setdefault('usage', {}).update(event.get('usage',{}))
                                        continue
                                    if event_type == 'message_stop':
                                        yield {'type':'completed_message','content':self.model_response_parse(accumulated_message)}
                                        return
                                except json.JSONDecodeError:
                                    continue
                except httpx.HTTPStatusError as e:
                    if self._is_retryable(e.response.status_code) and attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay * (2 ** attempt))
                        continue
                    raise RuntimeError(f"{self._classify_error(e)} (after {max_retries} attempts)") from e
                except httpx.RequestError as e:
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay * (2 ** attempt))
                        continue
                    raise RuntimeError(f"Network error after {max_retries} attempts: {e}") from e
        finally:
            self._active_requests -= 1
            self._semaphore.release()

    def payload_construct(self, model_input: Model_Input) -> dict:
        payload: dict[str, Any] = dict(self._base_payload)

        if model_input.prompt:
            payload['system'] = model_input.prompt

        if model_input.tools:
            payload['tools'] = [t.schema for t in model_input.tools]

        payload_messages: list[dict[str, Any]] = []
        if model_input.messages:
            for message in model_input.messages:
                if isinstance(message, HumanMessage):
                    if isinstance(message.content,list):
                        payload_messages.append({'role':'user', 'content':self.content_block_parse(message.content)})
                    else:
                        payload_messages.append({'role':'user', 'content':str(message.content)})
                if isinstance(message, ModelMessage):
                    payload_messages.append(self.model_message_to_payload(message))
                if isinstance(message, ToolMessage):
                    if isinstance(message.content,list):
                        payload_messages.append({'role':'user', 'content':[{'type':'tool_result','tool_use_id':message.id,'content':self.content_block_parse(message.content)}]})
                    else:
                        payload_messages.append({'role':'user', 'content':[{'type':'tool_result','tool_use_id':message.id,'content':str(message.content)}]})

        payload['messages'] = payload_messages

        return payload

    def model_message_to_payload(self, message: ModelMessage) -> dict:
        """Rebuild Anthropic API format from ModelMessage structured fields (without relying on raw_json)"""
        content: list[dict[str, Any]] = []
        # thinking block (with signature to maintain extended thinking continuity)
        if message.thinking:
            thinking_block = {"type": "thinking", "thinking": message.thinking}
            if message.thinking_signature:
                thinking_block["signature"] = message.thinking_signature
            content.append(thinking_block)
        # content block
        if isinstance(message.content, str):
            if message.content:
                content.append({"type": "text", "text": message.content})
        elif isinstance(message.content, list):
            content.extend(self.content_block_parse(message.content))
        # tool_use block
        for tc in message.tool_calls:
            content.append({
                "type": "tool_use",
                "id": tc.id,
                "name": tc.name,
                "input": tc.input,
            })
        return {"role": "assistant", "content": content}

    def content_block_parse(self, content_blocks: list[ContentBlock]) -> list[dict]:
        """Parse content blocks, actually only handles content block parsing in HumanMessage and ToolMessage"""
        result: list[dict[str, Any]] = []
        for block in content_blocks:
            if isinstance(block, TextBlock):
                result.append({'type':'text','text':block.text})
            if isinstance(block, ImageBlock):
                result.append({'type':'image','source':{'type':'base64','data':block.data,'media_type':block.image_type}})

        return result

    def model_response_parse(self, response:dict) -> ModelMessage:
        id = response.get('id','')
        stop_reason = response.get('stop_reason','')
        usage_data: dict[str, Any] = response.get('usage',{})
        raw_content = response.get('content',[])
        raw_json = json.dumps({'role':'assistant','content':raw_content}, ensure_ascii=False)

        tool_calls: list[ToolUseBlock] = []
        thinking = ''
        thinking_signature = ''
        content: list[ContentBlock] | str
        if isinstance(raw_content,list):
            content_blocks: list[ContentBlock] = []
            for block in raw_content:
                if block['type'] == 'text':
                    content_blocks.append(TextBlock(text=block['text'], origin="model"))
                if block['type'] == 'thinking':
                    thinking += block['thinking']
                    thinking_signature = block.get('signature', '') or thinking_signature
                if block['type'] == 'image':
                    content_blocks.append(
                        ImageBlock(
                            data=block['source']['data'],
                            image_type=block['source']['media_type'],
                            origin="model",
                        )
                    )
                if block['type'] == 'tool_use':
                    tool_calls.append(ToolUseBlock(id=block['id'], name=block['name'], input=block['input']))
            content = content_blocks
        else:
            content = raw_content

        input_tokens = (usage_data.get('input_tokens', 0)
                        + usage_data.get('cache_read_input_tokens', 0)
                        + usage_data.get('cache_creation_input_tokens', 0))
        output_tokens = usage_data.get('output_tokens', 0)

        return ModelMessage(id=id,
                            raw_json=raw_json,
                            content=content,
                            thinking=thinking,
                            thinking_signature=thinking_signature,
                            tool_calls=tool_calls,
                            stop_reason=stop_reason,
                            usage_data=usage_data,
                            input_tokens=input_tokens,
                            output_tokens=output_tokens)



# ----------------------------------------------------------------------------
# OpenAI Model
# ----------------------------------------------------------------------------
class OpenAIModel(Model):
    """OpenAI Chat Completions API https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create"""

    def __init__(self,
                 model: str,
                 api_key: str,
                 base_url: str = "https://api.openai.com/v1",
                 max_completion_tokens: int = 65536,
                 max_context_tokens: int = 200000,
                 max_concurrent: int = 5,
                 temperature: float = 1.0,
                 top_p: float = 1.0,
                 thinking: bool = True,
                 **kwargs):

        self.provider = "openai"
        self.base_url_raw = base_url

        super().__init__(model, api_key, base_url, max_context_tokens=max_context_tokens, max_concurrent=max_concurrent)
        self.base_url = base_url.rstrip('/') + '/chat/completions'
        self.max_completion_tokens = max_completion_tokens
        self.temperature = temperature
        self.top_p = top_p
        self.thinking = thinking
        self.extra_args = kwargs if kwargs else {}

        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

        self.payload = {
            "model": self.model,
            "max_completion_tokens": self.max_completion_tokens,
            "temperature": self.temperature,
            "top_p": self.top_p,
        }
        if thinking:
            self.payload["thinking"] = {"type": "adaptive"}
        else:
            self.payload["thinking"] = {"type": "disabled"}

        self.payload['n'] = 1

        self.payload.update(self.extra_args)
        self._base_payload = dict(self.payload)

    def payload_construct(self, model_input: Model_Input) -> dict:
        """Build OpenAI request payload from Model_Input"""
        payload: dict[str, Any] = dict(self._base_payload)
        messages: list[dict[str, Any]] = []

        # 1. handle system prompt (OpenAI uses system role)
        if model_input.prompt:
            messages.append({"role": "system", "content": model_input.prompt})

        # 2. convert history messages
        for msg in model_input.messages:
            if isinstance(msg, HumanMessage):
                # user message: can be plain text or content block list
                content = self.content_block_parse(msg.content)
                messages.append({"role": "user", "content": content})

            elif isinstance(msg, ModelMessage):
                messages.append(self.model_message_to_payload(msg))

            elif isinstance(msg, ToolMessage):
                # tool response message
                content = self.content_block_parse(msg.content)
                messages.append({
                    "role": "tool",
                    "tool_call_id": msg.id,
                    "content": content
                })

        payload["messages"] = messages

        # 3. handle tool definitions
        if model_input.tools:
            tools: list[dict[str, Any]] = []
            for tool in model_input.tools:
                # convert our Tool object to OpenAI function format
                tools.append({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.input_schema,  # assume parameters is already a JSON Schema dict
                    }
                })
            payload["tools"] = tools
            # default to auto tool selection, can be extended to accept tool_choice parameter
            if "tool_choice" not in payload:
                payload["tool_choice"] = "auto"

        return payload

    def model_message_to_payload(self, message: ModelMessage) -> dict:
        """Rebuild OpenAI API format from ModelMessage structured fields (without relying on raw_json)"""
        content = self.content_block_parse(message.content)
        result: dict[str, Any] = {"role": "assistant", "content": content if content else None}

        if message.thinking:
            result["reasoning_content"] = message.thinking

        # convert tool_calls to OpenAI function format
        if message.tool_calls:
            result["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.name,
                        "arguments": json.dumps(tc.input, ensure_ascii=False),
                    },
                }
                for tc in message.tool_calls
            ]
        return result

    def content_block_parse(self, content: str | list[ContentBlock]) -> str | list[dict]:
        """
        Convert internal ContentBlock list or plain text to format accepted by OpenAI API.
        Returns string or list of content parts.
        """
        if isinstance(content, str):
            return content
        if not isinstance(content, list):
            return str(content)

        parts: list[dict[str, Any]] = []
        for block in content:
            if isinstance(block, TextBlock):
                parts.append({"type": "text", "text": block.text})
            elif isinstance(block, ImageBlock):
                # OpenAI uses image_url type, needs data:image/...;base64,xxx
                mime = f"image/{block.image_type}" if block.image_type != "svg" else "image/svg+xml"
                data_url = f"data:{mime};base64,{block.data}"
                parts.append({
                    "type": "image_url",
                    "image_url": {"url": data_url}
                })
        return parts

    def model_response_parse(self, response: dict) -> ModelMessage:
        """Parse OpenAI response, return ModelMessage object"""
        msg_id = response.get("id", "")
        choice = response["choices"][0]
        message = choice["message"]
        finish_reason = choice.get("finish_reason", "")
        usage = response.get("usage", {})
        raw_json = json.dumps(message, ensure_ascii=False)

        # parse content (may be None or string)
        raw_content = message.get("content")
        content: list[ContentBlock] | str
        if raw_content is None:
            content = []
        elif isinstance(raw_content, str):
            content = raw_content
        else:
            # if list (multimodal response, rare), recurse
            content = self._parse_content_parts(raw_content)

        thinking = message.get("reasoning_content", "")

        # parse tool_calls
        tool_calls: list[ToolUseBlock] = []
        if message.get("tool_calls"):
            for tc in message["tool_calls"]:
                if tc["type"] == "function":
                    func = tc["function"]
                    try:
                        arguments = json.loads(func["arguments"])
                    except (json.JSONDecodeError, TypeError):
                        arguments = func["arguments"]
                    tool_calls.append(ToolUseBlock(
                        id=tc["id"],
                        name=func["name"],
                        input=arguments
                    ))

        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens = usage.get("completion_tokens", 0)

        stop_reason_normalized = finish_reason
        if finish_reason == 'stop':
            stop_reason_normalized = 'end_turn'
        elif finish_reason == 'tool_calls':
            stop_reason_normalized = 'tool_use'

        return ModelMessage(
            id=msg_id,
            raw_json=raw_json,
            content=content,
            thinking=thinking,
            tool_calls=tool_calls,
            stop_reason=stop_reason_normalized,
            usage_data=usage,
            input_tokens=input_tokens,
            output_tokens=output_tokens
        )



    def _parse_content_parts(self, parts: list) -> list[ContentBlock]:
        """Convert content parts in OpenAI response to internal ContentBlock list"""
        blocks: list[ContentBlock] = []
        for part in parts:
            if part.get("type") == "text":
                blocks.append(TextBlock(text=part["text"], origin="model"))
            elif part.get("type") == "image_url":
                # response usually has no image_url, but kept for compatibility
                url = part["image_url"]["url"]
                if url.startswith("data:"):
                    # parse base64
                    import re
                    match = re.match(r"data:image/(\w+);base64,(.+)", url)
                    if match:
                        img_type, data = match.groups()
                        blocks.append(ImageBlock(data=data, image_type=img_type, origin="model"))
            elif part.get("type") == "refusal":
                blocks.append(TextBlock(text=f"[Refusal: {part['refusal']}]", origin="model"))
        return blocks

    def invoke(self, model_input: Model_Input, max_retries: int = 3, retry_delay: float = 1.0) -> ModelMessage | str:
        payload = self.payload_construct(model_input)
        timeout = httpx.Timeout(60.0, read=300.0)

        for attempt in range(max_retries):
            with httpx.Client(timeout=timeout) as client:
                try:
                    response = client.post(self.base_url, headers=self.headers, json=payload)
                    response.raise_for_status()
                    return self.model_response_parse(response.json())
                except httpx.HTTPStatusError as e:
                    if self._is_retryable(e.response.status_code) and attempt < max_retries - 1:
                        import time
                        time.sleep(retry_delay * (2 ** attempt))
                        continue
                    raise RuntimeError(f"{self._classify_error(e)} (after {max_retries} attempts)") from e
                except httpx.RequestError as e:
                    if attempt < max_retries - 1:
                        import time
                        time.sleep(retry_delay * (2 ** attempt))
                        continue
                    raise RuntimeError(f"Network error after {max_retries} attempts: {e}") from e
        raise RuntimeError(f"OpenAI request failed after {max_retries} attempts")

    async def async_invoke(self, model_input: Model_Input, max_retries: int = 3, retry_delay: float = 1.0) -> ModelMessage | str:
        payload = self.payload_construct(model_input)
        client = self.async_client
        await self._semaphore.acquire()
        self._active_requests += 1
        try:
            for attempt in range(max_retries):
                try:
                    response = await client.post(self.base_url, json=payload)
                    response.raise_for_status()
                    return self.model_response_parse(response.json())
                except httpx.HTTPStatusError as e:
                    if self._is_retryable(e.response.status_code) and attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay * (2 ** attempt))
                        continue
                    raise RuntimeError(f"{self._classify_error(e)} (after {max_retries} attempts)") from e
                except httpx.RequestError as e:
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay * (2 ** attempt))
                        continue
                    raise RuntimeError(f"Network error after {max_retries} attempts: {e}") from e
            raise RuntimeError(f"OpenAI request failed after {max_retries} attempts")
        finally:
            self._active_requests -= 1
            self._semaphore.release()

    async def async_stream_invoke(
        self,
        model_input: Model_Input,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ) -> AsyncIterator[dict[str, Any]]:
        """Async streaming call, yields events (need_print, completed_tool_use, completed_message)"""
        payload = {**self.payload_construct(model_input), "stream": True, "stream_options": {"include_usage": True}}
        client = self.async_client
        await self._semaphore.acquire()
        self._active_requests += 1

        accumulated_response: dict[str, Any] = {}
        accumulated_response['usage'] = {}
        accumulated_response['id'] = ''
        accumulated_response['choices'] = [{}]
        accumulated_response['choices'][0]['message'] = {}
        accumulated_response['choices'][0]['index'] = 0
        accumulated_message: dict[str, Any] = accumulated_response['choices'][0]['message']
        accumulated_message['role'] = 'assistant'

        accumulated_tool_calls: dict[int, dict[str, str | None]] = {}
        _stream_finished = False

        try:
            for attempt in range(max_retries):
                try:
                    async with client.stream("POST", self.base_url, json=payload) as response:
                        response.raise_for_status()
                        async for line in response.aiter_lines():
                            if not line.startswith("data:"):
                                continue
                            data_str = line[5:].lstrip()
                            if data_str == "[DONE]":
                                if _stream_finished:
                                    if accumulated_response.get('usage'):
                                        yield {"type": "completed_message", "content": self.model_response_parse(accumulated_response)}
                                    return
                                continue
                            try:
                                chunk = json.loads(data_str)
                            except json.JSONDecodeError:
                                continue

                            if chunk.get("usage"):
                                accumulated_response['usage'] = chunk["usage"]
                                if _stream_finished:
                                    yield {"type": "completed_message", "content": self.model_response_parse(accumulated_response)}
                                    return

                            choices = chunk.get("choices", [])
                            if not choices:
                                continue

                            delta = choices[0].get("delta", {})
                            finish_reason = choices[0].get("finish_reason")

                            if "content" in delta and delta["content"] is not None:
                                accumulated_message['content'] = accumulated_message.get('content', '') + delta["content"]
                                yield {"type": "text", "content": delta["content"]}

                            if "reasoning_content" in delta and delta["reasoning_content"] is not None:
                                accumulated_message['reasoning_content'] = accumulated_message.get('reasoning_content', '') + delta["reasoning_content"]
                                yield {"type": "thinking", "content": delta["reasoning_content"]}

                            if "tool_calls" in delta and delta["tool_calls"] is not None:
                                for tc_delta in delta["tool_calls"]:
                                    idx = int(tc_delta.get("index", 0))
                                    if idx not in accumulated_tool_calls:
                                        accumulated_tool_calls[idx] = {
                                            "id": None,
                                            "name": None,
                                            "arguments": ""
                                        }
                                    if "id" in tc_delta:
                                        accumulated_tool_calls[idx]["id"] = tc_delta["id"]
                                    if "function" in tc_delta:
                                        func = tc_delta["function"]
                                        if "name" in func:
                                            accumulated_tool_calls[idx]["name"] = func["name"]
                                        if "arguments" in func:
                                            accumulated_tool_calls[idx]["arguments"] = (
                                                (accumulated_tool_calls[idx]["arguments"] or "") + func["arguments"]
                                            )

                            if finish_reason:
                                accumulated_response['id'] = chunk.get("id", "")
                                accumulated_response['choices'][0]['finish_reason'] = finish_reason
                                if accumulated_tool_calls:
                                    accumulated_message['tool_calls'] = []
                                    for idx, tc in accumulated_tool_calls.items():
                                        accumulated_message['tool_calls'].append({})
                                        accumulated_message['tool_calls'][idx]["index"] = idx

                                        tool_call_id = tc["id"]
                                        tool_call_name = tc["name"]
                                        tool_call_arguments = tc["arguments"] or ""
                                        if tool_call_id and tool_call_name:
                                            try:
                                                args = json.loads(tool_call_arguments)
                                            except json.JSONDecodeError:
                                                args = tool_call_arguments
                                            tool_use = ToolUseBlock(
                                                id=tool_call_id,
                                                name=tool_call_name,
                                                input=args
                                            )
                                            accumulated_message['tool_calls'][idx]["id"] = tool_call_id
                                            accumulated_message['tool_calls'][idx]["type"] = 'function'
                                            accumulated_message['tool_calls'][idx]["function"] = {
                                                "name": tool_call_name,
                                                "arguments": tool_call_arguments,
                                            }
                                            yield {"type": "completed_tool_use", "content": tool_use}
                                    accumulated_tool_calls.clear()

                                _stream_finished = True
                                if accumulated_response.get('usage'):
                                    yield {"type": "completed_message", "content": self.model_response_parse(accumulated_response)}
                                    return

                except httpx.HTTPStatusError as e:
                    if self._is_retryable(e.response.status_code) and attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay * (2 ** attempt))
                        continue
                    raise RuntimeError(f"{self._classify_error(e)} (after {max_retries} attempts)") from e
                except httpx.RequestError as e:
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay * (2 ** attempt))
                        continue
                    raise RuntimeError(f"Network error after {max_retries} attempts: {e}") from e
        finally:
            self._active_requests -= 1
            self._semaphore.release()

PROVIDER_REGISTRY["anthropic"] = AnthropicModel
PROVIDER_REGISTRY["openai"] = OpenAIModel
