"""Add FUSAA billing details and automatic shop invoice links."""
from alembic import op
import sqlalchemy as sa

revision = "0016_billing_module"
down_revision = "0015_shop_storefront"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("billing_profiles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False, unique=True),
        sa.Column("company_name", sa.String(255), nullable=False), sa.Column("address", sa.Text()), sa.Column("phone", sa.String(50)), sa.Column("email", sa.String(320)),
        sa.Column("nif", sa.String(80)), sa.Column("rccm", sa.String(80)), sa.Column("tax_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("tax_rate", sa.Numeric(5,2), nullable=False, server_default="0"), sa.Column("document_style", sa.String(40), nullable=False, server_default="moderne"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_billing_profiles_organization_id", "billing_profiles", ["organization_id"])
    with op.batch_alter_table("shop_products") as batch:
        batch.add_column(sa.Column("sku", sa.String(80)))
        batch.add_column(sa.Column("unit", sa.String(20), nullable=False, server_default="piece"))
        batch.add_column(sa.Column("cost_xof", sa.Numeric(12,2), nullable=False, server_default="0"))
        batch.add_column(sa.Column("stock_minimum", sa.Integer(), nullable=False, server_default="3"))
    with op.batch_alter_table("invoices") as batch:
        batch.add_column(sa.Column("source_shop_order_id", sa.String(36), sa.ForeignKey("shop_orders.id", name="fk_invoices_source_shop_order"), nullable=True))
        batch.add_column(sa.Column("document_type", sa.String(24), nullable=False, server_default="INVOICE"))
        batch.add_column(sa.Column("subject", sa.String(255)))
        batch.add_column(sa.Column("notes", sa.Text()))
        batch.add_column(sa.Column("subtotal_amount", sa.Numeric(12,2), nullable=False, server_default="0"))
        batch.add_column(sa.Column("tax_rate", sa.Numeric(5,2), nullable=False, server_default="0"))
        batch.add_column(sa.Column("tax_amount", sa.Numeric(12,2), nullable=False, server_default="0"))
        batch.add_column(sa.Column("discount_amount", sa.Numeric(12,2), nullable=False, server_default="0"))
        batch.add_column(sa.Column("pdf_key", sa.String(512)))
        batch.create_unique_constraint("uq_invoices_source_shop_order", ["source_shop_order_id"])
    op.create_index("ix_invoices_source_shop_order_id", "invoices", ["source_shop_order_id"])
    with op.batch_alter_table("invoice_lines") as batch:
        batch.add_column(sa.Column("shop_product_id", sa.String(36), sa.ForeignKey("shop_products.id", name="fk_invoice_lines_shop_product"), nullable=True))
        batch.add_column(sa.Column("unit", sa.String(20), nullable=False, server_default="piece"))

def downgrade():
    with op.batch_alter_table("invoice_lines") as batch:
        batch.drop_column("unit"); batch.drop_column("shop_product_id")
    op.drop_index("ix_invoices_source_shop_order_id", table_name="invoices")
    with op.batch_alter_table("invoices") as batch:
        batch.drop_constraint("uq_invoices_source_shop_order", type_="unique")
        for column in ("pdf_key","discount_amount","tax_amount","tax_rate","subtotal_amount","notes","subject","document_type","source_shop_order_id"): batch.drop_column(column)
    with op.batch_alter_table("shop_products") as batch:
        for column in ("stock_minimum","cost_xof","unit","sku"): batch.drop_column(column)
    op.drop_index("ix_billing_profiles_organization_id", table_name="billing_profiles")
    op.drop_table("billing_profiles")
