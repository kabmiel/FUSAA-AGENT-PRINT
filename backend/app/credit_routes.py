from io import BytesIO
from datetime import datetime, timezone
from types import SimpleNamespace

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .database import get_db
from .security import current_user
from .models import BillingHeader, Customer, CustomerCreditAccount as Account, OrganizationMember, User
from .business_schemas import CreditRepaymentIn
from .billing import default_billing_header
from .credit_accounts import account_for_write, account_data, history, fingerprint, money, repay, replay
from .billing_pdf import render_credit_statement_pdf

router = APIRouter(prefix="/api/v1/billing/credit-accounts", tags=["Comptes crédit"])


def access(db, user, organization_id, write=False):
    member = db.query(OrganizationMember).filter_by(organization_id=organization_id, user_id=user.id).first()
    if not member or (write and member.role not in {"OWNER", "ADMIN"}):
        raise HTTPException(403, "Accès au compte crédit non autorisé")


def read_account(db, organization_id, customer_id):
    row = db.query(Account, Customer).join(Customer, Account.customer_id == Customer.id).filter(
        Account.organization_id == organization_id, Customer.organization_id == organization_id, Customer.id == customer_id).first()
    if not row:
        raise HTTPException(404, "Compte crédit introuvable")
    return row


@router.get("")
def accounts(organization_id: str, status: str = Query("active", pattern="^(active|settled|all)$"),
             q: str = Query("", max_length=160), page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=50),
             user: User = Depends(current_user), db: Session = Depends(get_db)):
    access(db, user, organization_id)
    query = db.query(Account, Customer).join(Customer, Account.customer_id == Customer.id).filter(Account.organization_id == organization_id)
    if status == "active": query = query.filter(Account.balance > 0)
    if status == "settled": query = query.filter(Account.balance == 0)
    if q.strip(): query = query.filter(or_(Customer.name.ilike("%" + q.strip() + "%"), Customer.phone.ilike("%" + q.strip() + "%")))
    total = query.count()
    rows = query.order_by(Account.updated_at.desc(), Account.id).offset((page - 1) * page_size).limit(page_size).all()
    active, balance = db.query(func.count(Account.id), func.coalesce(func.sum(Account.balance), 0)).filter(Account.organization_id == organization_id, Account.balance > 0).one()
    return {"items": [account_data(a, c) for a, c in rows], "total": total, "page": page,
            "has_more": page * page_size < total, "active_count": active, "balance": float(balance)}


@router.get("/{customer_id}")
def detail(customer_id: str, organization_id: str, page: int = Query(1, ge=1),
           user: User = Depends(current_user), db: Session = Depends(get_db)):
    access(db, user, organization_id)
    account, customer = read_account(db, organization_id, customer_id)
    operations, count = history(db, account, page=page)
    return {**account_data(account, customer), "operations": operations, "page": page,
            "has_more": page * 30 < count, "operation_count": count}


@router.post("/{customer_id}/repayments", status_code=201)
def repayment(customer_id: str, organization_id: str, data: CreditRepaymentIn,
              user: User = Depends(current_user), db: Session = Depends(get_db)):
    access(db, user, organization_id, write=True)
    account = account_for_write(db, organization_id, customer_id)
    request_hash = fingerprint(data)
    existing = replay(db, organization_id, data.request_id, request_hash)
    if existing:
        if existing.account_id != account.id or existing.kind != "REPAYMENT": raise HTTPException(409, "Demande déjà utilisée")
        return {"operation_id": existing.id, "balance": float(account.balance), "archived": not bool(account.balance)}
    try:
        operation = repay(db, account, data.amount, user.id, data.request_id, request_hash,
                          data.occurred_on, data.method, data.note)
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = replay(db, organization_id, data.request_id, request_hash)
        if not existing or existing.account_id != account.id or existing.kind != "REPAYMENT": raise
        operation = existing
        db.refresh(account)
    return {"operation_id": operation.id, "balance": float(account.balance), "archived": not bool(account.balance)}


@router.get("/{customer_id}/statement.pdf")
def statement(customer_id: str, organization_id: str, billing_header_id: str | None = None,
              user: User = Depends(current_user), db: Session = Depends(get_db)):
    access(db, user, organization_id)
    account, customer = read_account(db, organization_id, customer_id)
    operations, _ = history(db, account, all_rows=True)
    # Render one coherent ledger snapshot even if another user repays while the
    # PDF request is running (PostgreSQL's default isolation is READ COMMITTED).
    balance = sum((money(op["amount"]) * (1 if op["kind"] == "PURCHASE" else -1) for op in operations), money(0))
    header_id = billing_header_id or next((op["billing_header_id"] for op in reversed(operations) if op["billing_header_id"]), None)
    header = db.get(BillingHeader, header_id) if header_id else default_billing_header(db, organization_id)
    if not header or header.organization_id != organization_id: raise HTTPException(422, "Entête introuvable")
    doc = SimpleNamespace(number="CREDIT-" + account.id[:8].upper(), document_type="CREDIT_STATEMENT",
        issued_on=datetime.now(timezone.utc), subject="Historique des achats à crédit et remboursements", total_amount=balance,
        document_style=header.document_style)
    content = render_credit_statement_pdf(doc, header, customer, operations, balance)
    return StreamingResponse(BytesIO(content), media_type="application/pdf",
        headers={"Content-Disposition": 'inline; filename="etat-credit-' + customer.id + '.pdf"', "Cache-Control": "no-store"})
