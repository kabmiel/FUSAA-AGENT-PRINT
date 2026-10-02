"""Explicit credit accounts and an immutable operation ledger."""
from alembic import context, op
import sqlalchemy as sa

revision = "0024_customer_credit_accounts"
down_revision = "0023_workshop_app_transparency"
branch_labels = None
depends_on = None


def timestamps():
    return [sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())]


def upgrade():
    # SQLite's local startup can create metadata before Alembic is next run.
    # Adopt those identical tables instead of failing with "already exists".
    inspector = None if context.is_offline_mode() else sa.inspect(op.get_bind())

    def create_table(name, *columns):
        if inspector is None or not inspector.has_table(name):
            op.create_table(name, *columns)

    def create_index(name, table, columns):
        if inspector is None or name not in {item["name"] for item in inspector.get_indexes(table)}:
            op.create_index(name, table, columns)

    create_table("customer_credit_accounts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("customer_id", sa.String(36), sa.ForeignKey("customers.id"), nullable=False, unique=True),
        sa.Column("balance", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("total_purchases", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("total_repaid", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("settled_at", sa.DateTime(timezone=True)),
        *timestamps(), sa.CheckConstraint("balance >= 0", name="ck_credit_balance"))
    create_index("ix_customer_credit_accounts_organization_id", "customer_credit_accounts", ["organization_id"])
    create_table("customer_credit_operations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("account_id", sa.String(36), sa.ForeignKey("customer_credit_accounts.id"), nullable=False),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("kind", sa.String(12), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("invoice_id", sa.String(36), sa.ForeignKey("invoices.id"), unique=True),
        sa.Column("request_id", sa.String(128), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("occurred_on", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("method", sa.String(40)), sa.Column("note", sa.Text()),
        sa.Column("allocations", sa.JSON(), nullable=False), *timestamps(),
        sa.UniqueConstraint("organization_id", "request_id", name="uq_credit_request"),
        sa.CheckConstraint("amount > 0", name="ck_credit_amount"),
        sa.CheckConstraint("kind IN ('PURCHASE', 'REPAYMENT')", name="ck_credit_kind"))
    create_index("ix_customer_credit_operations_account_id", "customer_credit_operations", ["account_id"])
    if inspector is not None and inspector.has_table("customer_credit_operations"):
        columns = {item["name"] for item in inspector.get_columns("customer_credit_operations")}
        if "request_hash" not in columns:
            # A local --reload may have created the first table definition while
            # files were being edited. Keep any history and complete that schema.
            op.add_column("customer_credit_operations", sa.Column("request_hash", sa.String(64), nullable=False, server_default=""))


def downgrade():
    op.drop_table("customer_credit_operations")
    op.drop_table("customer_credit_accounts")
