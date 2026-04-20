import json
from abc import ABC,abstractmethod
from typing import List,AsyncIterator
import httpx
import asyncio

from .message import *

class Model(ABC):
    def __init__(self, model: str, api_key: str, base_url: str):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url

    @abstractmethod
    def invoke(self,session: Session) -> AssistantMessage | str:
        pass

    @abstractmethod
    async def async_invoke(self,session: Session)-> AssistantMessage | str:
        pass

    @abstractmethod
    async def async_stream_invoke(self, session: Session) -> AsyncIterator[dict]:
        pass

    @abstractmethod
    def payload_construct(self,session: Session) -> None:
        pass

    @abstractmethod
    def model_response_parse(self,response:dict) -> AssistantMessage | str:
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
                 thinking: dict = {"type":"adaptive","display":"summarized"},
                 **kwargs):
        
        super().__init__(model, api_key, base_url+'/v1/messages')
        
        self.max_tokens = max_tokens
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
                    "max_tokens": self.max_tokens,
                    "model": self.model,
                    "temperature": self.temperature,
                    "top_p": self.top_p
                    }
        
        self.payload.update(self.extra_args)

    def invoke(self, session: Session, max_retries: int = 3, retry_delay: float = 1.0) -> AssistantMessage | str:
        
        self.payload_construct(session)
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
    
    async def async_invoke(self, session: Session, max_retries: int = 3, retry_delay: float = 1.0) -> AssistantMessage | str:
        
        self.payload_construct(session)
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
    
    async def async_stream_invoke(self, session: Session, max_retries: int = 3, retry_delay: float = 1.0):
        self.payload_construct(session)
        self.payload['stream'] = True
        timeout = httpx.Timeout(60.0, read=300.0)

        accumulated_message = {}
        accumulated_block = []

        for attempt in range(max_retries):
            async with httpx.AsyncClient(timeout=timeout) as client:
                try:
                    async with client.stream('POST', self.base_url, headers=self.headers, json=self.payload) as response:
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
                                                    yield {'type':'need_print','content':delta.get('text', '')}
                                            elif delta_type == 'input_json_delta':
                                                # 工具输入 JSON 增量：累积 partial_json 字符串
                                                if block.get('type') == 'tool_use':
                                                    block['partial_json'] = block.get('partial_json', '') + delta.get('partial_json', '')
                                                    continue
                                            elif delta_type == 'thinking_delta':
                                                # 思考内容增量
                                                if block.get('type') == 'thinking':
                                                    block['thinking'] = block.get('thinking', '') + delta.get('thinking', '')
                                                    yield {'type':'need_print','content':delta.get('thinking', '')}
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

    def payload_construct(self, session: Session):
        if session.system_prompt:
            self.payload['system'] = session.system_prompt
        
        if session.tools:
            self.payload['tools'] = [t.schema for t in session.tools]
        
        payload_messages = []
        if session.context:
            for message in session.context:
                if isinstance(message, SystemMessage):
                    continue
                if isinstance(message, HumanMessage) or isinstance(message, AssistantMessage):
                    if isinstance(message.content,list):
                        payload_messages.append({'role':message.role, 'content':self.content_block_parse(message.content)})
                    else:
                        payload_messages.append({'role':message.role, 'content':message.content})
                if isinstance(message, ToolResultMessage):
                    if isinstance(message.content,list):
                        payload_messages.append({'role':'user', 'content':[{'type':'tool_result','tool_use_id':message.id,'content':self.content_block_parse(message.content)}]})
                    else:
                        payload_messages.append({'role':'user', 'content':[{'type':'tool_result','tool_use_id':message.id,'content':message.content}]})
    
        self.payload['messages'] = payload_messages
        
        return
    
    def content_block_parse(self, content_blocks: List[ContentBlock]) -> List[dict]:
        """解析内容块"""
        result = []
        for block in content_blocks:
            if isinstance(block, TextBlock):
                result.append({'type':'text','text':block.text})
            if isinstance(block, ThinkingBlock):
                result.append({'type':'thinking','thinking':block.thinking,'signature':block.signature})
            if isinstance(block, ImageBlock):
                result.append({'type':'image','source':{'type':'base64','data':block.data,'media_type':block.image_type}})
            if isinstance(block, ToolUseBlock):
                result.append({'type':'tool_use','id':block.id,'name':block.name,'input':block.input})

        return result

    def model_response_parse(self, response:dict) -> AssistantMessage:       
        """解析模型响应"""
        id = response.get('id','')
        stop_reason = response.get('stop_reason','')       
        usage_data = response.get('usage',{})   
        raw_content = response.get('content',[])

        tool_calls = []
        if isinstance(raw_content,list):
            content = []
            for block in raw_content:
                if block['type'] == 'text':
                    content.append(TextBlock(text=block['text']))
                if block['type'] == 'thinking':
                    content.append(ThinkingBlock(thinking=block['thinking'],signature=block['signature']))
                if block['type'] == 'image':
                    content.append(ImageBlock(data=block['source']['data'], image_type=block['source']['media_type']))
                if block['type'] == 'tool_use':
                    content.append(ToolUseBlock(id=block['id'], name=block['name'], input=block['input']))
                    tool_calls.append(ToolUseBlock(id=block['id'], name=block['name'], input=block['input']))
        else:
            content = raw_content

        return AssistantMessage(id, content, stop_reason, tool_calls, usage_data)
   

#----------------------------------------------------------------------------
# OpenAI Model
##---------------------------------------------------------------------------   
# class OpenAIModel(Model):
#     """OpenAI Responses API https://platform.openai.com/docs/api-reference/responses"""

#     def __init__(self,
#                  model: str,
#                  api_key: str,
#                  base_url: str = "https://api.openai.com/v1",
#                  max_tokens: int = 4096,
#                  temperature: float = 1,
#                  top_p: float = 0.95,
#                  tools: List[Tool] = [],
#                  **kwargs):
#         super().__init__(model, api_key, base_url + '/response', tools)
        
#         self.max_tokens = max_tokens
#         self.temperature = temperature
#         self.top_p = top_p
#         self.extra_args = kwargs if kwargs else {}

#         self.headers = {
#             "Content-Type": "application/json",
#             "Authorization": f"Bearer {api_key}",
#         }

#         self.payload = {
#             "model": self.model,
#             "max_output_tokens": self.max_tokens,
#             "temperature": self.temperature,
#             "top_p": self.top_p,
#         }
        
#         self.payload.update(self.extra_args)

#     def invoke(self, messages: List[Message], max_retries: int = 3, retry_delay: float = 1.0) -> AIMessage | str:
        
#         self.payload_construct(messages)
#         timeout = httpx.Timeout(60.0, read=300.0)

#         for attempt in range(max_retries):
#             with httpx.Client(timeout=timeout) as client:
#                 try:
#                     response = client.post(self.base_url, headers=self.headers, json=self.payload)
#                     response.raise_for_status()
#                     return self.model_response_parse(response.json())
#                 except (httpx.HTTPStatusError, httpx.RequestError) as e:
#                     if attempt < max_retries - 1:
#                         import time
#                         time.sleep(retry_delay * (2 ** attempt))
#                         print(f"Retry {attempt + 1}/{max_retries} after error: {e}")
#                         continue
#                     print(f"HTTP error after {max_retries} attempts: {e}")
#                     raise
    
#     async def async_invoke(self, messages: List[Message], max_retries: int = 3, retry_delay: float = 1.0) -> AIMessage | str:
        
#         self.payload_construct(messages)
#         timeout = httpx.Timeout(60.0, read=300.0)

#         for attempt in range(max_retries):
#             async with httpx.AsyncClient(timeout=timeout) as client:
#                 try:
#                     response = await client.post(self.base_url, headers=self.headers, json=self.payload)
#                     response.raise_for_status()
#                     return self.model_response_parse(response.json())
#                 except (httpx.HTTPStatusError, httpx.RequestError) as e:
#                     if attempt < max_retries - 1:
#                         await asyncio.sleep(retry_delay * (2 ** attempt))
#                         print(f"Retry {attempt + 1}/{max_retries} after error: {e}")
#                         continue
#                     print(f"HTTP error after {max_retries} attempts: {e}")
#                     raise

#     def payload_construct(self, messages: List[Message]):
#         payload_messages = []
#         for m in messages:
#             if isinstance(m, SystemMessage):
#                 self.payload['system'] = m.content
#             if isinstance(m, HumanMessage):
#                 payload_messages.append({
#                     'role': 'user',
#                     'content': [{'type': 'input_text', 'text': m.content}]
#                 })
#             if isinstance(m, ToolMessage):
#                 payload_messages.append({
#                     'role': 'user',
#                     'content': [{
#                         'type': 'function_call_output',
#                         'call_id': m.id,
#                         'output': m.content
#                     }]
#                 })
#             if isinstance(m, AIMessage):
#                 if isinstance(m.content, list):
#                     content = []
#                     for c in m.content:
#                         if c.get('type') == 'function_call':
#                             content.append(c)
#                         elif c.get('type') == 'output_text':
#                             content.append(c)
#                 else:
#                     content = [{'type': 'output_text', 'text': m.content}]
#                 payload_messages.append({'role': 'assistant', 'content': content})
        
#         self.payload['input'] = payload_messages
#         if self.tools:
#             self.payload['tools'] = [{
#                 'type': 'function',
#                 'name': t.name,
#                 'description': t.description,
#                 'parameters': t.input_schema
#             } for t in self.tools]
#         return

#     def model_response_parse(self, response: dict) -> AIMessage:
        
#         output = response.get('output', [])
#         id = response.get('id', '')
        
#         text = ''
#         thinking = ''
#         tool_calls = []
#         content = []
        
#         for item in output:
#             if item.get('type') == 'message':
#                 message_content = item.get('content', [])
#                 for block in message_content:
#                     if block.get('type') == 'output_text':
#                         text += block.get('text', '')
#                         content.append(block)
#                     elif block.get('type') == 'refusal':
#                         content.append(block)
#             elif item.get('type') == 'function_call':
#                 tool_call = {
#                     'id': item.get('call_id', ''),
#                     'name': item.get('name', ''),
#                     'input': item.get('arguments', {})
#                 }
#                 tool_calls.append(tool_call)
#                 content.append(item)
        
#         stop_reason = response.get('status', '')
#         usage_data = response.get('usage', {})
        
#         return AIMessage(
#             content=content,
#             id=id,
#             text=text,
#             thinking=thinking,
#             stop_reason=stop_reason,
#             tool_calls=tool_calls,
#             usage_data=usage_data
#         )
