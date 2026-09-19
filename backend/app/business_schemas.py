from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
class CustomerIn(BaseModel): organization_id:str; name:str=Field(min_length=1,max_length=160); phone:str|None=None; email:str|None=None; address:str|None=None; notes:str|None=None
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
class BillingLineIn(BaseModel):
    product_id:str|None=None
    description:str=Field(min_length=1,max_length=255)
    quantity:float=Field(default=1,gt=0,le=9999)
    unit_amount:float=Field(ge=0)
    unit:str=Field(default="piece",max_length=20)
class BillingDocumentIn(BaseModel):
    organization_id:str
    billing_header_id:str|None=None
    issued_on:datetime|None=None
    customer_address:str|None=None
    document_type:str=Field(default="INVOICE",pattern="^(QUOTE|PROFORMA|INVOICE|DELIVERY_NOTE|RECEIPT)$")
    customer_id:str|None=None
    customer_name:str|None=Field(default=None,max_length=160)
    customer_phone:str|None=Field(default=None,max_length=50)
    customer_email:str|None=Field(default=None,max_length=320)
    subject:str|None=Field(default=None,max_length=255)
    notes:str|None=Field(default=None,max_length=2000)
    discount_amount:float=Field(default=0,ge=0)
    lines:list[BillingLineIn]=Field(min_length=1,max_length=100)
class BillingAssistantIn(BaseModel):
    """Context sent only to the billing assistant, never to the shop assistant."""
    organization_id:str
    message:str=Field(min_length=1,max_length=2000)
    billing_header_id:str|None=None
    customer_id:str|None=None
class StockMovementIn(BaseModel):
    catalogue:str=Field(pattern="^(SHOP|BILLING)$")
    product_id:str
    movement_type:str=Field(pattern="^(IN|OUT|ADJUSTMENT)$")
    quantity:int=Field(ge=0,le=999999)
    reason:str|None=Field(default=None,max_length=255)
class BillingCategoryIn(BaseModel): name:str=Field(min_length=1,max_length=100);description:str|None=Field(default=None,max_length=2000)
class BillingProductIn(CatalogIn): billing_category_id:str|None=None;stock_quantity:int=Field(default=0,ge=0);stock_minimum:int=Field(default=3,ge=0);cost_xof:float=Field(default=0,ge=0);unit:str=Field(default="piece",max_length=20)

class BillingHeaderIn(BaseModel):
    company_name:str=Field(min_length=1,max_length=255)
    address:str|None=None
    phone:str|None=Field(default=None,max_length=50)
    email:str|None=Field(default=None,max_length=320)
    nif:str|None=Field(default=None,max_length=80)
    rccm:str|None=Field(default=None,max_length=80)
    logo_url:str|None=Field(default=None,max_length=1024)
    document_style:str=Field(default="standard",pattern="^(standard|scan_gauche|scan_alasko|scan_centre|scan_compact|scan_facture_simple|ultra_compact|moderne_clair|moderne_bandeau|moderne_minimal)$")
    tax_enabled:bool=False
    tax_rate:float=Field(default=19,ge=0,le=100)
    isb_enabled:bool=False
    isb_rate:float=Field(default=3,ge=0,le=100)
    table_font_family:str|None=Field(default=None,max_length=20)
    table_font_size:float|None=Field(default=None,ge=8,le=14)
    is_default:bool=False

class BillingInvoiceStyleIn(BaseModel):
    document_style:str=Field(pattern="^(standard|scan_gauche|scan_alasko|scan_centre|scan_compact|scan_facture_simple|ultra_compact|moderne_clair|moderne_bandeau|moderne_minimal)$")

class BillingCompetitionIn(BaseModel):
    billing_header_id:str
    margin_percent:float=Field(ge=0,le=1000)
