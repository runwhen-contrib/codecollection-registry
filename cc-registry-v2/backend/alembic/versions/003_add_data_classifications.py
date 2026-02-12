"""add data_classifications column to codebundles

Revision ID: 003
Revises: 002
Create Date: 2026-02-11

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add data_classifications JSON column — stores per-codebundle summary
    # of data: tags extracted from task-level [Tags] in robot files.
    # Example: {"data:config": {"label": "Configuration data", "count": 5},
    #           "data:logs-regexp": {"label": "Filtered logs", "count": 2}}
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'codebundles' AND column_name = 'data_classifications'
            ) THEN
                ALTER TABLE codebundles
                ADD COLUMN data_classifications JSON DEFAULT '{}';
            END IF;
        END $$;
    """)


def downgrade() -> None:
    op.drop_column('codebundles', 'data_classifications')
