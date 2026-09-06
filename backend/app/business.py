from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy.orm import Session
from .models import Document, PriceRule, PrintJob

def money(value)->Decimal:return Decimal(str(value)).quantize(Decimal("0.01"),rounding=ROUND_HALF_UP)
def estimate_print_cost(db:Session,job:PrintJob)->tuple[Decimal,dict]:
    document=db.get(Document,job.document_id);pages=int((document.metadata_json or {}).get("pages",1) or 1);copies=job.copies
    rules=db.query(PriceRule).filter_by(organization_id=job.organization_id,enabled=True).order_by(PriceRule.priority.asc()).all()
    selected=None
    for rule in rules:
        cond=rule.conditions or {}
        if cond.get("paper_size") and cond["paper_size"]!=job.paper_size:continue
        if cond.get("color_mode") and cond["color_mode"]!=job.color_mode:continue
        if cond.get("printer_id") and cond["printer_id"]!=job.printer_id:continue
        if cond.get("min_copies") and copies<int(cond["min_copies"]):continue
        if cond.get("max_copies") and copies>int(cond["max_copies"]):continue
        selected=rule;break
    pricing=(selected.pricing if selected else {}) or {};base=money(pricing.get("base",0));per_copy=money(pricing.get("per_copy",0));per_page=money(pricing.get("per_page",0));total=base+per_copy*copies+per_page*pages*copies
    return total,{"rule_id":selected.id if selected else None,"rule_name":selected.name if selected else "Aucune règle","base":float(base),"per_copy":float(per_copy),"per_page":float(per_page),"pages":pages,"copies":copies,"total":float(total)}
