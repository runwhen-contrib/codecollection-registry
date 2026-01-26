"""add user_variables column

Revision ID: 001
Revises: 
Create Date: 2026-01-26

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add user_variables column if it doesn't exist
    op.execute("""
        DO $$ 
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'codebundles' AND column_name = 'user_variables'
            ) THEN
                ALTER TABLE codebundles 
                ADD COLUMN user_variables JSON DEFAULT '[]'::json;
            END IF;
        END $$;
    """)


def downgrade() -> None:
    # Remove user_variables column
    op.drop_column('codebundles', 'user_variables')
