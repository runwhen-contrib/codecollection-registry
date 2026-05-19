"""
Source registry / loader.

Built-in sources live in this package and are loaded eagerly.

Third-party / customer-specific sources can be registered via the
`CC_REGISTRY_EXTRA_SOURCES` environment variable, a colon-separated list of
import paths to modules that expose a top-level `SOURCE` instance. This
lets self-hosted operators plug in custom discovery logic (e.g. an internal
Harbor with non-standard tag schemas) without forking the catalog.

Example:

    CC_REGISTRY_EXTRA_SOURCES=mycorp.harbor:mycorp.gerrit
"""
from __future__ import annotations

import importlib
import logging
import os
from typing import Dict

from .base import ImageSource
from .oci import OCISource
from .static import StaticSource

logger = logging.getLogger(__name__)

SOURCE_REGISTRY: Dict[str, ImageSource] = {
    OCISource.name: OCISource(),
    StaticSource.name: StaticSource(),
}


def _load_extra_sources() -> None:
    paths = os.environ.get("CC_REGISTRY_EXTRA_SOURCES", "").strip()
    if not paths:
        return
    for module_path in paths.split(":"):
        module_path = module_path.strip()
        if not module_path:
            continue
        try:
            mod = importlib.import_module(module_path)
            source = getattr(mod, "SOURCE", None)
            if not isinstance(source, ImageSource):
                logger.warning(
                    "extra source %s did not expose a SOURCE: ImageSource",
                    module_path,
                )
                continue
            SOURCE_REGISTRY[source.name] = source
            logger.info("registered extra image source: %s", source.name)
        except Exception:  # pragma: no cover - defensive logging
            logger.exception("failed to load extra image source %s", module_path)


_load_extra_sources()


def get_source(name: str) -> ImageSource | None:
    return SOURCE_REGISTRY.get(name)
