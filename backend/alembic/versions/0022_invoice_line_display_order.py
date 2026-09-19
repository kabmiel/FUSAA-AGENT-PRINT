"""Keep the order entered for billing invoice lines."""
from alembic import op
import sqlalchemy as sa


revision = "0022_invoice_line_display_order"
down_revision = "0021_invoice_document_style"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("invoice_lines") as batch:
        batch.add_column(sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"))
        batch.create_index("ix_invoice_lines_invoice_display_order", ["invoice_id", "display_order"])


def downgrade():
    with op.batch_alter_table("invoice_lines") as batch:
        batch.drop_index("ix_invoice_lines_invoice_display_order")
        batch.drop_column("display_order")
