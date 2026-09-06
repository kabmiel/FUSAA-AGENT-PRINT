"""Deterministic document transformations. Original files are never modified."""
from io import BytesIO
from pathlib import Path
import fitz
from PIL import Image, ImageOps

MM_PER_INCH=25.4
PAPER_MM={"A4":(210,297),"A3":(297,420),"A5":(148,210)}

class DocumentProcessor:
    def process(self,source:Path,mime_type:str,operation:str,options:dict)->tuple[bytes,str,str,dict]:
        if operation=="convert_to_pdf":return self._to_pdf(source,mime_type)
        if mime_type=="application/pdf":return self._pdf_transform(source,operation,options)
        return self._image_transform(source,operation,options)
    def _image_transform(self,source,operation,options):
        with Image.open(source) as original:
            image=original.convert("RGB")
            if operation=="rotate":image=image.rotate(-int(options.get("degrees",0)),expand=True)
            elif operation=="resize":image=image.resize((int(options["width_px"]),int(options["height_px"])),Image.Resampling.LANCZOS)
            elif operation=="crop":image=image.crop((int(options["left"]),int(options["top"]),int(options["right"]),int(options["bottom"])))
            elif operation=="fit_to_page":
                width_mm,height_mm=PAPER_MM[options.get("paper_size","A4")];dpi=int(options.get("dpi",300));canvas=Image.new("RGB",(round(width_mm/MM_PER_INCH*dpi),round(height_mm/MM_PER_INCH*dpi)),"white");fit=ImageOps.contain(image,canvas.size,Image.Resampling.LANCZOS);canvas.paste(fit,((canvas.width-fit.width)//2,(canvas.height-fit.height)//2));image=canvas
            else:raise ValueError("Unsupported image operation")
            output=BytesIO();image.save(output,"PNG",dpi=(options.get("dpi",300),options.get("dpi",300)));return output.getvalue(),"image/png","png",{"operation":operation,"width_px":image.width,"height_px":image.height}
    def _to_pdf(self,source,mime_type):
        if mime_type=="application/pdf":return source.read_bytes(),"application/pdf","pdf",{"operation":"convert_to_pdf","passthrough":True}
        with Image.open(source) as image:
            output=BytesIO();image.convert("RGB").save(output,"PDF",resolution=300);return output.getvalue(),"application/pdf","pdf",{"operation":"convert_to_pdf"}
    def _pdf_transform(self,source,operation,options):
        if operation!="rotate":raise ValueError("PDF supports rotate or convert_to_pdf in this release")
        document=fitz.open(source);degrees=int(options.get("degrees",0))
        for page in document:page.set_rotation(degrees)
        output=document.tobytes();document.close();return output,"application/pdf","pdf",{"operation":"rotate","degrees":degrees}

class LayoutEngine:
    def create_sheet(self,source:Path,mime_type:str,item_width_mm:float,item_height_mm:float,quantity:int,gap_mm:float,paper_size:str="A4",dpi:int=300)->tuple[bytes,dict]:
        if paper_size not in PAPER_MM:raise ValueError("Unsupported paper size")
        if not 1<=quantity<=500 or min(item_width_mm,item_height_mm)<=0 or gap_mm<0:raise ValueError("Invalid layout dimensions")
        paper_w,paper_h=PAPER_MM[paper_size];scale=dpi/MM_PER_INCH;canvas=Image.new("RGB",(round(paper_w*scale),round(paper_h*scale)),"white")
        item_w,item_h=round(item_width_mm*scale),round(item_height_mm*scale);gap=round(gap_mm*scale);cols=(canvas.width+gap)//(item_w+gap);rows=(canvas.height+gap)//(item_h+gap);capacity=cols*rows
        if quantity>capacity:raise ValueError(f"{quantity} items do not fit; capacity is {capacity}")
        if mime_type=="application/pdf":
            pdf=fitz.open(source);pix=pdf[0].get_pixmap(matrix=fitz.Matrix(2,2),alpha=False);asset=Image.open(BytesIO(pix.tobytes("png"))).convert("RGB");pdf.close()
        else:
            with Image.open(source) as image:asset=image.convert("RGB")
        asset=ImageOps.contain(asset,(item_w,item_h),Image.Resampling.LANCZOS)
        for index in range(quantity):
            column=index%cols;row=index//cols;x=column*(item_w+gap)+(item_w-asset.width)//2;y=row*(item_h+gap)+(item_h-asset.height)//2;canvas.paste(asset,(x,y))
        output=BytesIO();canvas.save(output,"PDF",resolution=dpi)
        return output.getvalue(),{"paper_size":paper_size,"dpi":dpi,"quantity":quantity,"capacity":capacity,"columns":cols,"rows":rows,"item_width_mm":item_width_mm,"item_height_mm":item_height_mm,"gap_mm":gap_mm}
