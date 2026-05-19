"""
Destination registry / loader.

Built-ins are loaded eagerly. Third-party destinations register via
`CC_CATALOG_EXTRA_DESTINATIONS` (colon-separated list of import paths,
each module exposing a top-level `DESTINATION` of type `ImageDestination`).

This mirrors the pattern in `app.sources.registry`. The same plugin
contract works for sources and destinations because we deliberately
kept the loader simple.
"""
from __future__ import annotations

import importlib
import logging
import os
from typing import Dict, Optional

from app.destinations.base import ImageDestination
from app.destinations.jfrog import JFrogDestination

logger = logging.getLogger(__name__)


DESTINATION_REGISTRY: Dict[str, ImageDestination] = {
    JFrogDestination.name: JFrogDestination(),
}


def _load_extra_destinations() -> None:
    paths = os.environ.get("CC_CATALOG_EXTRA_DESTINATIONS", "").strip()
    if not paths:
        return
    for module_path in paths.split(":"):
        module_path = module_path.strip()
        if not module_path:
            continue
        try:
            mod = importlib.import_module(module_path)
            dest = getattr(mod, "DESTINATION", None)
            if not isinstance(dest, ImageDestination):
                logger.warning(
                    "extra destination %s did not expose a DESTINATION: ImageDestination",
                    module_path,
                )
                continue
            DESTINATION_REGISTRY[dest.name] = dest
            logger.info("registered extra image destination: %s", dest.name)
        except Exception:
            logger.exception("failed to load extra image destination %s", module_path)


_load_extra_destinations()


def get_destination(name: str) -> Optional[ImageDestination]:
    return DESTINATION_REGISTRY.get(name)
