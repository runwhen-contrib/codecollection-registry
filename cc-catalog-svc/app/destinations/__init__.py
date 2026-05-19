"""
Destination plugin system.

Where `app.sources` answers "what images exist for this CC?",
`app.destinations` answers "where should we publish a copy of those
images, and how do we get them there?".

The contract is small on purpose. Anything beyond it (signing,
attestation, scan hooks) is added on top of `push()` by individual
plugins so the base stays portable.

Built-in destinations:

  - jfrog   JFrog Artifactory Docker repositories

Add a new destination by writing a class that satisfies `ImageDestination`
and registering it in `DESTINATION_REGISTRY` (see `registry.py`), or by
shipping a module that exposes a top-level `DESTINATION` and setting
`CC_CATALOG_EXTRA_DESTINATIONS=mycorp.dst_ecr`.
"""
from app.destinations.base import (
    ImageDestination,
    MirrorResult,
)
from app.destinations.registry import DESTINATION_REGISTRY, get_destination

__all__ = [
    "ImageDestination",
    "MirrorResult",
    "DESTINATION_REGISTRY",
    "get_destination",
]
