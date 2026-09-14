"""Persist the Boulangerie-style competition document trace."""
from alembic import op
import sqlalchemy as sa


revision = "0020_billing_competition_trace"
down_revision = "0019_billing_headers"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("invoices") as batch:
        batch.add_column(sa.Column("competition_source_invoice_id", sa.String(36), sa.ForeignKey("invoices.id", name="fk_invoices_competition_source"), nullable=True))
        batch.add_column(sa.Column("competition_margin_percent", sa.Numeric(6, 2), nullable=True))
    op.create_index("ix_invoices_competition_source_invoice_id", "invoices", ["competition_source_invoice_id"])
    with op.batch_alter_table("invoice_lines") as batch:
        batch.add_column(sa.Column("billing_product_id", sa.String(36), sa.ForeignKey("products.id", name="fk_invoice_lines_billing_product"), nullable=True))
    op.create_index("ix_invoice_lines_billing_product_id", "invoice_lines", ["billing_product_id"])


def downgrade():
    op.drop_index("ix_invoice_lines_billing_product_id", table_name="invoice_lines")
    with op.batch_alter_table("invoice_lines") as batch:
        batch.drop_column("billing_product_id")
    op.drop_index("ix_invoices_competition_source_invoice_id", table_name="invoices")
    with op.batch_alter_table("invoices") as batch:
        batch.drop_column("competition_margin_percent")
        batch.drop_column("competition_source_invoice_id")
