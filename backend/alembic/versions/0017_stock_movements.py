"""Add billing stock fields and unified stock movement history."""
from alembic import op
import sqlalchemy as sa

revision = "0017_stock_movements"
down_revision = "0016_billing_module"
branch_labels = None
depends_on = None

def upgrade():
    with op.batch_alter_table("products") as batch:
        batch.add_column(sa.Column("unit", sa.String(20), nullable=False, server_default="piece"))
        batch.add_column(sa.Column("cost_xof", sa.Numeric(12,2), nullable=False, server_default="0"))
        batch.add_column(sa.Column("stock_quantity", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("stock_minimum", sa.Integer(), nullable=False, server_default="3"))
    op.create_table("stock_movements",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("catalogue", sa.String(16), nullable=False), sa.Column("product_id", sa.String(36), nullable=False),
        sa.Column("movement_type", sa.String(16), nullable=False), sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("previous_quantity", sa.Integer(), nullable=False), sa.Column("resulting_quantity", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(255)), sa.Column("reference", sa.String(80)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_stock_movements_organization_id", "stock_movements", ["organization_id"])
    op.create_index("ix_stock_movements_catalogue", "stock_movements", ["catalogue"])
    op.create_index("ix_stock_movements_product_id", "stock_movements", ["product_id"])

def downgrade():
    op.drop_table("stock_movements")
    with op.batch_alter_table("products") as batch:
        for column in ("stock_minimum","stock_quantity","cost_xof","unit"): batch.drop_column(column)
