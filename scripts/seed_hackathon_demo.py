"""Create a safe, isolated FUSAA demo dataset for the Hackathon presentation.

Run this only with a dedicated DATABASE_URL.  It never clears an existing
database: every item is created only when the matching demo item is absent.
"""
from pathlib import Path
import sys

# Keep the documented invocation simple: `python scripts/...` from the
# repository root works without manually setting PYTHONPATH.
ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.business_schemas import BillingCompetitionIn, BillingDocumentIn
from app.config import settings
from app.database import SessionLocal
from app.main import create_billing_competition, create_billing_document
from app.models import (
    BillingCategory,
    BillingHeader,
    Customer,
    Invoice,
    Organization,
    OrganizationMember,
    Product,
    User,
    Workshop,
    WorkshopMember,
)
from app.security import hash_password


DEMO_EMAIL = "demo@fusaa-agent.com"
DEMO_PASSWORD = "FusaaDemo2026!"
DEMO_ORGANIZATION = "FUSAA INFORMATIQUE · DEMO HACKATHON"


def first_or_create(db, model, defaults=None, **filters):
    item = db.query(model).filter_by(**filters).first()
    if item:
        return item
    values = dict(defaults or {})
    values.update(filters)
    item = model(**values)
    db.add(item)
    db.flush()
    return item


def main():
    with SessionLocal() as db:
        user = first_or_create(
            db,
            User,
            defaults={
                "display_name": "Equipe FUSAA",
                "password_hash": hash_password(DEMO_PASSWORD),
                "is_active": True,
            },
            email=DEMO_EMAIL,
        )
        organization = first_or_create(db, Organization, name=DEMO_ORGANIZATION)
        first_or_create(
            db,
            OrganizationMember,
            defaults={"role": "OWNER"},
            organization_id=organization.id,
            user_id=user.id,
        )
        # FUSAA can be configured for one workshop in .env.  The demo must
        # use that exact ID, otherwise the authenticated interface correctly
        # hides the workspace and remains on its session loader.
        workshop_filters = (
            {"id": settings.single_workshop_id}
            if settings.single_workshop_id
            else {"organization_id": organization.id, "name": "Atelier principal"}
        )
        workshop = first_or_create(
            db,
            Workshop,
            defaults={"organization_id": organization.id, "name": "Atelier principal"},
            **workshop_filters,
        )
        first_or_create(
            db,
            WorkshopMember,
            defaults={"role": "OWNER"},
            workshop_id=workshop.id,
            user_id=user.id,
        )

        fusaa_header = first_or_create(
            db,
            BillingHeader,
            defaults={
                "address": "Route Tanout, face a la CNSS, Zinder",
                "phone": "+227 98 31 33 69",
                "email": "contact@fusaa.local",
                "nif": "NIF-FUSAA-DEMO",
                "rccm": "RCCM-FUSAA-DEMO",
                "document_style": "moderne_bandeau",
                "tax_enabled": False,
                "tax_rate": 19,
                "isb_enabled": False,
                "isb_rate": 3,
                "table_font_family": "calibri",
                "table_font_size": 10,
                "is_default": True,
            },
            organization_id=organization.id,
            company_name="FUSAA INFORMATIQUE",
        )
        competitor_header = first_or_create(
            db,
            BillingHeader,
            defaults={
                "address": "Zinder, Niger",
                "phone": "+227 90 53 14 65",
                "email": "facturation@kabirou.local",
                "nif": "35252/P",
                "rccm": "NI-ZIN-2014-A-387",
                "document_style": "scan_alasko",
                "tax_enabled": True,
                "tax_rate": 19,
                "isb_enabled": False,
                "isb_rate": 3,
                "table_font_family": "times",
                "table_font_size": 10,
                "is_default": False,
            },
            organization_id=organization.id,
            company_name="KABIROU ABDOU SALAM MAMAN",
        )
        # Keep a default header even if the demo is resumed after manual edits.
        if not db.query(BillingHeader).filter_by(organization_id=organization.id, is_default=True).first():
            fusaa_header.is_default = True

        category = first_or_create(
            db,
            BillingCategory,
            defaults={"description": "Articles de bureau et impression"},
            organization_id=organization.id,
            name="Fournitures",
        )
        products = [
            ("Ramette A4 80 g", 3500, "RAM-A4-80", 34),
            ("Registre 200 pages", 3000, "REG-200", 18),
            ("Carnet de chantier", 3000, "CARN-CHANT", 21),
            ("Calculatrice scientifique", 2500, "CALC-SCI", 12),
        ]
        created_products = {}
        for name, price, sku, stock in products:
            created_products[name] = first_or_create(
                db,
                Product,
                defaults={
                    "unit_price": price,
                    "sku": sku,
                    "unit": "piece",
                    "stock_quantity": stock,
                    "stock_minimum": 3,
                    "billing_category_id": category.id,
                    "enabled": True,
                },
                organization_id=organization.id,
                name=name,
            )
        first_or_create(
            db,
            Customer,
            defaults={
                "phone": "+227 90 00 11 22",
                "email": "moussa@example.test",
                "address": "Zinder, Niger",
            },
            organization_id=organization.id,
            name="Moussa Ibrahim",
        )
        first_or_create(
            db,
            Customer,
            defaults={"phone": "+227 96 10 20 30", "address": "Route Tanout, Zinder"},
            organization_id=organization.id,
            name="Association Taimako",
        )
        db.commit()

        original = db.query(Invoice).filter_by(
            organization_id=organization.id,
            subject="Demonstration Hackathon FUSAA",
        ).first()
        if not original:
            original_result = create_billing_document(
                BillingDocumentIn(
                    organization_id=organization.id,
                    billing_header_id=fusaa_header.id,
                    document_type="INVOICE",
                    customer_name="Moussa Ibrahim",
                    customer_phone="+227 90 00 11 22",
                    subject="Demonstration Hackathon FUSAA",
                    notes="Paiement possible par MYNITA, AMANATA ou WAVE au +227 98 31 33 69.",
                    lines=[
                        {
                            "product_id": created_products["Ramette A4 80 g"].id,
                            "description": "Ramette A4 80 g",
                            "quantity": 2,
                            "unit_amount": 3500,
                        },
                        {
                            "product_id": created_products["Registre 200 pages"].id,
                            "description": "Registre 200 pages",
                            "quantity": 1,
                            "unit_amount": 3000,
                        },
                    ],
                ),
                user,
                db,
            )
            original_id = original_result["id"]
        else:
            original_id = original.id
        has_competition = db.query(Invoice).filter_by(
            competition_source_invoice_id=original_id
        ).first()
        if not has_competition:
            create_billing_competition(
                original_id,
                BillingCompetitionIn(billing_header_id=competitor_header.id, margin_percent=10),
                user,
                db,
            )
        db.commit()
        print("Demo Hackathon prête")
        print(f"  URL: http://127.0.0.1:8765")
        print(f"  Connexion: {DEMO_EMAIL} / {DEMO_PASSWORD}")


if __name__ == "__main__":
    main()
