"""Add categories for billing-only catalogue products."""
from alembic import op
import sqlalchemy as sa

revision="0018_billing_categories"
down_revision="0017_stock_movements"
branch_labels=None
depends_on=None

def upgrade():
    op.create_table("billing_categories",sa.Column("id",sa.String(36),primary_key=True),sa.Column("organization_id",sa.String(36),sa.ForeignKey("organizations.id"),nullable=False),sa.Column("name",sa.String(100),nullable=False),sa.Column("description",sa.Text()),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=False),sa.UniqueConstraint("organization_id","name",name="uq_billing_category_name"))
    op.create_index("ix_billing_categories_organization_id","billing_categories",["organization_id"])
    with op.batch_alter_table("products") as batch: batch.add_column(sa.Column("billing_category_id",sa.String(36),sa.ForeignKey("billing_categories.id",name="fk_products_billing_category"),nullable=True))
    op.create_index("ix_products_billing_category_id","products",["billing_category_id"])

def downgrade():
    op.drop_index("ix_products_billing_category_id",table_name="products")
    with op.batch_alter_table("products") as batch: batch.drop_column("billing_category_id")
    op.drop_table("billing_categories")
