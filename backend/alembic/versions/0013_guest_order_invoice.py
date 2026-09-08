"""Link public orders to their printable receipts."""
from alembic import op
import sqlalchemy as sa

revision="0013_guest_order_invoice"
down_revision="0012_guest_payment_verification"
branch_labels=None
depends_on=None

def upgrade():
    columns={column["name"] for column in sa.inspect(op.get_bind()).get_columns("guest_orders")}
    if "invoice_id" not in columns:
        with op.batch_alter_table("guest_orders") as batch:
            batch.add_column(sa.Column("invoice_id",sa.String(36),sa.ForeignKey("invoices.id",name="fk_guest_orders_invoice_id_invoices"),nullable=True))
            batch.create_unique_constraint("uq_guest_orders_invoice_id",["invoice_id"])

def downgrade():
    with op.batch_alter_table("guest_orders") as batch:
        batch.drop_column("invoice_id")
