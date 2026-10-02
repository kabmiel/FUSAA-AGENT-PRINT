"""Credit ledger. No commits here: invoice, balance and payments are atomic."""
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from .models import Customer, CustomerCreditAccount as Account, CustomerCreditOperation as Operation, Invoice, InvoiceLine, Payment
from .services import audit


def money(value):
    amount = Decimal(str(value or 0))
    if not amount.is_finite() or abs(amount) >= Decimal("10000000000"):
        raise HTTPException(422, "Montant hors limite")
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def fingerprint(data):
    return hashlib.sha256(json.dumps(data.model_dump(mode="json"), sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def replay(db, organization_id, request_id, request_hash):
    operation = db.query(Operation).filter_by(organization_id=organization_id, request_id=request_id).first()
    if operation and operation.request_hash != request_hash:
        raise HTTPException(409, "Cette demande a déjà été enregistrée avec d'autres informations. Rouvrez le formulaire.")
    return operation


def account_for_write(db, organization_id, customer_id, create=False):
    # Serialize writes per customer on PostgreSQL. Conditional balance updates
    # below also protect SQLite against two repayments spending the same balance.
    customer = db.query(Customer).filter_by(id=customer_id, organization_id=organization_id).with_for_update().first()
    if not customer:
        raise HTTPException(404, "Client introuvable")
    account = db.query(Account).filter_by(customer_id=customer_id, organization_id=organization_id).with_for_update().first()
    if not account and create:
        try:
            with db.begin_nested():
                account = Account(organization_id=organization_id, customer_id=customer_id, balance=0, total_purchases=0, total_repaid=0)
                db.add(account)
                db.flush()
        except IntegrityError:
            account = db.query(Account).filter_by(customer_id=customer_id, organization_id=organization_id).with_for_update().one()
    if not account:
        raise HTTPException(404, "Ce client n'a pas encore de compte crédit")
    return account


def purchase(db, invoice, actor_id, request_id, request_hash, initial_payment=0):
    amount, initial = money(invoice.total_amount), money(initial_payment)
    if amount <= 0 or initial > amount:
        raise HTTPException(422, "L'achat doit être positif et l'acompte ne peut pas dépasser son montant")
    account = account_for_write(db, invoice.organization_id, invoice.customer_id, create=True)
    operation = Operation(account_id=account.id, organization_id=invoice.organization_id, kind="PURCHASE", amount=amount,
        invoice_id=invoice.id, request_id=request_id, request_hash=request_hash,
        occurred_on=invoice.issued_on, actor_id=actor_id, allocations=[])
    db.add(operation)
    db.flush()  # Claim idempotency key before changing the balance.
    changed = db.query(Account).filter(Account.id == account.id, Account.balance + amount < Decimal("10000000000"),
        Account.total_purchases + amount < Decimal("10000000000")).update({Account.balance: func.round(Account.balance + amount, 2),
        Account.total_purchases: func.round(Account.total_purchases + amount, 2), Account.settled_at: None}, synchronize_session=False)
    if not changed:
        raise HTTPException(422, "Le compte dépasse la limite autorisée")
    db.refresh(account)
    if initial:
        repay(db, account, initial, actor_id, request_id + "-initial", request_hash,
            occurred_on=invoice.issued_on, method="ACOMPTE", target_invoice_id=invoice.id)
    audit(db, actor_id, "CREDIT_PURCHASE", "CustomerCreditAccount", account.id,
        parameters={"invoice_id": invoice.id, "amount": str(amount)}, result="SUCCESS")
    return account


def repay(db, account, amount, actor_id, request_id, request_hash, occurred_on=None, method="ESPECES", note=None, target_invoice_id=None):
    amount = money(amount)
    if amount <= 0 or amount > money(account.balance):
        raise HTTPException(422, "Le remboursement doit être positif et ne peut pas dépasser le solde")
    operation = Operation(account_id=account.id, organization_id=account.organization_id, kind="REPAYMENT", amount=amount,
        request_id=request_id, request_hash=request_hash, occurred_on=occurred_on or datetime.now(timezone.utc),
        actor_id=actor_id, method=method, note=note, allocations=[])
    db.add(operation)
    db.flush()
    changed = db.query(Account).filter(Account.id == account.id, Account.balance >= amount).update({
        Account.balance: func.round(Account.balance - amount, 2), Account.total_repaid: func.round(Account.total_repaid + amount, 2)}, synchronize_session=False)
    if not changed:
        raise HTTPException(409, "Le solde vient de changer. Actualisez le compte avant de rembourser.")
    invoices = db.query(Invoice).join(Operation, Operation.invoice_id == Invoice.id).filter(
        Operation.account_id == account.id, Operation.kind == "PURCHASE", Invoice.status != "PAID")
    if target_invoice_id:
        invoices = invoices.filter(Invoice.id == target_invoice_id)
    invoices = invoices.order_by(Operation.occurred_on, Operation.created_at, Operation.id).all()
    paid = dict(db.query(Payment.invoice_id, func.sum(Payment.amount)).filter(
        Payment.invoice_id.in_([item.id for item in invoices]), Payment.status == "CONFIRMED").group_by(Payment.invoice_id).all())
    remaining, allocations = amount, []
    for invoice in invoices:
        previous = money(paid.get(invoice.id, 0))
        allocation = min(remaining, max(Decimal("0"), money(invoice.total_amount) - previous))
        if allocation <= 0:
            continue
        payment = Payment(invoice_id=invoice.id, amount=allocation, method=method, reference=operation.id, status="CONFIRMED")
        db.add(payment)
        invoice.status = "PAID" if previous + allocation == money(invoice.total_amount) else "PARTIALLY_PAID"
        allocations.append({"invoice_id": invoice.id, "number": invoice.number, "amount": str(allocation)})
        remaining -= allocation
        if not remaining:
            break
    if remaining:
        # Roll back the whole request, never leave a balance without allocations.
        raise HTTPException(409, "L'historique et le solde ne concordent pas. Aucun remboursement n'a été enregistré.")
    operation.allocations = allocations
    db.refresh(account)
    account.settled_at = datetime.now(timezone.utc) if not money(account.balance) else None
    audit(db, actor_id, "CREDIT_REPAYMENT", "CustomerCreditAccount", account.id,
        parameters={"operation_id": operation.id, "amount": str(amount), "allocations": allocations}, result="SUCCESS")
    db.flush()
    return operation


def account_data(account, customer):
    return {"id": account.id, "customer_id": customer.id, "customer_name": customer.name, "phone": customer.phone,
        "balance": float(account.balance), "total_purchases": float(account.total_purchases),
        "total_repaid": float(account.total_repaid), "archived": not bool(account.balance),
        "settled_at": account.settled_at, "updated_at": account.updated_at}


def history(db, account, page=1, page_size=30, all_rows=False):
    # Two bounded/batched reads rather than a query for each operation/product.
    query = db.query(Operation).filter_by(account_id=account.id)
    total = query.count() if not all_rows else None
    # Ledger registration order is immutable; entered operation dates remain visible.
    query = query.order_by(Operation.created_at, Operation.id)
    operations = query.all() if all_rows else query.offset((page - 1) * page_size).limit(page_size).all()
    invoice_ids = [op.invoice_id for op in operations if op.invoice_id]
    invoices = {item.id: item for item in db.query(Invoice).filter(Invoice.id.in_(invoice_ids)).all()} if invoice_ids else {}
    lines = {}
    for line in db.query(InvoiceLine).filter(InvoiceLine.invoice_id.in_(invoice_ids)).order_by(InvoiceLine.display_order, InvoiceLine.id).all() if invoice_ids else []:
        lines.setdefault(line.invoice_id, []).append({"description": line.description, "quantity": line.quantity,
            "unit_amount": float(line.unit_amount), "total_amount": float(line.total_amount), "unit": line.unit})
    result = []
    for op in operations:
        invoice = invoices.get(op.invoice_id)
        result.append({"id": op.id, "kind": op.kind, "amount": float(op.amount), "date": op.occurred_on,
            "created_at": op.created_at, "invoice_id": op.invoice_id, "number": invoice.number if invoice else None,
            "billing_header_id": invoice.billing_header_id if invoice else None, "note": op.note,
            "method": op.method, "allocations": op.allocations, "lines": lines.get(op.invoice_id, [])})
    return result, total
