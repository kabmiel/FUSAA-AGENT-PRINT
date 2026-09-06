from typing import Literal
from pydantic import BaseModel, Field
class ProcessRequest(BaseModel):
    operation:Literal["rotate","resize","crop","fit_to_page","convert_to_pdf"]
    degrees:int|None=None; width_px:int|None=Field(default=None,ge=1,le=20000); height_px:int|None=Field(default=None,ge=1,le=20000)
    left:int|None=None; top:int|None=None; right:int|None=None; bottom:int|None=None; paper_size:Literal["A4","A3","A5"]="A4"; dpi:int=Field(default=300,ge=72,le=600)
class LayoutRequest(BaseModel):
    source_document_id:str; item_width_mm:float=Field(gt=0,le=1000); item_height_mm:float=Field(gt=0,le=1000); quantity:int=Field(ge=1,le=500); gap_mm:float=Field(default=2,ge=0,le=100); paper_size:Literal["A4","A3","A5"]="A4"; dpi:int=Field(default=300,ge=72,le=600)
