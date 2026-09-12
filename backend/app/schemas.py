from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from .models import JobStatus

class ORM(BaseModel): model_config=ConfigDict(from_attributes=True)
class RegisterIn(BaseModel): email: EmailStr; password: str = Field(min_length=12); display_name: str = Field(min_length=1,max_length=120)
class LoginIn(BaseModel): email: EmailStr; password: str
class TokenOut(BaseModel): access_token: str; token_type: str="bearer"
class PushSubscriptionIn(BaseModel): endpoint: str=Field(min_length=10,max_length=2048); p256dh: str=Field(min_length=10,max_length=255); auth: str=Field(min_length=10,max_length=255)
class OrganizationIn(BaseModel): name: str = Field(min_length=1,max_length=160)
class WorkshopIn(BaseModel): organization_id: str; name: str = Field(min_length=1,max_length=160)
class AgentIn(BaseModel): workshop_id: str; name: str = Field(min_length=1,max_length=160)
class AgentOut(ORM): id: str; workshop_id: str; name: str; is_online: bool; last_heartbeat_at: datetime|None
class AgentEnrollmentOut(AgentOut): enrollment_token: str
class AgentRegisterIn(BaseModel): enrollment_token: str; machine_fingerprint: str=Field(min_length=8,max_length=255)
class AgentTokenOut(BaseModel): agent_id: str; agent_key: str
class HeartbeatIn(BaseModel): status: str="ONLINE"
class PrinterIn(BaseModel): system_name: str; name: str; manufacturer: str|None=None; model: str|None=None; status: str="UNKNOWN"; color_supported: bool=True; duplex_supported: bool=False; capabilities: dict={}
class PrinterOut(ORM): id:str; computer_agent_id:str; system_name:str; name:str; status:str; enabled:bool; color_supported:bool; duplex_supported:bool; capabilities:dict
class DocumentOut(ORM): id:str; organization_id:str; original_name:str; mime_type:str; size_bytes:int; metadata_json:dict; preview_key:str|None; created_at:datetime
class JobOptions(BaseModel):
    printer_id:str
    copies:int=Field(default=1,ge=1,le=999)
    paper_size:Literal["A3","A4","A5"]|None=None
    orientation:Literal["PORTRAIT","LANDSCAPE"]|None=None
    color_mode:Literal["COLOR","MONOCHROME"]|None=None
    duplex:bool=False
    pages:str|None=Field(default=None,max_length=120,pattern=r"^\d+(?:-\d+)?(?:,\d+(?:-\d+)?)*$")
    instructions:str|None=Field(default=None,max_length=2000)
class PrintJobOut(ORM): id:str; organization_id:str; workshop_id:str; computer_agent_id:str|None; printer_id:str|None; document_id:str; status:JobStatus; copies:int; paper_size:str|None; orientation:str|None; color_mode:str|None; duplex:bool; pages:str|None; instructions:str|None; error_message:str|None; created_at:datetime; public_order:bool=False
class GuestOrderOut(BaseModel):
    order_number: str
    tracking_url: str
    status: JobStatus
    payment_status: str
    estimated_cost: float
    currency: str="XOF"
class GuestOrderStatusOut(BaseModel):
    order_number: str
    document_name: str
    status: JobStatus
    payment_status: str
    estimated_cost: float
    progress: int
    stage: str
    detail: str
    updated_at: datetime
    currency: str="XOF"
class GuestPaymentIn(BaseModel):
    status: Literal["PENDING","PAID","REJECTED"]
    reference: str|None=Field(default=None,max_length=120)
class GuestOrderAdminOut(BaseModel):
    id: str
    order_number: str
    print_job_id: str
    document_name: str
    phone: str
    display_name: str|None
    status: JobStatus
    payment_status: str
    payment_reference: str|None
    estimated_cost: float
    created_at: datetime
    payment_verified_at: datetime|None
    invoice_number: str|None=None
    archived_at: datetime|None=None
    currency: str="XOF"
class PublicPricingIn(BaseModel):
    base: float=Field(default=0,ge=0)
    per_copy: float=Field(default=0,ge=0)
    per_page: float=Field(default=0,ge=0)
    monochrome_page: float=Field(default=0,ge=0)
    monochrome_discount_from: int=Field(default=0,ge=0,le=999999)
    monochrome_discount_page: float=Field(default=0,ge=0)
    color_page: float=Field(default=0,ge=0)
    color_discount_from: int=Field(default=0,ge=0,le=999999)
    color_discount_page: float=Field(default=0,ge=0)
class PublicPricingOut(PublicPricingIn):
    rule_id: str|None=None
class PublicVisitIn(BaseModel):
    visitor_id: str=Field(min_length=16,max_length=128,pattern=r"^[A-Za-z0-9_-]+$")
    page: Literal["shop","print","tracking"]="shop"
class GuestReceiptOut(BaseModel):
    invoice_id: str
    invoice_number: str
    order_number: str
    document_name: str
    amount: float
    currency: str="XOF"
    payment_reference: str|None=None
    paid_at: datetime
class CommandResultIn(BaseModel): status: str; result: dict={}; error_message: str|None=None
class AuditOut(ORM): id:str; actor:str; action:str; resource_type:str; resource_id:str; result:str; timestamp:datetime
class WorkshopSettingsIn(BaseModel):
    workshop_name: str|None = Field(default=None,min_length=1,max_length=160)
    default_copies: int = Field(default=1,ge=1,le=999)
    default_paper_size: Literal["A3","A4","A5"] = "A4"
    default_orientation: Literal["PORTRAIT","LANDSCAPE"] = "PORTRAIT"
    default_color_mode: Literal["COLOR","MONOCHROME"] = "COLOR"
    default_duplex: bool = False
    popup_enabled: bool = True
    smart_suggestions: bool = True
class WorkshopSettingsOut(WorkshopSettingsIn):
    workshop_id: str
    workshop_name: str
