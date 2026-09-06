"""Command lease and attempt tracking.

Revision ID: 0003_command_leases
Revises: 0002_organization_members
"""
from alembic import op
import sqlalchemy as sa
revision="0003_command_leases"
down_revision="0002_organization_members"
branch_labels=None
depends_on=None
def upgrade():
    op.add_column("agent_commands",sa.Column("claimed_at",sa.DateTime(timezone=True),nullable=True))
    op.add_column("agent_commands",sa.Column("attempt_count",sa.Integer(),nullable=False,server_default="0"))
def downgrade():
    op.drop_column("agent_commands","attempt_count")
    op.drop_column("agent_commands","claimed_at")
