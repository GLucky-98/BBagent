from abc import ABC,abstractmethod
from typing import List
from unittest import result
from message import AnyMessage,AIMessage
import httpx
import asyncio


class Model(ABC):
    def __init__(self, model: str, api_key: str, base_url: str):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url

    @abstractmethod
    def invoke(self) -> AIMessage:
        # invoke the model
        pass

    @abstractmethod
    def model_response_parse(self,response:dict) -> AIMessage:
        # parse the model response
        pass


class AnthropicModel():
    pass


class OpenaiModel():
    pass



class MiniMaxModel(Model):
    def __init__(self, model: str, api_key: str, base_url: str):
        super().__init__(model, api_key, base_url)
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    async def invoke(self, messages: List[AnyMessage]) -> AIMessage | str:
        payload = {
            "model": self.model,
            "messages": [{"role": m.role, "content": m.content} for m in messages]
        }
        timeout = httpx.Timeout(30.0, read=60.0) # connect time out  and read time out
        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                response = await client.post(self.base_url, headers=self.headers, json=payload)
                response.raise_for_status()
                result=self.model_response_parse(response.json())
                if result.base_resp['status_code'] != 0:
                    # error handling
                    print(f"Error code:{result.base_resp['status_code']}, Error msg:{result.base_resp['status_msg']}")
                    return f"Error code:{result.base_resp['status_code']}, Error msg:{result.base_resp['status_msg']}"
                return result
            except httpx.HTTPStatusError as e:
                print(f"HTTP {e.response.status_code}: {e.response.text}")
                raise
    
    def model_response_parse(self,response:dict) -> AIMessage:
        # the raw response exmple: https://platform.minimaxi.com/docs/api-reference/text-post
        id=response.get('id',None)
        finish_reason=response['choices'][0]['finish_reason']
        message=response['choices'][0]['message']
        content=message.get('content','')         # the message content dict
        tool_calls=message.get('tool_calls',[])   # List[dict] {'id','name','arguments'}
        usage_data=response.get('usage',{})       # dict
        base_resp=response.get('base_resp',{})    # dict

        return AIMessage(id=id,content=content,finish_reason=finish_reason,tool_calls=tool_calls,usage_data=usage_data,base_resp=base_resp)

    


class GLMModel():
    pass

class DeepseekModel():
    pass

class KimiModel():
    pass