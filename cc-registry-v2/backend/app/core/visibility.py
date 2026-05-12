"""
Visibility filter helpers.

A CodeCollection's `visibility` flag controls whether it appears on
public-audience surfaces:

  - 'public'  – default. Shown on the registry website, MCP, AI search, etc.
  - 'hidden'  – tracked for PAPI consumption but excluded from public lists.

This is a UX/discovery toggle, NOT a security boundary. Image-level
access control still lives in the OCI registry.

Centralizing the filter here keeps the rule consistent across endpoints —
if we ever add a third visibility tier (e.g. 'archived'), we change one
place rather than auditing every router.
"""
from __future__ import annotations

from sqlalchemy.orm import Query

from app.models import CodeCollection

PUBLIC_VISIBILITY = "public"
HIDDEN_VISIBILITY = "hidden"


def public_only(query: Query) -> Query:
    """
    Apply `visibility = 'public'` to a SQLAlchemy query that selects from
    or joins to `codecollections`. Use this on every public-audience
    endpoint (anything PAPI / corestate would NOT call).
    """
    return query.filter(CodeCollection.visibility == PUBLIC_VISIBILITY)


def is_public(cc: CodeCollection) -> bool:
    """Predicate version for code paths that already have a loaded row."""
    return (cc.visibility or PUBLIC_VISIBILITY) == PUBLIC_VISIBILITY
