from abc import ABC,abstractmethod
from typing import List
from message import AnyMessage,AIMessage
import httpx
import asyncio
import json
from openai import OpenAI
import anthropic

class Model(ABC):
    def __init__(self, model: str, api_key: str, base_url: str):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url

    @abstractmethod
    def invoke(self,messages:List[AnyMessage]) -> AIMessage | str:
        pass

    @abstractmethod
    def stream_invoke(self,messages:List[AnyMessage]) -> AIMessage | str:
        pass

    @abstractmethod
    async def async_invoke(self,messages:List[AnyMessage])-> AIMessage | str:
        pass

    @abstractmethod
    async def async_stream_invoke(self,messages:List[AnyMessage]) -> AIMessage | str:
        pass

    @abstractmethod
    def model_response_parse(self,response:dict) -> AIMessage | str:
        # parse the model response
        pass


class AnthropicModel(Model):
    """Anthropic Claude API https://docs.anthropic.com/en/api/messages"""

    def __init__(self, model: str, api_key: str, base_url: str = "https://api.anthropic.com"):
        super().__init__(model, api_key, base_url)
        self.client = anthropic.Anthropic(api_key=api_key)

    async def invoke(self,
                     messages: List[AnyMessage],
                     max_completion_tokens: int = 10240,
                     temperature: float = 1,
                     top_p: float = 0.95) -> AIMessage:

        response = self.client.messages.create(
            model=self.model,
            messages=[{"role": m.role, "content": m.content} for m in messages],
            max_tokens=max_completion_tokens,
            temperature=temperature,
            top_p=top_p,
        )
        return self.model_response_parse(response.model_dump())

    def stream_invoke(self,
                      messages: List[AnyMessage],
                      max_completion_tokens: int = 10240,
                      temperature: float = 1,
                      top_p: float = 0.95):

        async def stream_generator():
            with self.client.messages.stream(
                model=self.model,
                messages=[{"role": m.role, "content": m.content} for m in messages],
                max_tokens=max_completion_tokens,
                temperature=temperature,
                top_p=top_p,
            ) as stream:
                for text in stream.text_stream:
                    chunk_data = {
                        "id": stream.get_final_message().id if hasattr(stream, 'get_final_message') else None,
                        "choices": [{
                            "finish_reason": "stop",
                            "delta": {"content": text}
                        }]
                    }
                    yield self.model_response_parse(chunk_data)

        return stream_generator()

    def model_response_parse(self, response: dict) -> AIMessage:
        id = response.get('id', None)
        finish_reason = response['stop_reason'] if 'stop_reason' in response else ''
        content = ''
        reasoning_content = ''

        if 'content' in response:
            for block in response['content']:
                if block.get('type') == 'text':
                    content += block.get('text', '')
                elif block.get('type') == 'thinking':
                    reasoning_content += block.get('thinking', '')

        tool_calls = response.get('tool_calls', [])
        usage_data = response.get('usage', {})

        return AIMessage(
            id=id,
            content=content,
            reasoning_content=reasoning_content,
            finish_reason=finish_reason,
            tool_calls=tool_calls,
            usage_data=usage_data
        )


class OpenaiModel(Model):
    """OpenAI Chat API https://platform.openai.com/docs/api-reference/chat"""

    def __init__(self, model: str, api_key: str, base_url: str = "https://api.openai.com/v1"):
        super().__init__(model, api_key, base_url)
        self.client = OpenAI(api_key=api_key, base_url=base_url)

    async def invoke(self,
                     messages: List[AnyMessage],
                     max_completion_tokens: int = 10240,
                     temperature: float = 1,
                     top_p: float = 0.95) -> AIMessage:

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": m.role, "content": m.content} for m in messages],
            max_tokens=max_completion_tokens,
            temperature=temperature,
            top_p=top_p,
        )
        return self.model_response_parse(response.model_dump())

    def stream_invoke(self,
                      messages: List[AnyMessage],
                      max_completion_tokens: int = 10240,
                      temperature: float = 1,
                      top_p: float = 0.95):

        async def stream_generator():
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": m.role, "content": m.content} for m in messages],
                max_tokens=max_completion_tokens,
                temperature=temperature,
                top_p=top_p,
                stream=True,
            )
            for chunk in stream:
                yield self.model_response_parse(chunk.model_dump())

        return stream_generator()

    def model_response_parse(self, response: dict) -> AIMessage:
        id = response.get('id', None)
        finish_reason = response['choices'][0].get('finish_reason', '') if response.get('choices') else ''
        message = response.get('choices', [{}])[0].get('delta', {}) if response.get('choices') else {}

        content = message.get('content', '') or ''
        reasoning_content = ''  # OpenAI 不支持 reasoning_content
        tool_calls = [tc.model_dump() for tc in message.get('tool_calls', [])] if message.get('tool_calls') else []
        usage_data = response.get('usage', {})

        return AIMessage(
            id=id,
            content=content,
            reasoning_content=reasoning_content,
            finish_reason=finish_reason,
            tool_calls=tool_calls,
            usage_data=usage_data
        )



class MiniMaxModel(Model):
    """MiniMax Model native API https://platform.minimaxi.com/docs/api-reference/text-post"""

    def __init__(self, model: str, api_key: str, base_url: str):
        super().__init__(model, api_key, base_url)
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def invoke(self,
               messages: List[AnyMessage],
               max_completion_tokens: int = 10240,
               temperature: float = 1,
               top_p: float = 0.95) -> AIMessage | str:

        payload = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "max_completion_tokens": max_completion_tokens,
            "temperature": temperature,
            "top_p": top_p
            }

        timeout = httpx.Timeout(30.0, read=300.0)
        with httpx.Client(timeout=timeout) as client:
            try:
                response = client.post(self.base_url, headers=self.headers, json=payload)
                response.raise_for_status()
                return self.model_response_parse(response.json())
            except httpx.HTTPStatusError as e:
                print(f"HTTP {e.response.status_code}: {e.response.text}")
                raise

    async def async_invoke(self,
                     messages: List[AnyMessage],
                     max_completion_tokens: int = 10240,
                     temperature: float = 1,
                     top_p: float = 0.95) -> AIMessage | str:

        payload = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "max_completion_tokens": max_completion_tokens,
            "temperature": temperature,
            "top_p": top_p
            }

        timeout = httpx.Timeout(30.0, read=300.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                response = await client.post(self.base_url, headers=self.headers, json=payload)
                response.raise_for_status()
                return self.model_response_parse(response.json())
            except httpx.HTTPStatusError as e:
                print(f"HTTP {e.response.status_code}: {e.response.text}")
                raise

    def stream_invoke(self,
                      messages: List[AnyMessage],
                      max_completion_tokens: int = 10240,
                      temperature: float = 1,
                      top_p: float = 0.95):

        """yield every chunk , the last chunk is the aggregation"""

        payload = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "max_completion_tokens": max_completion_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "stream": True,
            "stream_options": {"include_usage": True}
            }

        timeout = httpx.Timeout(30.0, read=300.0)
        with httpx.Client(timeout=timeout) as client:
            try:
                with client.stream("POST", self.base_url, headers=self.headers, json=payload) as chunk:
                    chunk.raise_for_status()
                    for line in chunk.iter_lines():
                        if not line.startswith("data:"):
                            continue
                        chunk_str = line[5:].lstrip()
                        chunk_data = json.loads(chunk_str)
                        parsed_chunk = self.model_response_parse(chunk_data)
                        yield parsed_chunk 
            except httpx.HTTPStatusError as e:
                print(f"HTTP {e.response.status_code}: {e.response.text}")
                raise

    async def async_stream_invoke(self,
                    messages: List[AnyMessage],
                    max_completion_tokens: int = 10240,
                    temperature: float = 1,
                    top_p: float = 0.95):
        
        payload = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "max_completion_tokens": max_completion_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "stream": True,
            "stream_options": {"include_usage": True}
            }

        timeout = httpx.Timeout(30.0, read=300.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                async with client.stream("POST", self.base_url, headers=self.headers, json=payload) as chunk:
                    chunk.raise_for_status()
                    async for line in chunk.aiter_lines():
                        if not line.startswith("data:"):
                            continue
                        chunk_str = line[5:].lstrip()
                        chunk_data = json.loads(chunk_str)
                        parsed_chunk = self.model_response_parse(chunk_data)
                        yield parsed_chunk
            except httpx.HTTPStatusError as e:
                print(f"HTTP {e.response.status_code}: {e.response.text}")
                raise
    
    def model_response_parse(self,response:dict) -> AIMessage:
        id=response.get('id',None)
        finish_reason=response['choices'][0].get('finish_reason','')
        if response.get('object') == 'chat.completion':
            message=response['choices'][0].get('message',[])
        else:
            message=response['choices'][0].get('delta',[])

        content=message.get('content',None)       # the message content 
        reasoning_content=message.get('reasoning_content','')
        tool_calls=message.get('tool_calls',[])   # List[dict] {'id','name','arguments'}
        usage_data=response.get('usage',{})       # dict

        return AIMessage(id=id,content=content,reasoning_content=reasoning_content,finish_reason=finish_reason,tool_calls=tool_calls,usage_data=usage_data)

class GLMModel():
    pass

class DeepseekModel():
    pass

class KimiModel():
    pass