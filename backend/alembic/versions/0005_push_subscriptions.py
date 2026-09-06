"""Web Push subscription persistence.

Revision ID: 0005_push_subscriptions
Revises: 0004_timestamp_defaults
"""
from alembic import op
import sqlalchemy as sa
revision="0005_push_subscriptions"
down_revision="0004_timestamp_defaults"
branch_labels=None
depends_on=None
def upgrade():
    op.create_table("push_subscriptions",sa.Column("id",sa.String(36),primary_key=True),sa.Column("user_id",sa.String(36),sa.ForeignKey("users.id"),nullable=False),sa.Column("endpoint",sa.String(2048),nullable=False),sa.Column("p256dh",sa.String(255),nullable=False),sa.Column("auth",sa.String(255),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True)),sa.Column("updated_at",sa.DateTime(timezone=True)),sa.UniqueConstraint("endpoint"))
def downgrade():op.drop_table("push_subscriptions")
