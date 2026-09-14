"""PDF documents using the selectable Boulangerie company-header settings."""
from io import BytesIO
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


STYLE_OPTIONS = {
    "standard": ("#17324b", "#edf5fa", "left", False, "Helvetica", 9, None),
    "scan_gauche": ("#17324b", "#ffffff", "left", False, "Times-Roman", 14, "FACTURE PRO-FORMA"),
    "scan_alasko": ("#16547a", "#e8f5fa", "left", False, "Helvetica", 13.5, "FACTURE PRO FORMA"),
    "scan_centre": ("#17324b", "#ffffff", "center", False, "Times-Roman", 14, "FACTURE PRO FORMA"),
    "scan_compact": ("#17324b", "#f2f5f7", "left", True, "Times-Roman", 11.5, "FACTURE PRO-FORMA"),
    "scan_facture_simple": ("#101d2a", "#ffffff", "left", True, "Helvetica", 11.5, "FACTURE PROFORMA"),
    "moderne_clair": ("#137b8a", "#effafb", "left", False, "Helvetica", 9, None),
    "moderne_bandeau": ("#0e4f82", "#eaf6fc", "left", False, "Helvetica", 9, None),
    "moderne_minimal": ("#263b4d", "#ffffff", "left", True, "Helvetica", 9, None),
}
DOCUMENT_NAMES = {
    "INVOICE":"FACTURE", "QUOTE":"DEVIS", "PROFORMA":"FACTURE PROFORMA",
    "DELIVERY_NOTE":"BON DE LIVRAISON", "RECEIPT":"REÇU",
}
FONT_NAMES = {"times":"Times-Roman","arial":"Helvetica","calibri":"Helvetica","segoe":"Helvetica","courier":"Courier","trebuchet":"Helvetica"}


def _logo_reader(url: str | None):
    if not url:return None
    parts=urlparse(url)
    if parts.scheme!="https" or parts.hostname!="res.cloudinary.com":return None
    try:
        with urlopen(url,timeout=4) as response:
            raw=response.read(2_000_001)
        if len(raw)>2_000_000:return None
        return ImageReader(BytesIO(raw))
    except Exception:return None


def render_invoice_pdf(path: Path, invoice, header, customer, lines):
    path.parent.mkdir(parents=True,exist_ok=True)
    pdf=canvas.Canvas(str(path),pagesize=A4)
    width,height=A4
    accent,bg,alignment,compact,style_font,style_size,style_title=STYLE_OPTIONS.get(header.document_style,STYLE_OPTIONS["standard"])
    accent_color=colors.HexColor(accent)
    text_color=colors.HexColor("#142433")
    base_font=FONT_NAMES.get(header.table_font_family or "",style_font)
    base_size=float(header.table_font_size or style_size)
    logo=_logo_reader(header.logo_url)
    document_title=DOCUMENT_NAMES.get(invoice.document_type,"FACTURE")
    if style_title and invoice.document_type in {"PROFORMA","QUOTE"}: document_title=style_title if invoice.document_type=="PROFORMA" else "DEVIS"

    def company_header():
        if header.document_style in {"moderne_bandeau","scan_alasko"}:
            pdf.setFillColor(accent_color);pdf.rect(0,height-52*mm,width,52*mm,fill=1,stroke=0)
            foreground=colors.white
        else:
            pdf.setFillColor(accent_color);pdf.rect(16*mm,height-17*mm,width-32*mm,1.6*mm,fill=1,stroke=0)
            foreground=text_color
        if logo:
            try:pdf.drawImage(logo,18*mm,height-44*mm,width=24*mm,height=24*mm,preserveAspectRatio=True,mask="auto")
            except Exception:pass
        x=width/2 if alignment=="center" else (46*mm if logo else 18*mm)
        draw=pdf.drawCentredString if alignment=="center" else pdf.drawString
        pdf.setFillColor(foreground);pdf.setFont("Helvetica-Bold",15 if compact else 17)
        draw(x,height-26*mm,str(header.company_name)[:52])
        pdf.setFont("Helvetica",8)
        details=[header.address,header.phone,header.email]
        y=height-32*mm
        for detail in filter(None,details):
            draw(x,y,str(detail).replace("\r"," ").replace("\n"," ")[:82]);y-=4.4*mm
        pdf.setFillColor(text_color);pdf.setFont("Helvetica-Bold",12)
        pdf.drawRightString(width-18*mm,height-58*mm,document_title)
        pdf.setFont("Helvetica",9);pdf.drawRightString(width-18*mm,height-64*mm,invoice.number)
        if invoice.issued_on:pdf.drawRightString(width-18*mm,height-69*mm,invoice.issued_on.strftime("%d/%m/%Y"))
        pdf.setFont("Helvetica",8)
        if header.nif:pdf.drawString(18*mm,height-58*mm,"NIF : "+str(header.nif))
        if header.rccm:pdf.drawString(18*mm,height-63*mm,"RCCM : "+str(header.rccm))
        pdf.setStrokeColor(colors.HexColor("#cbd6df"));pdf.line(18*mm,height-74*mm,width-18*mm,height-74*mm)
        pdf.setFont("Helvetica-Bold",9);pdf.drawString(18*mm,height-82*mm,"CLIENT")
        pdf.setFont("Helvetica",9);pdf.drawString(18*mm,height-88*mm,(customer.name if customer else "Client comptant")[:65])
        if customer and customer.phone:pdf.drawString(18*mm,height-93*mm,customer.phone)
        if invoice.subject:pdf.drawString(18*mm,height-102*mm,"Objet : "+invoice.subject[:92])
        return height-(109 if invoice.subject else 101)*mm

    def table_header(y):
        pdf.setFillColor(accent_color);pdf.rect(18*mm,y-3*mm,width-36*mm,9*mm,fill=1,stroke=0)
        pdf.setFillColor(colors.white);pdf.setFont("Helvetica-Bold",8)
        pdf.drawString(21*mm,y,"DÉSIGNATION")
        pdf.drawRightString(width-67*mm,y,"QTÉ")
        pdf.drawRightString(width-42*mm,y,"PRIX")
        pdf.drawRightString(width-20*mm,y,"TOTAL")
        return y-10*mm

    y=table_header(company_header())
    row_height=(8 if compact else 10)*mm
    for index,line in enumerate(lines):
        if y<60*mm:
            pdf.showPage();y=table_header(company_header())
        if index%2==0:
            pdf.setFillColor(colors.HexColor(bg));pdf.rect(18*mm,y-3*mm,width-36*mm,row_height,fill=1,stroke=0)
        pdf.setFillColor(text_color);pdf.setFont(base_font,base_size)
        pdf.drawString(21*mm,y,str(line.description)[:47])
        pdf.drawRightString(width-67*mm,y,str(line.quantity))
        pdf.drawRightString(width-42*mm,y,f"{float(line.unit_amount):,.0f}".replace(","," "))
        pdf.drawRightString(width-20*mm,y,f"{float(line.total_amount):,.0f}".replace(","," "))
        y-=row_height
    if y<60*mm:pdf.showPage();y=table_header(company_header())
    y-=8*mm
    pdf.setFillColor(text_color);pdf.setFont("Helvetica",9)
    def total_row(label,value):
        nonlocal y
        pdf.drawRightString(width-20*mm,y,f"{label} : {float(value):,.0f} FCFA".replace(","," "));y-=6*mm
    total_row("Total HT",invoice.subtotal_amount)
    if float(invoice.discount_amount or 0):total_row("Remise",-float(invoice.discount_amount))
    if float(invoice.tax_amount or 0):total_row(f"TVA ({float(invoice.tax_rate):g} %)",invoice.tax_amount)
    if float(invoice.isb_amount or 0):total_row(f"ISB ({float(header.isb_rate):g} %) déduit",-float(invoice.isb_amount))
    pdf.setFillColor(accent_color);pdf.setFont("Helvetica-Bold",12)
    pdf.drawRightString(width-20*mm,y-2*mm,f"TOTAL TTC : {float(invoice.total_amount):,.0f} FCFA".replace(","," "))
    if invoice.notes:
        pdf.setFillColor(text_color);pdf.setFont("Helvetica",8)
        pdf.drawString(18*mm,max(29*mm,y-16*mm),"Notes : "+invoice.notes.replace("\n"," ")[:110])
    pdf.setFillColor(colors.HexColor("#6c7d89"));pdf.setFont("Helvetica",7)
    pdf.drawString(18*mm,15*mm,"Document émis par "+str(header.company_name)[:65])
    pdf.save()
