"""
Configuration: env vars (Pydantic Settings) + a single YAML config file.

Why two layers?
  - Operational knobs that change between environments (DB URL, log level,
    admin token, listen port) live in env vars so deployments can rotate
    them without rebuilding configmaps.
  - The substantive config — which sources to poll, which destinations to
    mirror to, what to mirror — lives in `config.yaml` because it is
    structured, list-shaped, and benefits from PR review.

Env vars use the `CC_CATALOG_` prefix to avoid collisions with the
existing `cc-registry-v2` env vars when both services run in the same
namespace.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Any, Literal, Optional

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Env-driven settings (process-level, change per deployment)
# ---------------------------------------------------------------------------
class Settings(BaseSettings):
    """Process-level settings sourced from env vars.

    Keep this surface tight — anything list-shaped or that benefits from
    review history belongs in `config.yaml`, not here.
    """

    model_config = SettingsConfigDict(
        env_prefix="CC_CATALOG_",
        case_sensitive=False,
        env_file=".env",
        extra="ignore",
    )

    # Where to find the YAML config. Resolved relative to CWD if not absolute.
    config_file: str = "config.yaml"

    # SQLAlchemy URL. Defaults to a local SQLite file so the service runs
    # out-of-the-box with zero infra. Swap to postgres://... in HA setups.
    db_url: str = "sqlite:///./data/catalog.db"

    # HTTP listen surface.
    host: str = "0.0.0.0"
    port: int = 8080
    log_level: str = "INFO"

    # Admin token for the small handful of POST endpoints (manual sync
    # triggers). Empty string = admin endpoints disabled (read-only mode).
    admin_token: str = ""

    # The catalog API is unauthenticated by design (matches the existing
    # registry's PAPI contract). If you front it with an ingress that adds
    # auth, leave this as-is and let the ingress handle it.

    @field_validator("log_level")
    @classmethod
    def _upper_log_level(cls, v: str) -> str:
        return (v or "INFO").upper()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Module-level cached accessor. Tests patch via `get_settings.cache_clear()`."""
    return Settings()


# ---------------------------------------------------------------------------
# YAML config (codecollections to track, destinations to mirror to)
# ---------------------------------------------------------------------------
class CodeCollectionConfig(BaseModel):
    """A single CC to track. Subset of fields from the existing
    `codecollections.yaml` schema — we only need what the catalog/mirror
    uses; descriptive metadata (owner, icon, description) is irrelevant
    here and is left to the website's registry instead.
    """

    slug: str = Field(..., description="Stable identifier; matches the registry.")
    name: Optional[str] = None
    git_url: Optional[str] = None
    image_registry: Optional[str] = Field(
        None,
        description="OCI repo path for the 'oci' source, e.g. ghcr.io/runwhen-contrib/foo.",
    )
    default_ref: str = Field("main", description="Ref whose newest build is 'latest'.")
    visibility: Literal["public", "hidden"] = "public"
    static_path: Optional[str] = Field(
        None,
        description="JSON file path for the 'static' source.",
    )

    @field_validator("slug")
    @classmethod
    def _slug_nonempty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("slug must be a non-empty string")
        return v.strip()


class SourceAuth(BaseModel):
    """Auth for an OCI-style source.

    Set EITHER ``token_env`` OR ``user_env``+``pass_env`` — not both.
    Unset = anonymous; the OCI source falls back to the public-GHCR
    bearer-realm dance so this still works against public registries.

    Env var names (not values) live here on purpose: the YAML stays
    safe to commit, and secrets are injected via the deployment's
    Secret/env-file at runtime.
    """

    token_env: Optional[str] = Field(
        None,
        description="Env var name holding a Bearer access token "
        "(JFrog access token, GHCR PAT, etc.).",
    )
    user_env: Optional[str] = Field(
        None,
        description="Env var name holding the HTTP Basic username.",
    )
    pass_env: Optional[str] = Field(
        None,
        description="Env var name holding the HTTP Basic password "
        "(or an access token used as a password).",
    )

    @model_validator(mode="after")
    def _exactly_one_or_none(self) -> "SourceAuth":
        token = bool(self.token_env)
        basic_any = bool(self.user_env) or bool(self.pass_env)
        basic_both = bool(self.user_env) and bool(self.pass_env)
        if token and basic_any:
            raise ValueError("source.auth: set EITHER token_env OR user_env+pass_env, not both")
        if basic_any and not basic_both:
            raise ValueError("source.auth: user_env and pass_env must be set together")
        return self


class SourceConfig(BaseModel):
    """One configured source. The same source `type` can be instantiated
    multiple times with different CC lists (e.g. one `oci` block for GHCR
    and another for a customer's internal Artifactory).
    """

    name: str = Field(..., description="Unique identifier for this source instance.")
    type: str = Field(..., description="Plugin type: 'oci' | 'static' | 'upstream' | custom.")
    codecollections: list[CodeCollectionConfig] = Field(default_factory=list)

    # One auth block per source — every CC under this source uses these
    # credentials. CCs needing different creds belong in a separate source.
    auth: SourceAuth = Field(default_factory=SourceAuth)

    # Source-specific keys. Kept open-ended so plugins can read whatever
    # they need without us having to grow this schema for every new source.
    options: dict[str, Any] = Field(default_factory=dict)

    @field_validator("auth", mode="before")
    @classmethod
    def _none_to_empty_auth(cls, v):
        # `auth:` (bare key in YAML) parses to None; treat as defaults.
        if v is None:
            return {}
        return v


class JFrogAuth(BaseModel):
    """JFrog Artifactory auth.

    Set EXACTLY ONE of:

    * ``token_env`` — Bearer access token
    * ``user_env`` + ``pass_env`` — HTTP Basic (LDAP user, or user + access token)
    * ``docker_config_env`` — path to a pre-existing Docker config.json
      (handy for reusing an existing k8s pull secret verbatim)

    If none are set, ``crane`` will attempt anonymous auth — only useful
    for repos that allow anonymous push, which is rare in practice.
    """

    token_env: Optional[str] = Field(
        None,
        description="Env var name holding a JFrog access token (Bearer auth).",
    )
    user_env: Optional[str] = Field(
        None,
        description="Env var name holding the HTTP Basic username.",
    )
    pass_env: Optional[str] = Field(
        None,
        description="Env var name holding the HTTP Basic password "
        "(or an access token used as a password).",
    )
    docker_config_env: Optional[str] = Field(
        None,
        description=(
            "Env var name holding the path to a Docker config.json. "
            "When set, the mirror engine passes it to `crane` via DOCKER_CONFIG."
        ),
    )

    @model_validator(mode="after")
    def _at_most_one_mode(self) -> "JFrogAuth":
        token = bool(self.token_env)
        basic_any = bool(self.user_env) or bool(self.pass_env)
        basic_both = bool(self.user_env) and bool(self.pass_env)
        docker = bool(self.docker_config_env)

        modes = int(token) + int(basic_any) + int(docker)
        if modes > 1:
            raise ValueError(
                "destination.auth: set EXACTLY ONE of token_env, "
                "user_env+pass_env, or docker_config_env"
            )
        if basic_any and not basic_both:
            raise ValueError("destination.auth: user_env and pass_env must be set together")
        return self


class MirrorFilter(BaseModel):
    """Which refs of each CC to mirror. Reasonable defaults keep noisy
    PR/preview tags out of the destination while still covering both
    pointers and semver releases.
    """

    codecollections: list[str] = Field(
        default_factory=lambda: ["*"],
        description="CC slugs to mirror, or ['*'] for all known CCs.",
    )
    include_pointers: list[Literal["latest", "stable"]] = Field(
        default_factory=lambda: ["latest", "stable"],
        description="Always mirror whatever ref these pointers currently resolve to.",
    )
    include_branches: list[str] = Field(
        default_factory=lambda: ["main"],
        description="Branch refs to mirror. Empty list = no branches.",
    )
    include_semver_tags: bool = True
    include_pr_refs: bool = False


class DestinationConfig(BaseModel):
    """One configured destination. Currently supported types: 'jfrog'.
    Adding 'ecr' / 'gar' / 'harbor' is a new plugin + a literal here.
    """

    name: str
    type: Literal["jfrog"] = "jfrog"
    base_url: str = Field(..., description="e.g. https://acme.jfrog.io")
    repo_key: str = Field(..., description="Artifactory repository key.")
    path_prefix: Optional[str] = Field(
        None,
        description="Optional path under the repo, e.g. 'codecollections'.",
    )
    auth: JFrogAuth = Field(default_factory=JFrogAuth)
    enable_xray_scan: bool = Field(
        False,
        description="If true, kick a JFrog Xray scan after each successful push.",
    )
    mirror: MirrorFilter = Field(default_factory=MirrorFilter)


class SchedulerConfig(BaseModel):
    catalog_poll_minutes: int = Field(5, ge=1, le=1440)
    mirror_poll_minutes: int = Field(5, ge=1, le=1440)
    mirror_workers: int = Field(2, ge=1, le=32)
    per_job_timeout_seconds: int = Field(600, ge=10, le=3600)
    git_sync_minutes: int = Field(
        60,
        ge=1,
        le=1440,
        description="How often to fetch upstream git repos into local mirrors.",
    )


class GitAuth(BaseModel):
    """Auth for fetching upstream git repos (GitHub PAT, etc.)."""

    token_env: Optional[str] = Field(
        None,
        description="Env var holding a Bearer token (GitHub PAT, etc.).",
    )
    user_env: Optional[str] = Field(
        None,
        description="Env var holding HTTP Basic username.",
    )
    pass_env: Optional[str] = Field(
        None,
        description="Env var holding HTTP Basic password or token-as-password.",
    )

    @model_validator(mode="after")
    def _exactly_one_or_none(self) -> "GitAuth":
        token = bool(self.token_env)
        basic_any = bool(self.user_env) or bool(self.pass_env)
        basic_both = bool(self.user_env) and bool(self.pass_env)
        if token and basic_any:
            raise ValueError("git.auth: set EITHER token_env OR user_env+pass_env, not both")
        if basic_any and not basic_both:
            raise ValueError("git.auth: user_env and pass_env must be set together")
        return self


class GitServiceConfig(BaseModel):
    """Local git mirror + smart HTTP service for air-gapped deployments.

    When enabled, cc-catalog-svc maintains bare mirror clones of each
    configured CodeCollection ``git_url`` and serves them read-only at
    ``mount_path``. Catalog API responses rewrite ``git_url`` to
    ``public_base_url/<slug>.git`` once a mirror exists.
    """

    enabled: bool = False
    data_dir: str = Field(
        "/data/git",
        description="Directory for bare mirror repos (<slug>.git).",
    )
    mount_path: str = Field(
        "/git",
        description="HTTP path prefix for git smart HTTP (clone URL path).",
    )
    public_base_url: Optional[str] = Field(
        None,
        description=(
            "External base URL for clone commands, e.g. "
            "https://cc-catalog.example.com/git. Omit to keep upstream git_url "
            "in catalog responses even when mirrors exist."
        ),
    )
    auth: GitAuth = Field(default_factory=GitAuth)
    codecollections: list[str] = Field(
        default_factory=list,
        description=("Slugs to mirror. Empty = every CC with a git_url from sources."),
    )
    clone_timeout_seconds: int = Field(900, ge=30, le=7200)
    fetch_timeout_seconds: int = Field(600, ge=30, le=3600)

    @field_validator("auth", mode="before")
    @classmethod
    def _none_to_empty_auth(cls, v):
        if v is None:
            return {}
        return v


class CatalogAPIConfig(BaseModel):
    prefix: str = "/api/v1/catalog"


class StorageConfig(BaseModel):
    """Storage-related YAML overrides. Most deployments set
    `CC_CATALOG_DB_URL` in env instead; this exists for documentation
    parity with the registry's `schedules.yaml` pattern.
    """

    url: Optional[str] = None


class AppConfig(BaseModel):
    """Top-level YAML schema. Loaded once at startup and validated; any
    schema error fails the service fast rather than silently running with
    a half-formed config.

    Sub-blocks tolerate explicit `null` (a bare `key:` in YAML parses to
    None) by falling back to their default-factory instances. This keeps
    minimal configs like `storage:` valid.
    """

    storage: StorageConfig = Field(default_factory=StorageConfig)
    catalog_api: CatalogAPIConfig = Field(default_factory=CatalogAPIConfig)
    scheduler: SchedulerConfig = Field(default_factory=SchedulerConfig)
    git: GitServiceConfig = Field(default_factory=GitServiceConfig)
    sources: list[SourceConfig] = Field(default_factory=list)
    destinations: list[DestinationConfig] = Field(default_factory=list)

    @field_validator("storage", "catalog_api", "scheduler", "git", mode="before")
    @classmethod
    def _none_to_default(cls, v, info):
        # `key:` in YAML => None; treat as "use defaults".
        if v is None:
            return {}
        return v

    @field_validator("sources", "destinations", mode="before")
    @classmethod
    def _none_to_empty_list(cls, v, info):
        if v is None:
            return []
        return v

    # ----- convenience views -----
    def all_codecollections(self) -> dict[str, CodeCollectionConfig]:
        """Flatten every source's CC list into a slug -> CC dict.

        Slugs MUST be globally unique across sources because they are the
        primary key in the catalog DB. We raise loudly on duplicates so
        the operator doesn't silently end up with the wrong source winning
        the race.
        """
        seen: dict[str, CodeCollectionConfig] = {}
        collisions: list[str] = []
        for src in self.sources:
            for cc in src.codecollections:
                if cc.slug in seen:
                    collisions.append(cc.slug)
                else:
                    seen[cc.slug] = cc
        if collisions:
            raise ValueError(
                f"Duplicate CodeCollection slug(s) across sources: {sorted(set(collisions))!r}. "
                "Each slug must appear under exactly one source."
            )
        return seen

    def destination_by_name(self, name: str) -> Optional[DestinationConfig]:
        return next((d for d in self.destinations if d.name == name), None)


_CONFIG_CACHE: Optional[AppConfig] = None


def load_config(path: Optional[str] = None) -> AppConfig:
    """Read and validate the YAML config.

    Resolution order:
      1. Explicit `path` arg (used by tests).
      2. `CC_CATALOG_CONFIG_FILE` env var.
      3. `./config.yaml` relative to CWD.

    An absent file is *not* an error — we return an empty AppConfig so the
    service can start, expose `/healthz` and `/readyz`, and serve an empty
    catalog. This lets operators bring up the container first and then
    mount config in a second step (matches the cc-registry-v2 ConfigMap
    pattern).
    """
    global _CONFIG_CACHE
    if path is None:
        path = get_settings().config_file
    if not os.path.isabs(path):
        path = os.path.abspath(path)

    if not os.path.exists(path):
        logger.warning(
            "config file %s not found; running with empty config "
            "(catalog will be empty until config is mounted)",
            path,
        )
        _CONFIG_CACHE = AppConfig()
        return _CONFIG_CACHE

    with open(path, "r") as f:
        raw = yaml.safe_load(f) or {}

    cfg = AppConfig.model_validate(raw)
    logger.info(
        "loaded config from %s: %d source(s), %d destination(s), %d CC(s) tracked",
        path,
        len(cfg.sources),
        len(cfg.destinations),
        sum(len(s.codecollections) for s in cfg.sources),
    )
    _CONFIG_CACHE = cfg
    return cfg


def get_config() -> AppConfig:
    """Return the last-loaded config. Always call `load_config()` first
    (the FastAPI lifespan does this at startup)."""
    if _CONFIG_CACHE is None:
        return load_config()
    return _CONFIG_CACHE


def reload_config() -> AppConfig:
    """Re-read the YAML file from disk. Wired to a `/admin/reload` route."""
    global _CONFIG_CACHE
    _CONFIG_CACHE = None
    return load_config()
