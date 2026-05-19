"""
Static JSON image source.

Useful for:
  - Air-gapped envs where the build system drops a JSON file somewhere
    the service can read.
  - Tests / fixtures.
  - Pinning a CC to a known-good set of refs without polling.

Expected file shape (identical to cc-registry-v2's StaticSource):

    {
      "default_ref": "main",
      "stable_ref":  "v1.2.0",
      "refs": [
        {
          "ref": "main",
          "ref_type": "branch",
          "commit": "c1a2b3d...",
          "rt_revision": "e4f5a6b...",
          "image_tag": "main-c1a2b3d-e4f5a6b",
          "image_digest": "sha256:...",
          "built_at": "2026-05-11T20:00:00Z"
        }
      ]
    }
"""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Optional

from app.sources.base import DiscoveredImageRef, ImageSource

logger = logging.getLogger(__name__)


class StaticSource(ImageSource):
    name = "static"

    def discover_refs(self, cc: dict) -> list[DiscoveredImageRef]:
        path = cc.get("static_path")
        if not path or not os.path.exists(path):
            logger.warning(
                "static source skipping %s: static_path missing (%r)",
                cc.get("slug"),
                path,
            )
            return []

        with open(path, "r") as f:
            payload = json.load(f)

        default_ref = payload.get("default_ref", "main")
        stable_ref = payload.get("stable_ref")

        refs: list[DiscoveredImageRef] = []
        for entry in payload.get("refs", []):
            built_at_raw = entry.get("built_at")
            built_at: Optional[datetime] = None
            if built_at_raw:
                try:
                    built_at = datetime.fromisoformat(
                        built_at_raw.replace("Z", "+00:00")
                    )
                except ValueError:
                    built_at = None
            refs.append(
                DiscoveredImageRef(
                    ref=entry["ref"],
                    ref_type=entry.get("ref_type", "branch"),
                    commit=entry["commit"],
                    rt_revision=entry["rt_revision"],
                    image_tag=entry["image_tag"],
                    image_digest=entry.get("image_digest"),
                    built_at=built_at,
                    extra={"default_ref": default_ref, "stable_ref": stable_ref},
                )
            )
        return refs

    def resolve_latest(
        self, cc: dict, refs: list[DiscoveredImageRef]
    ) -> Optional[str]:
        if not refs:
            return None
        default_ref = refs[0].extra.get("default_ref", "main")
        matches = [r for r in refs if r.ref == default_ref]
        return matches[-1].image_tag if matches else None

    def resolve_stable(
        self, cc: dict, refs: list[DiscoveredImageRef]
    ) -> Optional[str]:
        if not refs:
            return None
        stable_ref = refs[0].extra.get("stable_ref")
        if stable_ref:
            for r in refs:
                if r.ref == stable_ref:
                    return r.image_tag
        return self.resolve_latest(cc, refs)
