"""
Auth config + plugin-resolution tests.

Covers:
  - SourceAuth / JFrogAuth pydantic validators (mode exclusivity, basic pairing)
  - OCISource._resolve_auth_header for token, basic, and anonymous modes
  - OCISource end-to-end (respx) behaviour: explicit creds sent up-front,
    no bearer-realm dance attempted when creds are explicit
  - JFrogDestination basic-auth credentials threaded through to crane
    via DOCKER_CONFIG and through to httpx via _http_auth
"""

from __future__ import annotations

import base64
import json
import os

import httpx
import pydantic
import pytest
import respx

from app.config import JFrogAuth, SourceAuth, SourceConfig
from app.destinations.jfrog import JFrogDestination
from app.sources.oci import OCISource


# ---------------------------------------------------------------------------
# SourceAuth validators
# ---------------------------------------------------------------------------
class TestSourceAuthValidators:
    def test_empty_is_anonymous(self):
        auth = SourceAuth()
        assert auth.token_env is None
        assert auth.user_env is None
        assert auth.pass_env is None

    def test_token_only_ok(self):
        auth = SourceAuth(token_env="JCR_TOKEN")
        assert auth.token_env == "JCR_TOKEN"

    def test_basic_pair_ok(self):
        auth = SourceAuth(user_env="JCR_USER", pass_env="JCR_PASS")
        assert auth.user_env == "JCR_USER"
        assert auth.pass_env == "JCR_PASS"

    def test_token_plus_basic_rejected(self):
        with pytest.raises(pydantic.ValidationError) as exc:
            SourceAuth(token_env="T", user_env="U", pass_env="P")
        assert "EITHER token_env OR user_env+pass_env" in str(exc.value)

    def test_token_plus_half_basic_rejected(self):
        with pytest.raises(pydantic.ValidationError):
            SourceAuth(token_env="T", user_env="U")

    def test_half_basic_user_only_rejected(self):
        with pytest.raises(pydantic.ValidationError) as exc:
            SourceAuth(user_env="U")
        assert "user_env and pass_env must be set together" in str(exc.value)

    def test_half_basic_pass_only_rejected(self):
        with pytest.raises(pydantic.ValidationError):
            SourceAuth(pass_env="P")

    def test_source_config_bare_auth_key_means_defaults(self):
        """`auth:` (bare key in YAML) parses to None — treat as empty defaults."""
        sc = SourceConfig(name="s", type="oci", auth=None)
        assert isinstance(sc.auth, SourceAuth)
        assert sc.auth.token_env is None


# ---------------------------------------------------------------------------
# JFrogAuth validators
# ---------------------------------------------------------------------------
class TestJFrogAuthValidators:
    def test_empty_ok(self):
        a = JFrogAuth()
        assert a.token_env is None

    def test_token_only_ok(self):
        a = JFrogAuth(token_env="TOK")
        assert a.token_env == "TOK"

    def test_basic_only_ok(self):
        a = JFrogAuth(user_env="U", pass_env="P")
        assert a.user_env == "U"

    def test_docker_config_only_ok(self):
        a = JFrogAuth(docker_config_env="DC")
        assert a.docker_config_env == "DC"

    def test_token_plus_basic_rejected(self):
        with pytest.raises(pydantic.ValidationError) as exc:
            JFrogAuth(token_env="T", user_env="U", pass_env="P")
        assert "EXACTLY ONE" in str(exc.value)

    def test_token_plus_docker_config_rejected(self):
        with pytest.raises(pydantic.ValidationError):
            JFrogAuth(token_env="T", docker_config_env="DC")

    def test_basic_plus_docker_config_rejected(self):
        with pytest.raises(pydantic.ValidationError):
            JFrogAuth(user_env="U", pass_env="P", docker_config_env="DC")

    def test_half_basic_rejected_even_with_docker_config(self):
        with pytest.raises(pydantic.ValidationError):
            JFrogAuth(user_env="U", docker_config_env="DC")

    def test_half_basic_alone_rejected(self):
        with pytest.raises(pydantic.ValidationError):
            JFrogAuth(user_env="U")


# ---------------------------------------------------------------------------
# OCISource._resolve_auth_header
# ---------------------------------------------------------------------------
class TestOCISourceAuthResolution:
    def test_no_source_auth_is_anonymous(self):
        header, mode = OCISource._resolve_auth_header({"slug": "x"})
        assert header is None
        assert mode == "anonymous"

    def test_token_env_resolves_to_bearer(self, monkeypatch):
        monkeypatch.setenv("MY_TOK", "abc123")
        header, mode = OCISource._resolve_auth_header(
            {"slug": "x", "_source_auth": {"token_env": "MY_TOK"}}
        )
        assert header == "Bearer abc123"
        assert mode == "bearer"

    def test_token_env_empty_falls_back_to_anonymous(self, monkeypatch):
        # env var name was requested but its value is empty -> anon fallback,
        # plus a warning. Surfacing as anonymous lets the bearer-realm dance
        # still work for public registries that don't need auth.
        monkeypatch.delenv("MY_TOK", raising=False)
        header, mode = OCISource._resolve_auth_header(
            {"slug": "x", "_source_auth": {"token_env": "MY_TOK"}}
        )
        assert header is None
        assert mode == "anonymous"

    def test_basic_pair_resolves_to_basic(self, monkeypatch):
        monkeypatch.setenv("MY_USER", "alice")
        monkeypatch.setenv("MY_PASS", "s3cr3t!")
        header, mode = OCISource._resolve_auth_header(
            {
                "slug": "x",
                "_source_auth": {"user_env": "MY_USER", "pass_env": "MY_PASS"},
            }
        )
        expected = "Basic " + base64.b64encode(b"alice:s3cr3t!").decode()
        assert header == expected
        assert mode == "basic"

    def test_basic_pair_empty_pwd_falls_back_to_anonymous(self, monkeypatch):
        monkeypatch.setenv("MY_USER", "alice")
        monkeypatch.delenv("MY_PASS", raising=False)
        header, mode = OCISource._resolve_auth_header(
            {
                "slug": "x",
                "_source_auth": {"user_env": "MY_USER", "pass_env": "MY_PASS"},
            }
        )
        assert mode == "anonymous"


# ---------------------------------------------------------------------------
# OCISource end-to-end via respx
# ---------------------------------------------------------------------------
class TestOCISourceWireBehavior:
    @respx.mock
    def test_discover_with_bearer_token_sends_authorization_header(self, monkeypatch):
        monkeypatch.setenv("JCR_TOKEN", "my-access-token")
        src = OCISource()
        cc = {
            "slug": "rw-cli-codecollection",
            "image_registry": "artifactory.example.com/docker-ghcr/runwhen-contrib/rw-cli-codecollection",
            "_source_auth": {"token_env": "JCR_TOKEN"},
        }
        route = respx.get(
            "https://artifactory.example.com/v2/docker-ghcr/runwhen-contrib/"
            "rw-cli-codecollection/tags/list"
        ).mock(return_value=httpx.Response(200, json={"tags": ["main-c1a2b3d-e4f5a6b"]}))

        refs = src.discover_refs(cc)

        assert len(refs) == 1
        assert refs[0].ref == "main"
        # Exactly one request, with the Bearer header attached.
        assert route.call_count == 1
        sent = route.calls[0].request
        assert sent.headers["authorization"] == "Bearer my-access-token"

    @respx.mock
    def test_discover_with_basic_sends_base64_authorization_header(self, monkeypatch):
        monkeypatch.setenv("JCR_USER", "alice")
        monkeypatch.setenv("JCR_PASS", "s3cr3t!")
        src = OCISource()
        cc = {
            "slug": "rw-cli-codecollection",
            "image_registry": "artifactory.example.com/docker-ghcr/runwhen-contrib/rw-cli-codecollection",
            "_source_auth": {"user_env": "JCR_USER", "pass_env": "JCR_PASS"},
        }
        route = respx.get(
            "https://artifactory.example.com/v2/docker-ghcr/runwhen-contrib/"
            "rw-cli-codecollection/tags/list"
        ).mock(return_value=httpx.Response(200, json={"tags": ["main-c1a2b3d-e4f5a6b"]}))

        refs = src.discover_refs(cc)

        assert len(refs) == 1
        sent = route.calls[0].request
        expected = "Basic " + base64.b64encode(b"alice:s3cr3t!").decode()
        assert sent.headers["authorization"] == expected

    @respx.mock
    def test_explicit_bearer_does_not_trigger_dance_on_401(self, monkeypatch):
        """A pre-minted Bearer token can't be re-minted. If it's rejected,
        surface the 401 — don't silently re-auth anonymously, which would
        mask the real failure (bad / expired / under-scoped token).
        """
        monkeypatch.setenv("JCR_TOKEN", "wrong-token")
        src = OCISource()
        cc = {
            "slug": "rw-cli-codecollection",
            "image_registry": "artifactory.example.com/docker-ghcr/runwhen-contrib/rw-cli-codecollection",
            "_source_auth": {"token_env": "JCR_TOKEN"},
        }
        tags_route = respx.get(
            "https://artifactory.example.com/v2/docker-ghcr/runwhen-contrib/"
            "rw-cli-codecollection/tags/list"
        ).mock(
            return_value=httpx.Response(
                401,
                headers={
                    "WWW-Authenticate": 'Bearer realm="https://x/token",service="x"',
                },
            )
        )
        # If the dance were attempted, this route would be hit. It must NOT be.
        token_route = respx.get("https://x/token").mock(
            return_value=httpx.Response(200, json={"token": "should-not-happen"})
        )

        with pytest.raises(httpx.HTTPStatusError):
            src.discover_refs(cc)

        assert tags_route.call_count == 1  # exactly one tags request
        assert token_route.call_count == 0  # dance was NOT attempted

    @respx.mock
    def test_basic_does_dance_with_basic_header_on_token_endpoint(self, monkeypatch):
        """JFrog/Artifactory pattern: GET /v2/.../tags/list returns 401
        with a Bearer realm, the client trades Basic creds for a scoped
        Bearer at the realm endpoint, then retries with that Bearer.
        We MUST forward Basic on the realm GET — that's the only way the
        token endpoint can identify us.
        """
        monkeypatch.setenv("JCR_USER", "alice")
        monkeypatch.setenv("JCR_PASS", "s3cr3t!")
        src = OCISource()
        cc = {
            "slug": "rw-cli-codecollection",
            "image_registry": "artifactory.example.com/docker-ghcr/runwhen-contrib/rw-cli-codecollection",
            "_source_auth": {"user_env": "JCR_USER", "pass_env": "JCR_PASS"},
        }
        list_url = (
            "https://artifactory.example.com/v2/docker-ghcr/runwhen-contrib/"
            "rw-cli-codecollection/tags/list"
        )
        realm_url = "https://artifactory.example.com/artifactory/api/docker/" "docker-ghcr/v2/token"
        # Tags endpoint: 401 first, then 200 once we present a Bearer.
        tags_route = respx.get(list_url)
        tags_route.side_effect = [
            httpx.Response(
                401,
                headers={
                    "WWW-Authenticate": (
                        f'Bearer realm="{realm_url}",' 'service="artifactory.example.com"'
                    ),
                },
            ),
            httpx.Response(200, json={"tags": ["main-c1a2b3d-e4f5a6b"]}),
        ]
        token_route = respx.get(realm_url).mock(
            return_value=httpx.Response(200, json={"token": "minted-bearer"})
        )

        refs = src.discover_refs(cc)

        assert len(refs) == 1
        assert refs[0].ref == "main"

        # Verify: realm endpoint was called WITH our Basic header
        # (not anonymously). Otherwise JFrog wouldn't mint a token.
        assert token_route.call_count == 1
        expected_basic = "Basic " + base64.b64encode(b"alice:s3cr3t!").decode()
        assert token_route.calls[0].request.headers["authorization"] == expected_basic

        # Verify: the retry of the tags endpoint used the minted Bearer.
        assert tags_route.call_count == 2
        retry_req = tags_route.calls[1].request
        assert retry_req.headers["authorization"] == "Bearer minted-bearer"

    @respx.mock
    def test_basic_surfaces_when_token_endpoint_itself_rejects_basic(self, monkeypatch):
        """If the token endpoint returns 401 too, the Basic creds are
        actually wrong/unauthorized. Surface that as an HTTPStatusError
        rather than papering over it with another fallback.
        """
        monkeypatch.setenv("JCR_USER", "alice")
        monkeypatch.setenv("JCR_PASS", "wrong-pass")
        src = OCISource()
        cc = {
            "slug": "rw-cli-codecollection",
            "image_registry": "artifactory.example.com/docker-ghcr/runwhen-contrib/rw-cli-codecollection",
            "_source_auth": {"user_env": "JCR_USER", "pass_env": "JCR_PASS"},
        }
        list_url = (
            "https://artifactory.example.com/v2/docker-ghcr/runwhen-contrib/"
            "rw-cli-codecollection/tags/list"
        )
        realm_url = "https://x/token"
        respx.get(list_url).mock(
            return_value=httpx.Response(
                401,
                headers={
                    "WWW-Authenticate": f'Bearer realm="{realm_url}",service="x"',
                },
            )
        )
        # Token endpoint rejects the Basic creds too.
        respx.get(realm_url).mock(return_value=httpx.Response(401))

        with pytest.raises(httpx.HTTPStatusError):
            src.discover_refs(cc)

    @respx.mock
    def test_anonymous_still_does_the_bearer_dance(self):
        """Public GHCR-style anonymous reads must still work: get a 401,
        fetch an anonymous token from the WWW-Authenticate realm, retry.
        """
        src = OCISource()
        cc = {
            "slug": "rw-cli-codecollection",
            "image_registry": "ghcr.io/runwhen-contrib/rw-cli-codecollection",
            # No _source_auth at all -> anonymous mode.
        }
        list_url = "https://ghcr.io/v2/runwhen-contrib/rw-cli-codecollection/tags/list"
        tags_route = respx.get(list_url)
        tags_route.side_effect = [
            httpx.Response(
                401,
                headers={
                    "WWW-Authenticate": (
                        'Bearer realm="https://ghcr.io/token",'
                        'service="ghcr.io",'
                        'scope="repository:runwhen-contrib/rw-cli-codecollection:pull"'
                    ),
                },
            ),
            httpx.Response(200, json={"tags": ["main-c1a2b3d-e4f5a6b"]}),
        ]
        respx.get("https://ghcr.io/token").mock(
            return_value=httpx.Response(200, json={"token": "anon-token"})
        )

        refs = src.discover_refs(cc)

        assert len(refs) == 1
        assert tags_route.call_count == 2  # first 401, then retry with anon token


# ---------------------------------------------------------------------------
# JFrogDestination basic-auth support
# ---------------------------------------------------------------------------
class TestJFrogDestinationBasicAuth:
    @pytest.fixture
    def basic_dest_cfg(self):
        return {
            "name": "acme-jfrog",
            "type": "jfrog",
            "base_url": "https://acme.jfrog.io",
            "repo_key": "runwhen-virtual",
            "path_prefix": "codecollections",
            "auth": {"user_env": "JCR_USER", "pass_env": "JCR_PASS"},
        }

    def test_with_crane_auth_writes_docker_config_for_basic(self, basic_dest_cfg, monkeypatch):
        monkeypatch.setenv("JCR_USER", "alice")
        monkeypatch.setenv("JCR_PASS", "s3cr3t!")
        d = JFrogDestination()
        with d._with_crane_auth(basic_dest_cfg) as env:
            config_path = os.path.join(env["DOCKER_CONFIG"], "config.json")
            with open(config_path) as fp:
                data = json.load(fp)
            entry = data["auths"]["acme.jfrog.io"]
            assert base64.b64decode(entry["auth"]).decode() == "alice:s3cr3t!"

    def test_with_crane_auth_token_path_still_uses_underscore_user(self, monkeypatch):
        """Make sure I didn't break the existing token flow: token_env should
        encode as `_:<token>`, the Artifactory convention.
        """
        monkeypatch.setenv("JCR_TOKEN", "abc")
        d = JFrogDestination()
        cfg = {
            "name": "x",
            "base_url": "https://acme.jfrog.io",
            "repo_key": "k",
            "auth": {"token_env": "JCR_TOKEN"},
        }
        with d._with_crane_auth(cfg) as env:
            config_path = os.path.join(env["DOCKER_CONFIG"], "config.json")
            with open(config_path) as fp:
                data = json.load(fp)
            entry = data["auths"]["acme.jfrog.io"]
            assert base64.b64decode(entry["auth"]).decode() == "_:abc"

    def test_with_crane_auth_anonymous_when_no_creds(self, monkeypatch):
        monkeypatch.delenv("JCR_TOKEN", raising=False)
        d = JFrogDestination()
        cfg = {
            "name": "x",
            "base_url": "https://acme.jfrog.io",
            "repo_key": "k",
            "auth": {},
        }
        with d._with_crane_auth(cfg) as env:
            assert env == {}

    def test_http_auth_returns_basic_pair(self, basic_dest_cfg, monkeypatch):
        monkeypatch.setenv("JCR_USER", "alice")
        monkeypatch.setenv("JCR_PASS", "s3cr3t!")
        d = JFrogDestination()
        assert d._http_auth(basic_dest_cfg) == ("alice", "s3cr3t!")

    def test_http_auth_token_returns_underscore_user(self, monkeypatch):
        monkeypatch.setenv("JCR_TOKEN", "abc")
        d = JFrogDestination()
        cfg = {"name": "x", "auth": {"token_env": "JCR_TOKEN"}}
        assert d._http_auth(cfg) == ("_", "abc")

    def test_http_auth_returns_none_when_nothing_set(self):
        d = JFrogDestination()
        assert d._http_auth({"name": "x", "auth": {}}) is None
        assert d._http_auth({"name": "x"}) is None
