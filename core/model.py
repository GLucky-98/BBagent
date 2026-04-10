from abc import ABC,abstractmethod
from termios import tcdrain
from tracemalloc import stop
from typing import List
import httpx
import asyncio
import json

from .tool import Tool
from .message import Message,AIMessage,HumanMessage,SystemMessage,ToolMessage

class Model(ABC):
    def __init__(self, model: str, api_key: str, base_url: str):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url

    @abstractmethod
    def invoke(self,messages:List[Message]) -> AIMessage | str:
        pass

    # @abstractmethod
    # def stream_invoke(self,messages:List[Message]) -> AIMessage | str:
    #     pass

    # @abstractmethod
    # async def async_invoke(self,messages:List[Message])-> AIMessage | str:
    #     pass

    # @abstractmethod
    # async def async_stream_invoke(self,messages:List[Message]) -> AIMessage | str:
    #     pass

    # @abstractmethod
    # def model_response_parse(self,response:dict) -> AIMessage | str:
    #     # parse the model response
    #     pass


class AnthropicModel(Model):
    """Anthropic Claude API https://platform.claude.com/docs/en/api/messages/create"""

    def __init__(self,
                 model: str,
                 api_key: str,
                 base_url: str = "https://api.anthropic.com",
                 max_tokens: int =10240,
                 temperature: float = 1,
                 top_p: float = 0.95,
                 thinking: dict = {"type":"adaptive","display":"summarized"},
                 **kwargs):
        super().__init__(model, api_key, base_url+'/v1/messages')
        
        self.max_tokens=max_tokens
        self.temperature=temperature
        self.top_p=top_p
        self.thinking=thinking
        self.extra_args=kwargs

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

    def invoke(self, messages: List[Message], max_retries: int = 3, retry_delay: float = 1.0) -> AIMessage | str:
        #   {
        #   "messages": [
        #     {
        #       "content": "string",
        #       "role": "user"
        #     }
        #   ],
        #   "model": "claude-opus-4-6",
        #   "cache_control": ,
        #   "container": ,
        #   "inference_geo": ,
        #   "metadata": ,
        #   "output_config": ,
        #   "service_tier": ,
        #   "stop_sequences": ,
        #   "stream": ,
        #   "system": ,
        #   "temperature": ,
        #   "thinking": {"type":"adaptive","display":"summarized"},
        #   "tool_choice": {"type":"auto","disable_parallel_tool_use":false},
        #   "tools": ,
        #   "top_k": ,
        #   "top_p":
        #    }
        self.payload_construct(messages)

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

    def payload_construct(self, messages: List[Message]):
        payload_messages=[]
        for m in messages:
            if isinstance(m,SystemMessage):
                self.sytem = m.content
                self.payload['system'] = m.content 
            if isinstance(m,HumanMessage):
                payload_messages.append({'role':m.role, 'content':m.content})
            if isinstance(m,ToolMessage):
                payload_messages.append({'role':'user', 'content':[{'type':'tool_result','tool_use_id':m.id,'content':m.content}]})
            if isinstance(m,AIMessage):
                if isinstance(m.content,list):
                    content=[]
                    for c in m.content:
                        if c['type'] != 'thinking': # delete the thinking
                            content.append(c)
                else:
                    content=m.content    
                payload_messages.append({'role':m.role, 'content':content})
        
        self.payload['messages']=payload_messages
        return

    def model_response_parse(self,response:dict) -> AIMessage:       
        
        content=response.get('content',{})
        id=response.get('id','')
        
        text=''
        thinking=''
        tool_calls=[]
        if isinstance(content,list):
            for block in content:
                if 'text' in block:
                    text+=block['text']
                if 'thinking' in block:
                    thinking+=block['thinking']
                if block['type'] == 'tool_use':
                    tool_calls.append({'id':block['id'], 'name':block['name'], 'input':block['input']})
        else:
            text=content

        stop_reason=response.get('stop_reason','')       
        usage_data=response.get('usage',{})   

        return AIMessage(content=content,id=id,text=text,thinking=thinking,stop_reason=stop_reason,tool_calls=tool_calls,usage_data=usage_data)

    def bind_tools(self,tools:List[Tool]):
        self.tools=tools
        tool_prompt=[]
        for t in tools:
            tool_prompt.append({"name":t.name, "description":t.description, "input_schema":t.input_schema})
        self.payload['tools'] = tool_prompt

class MiniMaxModel(Model):
    """MiniMax Model native API https://platform.minimaxi.com/docs/api-reference/text-post"""

    def __init__(
                self, 
                model: str,
                api_key: str,  
                base_url: str,
                max_completion_tokens: int = 10240,
                temperature: float = 1,
                top_p: float = 0.95,
                **kwargs
                ):
        
        super().__init__(model, api_key, base_url)
        self.max_completion_tokens = max_completion_tokens
        self.temperature = temperature
        self.top_p = top_p
        self.extra_args = kwargs

        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        self.payload = {
            "model": self.model,
            "max_completion_tokens": max_completion_tokens,
            "temperature": temperature,
            "top_p": top_p
        }

        self.payload.update(self.extra_args)

    def invoke(self,
               messages: List[Message]             
               ) -> AIMessage | str:

        self.payload_construct(messages)

        print(self.payload)

        timeout = httpx.Timeout(60.0, read=300.0)
        with httpx.Client(timeout=timeout) as client:
            try:
                response = client.post(self.base_url, headers=self.headers, json=self.payload)
                response.raise_for_status()
                return self.model_response_parse(response.json())
            except httpx.HTTPStatusError as e:
                print(f"HTTP {e.response.status_code}: {e.response.text}")
                raise

    async def async_invoke(self,
                     messages: List[Message],
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
                      messages: List[Message],
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
                    messages: List[Message],
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
    
    def payload_construct(self, messages:List[Message]):
        payload_messages=[]
        for m in messages:
            if isinstance(m,SystemMessage) or isinstance(m,HumanMessage):
                payload_messages.append({'role':m.role, 'content':m.content})
            if isinstance(m,ToolMessage):
                payload_messages.append({'role':m.role, 'name':m.name, 'content':f'{m.content}'})
            if isinstance(m,AIMessage):
                payload_messages.append({'role':m.role, 'content':m.text})
        
        self.payload['messages']=payload_messages
        return

    def model_response_parse(self,response:dict) -> AIMessage:       
        content=response['choices'][0].get('message',{})
        
        id=response.get('id',None)
        text=content.get('content','')
        thinking=content.get('reasoning_content','')

        stop_reason=response['choices'][0].get('finish_reason','')
        tool_calls=[]
        if tcs:= content.get('tool_calls',None):
            for tc in tcs:
                tool_calls.append({'id':tc['id'], 'name':tc['function']['name'], 'input':json.loads(tc['function']['arguments'])})
        usage_data=response.get('usage',{})   

        return AIMessage(content=content,id=id,text=text,thinking=thinking,stop_reason=stop_reason,tool_calls=tool_calls,usage_data=usage_data)

    def bind_tools(self,tools:List[Tool]):
        self.tools=tools
        tool_prompt=[]
        for t in tools:
            tool_prompt.append({'type':'function','function':{'name':t.name, 'description':t.description, 'parameters':t.input_schema}})
        self.payload['tools'] = tool_prompt

class GLMModel():
    pass

class DeepseekModel():
    pass

class KimiModel():
    pass

class OpenaiModel(Model):
    """OpenAI Chat API https://platform.openai.com/docs/api-reference/chat"""

    pass
