"""Timestamp defaults for all supported database engines.

Revision ID: 0004_timestamp_defaults
Revises: 0003_command_leases
"""
revision="0004_timestamp_defaults"
down_revision="0003_command_leases"
branch_labels=None
depends_on=None
def upgrade():
    # Python-side defaults in the ORM are portable across PostgreSQL and SQLite.
    pass
def downgrade():
    pass
