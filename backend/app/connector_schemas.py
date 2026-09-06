from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
class ConnectorCreate(BaseModel):
    organization_id:str; workshop_id:str; connector_type:Literal["UPLOAD","EMAIL","API","WHATSAPP"]; name:str=Field(min_length=1,max_length=120); config:dict={}
class ConnectorOut(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id:str; organization_id:str; workshop_id:str; connector_type:str; name:str; enabled:bool; config:dict; created_at:datetime
class ConnectorSecretOut(ConnectorOut): secret:str
