"""add task growth metrics table

Revision ID: 002
Revises: 001
Create Date: 2026-01-26

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Create task_growth_metrics table for caching analytics data.
    """
    op.execute("""
        CREATE TABLE IF NOT EXISTS task_growth_metrics (
            id SERIAL PRIMARY KEY,
            metric_type VARCHAR(50) NOT NULL DEFAULT 'monthly_growth',
            time_period VARCHAR(20) NOT NULL,
            data JSON NOT NULL,
            computed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
            computation_duration_seconds INTEGER,
            codebundles_analyzed INTEGER,
            notes TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
        );
        
        CREATE INDEX IF NOT EXISTS idx_task_growth_metrics_metric_type 
        ON task_growth_metrics(metric_type);
        
        CREATE INDEX IF NOT EXISTS idx_task_growth_metrics_computed_at 
        ON task_growth_metrics(computed_at DESC);
    """)


def downgrade() -> None:
    """
    Drop task_growth_metrics table.
    """
    op.execute("DROP TABLE IF EXISTS task_growth_metrics;")
