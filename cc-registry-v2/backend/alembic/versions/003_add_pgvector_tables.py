"""add pgvector extension and vector search tables

Revision ID: 003
Revises: 002
Create Date: 2026-02-10

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Enable pgvector and create vector search tables.
    Replaces the embedded ChromaDB vector store in the MCP server.
    """
    # Enable pgvector extension (requires superuser or CREATE privilege)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    op.execute("""
        CREATE TABLE IF NOT EXISTS vector_codebundles (
            id TEXT PRIMARY KEY,
            embedding vector(1536),
            document TEXT,
            metadata JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS idx_vector_codebundles_embedding
            ON vector_codebundles USING hnsw (embedding vector_cosine_ops);
        CREATE INDEX IF NOT EXISTS idx_vector_codebundles_platform
            ON vector_codebundles USING btree ((metadata->>'platform'));
        CREATE INDEX IF NOT EXISTS idx_vector_codebundles_collection
            ON vector_codebundles USING btree ((metadata->>'collection_slug'));

        CREATE TABLE IF NOT EXISTS vector_codecollections (
            id TEXT PRIMARY KEY,
            embedding vector(1536),
            document TEXT,
            metadata JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS idx_vector_codecollections_embedding
            ON vector_codecollections USING hnsw (embedding vector_cosine_ops);

        CREATE TABLE IF NOT EXISTS vector_libraries (
            id TEXT PRIMARY KEY,
            embedding vector(1536),
            document TEXT,
            metadata JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS idx_vector_libraries_embedding
            ON vector_libraries USING hnsw (embedding vector_cosine_ops);
        CREATE INDEX IF NOT EXISTS idx_vector_libraries_category
            ON vector_libraries USING btree ((metadata->>'category'));

        CREATE TABLE IF NOT EXISTS vector_documentation (
            id TEXT PRIMARY KEY,
            embedding vector(1536),
            document TEXT,
            metadata JSONB NOT NULL DEFAULT '{}',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS idx_vector_documentation_embedding
            ON vector_documentation USING hnsw (embedding vector_cosine_ops);
        CREATE INDEX IF NOT EXISTS idx_vector_documentation_category
            ON vector_documentation USING btree ((metadata->>'category'));
    """)


def downgrade() -> None:
    """
    Drop vector search tables. Extension is left in place.
    """
    op.execute("DROP TABLE IF EXISTS vector_documentation;")
    op.execute("DROP TABLE IF EXISTS vector_libraries;")
    op.execute("DROP TABLE IF EXISTS vector_codecollections;")
    op.execute("DROP TABLE IF EXISTS vector_codebundles;")
