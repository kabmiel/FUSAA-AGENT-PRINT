"""Organization membership scope.

Revision ID: 0002_organization_members
Revises: 0001_print_core
"""
from alembic import op
import sqlalchemy as sa
revision="0002_organization_members"
down_revision="0001_print_core"
branch_labels=None
depends_on=None
def upgrade():
    op.create_table("organization_members",sa.Column("id",sa.String(36),primary_key=True),sa.Column("organization_id",sa.String(36),sa.ForeignKey("organizations.id"),nullable=False),sa.Column("user_id",sa.String(36),sa.ForeignKey("users.id"),nullable=False),sa.Column("role",sa.String(30),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True)),sa.Column("updated_at",sa.DateTime(timezone=True)),sa.UniqueConstraint("organization_id","user_id",name="uq_org_member"))
def downgrade():op.drop_table("organization_members")
