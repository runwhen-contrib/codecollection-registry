"""
SQLAlchemy ORM models.

Schema is intentionally narrow — 5 tables that map 1:1 to the operational
concepts the service deals with:

  codecollections       one row per tracked CC
  image_refs            one row per discovered image (ccv-shaped)
  destinations          one row per configured destination
  mirror_targets        one row per (cc, dest, image_tag) we've mirrored
  mirror_jobs           one row per pending/running/completed copy job

`image_refs` matches the shape of `CodeCollectionVersion` in cc-registry-v2
so the catalog resolver logic ports cleanly. We don't reuse that model
class because we don't want a hard dependency on the registry's package.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Single declarative base for the whole service."""


# ---------------------------------------------------------------------------
# Catalog tables
# ---------------------------------------------------------------------------
class CodeCollection(Base):
    __tablename__ = "codecollections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(200), unique=True, nullable=False, index=True)
    name: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    git_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    image_registry: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    default_ref: Mapped[str] = mapped_column(String(200), nullable=False, default="main")
    visibility: Mapped[str] = mapped_column(String(20), nullable=False, default="public")
    source_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Which configured source produced this CC's image refs.",
    )

    last_synced: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_sync_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now(),
    )

    refs: Mapped[list["ImageRef"]] = relationship(
        back_populates="cc",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class ImageRef(Base):
    """One discovered image tag for a CodeCollection.

    Mirrors the columns of cc-registry-v2's `CodeCollectionVersion`. The
    `(cc_id, ref_name)` pair is the natural key — re-syncs upsert by it.
    """

    __tablename__ = "image_refs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cc_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("codecollections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ref_name: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        comment="Git ref this build represents (branch/tag).",
    )
    ref_type: Mapped[str] = mapped_column(String(20), nullable=False, default="branch")

    image_registry: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    image_tag: Mapped[str] = mapped_column(String(500), nullable=False)
    image_digest: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)

    commit_hash: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    rt_revision: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    image_built_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    is_latest: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_stable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_prerelease: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now(),
    )

    cc: Mapped[CodeCollection] = relationship(back_populates="refs")

    __table_args__ = (
        UniqueConstraint("cc_id", "ref_name", name="uq_image_refs_cc_ref"),
        Index("ix_image_refs_cc_active", "cc_id", "is_active"),
        Index("ix_image_refs_image_tag", "cc_id", "image_tag"),
    )


# ---------------------------------------------------------------------------
# Mirror tables
# ---------------------------------------------------------------------------
class Destination(Base):
    """One configured mirror destination.

    `config_json` snapshots the YAML so we can reason about what was
    asked for even if config.yaml later changes. Auth secrets are NEVER
    persisted — only the env-var names that point at them.
    """

    __tablename__ = "destinations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), unique=True, nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    config_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    last_synced: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_sync_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now(),
    )


class MirrorTarget(Base):
    """A successful mirror of one (cc, dest, source_tag) -> destination tag.

    This is the "I already have it, no need to push again" lookup that
    keeps the mirror engine idempotent. A row appears here only on
    successful push; failures live in mirror_jobs until they succeed or
    are explicitly abandoned.
    """

    __tablename__ = "mirror_targets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cc_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("codecollections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    destination_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("destinations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_image_tag: Mapped[str] = mapped_column(String(500), nullable=False)
    target_image_ref: Mapped[str] = mapped_column(
        String(1000),
        nullable=False,
        comment="Fully-qualified destination ref, e.g. acme.jfrog.io/runwhen-virtual/foo:tag.",
    )
    target_digest: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    mirrored_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "cc_id", "destination_id", "source_image_tag",
            name="uq_mirror_targets_cc_dest_tag",
        ),
    )


class MirrorJob(Base):
    """One unit of mirror work: copy `source_image_ref` -> `target_image_ref`.

    Lifecycle: pending -> running -> done | failed
    Failed jobs are retried on the next mirror poll up to `max_attempts`,
    then left in `failed` for an operator to inspect.
    """

    __tablename__ = "mirror_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cc_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("codecollections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    destination_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("destinations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_image_ref: Mapped[str] = mapped_column(String(1000), nullable=False)
    target_image_ref: Mapped[str] = mapped_column(String(1000), nullable=False)

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        index=True,
        comment="pending | running | done | failed",
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    log_text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Tail of stdout/stderr from the last copy attempt.",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(),
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_mirror_jobs_status_created", "status", "created_at"),
    )
