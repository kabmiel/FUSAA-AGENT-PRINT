from typing import Any
from typing import Literal
from pydantic import BaseModel, Field
from .ai import SafetyLevel
class ChatMessage(BaseModel):
    role:Literal["user","assistant"]
    content:str=Field(max_length=4000)
class AssistantRequest(BaseModel):
    message:str=Field(min_length=1,max_length=2000)
    history:list[ChatMessage]=Field(default_factory=list,max_length=8)
    selected_job_id:str|None=Field(default=None,max_length=36)
class ToolCall(BaseModel): name:str; arguments:dict[str,Any]={}; safety:SafetyLevel; result:dict[str,Any]|None=None
class AssistantResponse(BaseModel):
    answer:str
    title:str="Assistant FUSAA"
    steps:list[str]=Field(default_factory=list)
    next_view:Literal["upload","print","connectors","settings","dashboard","publicOrders"]|None=None
    next_label:str|None=None
    tool_calls:list[ToolCall]
    requires_confirmation:bool
class AssistantExecuteRequest(BaseModel): name:str; arguments:dict[str,Any]={}; confirmed:bool=False
