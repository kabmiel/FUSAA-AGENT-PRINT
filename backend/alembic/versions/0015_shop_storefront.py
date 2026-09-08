"""Add the FUSAA Shop storefront tables.

The storefront is scoped to the same organization as the print workshop, so
one FUSAA owner can manage both activities from one administration area.
"""
from alembic import op
import sqlalchemy as sa

revision = "0015_shop_storefront"
down_revision = "0014_guest_order_archive"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("shop_categories",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False), sa.Column("slug", sa.String(140), nullable=False),
        sa.Column("description", sa.Text(), nullable=True), sa.Column("icon", sa.String(80), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "slug", name="uq_shop_category_org_slug"))
    op.create_index("ix_shop_categories_organization_id", "shop_categories", ["organization_id"])
    op.create_index("ix_shop_categories_slug", "shop_categories", ["slug"])
    op.create_table("shop_products",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("category_id", sa.String(36), sa.ForeignKey("shop_categories.id"), nullable=True),
        sa.Column("name", sa.String(255), nullable=False), sa.Column("slug", sa.String(280), nullable=False),
        sa.Column("description", sa.Text(), nullable=False), sa.Column("brand", sa.String(100), nullable=True),
        sa.Column("price_xof", sa.Numeric(12,2), nullable=False), sa.Column("original_price_xof", sa.Numeric(12,2), nullable=True),
        sa.Column("condition", sa.String(16), nullable=False), sa.Column("stock_quantity", sa.Integer(), nullable=False),
        sa.Column("specifications", sa.JSON(), nullable=False), sa.Column("image_url", sa.String(2048), nullable=True),
        sa.Column("cloudinary_public_id", sa.String(255), nullable=True), sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "slug", name="uq_shop_product_org_slug"))
    op.create_index("ix_shop_products_organization_id", "shop_products", ["organization_id"])
    op.create_index("ix_shop_products_category_id", "shop_products", ["category_id"])
    op.create_index("ix_shop_products_slug", "shop_products", ["slug"])
    op.create_table("shop_orders",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("order_number", sa.String(60), nullable=False, unique=True), sa.Column("customer_name", sa.String(160), nullable=False),
        sa.Column("customer_phone", sa.String(50), nullable=False), sa.Column("delivery_address", sa.Text(), nullable=True), sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(24), nullable=False), sa.Column("payment_status", sa.String(24), nullable=False), sa.Column("payment_method", sa.String(50), nullable=True),
        sa.Column("total_xof", sa.Numeric(12,2), nullable=False), sa.Column("access_token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_shop_orders_organization_id", "shop_orders", ["organization_id"])
    op.create_index("ix_shop_orders_order_number", "shop_orders", ["order_number"])
    op.create_index("ix_shop_orders_customer_phone", "shop_orders", ["customer_phone"])
    op.create_index("ix_shop_orders_status", "shop_orders", ["status"])
    op.create_table("shop_order_lines",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("order_id", sa.String(36), sa.ForeignKey("shop_orders.id"), nullable=False),
        sa.Column("product_id", sa.String(36), sa.ForeignKey("shop_products.id"), nullable=True), sa.Column("product_name", sa.String(255), nullable=False),
        sa.Column("unit_price_xof", sa.Numeric(12,2), nullable=False), sa.Column("quantity", sa.Integer(), nullable=False))
    op.create_index("ix_shop_order_lines_order_id", "shop_order_lines", ["order_id"])

def downgrade():
    op.drop_table("shop_order_lines")
    op.drop_table("shop_orders")
    op.drop_table("shop_products")
    op.drop_table("shop_categories")
