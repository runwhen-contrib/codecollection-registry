# PAPI integration

PAPI consumes the catalog over plain HTTP — no auth, no SDK, no
generated client. This doc covers the integration surface and the one
new query param (`?destination=`) PAPI uses to consume mirrored images.

---

## The unchanged path (public envs)

In public environments PAPI calls cc-catalog-svc the same way it calls
`cc-registry-v2`'s catalog. Same paths, same response shapes:

```bash
# List of every CC PAPI may need to resolve
GET /api/v1/catalog/codecollections

# Per-CC detail + all refs
GET /api/v1/catalog/codecollections/{slug}

# Resolve a pointer
GET /api/v1/catalog/codecollections/{slug}/resolve?pointer=latest
GET /api/v1/catalog/codecollections/{slug}/resolve?pointer=stable

# Resolve a specific ref
GET /api/v1/catalog/codecollections/{slug}/resolve?ref=v1.2.0
```

Response:

```json
{
  "slug": "rw-cli-codecollection",
  "requested": "latest",
  "image_tag": "main-c1a2b3d-e4f5a6b",
  "image_registry": "ghcr.io/runwhen-contrib/rw-cli-codecollection",
  "image_digest": null,
  "commit_hash": "c1a2b3def123",
  "rt_revision": "e4f5a6b789"
}
```

PAPI composes the pull ref as `{image_registry}:{image_tag}` (or
`{image_registry}@{image_digest}` once digest pinning lands).

To migrate PAPI from `cc-registry-v2` to cc-catalog-svc, change the
base URL. That's it.

---

## The new path (air-gapped / customer-private envs)

In environments where workspaces pull from a customer registry (JFrog
Artifactory in v1) instead of GHCR, PAPI passes the destination name:

```bash
GET /api/v1/catalog/codecollections/rw-cli-codecollection/resolve?pointer=latest&destination=acme-jfrog
```

Response — adds three fields, leaves the source ref intact:

```json
{
  "slug": "rw-cli-codecollection",
  "requested": "latest",
  "image_tag": "main-c1a2b3d-e4f5a6b",
  "image_registry": "ghcr.io/runwhen-contrib/rw-cli-codecollection",
  "image_digest": null,
  "commit_hash": "c1a2b3def123",
  "rt_revision": "e4f5a6b789",
  "destination": "acme-jfrog",
  "target_image_ref": "acme.jfrog.io/runwhen-virtual/codecollections/rw-cli-codecollection:main-c1a2b3d-e4f5a6b",
  "target_digest": "sha256:..."
}
```

PAPI should prefer `target_image_ref` when set; if `destination` is
non-null but `target_image_ref` is null, the mirror hasn't run yet for
this ref — PAPI can fall back to the source `image_registry`/`image_tag`
or surface a soft error depending on the env's policy.

---

## Suggested PAPI-side client shape

```python
# backend-services-v2/papi/clients/cc_catalog.py
from typing import Optional
import httpx

class CatalogClient:
    def __init__(self, base_url: str, destination: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        # destination is per-environment: SaaS envs leave it None, air-gap
        # envs set it (e.g. "acme-jfrog"). Single source of truth at config.
        self.destination = destination

    async def resolve(self, slug: str, *, pointer: Optional[str] = None, ref: Optional[str] = None) -> dict:
        params = {}
        if pointer:
            params["pointer"] = pointer
        elif ref:
            params["ref"] = ref
        if self.destination:
            params["destination"] = self.destination
        async with httpx.AsyncClient(timeout=10.0) as c:
            r = await c.get(
                f"{self.base_url}/api/v1/catalog/codecollections/{slug}/resolve",
                params=params,
            )
            r.raise_for_status()
            return r.json()

    @staticmethod
    def pull_ref(response: dict) -> str:
        """Pick the right ref out of a resolve response.

        Returns target_image_ref when a destination was requested AND the
        mirror has caught up; otherwise the source ref.
        """
        target = response.get("target_image_ref")
        if target:
            return target
        return f"{response['image_registry']}:{response['image_tag']}"
```

Env-config side:

```python
class Settings(BaseSettings):
    catalog_base_url: str = "https://catalog.runwhen.com"
    catalog_destination: Optional[str] = None  # set in air-gap envs
```

---

## Feature flag / rollout

Use the same `CC_SOURCE=catalog|legacy` flag the
[radically-simple-design doc](../../platform-robot-runtime/docs/migration/radically-simple-design.md)
already calls for; `catalog` mode points at cc-catalog-svc or
cc-registry-v2 interchangeably (the URL is the only thing that
differs).

---

## Failure modes the client should handle

| Symptom | Likely cause | PAPI response |
|---|---|---|
| 404 on `/codecollections/{slug}` | CC not in catalog config yet | Surface to operator; do not retry tightly |
| 404 on `/refs/{ref}` | Ref not built yet, or filtered out by `image_source` config | Fall back to pointer-based resolve if the workspace will accept `latest`/`stable` |
| 400 from `/resolve` | Both `pointer` and `ref` supplied, or neither | Bug in the PAPI caller; fix and re-deploy |
| `target_image_ref: null` with `destination` set | Mirror hasn't run for this ref yet | Either retry later or fall back to source ref depending on the env's policy |
| Connection timeout / 5xx | Catalog svc unhealthy | PAPI should serve stale cached resolve results if available; the catalog DB is the catalog's own source of truth and recovers without intervention |
