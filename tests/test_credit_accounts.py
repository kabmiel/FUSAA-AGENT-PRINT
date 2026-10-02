"""Short checks on an isolated database; no server, AI or production writes."""
import sys
from datetime import datetime, timezone
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).parents[1] / "backend"))
from app.database import Base
from app.models import Customer, CustomerCreditAccount, CustomerCreditOperation, Organization, OrganizationMember, User, BillingHeader, Invoice, Payment, Product, ShopProduct
from app.business_schemas import BillingDocumentIn, CreditRepaymentIn, PaymentIn
from app.main import create_billing_document, update_billing_invoice, record_payment
from app.credit_routes import accounts, repayment, access
from app.credit_accounts import history
from app.billing_pdf import render_credit_statement_pdf


@pytest.fixture
def ledger():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user = User(id="u", email="admin@example.test", password_hash="x", display_name="Admin")
        db.add_all([user, Organization(id="o", name="Test"), Customer(id="c", organization_id="o", name="Client Exemple", address="Adresse non imprimée"),
            OrganizationMember(user_id="u", organization_id="o", role="OWNER"),
            BillingHeader(id="h", organization_id="o", company_name="FUSAA INFORMATIQUE", document_style="standard", is_default=True),
            Product(id="p", organization_id="o", name="Ramette", unit_price=100),
            ShopProduct(id="s", organization_id="o", name="Cahier", slug="cahier", price_xof=200)])
        db.commit()
        yield db, user
    engine.dispose()


def document(key, amount=300, initial=0):
    return BillingDocumentIn(organization_id="o", customer_id="c", billing_header_id="h", on_credit=True,
        initial_payment=initial, request_id=key, issued_on=datetime(2026, 10, 2, 12, tzinfo=timezone.utc),
        lines=[{"product_id":"p", "description":"Ramette", "quantity":1, "unit_amount":amount-200},
               {"product_id":"s", "description":"Cahier", "quantity":1, "unit_amount":200}])


def refund(db, user, amount, key):
    return repayment("c", "o", CreditRepaymentIn(amount=amount, request_id=key), user, db)


def test_repeat_purchases_fifo_full_settlement_and_reactivation(ledger):
    db, user = ledger
    first = create_billing_document(document("purchase-first-0001", initial=50), user, db)
    second = create_billing_document(document("purchase-second-001"), user, db)
    account = db.query(CustomerCreditAccount).one()
    assert account.balance == Decimal("550.00")
    refund(db, user, 300, "repayment-first-001")
    assert db.get(Invoice, first["id"]).status == "PAID"
    assert db.get(Invoice, second["id"]).status == "PARTIALLY_PAID"
    assert db.query(Payment).filter_by(invoice_id=second["id"]).one().amount == Decimal("50.00")
    refund(db, user, 250, "repayment-settle-01")
    assert account.balance == 0 and account.settled_at is not None
    assert accounts("o", "active", "", 1, 20, user, db)["total"] == 0
    assert accounts("o", "settled", "", 1, 20, user, db)["total"] == 1
    assert db.get(Customer, "c") is not None
    create_billing_document(document("purchase-reactivate"), user, db)
    assert db.query(CustomerCreditAccount).count() == 1
    assert account.balance == 300 and account.settled_at is None


def test_idempotency_overpayment_and_immutable_purchase(ledger):
    db, user = ledger
    data = document("purchase-request-01")
    invoice = create_billing_document(data, user, db)
    assert create_billing_document(data, user, db)["id"] == invoice["id"]
    assert db.query(Invoice).count() == 1
    with pytest.raises(HTTPException) as conflict:
        create_billing_document(document("purchase-request-01", amount=400), user, db)
    assert conflict.value.status_code == 409
    db.rollback()
    with pytest.raises(HTTPException): refund(db, user, 301, "repayment-too-much1")
    db.rollback()
    assert db.query(CustomerCreditAccount).one().balance == 300
    refund(db, user, 100, "repayment-repeat-01")
    refund(db, user, 100, "repayment-repeat-01")
    assert db.query(CustomerCreditAccount).one().balance == 200
    assert db.query(CustomerCreditOperation).count() == 2
    with pytest.raises(HTTPException): update_billing_invoice(invoice["id"], data, user, db)
    with pytest.raises(HTTPException): record_payment(invoice["id"], PaymentIn(amount=10, method="ESPECES"), user, db)
    refund(db, user, Decimal("199.80"), "repayment-decimal01")
    refund(db, user, Decimal("0.20"), "repayment-decimal02")
    assert db.query(CustomerCreditAccount).one().balance == Decimal("0.00")


def test_credit_permissions_and_ordinary_invoice_are_separate(ledger):
    db, user = ledger
    stranger = User(id="stranger", email="s@example.test", password_hash="x", display_name="S")
    db.add(stranger); db.commit()
    with pytest.raises(HTTPException): access(db, stranger, "o")
    db.query(OrganizationMember).one().role="VIEWER";db.commit()
    with pytest.raises(HTTPException): create_billing_document(document("purchase-forbidden1"), user, db)
    db.rollback()
    ordinary = document("unused-request-0001").model_copy(update={"on_credit":False})
    create_billing_document(ordinary, user, db)
    assert db.query(CustomerCreditAccount).count() == 0
    assert db.query(CustomerCreditOperation).count() == 0


def test_statement_dates_order_same_header_and_multi_page(ledger, tmp_path):
    from pypdf import PdfReader
    db, user = ledger
    create_billing_document(document("purchase-pdf-000001"), user, db)
    account = db.query(CustomerCreditAccount).one()
    operations, _ = history(db, account, all_rows=True)
    operations[0]["lines"] = [{"description":f"Article {i:02d}", "quantity":1, "total_amount":6} for i in range(50)]
    doc=SimpleNamespace(number="CREDIT-TEST",document_type="CREDIT_STATEMENT",issued_on=datetime(2026,10,2),subject=None,total_amount=300)
    header=db.get(BillingHeader,"h")
    for style in ("standard", "ultra_compact", "moderne_clair"):
        header.document_style=style
        content=render_credit_statement_pdf(doc,header,db.get(Customer,"c"),operations,300)
        reader=PdfReader(BytesIO(content));text="\n".join(page.extract_text() for page in reader.pages)
        assert "FUSAA INFORMATIQUE" in text and "Client Exemple" in text
        assert "02/10/2026" in text and "Solde en lettres" in text
        assert "Adresse non imprimée" not in text
        assert text.index("Article 00") < text.index("Article 49")
        assert len(reader.pages)>=2
        (tmp_path / (style+".pdf")).write_bytes(content)
