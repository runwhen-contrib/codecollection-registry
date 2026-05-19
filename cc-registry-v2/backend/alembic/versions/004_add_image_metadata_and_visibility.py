"""add image metadata to codecollection_versions and visibility to codecollections

Adds the columns needed to track versioned OCI image artifacts per ref so the
RunWhen platform (PAPI) can consume a built-image catalog directly from the
codecollection-registry instead of running its own corestate-operator.

Also adds a `visibility` column on `codecollections` so a CC can be tracked
for image consumption but kept out of the public registry website / MCP /
AI search (e.g. customer-private, internal, deprecated CCs).

Revision ID: 004
Revises: 003
Create Date: 2026-05-11
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- image metadata on codecollection_versions ---
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'codecollection_versions'
                  AND column_name = 'image_registry'
            ) THEN
                ALTER TABLE codecollection_versions
                    ADD COLUMN image_registry VARCHAR(500),
                    ADD COLUMN image_tag      VARCHAR(200),
                    ADD COLUMN image_digest   VARCHAR(80),
                    ADD COLUMN commit_hash    VARCHAR(40),
                    ADD COLUMN rt_revision    VARCHAR(40),
                    ADD COLUMN image_built_at TIMESTAMP;
            END IF;
        END $$;
        """
    )

    # Index for PAPI's "latest ref for this CC" lookups.
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_ccv_collection_image_tag
            ON codecollection_versions (codecollection_id, image_tag);
        """
    )

    # --- visibility on codecollections ---
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'codecollections'
                  AND column_name = 'visibility'
            ) THEN
                ALTER TABLE codecollections
                    ADD COLUMN visibility VARCHAR(20) NOT NULL DEFAULT 'public';
            END IF;
        END $$;
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_cc_visibility
            ON codecollections (visibility);
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_cc_visibility")
    op.execute("ALTER TABLE codecollections DROP COLUMN IF EXISTS visibility")

    op.execute("DROP INDEX IF EXISTS ix_ccv_collection_image_tag")
    op.execute(
        """
        ALTER TABLE codecollection_versions
            DROP COLUMN IF EXISTS image_built_at,
            DROP COLUMN IF EXISTS rt_revision,
            DROP COLUMN IF EXISTS commit_hash,
            DROP COLUMN IF EXISTS image_digest,
            DROP COLUMN IF EXISTS image_tag,
            DROP COLUMN IF EXISTS image_registry;
        """
    )
