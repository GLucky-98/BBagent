from .message import ModelMessage
import json
from abc import ABC, abstractmethod
from typing import List, AsyncIterator, Union
import httpx
import asyncio
from dataclasses import dataclass, field



from .message import *
from .tool import Tool

@dataclass
class Model_Input:
    prompt: str = ''
    tools: List[Tool] = field(default_factory=list)
    messages: List[Message] = field(default_factory=list)

class Model(ABC):
    def __init__(self, model: str, api_key: str, base_url: str):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url

    @abstractmethod
    def invoke(self, model_input: Model_Input) -> ModelMessage | str:
        pass

    @abstractmethod
    async def async_invoke(self, model_input: Model_Input)-> ModelMessage | str:
        pass

    @abstractmethod
    async def async_stream_invoke(self, model_input: Model_Input) -> AsyncIterator[dict]:
        pass

    @abstractmethod
    def payload_construct(self, model_input: Model_Input) -> None:
        pass

    @abstractmethod
    def model_response_parse(self, response:dict) -> ModelMessage | str:
        pass
#----------------------------------------------------------------------------
# Anthropic Model
##---------------------------------------------------------------------------
class AnthropicModel(Model):
    """Anthropic Claude API https://platform.claude.com/docs/en/api/messages/create"""

    def __init__(self,
                 model: str,
                 api_key: str,
                 base_url: str = "https://api.anthropic.com",
                 max_tokens: int = 100000,
                 temperature: float = 1,
                 top_p: float = 0.95,
                 thinking: dict = None,
                 **kwargs):
        
        super().__init__(model, api_key, base_url+'/v1/messages')
        
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.top_p = top_p
        self.thinking = thinking if thinking is not None else {"type":"adaptive","display":"summarized"}
        self.extra_args = kwargs if kwargs else {}

        self.headers = {
                    "Content-Type": "application/json",
                    "anthropic-version": "2023-06-01",
                    "X-Api-Key": api_key,
                    }

        self.payload = {
                    "max_tokens": self.max_tokens,
                    "model": self.model,
                    "temperature": self.temperature,
                    "top_p": self.top_p
                    }
        
        self.payload.update(self.extra_args)
        self._base_payload = dict(self.payload)

    def invoke(self, model_input: Model_Input, max_retries: int = 3, retry_delay: float = 1.0) -> ModelMessage | str:
        
        self.payload_construct(model_input)
        # print(self.payload)
        timeout = httpx.Timeout(60.0, read=300.0)

        for attempt in range(max_retries):
            with httpx.Client(timeout=timeout) as client:
                try:
                    response = client.post(self.base_url, headers=self.headers, json=self.payload)
                    response.raise_for_status()
                    return self.model_response_parse(response.json())
                except (httpx.HTTPStatusError, httpx.RequestError) as e:
                    if attempt < max_retries - 1:
                        import time
                        time.sleep(retry_delay * (2 ** attempt))  # exponential backoff
                        print(f"Retry {attempt + 1}/{max_retries} after error: {e}")
                        continue
                    print(f"HTTP error after {max_retries} attempts: {e}")
                    raise
    
    async def async_invoke(self, model_input: Model_Input, max_retries: int = 3, retry_delay: float = 1.0) -> ModelMessage | str:
        self.payload_construct(model_input)
        timeout = httpx.Timeout(60.0, read=300.0)

        for attempt in range(max_retries):
            async with httpx.AsyncClient(timeout=timeout) as client:
                try:
                    response = await client.post(self.base_url, headers=self.headers, json=self.payload)
                    response.raise_for_status()
                    return self.model_response_parse(response.json())
                except (httpx.HTTPStatusError, httpx.RequestError) as e:
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay * (2 ** attempt))
                        print(f"Retry {attempt + 1}/{max_retries} after error: {e}")
                        continue
                    print(f"HTTP error after {max_retries} attempts: {e}")
                    raise
    
    async def async_stream_invoke(self, model_input: Model_Input, max_retries: int = 3, retry_delay: float = 1.0):
        self.payload_construct(model_input)
        payload = {**self.payload, 'stream': True}
        timeout = httpx.Timeout(60.0, read=300.0)

        accumulated_message = {}
        accumulated_block = []

        for attempt in range(max_retries):
            async with httpx.AsyncClient(timeout=timeout) as client:
                try:
                    async with client.stream('POST', self.base_url, headers=self.headers, json=payload) as response:
                        response.raise_for_status()
                        async for line in response.aiter_lines():
                            if line.startswith('data: '):
                                data = line[6:]
                                if data == '[DONE]':
                                    continue                           
                                try:
                                    event = json.loads(data)
                                    event_type = event.get('type','')
                                    # ping event
                                    if event_type == 'ping':
                                        continue
                                    # error event
                                    if event_type == 'error':
                                        error_info = event.get('error', {})
                                        raise Exception(f"Stream error: {error_info.get('type')} - {error_info.get('message')}")
                                    # message start
                                    if event_type == 'message_start':
                                        accumulated_message.update(event.get('message',{}))
                                        continue
                                    # block start
                                    if event_type == 'content_block_start':
                                        index = event.get('index',None)
                                        while len(accumulated_block) <= index:
                                            accumulated_block.append(None)
                                        accumulated_block[index] = event.get('content_block',{})
                                        continue
                                    # block delta
                                    if event_type == 'content_block_delta':
                                        index = event.get('index',None)
                                        delta = event.get('delta',{})
                                        delta_type = delta.get('type','')
                                        block = accumulated_block[index] if index < len(accumulated_block) else None
                                        if block:
                                            if delta_type == 'text_delta':
                                                # 文本增量：追加到 text 字段
                                                if block.get('type') == 'text':
                                                    block['text'] = block.get('text', '') + delta.get('text', '')
                                                    yield {'type':'text','content':delta.get('text', '')}
                                            elif delta_type == 'input_json_delta':
                                                # 工具输入 JSON 增量：累积 partial_json 字符串
                                                if block.get('type') == 'tool_use':
                                                    block['partial_json'] = block.get('partial_json', '') + delta.get('partial_json', '')
                                                    continue
                                            elif delta_type == 'thinking_delta':
                                                # 思考内容增量
                                                if block.get('type') == 'thinking':
                                                    block['thinking'] = block.get('thinking', '') + delta.get('thinking', '')
                                                    yield {'type':'thinking','content':delta.get('thinking', '')}
                                            elif delta_type == 'signature_delta':
                                                # 签名增量（用于 thinking 块）
                                                if block.get('type') == 'thinking':
                                                    block['signature'] = delta.get('signature', '')
                                    # block stop
                                    if event_type == 'content_block_stop':
                                        index = event.get('index',None)
                                        block = accumulated_block[index] if index < len(accumulated_block) else None
                                        # yield completed tool use block for stream tool invoking
                                        if block.get('type','') == 'tool_use':
                                            block['input'] = json.loads(block['partial_json'])
                                            tool_use = ToolUseBlock(block['id'], block['name'], block['input'])
                                            yield {'type':'completed_tool_use','content':tool_use}
                                        accumulated_message['content'].append(block)
                                        continue
                                    # message delta
                                    if event_type == 'message_delta':
                                        if 'delta' in event:
                                            accumulated_message.update(event.get('delta',{}))
                                        if 'usage' in event:
                                            accumulated_message['usage'].update(event.get('usage',{}))
                                        continue
                                    # message stop
                                    if event_type == 'message_stop':
                                        yield {'type':'completed_message','content':self.model_response_parse(accumulated_message)}
                                        return
                                except json.JSONDecodeError:
                                    continue             
                except (httpx.HTTPStatusError, httpx.RequestError) as e:
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay * (2 ** attempt))
                        print(f"Retry {attempt + 1}/{max_retries} after error: {e}")
                        continue
                    print(f"HTTP error after {max_retries} attempts: {e}")
                    raise Exception(f"HTTP error after {max_retries} attempts: {e}")    

    def payload_construct(self, model_input: Model_Input):
        self.payload = dict(self._base_payload)

        if model_input.prompt:
            self.payload['system'] = model_input.prompt

        if model_input.tools:
            self.payload['tools'] = [t.schema for t in model_input.tools]

        if self.thinking:
            self.payload['thinking'] = self.thinking
        
        payload_messages = []
        if model_input.messages:
            for message in model_input.messages:
                if isinstance(message, HumanMessage):
                    if isinstance(message.content,list):
                        payload_messages.append({'role':'user', 'content':self.content_block_parse(message.content)})
                    else:
                        payload_messages.append({'role':'user', 'content':str(message.content)})
                if isinstance(message, ModelMessage):
                    payload_messages.append(json.loads(message.raw_json))
                if isinstance(message, ToolMessage):
                    if isinstance(message.content,list):
                        payload_messages.append({'role':'user', 'content':[{'type':'tool_result','tool_use_id':message.id,'content':self.content_block_parse(message.content)}]})
                    else:
                        payload_messages.append({'role':'user', 'content':[{'type':'tool_result','tool_use_id':message.id,'content':str(message.content)}]})
    
        self.payload['messages'] = payload_messages
        
        return
    
    def content_block_parse(self, content_blocks: List[ContentBlock]) -> List[dict]:
        """解析内容块, 其实只负责HumanMessage和ToolMessage里的内容块解析"""
        result = []
        for block in content_blocks:
            if isinstance(block, TextBlock):
                result.append({'type':'text','text':block.text})
            if isinstance(block, ImageBlock):
                result.append({'type':'image','source':{'type':'base64','data':block.data,'media_type':block.image_type}})

        return result

    def model_response_parse(self, response:dict) -> ModelMessage:       
        id = response.get('id','')
        stop_reason = response.get('stop_reason','')       
        usage_data = response.get('usage',{})   
        raw_content = response.get('content',[])
        raw_json = json.dumps({'role':'assistant','content':raw_content})

        tool_calls = []
        thinking = ''
        if isinstance(raw_content,list):
            content = []
            for block in raw_content:
                if block['type'] == 'text':
                    content.append(TextBlock(text=block['text']))
                if block['type'] == 'thinking':
                    thinking += block['thinking']
                if block['type'] == 'image':
                    content.append(ImageBlock(data=block['source']['data'], image_type=block['source']['media_type']))
                if block['type'] == 'tool_use':
                    tool_calls.append(ToolUseBlock(id=block['id'], name=block['name'], input=block['input']))
        else:
            content = raw_content
        
        input_tokens = usage_data.get('input_tokens',0)
        token_num = usage_data.get('output_tokens',0)

        return ModelMessage(id=id,
                            raw_json=raw_json,
                            content=content,
                            thinking=thinking,
                            tool_calls=tool_calls,
                            stop_reason=stop_reason,
                            usage_data=usage_data,
                            input_tokens=input_tokens,
                            token_num=token_num)       



# ----------------------------------------------------------------------------
# OpenAI Model
# ----------------------------------------------------------------------------
class OpenAIModel(Model):
    """OpenAI Chat Completions API https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create"""

    def __init__(self,
                 model: str,
                 api_key: str,
                 base_url: str = "https://api.openai.com/v1",
                 max_completion_tokens: int = 100000,
                 temperature: float = 1.0,
                 top_p: float = 1.0,
                 thinking: dict = None,
                 **kwargs):

        super().__init__(model, api_key, base_url)
        self.base_url = base_url.rstrip('/') + '/chat/completions'
        self.max_completion_tokens = max_completion_tokens
        self.temperature = temperature
        self.top_p = top_p
        self.thinking = thinking if thinking is not None else {'type':'enabled'}
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
            "thinking": self.thinking,
        }

        self.payload['n'] = 1

        self.payload.update(self.extra_args)
        self._base_payload = dict(self.payload)

    def payload_construct(self, model_input: Model_Input) -> None:
        """根据 Model_Input 构建 OpenAI 请求 payload"""
        self.payload = dict(self._base_payload)
        messages = []

        # 1. 处理 system prompt（OpenAI 使用 system 角色）
        if model_input.prompt:
            messages.append({"role": "system", "content": model_input.prompt})

        # 2. 转换历史消息
        for msg in model_input.messages:
            if isinstance(msg, HumanMessage):
                # 用户消息：可以是纯文本或 content block 列表
                content = self.content_block_parse(msg.content)
                messages.append({"role": "user", "content": content})

            elif isinstance(msg, ModelMessage):
                raw_message = json.loads(msg.raw_json)
                need_part = {
                    'role': raw_message.get('role', 'assistant'),
                    'content': raw_message.get('content'),
                }
                if 'tool_calls' in raw_message:
                    need_part['tool_calls'] = raw_message['tool_calls']
                messages.append(need_part)

            elif isinstance(msg, ToolMessage):
                # 工具响应消息
                content = self.content_block_parse(msg.content)
                messages.append({
                    "role": "tool",
                    "tool_call_id": msg.id,
                    "content": content
                })

        self.payload["messages"] = messages

        # 3. 处理工具定义
        if model_input.tools:
            tools = []
            for tool in model_input.tools:
                # 将我们的 Tool 对象转换为 OpenAI function 格式
                tools.append({
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.input_schema,  # 假定 parameters 已是 JSON Schema dict
                    }
                })
            self.payload["tools"] = tools
            # 默认自动选择工具，可扩展为接收 tool_choice 参数
            if "tool_choice" not in self.payload:
                self.payload["tool_choice"] = "auto"

    def content_block_parse(self, content: Union[str, List[ContentBlock]]) -> Union[str, List[dict]]:
        """
        将内部 ContentBlock 列表或纯文本转换为 OpenAI API 接受的格式
        返回字符串或 list of content parts
        """
        if isinstance(content, str):
            return content
        if not isinstance(content, list):
            return str(content)

        parts = []
        for block in content:
            if isinstance(block, TextBlock):
                parts.append({"type": "text", "text": block.text})
            elif isinstance(block, ImageBlock):
                # OpenAI 使用 image_url 类型，需要 data:image/...;base64,xxx
                mime = f"image/{block.image_type}" if block.image_type != "svg" else "image/svg+xml"
                data_url = f"data:{mime};base64,{block.data}"
                parts.append({
                    "type": "image_url",
                    "image_url": {"url": data_url}
                })
        return parts

    def model_response_parse(self, response: dict) -> ModelMessage:
        """解析 OpenAI 响应，返回 ModelMessage 对象"""
        msg_id = response.get("id", "")
        choice = response["choices"][0]
        message = choice["message"]
        finish_reason = choice.get("finish_reason", "")
        usage = response.get("usage", {})
        raw_json = json.dumps(message)

        # 解析 content (可能为 None 或字符串)
        raw_content = message.get("content")
        if raw_content is None:
            content = []
        elif isinstance(raw_content, str):
            content = raw_content
        else:
            # 如果是 list (多模态响应，少见)，递归处理
            content = self._parse_content_parts(raw_content)

        thinking = message.get("reasoning_content", "")

        # 解析 tool_calls
        tool_calls = []
        if "tool_calls" in message and message["tool_calls"]:
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
        token_num = usage.get("completion_tokens", 0)
        
        # 构造 ModelMessage，需要 id（从响应中获取）
        return ModelMessage(
            id=msg_id,
            raw_json=raw_json,
            content=content,
            thinking=thinking,
            tool_calls=tool_calls,
            stop_reason=finish_reason,
            usage_data=usage,
            input_tokens=input_tokens,
            token_num=token_num
        )

    def _parse_content_parts(self, parts: list) -> List[ContentBlock]:
        """将 OpenAI 响应中的 content parts 转换为内部 ContentBlock 列表"""
        blocks = []
        for part in parts:
            if part.get("type") == "text":
                blocks.append(TextBlock(text=part["text"]))
            elif part.get("type") == "image_url":
                # 通常响应不会有 image_url，但保留兼容
                url = part["image_url"]["url"]
                if url.startswith("data:"):
                    # 解析 base64
                    import re
                    match = re.match(r"data:image/(\w+);base64,(.+)", url)
                    if match:
                        img_type, data = match.groups()
                        blocks.append(ImageBlock(data=data, image_type=img_type))
            elif part.get("type") == "refusal":
                blocks.append(TextBlock(text=f"[Refusal: {part['refusal']}]"))
        return blocks

    def invoke(self, model_input: Model_Input, max_retries: int = 3, retry_delay: float = 1.0) -> ModelMessage | str:
        """同步调用，返回 ModelMessage 或字符串（仅文本）"""
        self.payload_construct(model_input)
        timeout = httpx.Timeout(60.0, read=300.0)

        for attempt in range(max_retries):
            with httpx.Client(timeout=timeout) as client:
                try:
                    response = client.post(self.base_url, headers=self.headers, json=self.payload)
                    response.raise_for_status()
                    return self.model_response_parse(response.json())
                except (httpx.HTTPStatusError, httpx.RequestError) as e:
                    if attempt < max_retries - 1:
                        import time
                        time.sleep(retry_delay * (2 ** attempt))
                        print(f"Retry {attempt + 1}/{max_retries} after error: {e}")
                        continue
                    print(f"HTTP error after {max_retries} attempts: {e}")
                    raise

    async def async_invoke(self, model_input: Model_Input, max_retries: int = 3, retry_delay: float = 1.0) -> ModelMessage | str:
        """异步调用"""
        self.payload_construct(model_input)
        timeout = httpx.Timeout(60.0, read=300.0)

        for attempt in range(max_retries):
            async with httpx.AsyncClient(timeout=timeout) as client:
                try:
                    response = await client.post(self.base_url, headers=self.headers, json=self.payload)
                    response.raise_for_status()
                    return self.model_response_parse(response.json())
                except (httpx.HTTPStatusError, httpx.RequestError) as e:
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay * (2 ** attempt))
                        print(f"Retry {attempt + 1}/{max_retries} after error: {e}")
                        continue
                    print(f"HTTP error after {max_retries} attempts: {e}")
                    raise

    async def async_stream_invoke(self, model_input: Model_Input, max_retries: int = 3, retry_delay: float = 1.0):
        """异步流式调用，yield 事件（need_print, completed_tool_use, completed_message）"""
        self.payload_construct(model_input)
        payload = {**self.payload, "stream": True, "stream_options": {"include_usage": True}}
        timeout = httpx.Timeout(60.0, read=300.0)

        accumulated_response = {}      # 累积文本块（用于构建最终文本）
        accumulated_response['usage'] = {}
        accumulated_response['id'] = ''
        accumulated_response['choices'] = [{}]
        accumulated_response['choices'][0]['message'] = {}
        accumulated_response['choices'][0]['index'] = 0
        accumulated_message = accumulated_response['choices'][0]['message']
        accumulated_message['role'] = 'assistant'

        accumulated_tool_calls = {}   # {index: {id, name, arguments}}

        for attempt in range(max_retries):
            async with httpx.AsyncClient(timeout=timeout) as client:
                try:
                    async with client.stream("POST", self.base_url, headers=self.headers, json=payload) as response:
                        response.raise_for_status()
                        async for line in response.aiter_lines():
                            if not line.startswith("data:"):
                                continue
                            data_str = line[5:].lstrip()
                            if data_str == "[DONE]":
                                continue
                            try:
                                chunk = json.loads(data_str)
                            except json.JSONDecodeError:
                                continue

                            # 处理 usage（通常在最后一个 usage chunk 中）
                            if "usage" in chunk and chunk["usage"]:
                                accumulated_response['usage'] = chunk["usage"]
                                # 不立即结束，等待最终 done

                            choices = chunk.get("choices", [])
                            if not choices:
                                continue

                            delta = choices[0].get("delta", {})
                            finish_reason = choices[0].get("finish_reason")

                            # 文本内容增量
                            if "content" in delta and delta["content"] is not None:
                                accumulated_message['content'] = accumulated_message.get('content', '') + delta["content"]
                                yield {"type": "text", "content": delta["content"]}
                            
                            if "reasoning_content" in delta and delta["reasoning_content"] is not None:
                                accumulated_message['reasoning_content'] = accumulated_message.get('reasoning_content', '') + delta["reasoning_content"]
                                yield {"type": "thinking", "content": delta["reasoning_content"]}

                            # 工具调用增量
                            if "tool_calls" in delta and delta["tool_calls"] is not None:
                                for tc_delta in delta["tool_calls"]:
                                    idx = tc_delta.get("index", 0)
                                    if idx not in accumulated_tool_calls:
                                        accumulated_tool_calls[idx] = {
                                            "id": None,
                                            "name": None,
                                            "arguments": ""
                                        }
                                    # 更新 id 和 name
                                    if "id" in tc_delta:
                                        accumulated_tool_calls[idx]["id"] = tc_delta["id"]
                                    if "function" in tc_delta:
                                        func = tc_delta["function"]
                                        if "name" in func:
                                            accumulated_tool_calls[idx]["name"] = func["name"]
                                        if "arguments" in func:
                                            accumulated_tool_calls[idx]["arguments"] += func["arguments"]
                                

                            # 若 finish_reason 为 tool_calls 或 stop，表示当前 choice 结束
                            if finish_reason:
                                accumulated_response['id'] = chunk.get("id", "")
                                accumulated_response['choices'][0]['finish_reason'] = finish_reason
                                # 如果有未完成的 tool_calls，输出完整工具调用
                                if accumulated_tool_calls:
                                    accumulated_message['tool_calls'] = []
                                    for idx, tc in accumulated_tool_calls.items():
                                        accumulated_message['tool_calls'].append({})
                                        accumulated_message['tool_calls'][idx]["index"] = idx
                                        
                                        if tc["id"] and tc["name"]:
                                            try:
                                                args = json.loads(tc["arguments"])
                                            except json.JSONDecodeError:
                                                args = tc["arguments"]
                                            tool_use = ToolUseBlock(
                                                id=tc["id"],
                                                name=tc["name"],
                                                input=args
                                            )
                                            accumulated_message['tool_calls'][idx]["id"] = tc["id"]
                                            accumulated_message['tool_calls'][idx]["type"] = 'function'
                                            accumulated_message['tool_calls'][idx]["function"] = {"name": tc["name"], "arguments": tc["arguments"]}
                                            yield {"type": "completed_tool_use", "content": tool_use}
                                    accumulated_tool_calls.clear()

                                yield {"type": "completed_message", "content": self.model_response_parse(accumulated_response)}
                                return  # 流结束
                            
                except (httpx.HTTPStatusError, httpx.RequestError) as e:
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay * (2 ** attempt))
                        print(f"Retry {attempt + 1}/{max_retries} after error: {e}")
                        continue
                    print(f"HTTP error after {max_retries} attempts: {e}")
                    raise