"""PDF/image raster rendering to Windows GDI, with per-job driver settings."""
import re
import logging
from pathlib import Path

log = logging.getLogger(__name__)

def page_indices(expression, count):
    if not expression:return list(range(count))
    result=[]
    for part in expression.split(","):
        if not re.fullmatch(r"\s*\d+(?:\s*-\s*\d+)?\s*",part):raise ValueError("Invalid page selection")
        bounds=[int(n) for n in part.split("-")]
        start,end=bounds[0],bounds[-1]
        if start<1 or end<start or end>count:raise ValueError("Page selection outside document")
        result.extend(range(start-1,end))
    return list(dict.fromkeys(result))

def configured_devmode(printer,options):
    import win32print, win32con
    handle=win32print.OpenPrinter(printer)
    try:
        info=win32print.GetPrinter(handle,2)
        mode=info["pDevMode"]
        if mode is None:raise ValueError("Printer has no configurable driver")
        if info.get("pPortName") in {"PORTPROMPT:","FILE:"}:raise ValueError("Interactive file printer: choose a physical printer")
        requested={"Copies":1,"Duplex":2 if options.get("duplex") else 1}
        if options.get("duplex") and not win32print.DeviceCapabilities(printer,info["pPortName"],win32con.DC_DUPLEX):
            raise ValueError("Printer does not support duplex")
        paper=options.get("paper_size")
        if paper:
            papers={"A3":8,"A4":9,"A5":11}
            if paper not in papers:raise ValueError("Unsupported paper size")
            if papers[paper] not in win32print.DeviceCapabilities(printer,info["pPortName"],win32con.DC_PAPERS):raise ValueError("Paper not supported by this printer")
            requested["PaperSize"]=papers[paper]
        if options.get("orientation"):requested["Orientation"]={"PORTRAIT":1,"LANDSCAPE":2}[options["orientation"]]
        if options.get("color_mode"):requested["Color"]={"MONOCHROME":1,"COLOR":2}[options["color_mode"]]
        flags={"Copies":win32con.DM_COPIES,"Duplex":win32con.DM_DUPLEX,"PaperSize":win32con.DM_PAPERSIZE,"Orientation":win32con.DM_ORIENTATION,"Color":win32con.DM_COLOR}
        for key,value in requested.items():
            setattr(mode,key,value);mode.Fields|=flags[key]
        status=win32print.DocumentProperties(0,handle,printer,mode,mode,win32con.DM_IN_BUFFER|win32con.DM_OUT_BUFFER)
        if status!=1:raise ValueError("Driver refused print settings")
        changed={key:(value,getattr(mode,key)) for key,value in requested.items() if getattr(mode,key)!=value}
        if changed:
            # Some Windows drivers normalize valid values (especially paper and
            # color).  The returned DEVMODE is the driver's accepted setting;
            # aborting here prevents otherwise valid printers from printing.
            log.warning("Printer driver normalized settings for %s: %s",printer,changed)
        return mode
    finally:win32print.ClosePrinter(handle)

def render_job(path,printer,options,title):
    import fitz
    import win32gui,win32print,win32con
    from PIL import Image,ImageWin
    copies=int(options.get("copies",1))
    if not 1<=copies<=999:raise ValueError("Copies must be between 1 and 999")
    source=fitz.open(path)
    if not source.is_pdf:
        converted=source.convert_to_pdf();source.close();source=fitz.open("pdf",converted)
    dc=None;started=False
    try:
        pages=page_indices(options.get("pages"),source.page_count)
        if not pages:raise ValueError("Document has no pages")
        mode=configured_devmode(printer,options)
        dc=win32gui.CreateDC("WINSPOOL",printer,mode)
        width=win32print.GetDeviceCaps(dc,win32con.HORZRES)
        height=win32print.GetDeviceCaps(dc,win32con.VERTRES)
        dpi_x=win32print.GetDeviceCaps(dc,win32con.LOGPIXELSX)
        dpi_y=win32print.GetDeviceCaps(dc,win32con.LOGPIXELSY)
        job_id=win32print.StartDoc(dc,(title,None,None,0));started=True
        for _ in range(copies):
            for index in pages:
                pix=source[index].get_pixmap(dpi=200,alpha=False,colorspace=fitz.csGRAY if options.get("color_mode")=="MONOCHROME" else fitz.csRGB)
                image=Image.frombytes("L" if pix.n==1 else "RGB",(pix.width,pix.height),pix.samples)
                scale=min(width/image.width,height/image.height)
                w,h=int(image.width*scale),int(image.height*scale)
                x,y=(width-w)//2,(height-h)//2
                win32print.StartPage(dc)
                ImageWin.Dib(image).draw(int(dc),(x,y,x+w,y+h))
                win32print.EndPage(dc)
            if options.get("duplex") and len(pages)%2 and copies>1:
                win32print.StartPage(dc);win32print.EndPage(dc)
        win32print.EndDoc(dc);started=False
        return {"accepted_by_windows":True,"printer":printer,"spooler_job_id":job_id,"rendered_pages":len(pages),"copies":copies}
    finally:
        if dc is not None:
            try:
                if started:win32print.AbortDoc(dc)
            finally:win32gui.DeleteDC(dc)
        source.close()
