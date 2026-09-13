from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
class CustomerIn(BaseModel): organization_id:str; name:str=Field(min_length=1,max_length=160); phone:str|None=None; email:str|None=None; notes:str|None=None
class CustomerOut(CustomerIn): model_config=ConfigDict(from_attributes=True); id:str
class CatalogIn(BaseModel): organization_id:str; name:str=Field(min_length=1,max_length=160); unit_price:float=Field(ge=0); sku:str|None=None
class ServiceIn(BaseModel): organization_id:str; name:str=Field(min_length=1,max_length=160); unit_price:float=Field(ge=0)
class PriceRuleIn(BaseModel): organization_id:str; name:str; priority:int=100; conditions:dict={}; pricing:dict={}
class PriceRuleOut(PriceRuleIn): model_config=ConfigDict(from_attributes=True); id:str; enabled:bool
class PrintCostOut(BaseModel): model_config=ConfigDict(from_attributes=True); id:str; print_job_id:str; estimated_amount:float; final_amount:float|None; currency:str; breakdown:dict
class FinalCostIn(BaseModel): amount:float=Field(ge=0)
class InvoiceCreate(BaseModel): organization_id:str; customer_id:str|None=None; job_ids:list[str]=Field(min_length=1); currency:str="XOF"
class InvoiceOut(BaseModel): model_config=ConfigDict(from_attributes=True); id:str; organization_id:str; customer_id:str|None; number:str; status:str; currency:str; total_amount:float; created_at:datetime
class PaymentIn(BaseModel): amount:float=Field(gt=0); method:str=Field(min_length=1,max_length=40); reference:str|None=None
class BillingProfileIn(BaseModel):
    company_name:str=Field(min_length=1,max_length=255)
    address:str|None=Field(default=None,max_length=2000)
    phone:str|None=Field(default=None,max_length=50)
    email:str|None=Field(default=None,max_length=320)
    nif:str|None=Field(default=None,max_length=80)
    rccm:str|None=Field(default=None,max_length=80)
    tax_enabled:bool=False
    tax_rate:float=Field(default=0,ge=0,le=100)
    document_style:str=Field(default="moderne",max_length=40)
