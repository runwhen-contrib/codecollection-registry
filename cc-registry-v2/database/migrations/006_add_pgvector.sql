-- Migration 006: Add pgvector extension and vector search tables
-- These tables replace the embedded ChromaDB vector store in the MCP server.
-- Now both the MCP server and backend share the same PostgreSQL database.

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- =========================================================================
-- Codebundle embeddings
-- =========================================================================
CREATE TABLE IF NOT EXISTS vector_codebundles (
    id TEXT PRIMARY KEY,
    embedding vector(1536),  -- Azure OpenAI text-embedding-3-small
    document TEXT,           -- Searchable text used for embedding
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

-- =========================================================================
-- Codecollection embeddings
-- =========================================================================
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

-- =========================================================================
-- Library embeddings
-- =========================================================================
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

-- =========================================================================
-- Documentation embeddings
-- =========================================================================
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

-- Log migration
SELECT 'pgvector migration complete - 4 vector tables created' AS status;
