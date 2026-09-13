"""Bring Boulangerie-style company headers into integrated billing."""
from alembic import op
import sqlalchemy as sa

revision = "0019_billing_headers"
down_revision = "0018_billing_categories"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "billing_headers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("company_name", sa.String(255), nullable=False),
        sa.Column("address", sa.Text()), sa.Column("phone", sa.String(50)),
        sa.Column("email", sa.String(320)), sa.Column("nif", sa.String(80)),
        sa.Column("rccm", sa.String(80)), sa.Column("logo_url", sa.String(1024)),
        sa.Column("document_style", sa.String(40), nullable=False, server_default="standard"),
        sa.Column("tax_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("tax_rate", sa.Numeric(5, 2), nullable=False, server_default="19"),
        sa.Column("isb_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("isb_rate", sa.Numeric(5, 2), nullable=False, server_default="3"),
        sa.Column("table_font_family", sa.String(20)),
        sa.Column("table_font_size", sa.Numeric(4, 1)),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_billing_headers_organization_id", "billing_headers", ["organization_id"])
    with op.batch_alter_table("invoices") as batch:
        batch.add_column(sa.Column("billing_header_id", sa.String(36), sa.ForeignKey("billing_headers.id", name="fk_invoices_billing_header"), nullable=True))
        batch.add_column(sa.Column("isb_amount", sa.Numeric(12, 2), nullable=False, server_default="0"))
        batch.add_column(sa.Column("issued_on", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_invoices_billing_header_id", "invoices", ["billing_header_id"])
    with op.batch_alter_table("customers") as batch:
        batch.add_column(sa.Column("address", sa.Text(), nullable=True))
    with op.batch_alter_table("invoice_lines") as batch:
        batch.alter_column("quantity", existing_type=sa.Integer(), type_=sa.Numeric(10, 2), existing_nullable=False)

def downgrade():
    with op.batch_alter_table("invoice_lines") as batch:
        batch.alter_column("quantity", existing_type=sa.Numeric(10, 2), type_=sa.Integer(), existing_nullable=False)
    with op.batch_alter_table("customers") as batch:
        batch.drop_column("address")
    op.drop_index("ix_invoices_billing_header_id", table_name="invoices")
    with op.batch_alter_table("invoices") as batch:
        batch.drop_column("billing_header_id")
        batch.drop_column("isb_amount")
        batch.drop_column("issued_on")
    op.drop_table("billing_headers")
