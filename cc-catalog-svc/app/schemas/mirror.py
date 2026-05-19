"""Mirror API response models."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class DestinationSummary(BaseModel):
    name: str
    type: str
    enabled: bool = True
    base_url: Optional[str] = None
    repo_key: Optional[str] = None
    path_prefix: Optional[str] = None
    enable_xray_scan: bool = False
    last_synced: Optional[datetime] = None
    last_sync_error: Optional[str] = None
    tracked_codecollections: list[str] = Field(default_factory=list)
    mirrored_tag_count: int = 0


class MirrorJobView(BaseModel):
    id: int
    cc_slug: str
    destination: str
    source_image_ref: str
    target_image_ref: str
    status: str
    attempts: int
    max_attempts: int
    last_error: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class MirrorJobDetail(MirrorJobView):
    log_text: Optional[str] = None


class MirrorJobsResponse(BaseModel):
    total: int
    items: list[MirrorJobView]


class MirrorTriggerResponse(BaseModel):
    """Returned when an admin triggers a sync. The work is enqueued in
    `mirror_jobs`; this response just confirms the count."""

    destination: str
    codecollection_slug: Optional[str] = None
    jobs_enqueued: int
    refs_already_mirrored: int
    detail: str
