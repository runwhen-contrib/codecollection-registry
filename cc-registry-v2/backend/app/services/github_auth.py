"""
GitHub App authentication service.

Generates short-lived installation access tokens from a GitHub App's
private key.  Falls back to the static GITHUB_TOKEN PAT when App
credentials are not configured.
"""
import base64
import logging
import threading
import time
from typing import Optional

import httpx
from jose import jwt as jose_jwt

from app.core.config import settings

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"


class GitHubAuth:
    """Manages GitHub authentication via App credentials or PAT fallback."""

    def __init__(self) -> None:
        self._private_key: Optional[str] = None
        self._app_id: Optional[str] = None
        self._installation_id: Optional[int] = settings.GITHUB_APP_INSTALLATION_ID
        self._token: Optional[str] = None
        self._token_expires_at: float = 0
        self._lock = threading.Lock()

        raw_key = settings.GITHUB_APP_PRIVATE_KEY
        has_app_id = bool(settings.GITHUB_APP_ID)
        has_key = bool(raw_key)
        has_pat = bool(settings.GITHUB_TOKEN and settings.GITHUB_TOKEN != "your_github_token_here")

        logger.info(
            "GitHub auth init: GITHUB_APP_ID=%s, GITHUB_APP_PRIVATE_KEY=%s (%d chars), "
            "GITHUB_APP_INSTALLATION_ID=%s, GITHUB_TOKEN=%s",
            "set" if has_app_id else "MISSING",
            "set" if has_key else "MISSING",
            len(raw_key) if raw_key else 0,
            settings.GITHUB_APP_INSTALLATION_ID or "not set (will auto-discover)",
            "set" if has_pat else "MISSING/default",
        )

        if has_app_id and has_key:
            self._app_id = settings.GITHUB_APP_ID
            self._private_key = self._decode_key(raw_key)
            if self._private_key:
                logger.info("GitHub App authentication configured (app_id=%s)", self._app_id)
            else:
                logger.warning("GITHUB_APP_PRIVATE_KEY could not be decoded; falling back to PAT")
        elif has_app_id and not has_key:
            logger.warning("GITHUB_APP_ID is set but GITHUB_APP_PRIVATE_KEY is missing")
        elif has_key and not has_app_id:
            logger.warning("GITHUB_APP_PRIVATE_KEY is set but GITHUB_APP_ID is missing")

        if not self.is_configured:
            logger.warning(
                "GitHub integration NOT configured — issue creation will be disabled. "
                "Set GITHUB_APP_ID + GITHUB_APP_PRIVATE_KEY, or GITHUB_TOKEN."
            )

    @property
    def is_app_auth(self) -> bool:
        return bool(self._app_id and self._private_key)

    @property
    def is_configured(self) -> bool:
        if self.is_app_auth:
            return True
        return bool(settings.GITHUB_TOKEN and settings.GITHUB_TOKEN != "your_github_token_here")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_token(self) -> str:
        """Return a valid GitHub token (installation token or PAT)."""
        if self.is_app_auth:
            return self._get_installation_token()
        return settings.GITHUB_TOKEN

    def auth_header(self) -> dict:
        """Return an Authorization header dict ready for requests."""
        token = self.get_token()
        if self.is_app_auth:
            return {"Authorization": f"Bearer {token}"}
        return {"Authorization": f"token {token}"}

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _decode_key(raw: str) -> Optional[str]:
        """Accept either a PEM string or a base64-encoded PEM."""
        if raw.startswith("-----BEGIN"):
            return raw
        try:
            decoded = base64.b64decode(raw).decode("utf-8")
            if "-----BEGIN" in decoded:
                return decoded
        except Exception:
            pass
        logger.error("GITHUB_APP_PRIVATE_KEY is not a valid PEM or base64-encoded PEM")
        return None

    def _make_jwt(self) -> str:
        """Create a short-lived JWT signed with the App's private key."""
        now = int(time.time())
        payload = {
            "iat": now - 60,
            "exp": now + (10 * 60),
            "iss": self._app_id,
        }
        return jose_jwt.encode(payload, self._private_key, algorithm="RS256")

    def _discover_installation_id(self, app_jwt: str) -> Optional[int]:
        """Find the first installation of the App."""
        try:
            resp = httpx.get(
                f"{GITHUB_API}/app/installations",
                headers={
                    "Authorization": f"Bearer {app_jwt}",
                    "Accept": "application/vnd.github+json",
                },
                timeout=15,
            )
            if resp.status_code != 200:
                logger.error("Failed to list installations: %s %s", resp.status_code, resp.text)
                return None
            installations = resp.json()
            if not installations:
                logger.error("No installations found for GitHub App %s", self._app_id)
                return None
            inst_id = installations[0]["id"]
            logger.info("Auto-discovered GitHub App installation_id=%s", inst_id)
            return inst_id
        except Exception as exc:
            logger.error("Error discovering installation: %s", exc)
            return None

    def _request_installation_token(self, app_jwt: str, installation_id: int) -> Optional[str]:
        """Exchange the JWT for an installation access token."""
        try:
            resp = httpx.post(
                f"{GITHUB_API}/app/installations/{installation_id}/access_tokens",
                headers={
                    "Authorization": f"Bearer {app_jwt}",
                    "Accept": "application/vnd.github+json",
                },
                timeout=15,
            )
            if resp.status_code != 201:
                logger.error("Failed to create installation token: %s %s", resp.status_code, resp.text)
                return None
            data = resp.json()
            self._token_expires_at = time.time() + 3500
            return data["token"]
        except Exception as exc:
            logger.error("Error requesting installation token: %s", exc)
            return None

    def _get_installation_token(self) -> str:
        """Return a cached installation token, refreshing if needed."""
        if self._token and time.time() < self._token_expires_at:
            return self._token

        with self._lock:
            if self._token and time.time() < self._token_expires_at:
                return self._token

            app_jwt = self._make_jwt()

            if not self._installation_id:
                self._installation_id = self._discover_installation_id(app_jwt)
                if not self._installation_id:
                    raise RuntimeError("Cannot discover GitHub App installation; set GITHUB_APP_INSTALLATION_ID")

            token = self._request_installation_token(app_jwt, self._installation_id)
            if not token:
                raise RuntimeError("Failed to obtain GitHub App installation token")

            self._token = token
            return self._token


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_instance: Optional[GitHubAuth] = None
_singleton_lock = threading.Lock()


def get_github_auth() -> GitHubAuth:
    global _instance
    if _instance is None:
        with _singleton_lock:
            if _instance is None:
                _instance = GitHubAuth()
    return _instance
