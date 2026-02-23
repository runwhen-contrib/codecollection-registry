"""
SQLAlchemy models for pgvector tables.

Maps to the tables created by database/migrations/006_add_pgvector.sql.
"""
from sqlalchemy import Column, String, Text, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from pgvector.sqlalchemy import Vector

from app.core.database import Base

EMBEDDING_DIMENSIONS = 1536


class VectorCodebundle(Base):
    __tablename__ = "vector_codebundles"

    id = Column(String, primary_key=True)
    embedding = Column(Vector(EMBEDDING_DIMENSIONS))
    document = Column(Text)
    metadata_ = Column("metadata", JSONB, nullable=False, server_default="{}")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class VectorCodecollection(Base):
    __tablename__ = "vector_codecollections"

    id = Column(String, primary_key=True)
    embedding = Column(Vector(EMBEDDING_DIMENSIONS))
    document = Column(Text)
    metadata_ = Column("metadata", JSONB, nullable=False, server_default="{}")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class VectorLibrary(Base):
    __tablename__ = "vector_libraries"

    id = Column(String, primary_key=True)
    embedding = Column(Vector(EMBEDDING_DIMENSIONS))
    document = Column(Text)
    metadata_ = Column("metadata", JSONB, nullable=False, server_default="{}")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class VectorDocumentation(Base):
    __tablename__ = "vector_documentation"

    id = Column(String, primary_key=True)
    embedding = Column(Vector(EMBEDDING_DIMENSIONS))
    document = Column(Text)
    metadata_ = Column("metadata", JSONB, nullable=False, server_default="{}")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
