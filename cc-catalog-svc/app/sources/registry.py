"""
Source registry / loader.

Built-ins are loaded eagerly. Third-party / customer sources can be
registered via the `CC_CATALOG_EXTRA_SOURCES` env var (colon-separated
list of import paths; each module must expose a top-level `SOURCE` of
type `ImageSource`).

This matches the cc-registry-v2 plugin contract exactly so a custom
source written for the registry plugs into this service unchanged —
just point its env var here.
"""
from __future__ import annotations

import importlib
import logging
import os
from typing import Dict, Optional

from app.sources.base import ImageSource
from app.sources.oci import OCISource
from app.sources.static import StaticSource
from app.sources.upstream import UpstreamCatalogSource

logger = logging.getLogger(__name__)


SOURCE_REGISTRY: Dict[str, ImageSource] = {
    OCISource.name: OCISource(),
    StaticSource.name: StaticSource(),
    UpstreamCatalogSource.name: UpstreamCatalogSource(),
}


def _load_extra_sources() -> None:
    paths = os.environ.get("CC_CATALOG_EXTRA_SOURCES", "").strip()
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
        except Exception:
            logger.exception("failed to load extra image source %s", module_path)


_load_extra_sources()


def get_source(name: str) -> Optional[ImageSource]:
    return SOURCE_REGISTRY.get(name)


def configure_source_from_options(name: str, options: dict) -> Optional[ImageSource]:
    """Some sources have per-source-instance config (e.g. upstream's
    default URL). Return an instance with that config baked in if the
    source supports it; otherwise return the registry's shared instance.
    """
    base = SOURCE_REGISTRY.get(name)
    if base is None:
        return None
    if name == UpstreamCatalogSource.name:
        return UpstreamCatalogSource(
            default_upstream_url=options.get("upstream_url"),
            timeout=float(options.get("timeout", 15.0)),
        )
    return base
