"""Workshop-level roles for central multi-site supervision.

Revision ID: 0008_multisite
Revises: 0007_business
"""
from alembic import op
import sqlalchemy as sa
revision="0008_multisite"
down_revision="0007_business"
branch_labels=None
depends_on=None
def upgrade():
    op.create_table("workshop_members",sa.Column("id",sa.String(36),primary_key=True),sa.Column("workshop_id",sa.String(36),sa.ForeignKey("workshops.id"),nullable=False),sa.Column("user_id",sa.String(36),sa.ForeignKey("users.id"),nullable=False),sa.Column("role",sa.String(30),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True)),sa.Column("updated_at",sa.DateTime(timezone=True)),sa.UniqueConstraint("workshop_id","user_id",name="uq_workshop_member"))
def downgrade():op.drop_table("workshop_members")
