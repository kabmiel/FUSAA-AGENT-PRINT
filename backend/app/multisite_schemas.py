from pydantic import BaseModel, Field
class WorkshopMemberIn(BaseModel): user_email:str; role:str=Field(pattern="^(MANAGER|OPERATOR|VIEWER)$")
class WorkshopMemberRoleIn(BaseModel): role:str=Field(pattern="^(MANAGER|OPERATOR|VIEWER)$")
class RouteJobIn(BaseModel): workshop_id:str; printer_id:str|None=None
