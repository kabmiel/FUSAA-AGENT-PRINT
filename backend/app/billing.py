"""Billing helpers shared by the shop checkout and the administration API."""
from datetime import datetime, timezone
from pathlib import Path
import secrets
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from .config import settings
from .billing_pdf import render_invoice_pdf
from .models import BillingHeader, BillingProfile, Customer, Invoice, InvoiceLine, ShopOrder, ShopOrderLine

def money(value: float) -> str:
    return f"{float(value or 0):,.0f} FCFA".replace(",", " ")

def invoice_number(db) -> str:
    while True:
        number=f"FAC-{datetime.now(timezone.utc):%Y%m%d}-{secrets.token_hex(3).upper()}"
        if not db.query(Invoice).filter_by(number=number).first(): return number

def billing_profile(db, organization_id: str) -> BillingProfile:
    profile=db.query(BillingProfile).filter_by(organization_id=organization_id).one_or_none()
    if not profile:
        profile=BillingProfile(organization_id=organization_id,company_name="FUSAA INFORMATIQUE")
        db.add(profile);db.flush()
    return profile


def default_billing_header(db, organization_id: str) -> BillingHeader:
    """Seed the existing Boulangerie header once for each FUSAA organization."""
    header=db.query(BillingHeader).filter_by(organization_id=organization_id,is_default=True).first()
    if header:return header
    header=db.query(BillingHeader).filter_by(organization_id=organization_id).order_by(BillingHeader.created_at).first()
    if header:
        header.is_default=True
        return header
    header=BillingHeader(
        organization_id=organization_id,company_name="KABIROU ABDOU SALAM MAMAN",
        address="ZINDER, NIGER",phone="98313369",email="kabmiel43@gmail.com",
        nif="35252/P",rccm="NI-ZIN-2014-A-387",document_style="standard",
        # Même configuration fiscale que l’application Boulangerie.
        tax_enabled=True,tax_rate=19,isb_enabled=False,isb_rate=3,is_default=True,
    )
    db.add(header);db.flush()
    return header


def header_tax(header: BillingHeader, subtotal: float, discount: float = 0) -> tuple[float,float,float]:
    base=max(0,subtotal-discount)
    if header.isb_enabled:
        deduction=round(base*float(header.isb_rate or 0)/100,2)
        return 0,deduction,round(base-deduction,2)
    tax=round(base*float(header.tax_rate or 0)/100,2) if header.tax_enabled else 0
    return tax,0,round(base+tax,2)

def ensure_shop_invoice(db, order: ShopOrder) -> Invoice:
    existing=db.query(Invoice).filter_by(source_shop_order_id=order.id).one_or_none()
    if existing:return existing
    customer=db.query(Customer).filter_by(organization_id=order.organization_id,phone=order.customer_phone).one_or_none()
    if not customer:
        customer=Customer(organization_id=order.organization_id,name=order.customer_name,phone=order.customer_phone,notes=order.delivery_address)
        db.add(customer);db.flush()
    header=default_billing_header(db,order.organization_id)
    lines=db.query(ShopOrderLine).filter_by(order_id=order.id).all()
    subtotal=sum(float(line.unit_price_xof)*line.quantity for line in lines)
    tax_amount,isb_amount,total=header_tax(header,subtotal)
    tax_rate=float(header.tax_rate or 0) if header.tax_enabled else 0
    invoice=Invoice(organization_id=order.organization_id,customer_id=customer.id,source_shop_order_id=order.id,billing_header_id=header.id,number=invoice_number(db),status="PENDING_PAYMENT",currency="XOF",document_type="INVOICE",subject=f"Commande boutique {order.order_number}",notes=order.notes,subtotal_amount=subtotal,tax_rate=tax_rate,tax_amount=tax_amount,isb_amount=isb_amount,total_amount=total)
    db.add(invoice);db.flush()
    for line in lines:
        db.add(InvoiceLine(invoice_id=invoice.id,shop_product_id=line.product_id,description=line.product_name,unit="piece",quantity=line.quantity,unit_amount=float(line.unit_price_xof),total_amount=float(line.unit_price_xof)*line.quantity))
    return invoice

def _legacy_invoice_pdf(db, invoice: Invoice) -> Path:
    profile=billing_profile(db,invoice.organization_id)
    customer=db.get(Customer,invoice.customer_id) if invoice.customer_id else None
    lines=db.query(InvoiceLine).filter_by(invoice_id=invoice.id).order_by(InvoiceLine.id).all()
    path=settings.storage_dir / "invoices" / f"{invoice.number}.pdf";path.parent.mkdir(parents=True,exist_ok=True)
    pdf=canvas.Canvas(str(path),pagesize=A4);width,height=A4
    pdf.setFillColor(colors.HexColor("#071a2a"));pdf.rect(0,height-48*mm,width,48*mm,fill=1,stroke=0)
    pdf.setFillColor(colors.HexColor("#38dec5"));pdf.setFont("Helvetica-Bold",17);pdf.drawString(18*mm,height-24*mm,profile.company_name)
    pdf.setFillColor(colors.white);pdf.setFont("Helvetica-Bold",10);pdf.drawRightString(width-18*mm,height-20*mm,"FACTURE")
    pdf.setFont("Helvetica",8);pdf.drawRightString(width-18*mm,height-27*mm,invoice.number)
    pdf.setFillColor(colors.HexColor("#26455a"));pdf.setFont("Helvetica",9)
    y=height-58*mm
    for detail in filter(None,[profile.address,profile.phone,profile.email]):pdf.drawString(18*mm,y,str(detail));y-=5*mm
    pdf.setFillColor(colors.HexColor("#071a2a"));pdf.setFont("Helvetica-Bold",10);pdf.drawString(18*mm,y-5*mm,"FACTURÉ À")
    pdf.setFont("Helvetica",9);pdf.drawString(18*mm,y-11*mm,customer.name if customer else "Client comptant")
    if customer and customer.phone:pdf.drawString(18*mm,y-16*mm,customer.phone)
    y-=30*mm;pdf.setFillColor(colors.HexColor("#12354d"));pdf.rect(18*mm,y,width-36*mm,9*mm,fill=1,stroke=0)
    pdf.setFillColor(colors.white);pdf.setFont("Helvetica-Bold",8);pdf.drawString(21*mm,y+3*mm,"DÉSIGNATION");pdf.drawRightString(width-67*mm,y+3*mm,"QTÉ");pdf.drawRightString(width-42*mm,y+3*mm,"PRIX");pdf.drawRightString(width-20*mm,y+3*mm,"TOTAL")
    y-=8*mm
    for line in lines:
        pdf.setFillColor(colors.HexColor("#f0f6f8"));pdf.rect(18*mm,y,width-36*mm,8*mm,fill=1,stroke=0)
        pdf.setFillColor(colors.HexColor("#102434"));pdf.setFont("Helvetica",8);pdf.drawString(21*mm,y+3*mm,line.description[:56]);pdf.drawRightString(width-67*mm,y+3*mm,str(line.quantity));pdf.drawRightString(width-42*mm,y+3*mm,money(line.unit_amount));pdf.drawRightString(width-20*mm,y+3*mm,money(line.total_amount));y-=8*mm
    y-=8*mm;pdf.setFont("Helvetica",9);pdf.setFillColor(colors.HexColor("#17364b"));pdf.drawRightString(width-20*mm,y,"Sous-total : "+money(invoice.subtotal_amount));y-=6*mm
    if float(invoice.tax_amount or 0):pdf.drawRightString(width-20*mm,y,f"Taxe ({float(invoice.tax_rate):.0f} %) : "+money(invoice.tax_amount));y-=7*mm
    pdf.setFillColor(colors.HexColor("#0b8c83"));pdf.setFont("Helvetica-Bold",12);pdf.drawRightString(width-20*mm,y,"TOTAL : "+money(invoice.total_amount))
    pdf.setFillColor(colors.HexColor("#5a7180"));pdf.setFont("Helvetica",7);pdf.drawString(18*mm,16*mm,"Document généré par FUSAA · Paiement à confirmer avant livraison.")
    pdf.save();invoice.pdf_key=str(path.relative_to(settings.storage_dir));return path


def generate_invoice_pdf(db, invoice: Invoice) -> Path:
    header=db.get(BillingHeader,invoice.billing_header_id) if invoice.billing_header_id else default_billing_header(db,invoice.organization_id)
    customer=db.get(Customer,invoice.customer_id) if invoice.customer_id else None
    lines=db.query(InvoiceLine).filter_by(invoice_id=invoice.id).order_by(InvoiceLine.id).all()
    path=settings.storage_dir / "invoices" / f"{invoice.number}.pdf"
    render_invoice_pdf(path,invoice,header,customer,lines)
    invoice.pdf_key=str(path.relative_to(settings.storage_dir))
    return path
