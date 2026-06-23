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
        # Validator now covers three modes (token / basic / dockerconfigjson);
        # message updated to "AT MOST ONE" to match.
        assert "AT MOST ONE" in str(exc.value)

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


# ---------------------------------------------------------------------------
# Shared dockerconfigjson lookup helper
# ---------------------------------------------------------------------------
class TestDockerconfigjsonResolveBasicPair:
    """Direct tests of app.auth_dockerconfigjson.resolve_basic_pair.

    The OCI source + git mirror service both funnel through this helper,
    so per-edge-case coverage lives here rather than being duplicated in
    each call site's test class.
    """

    def _write_config(self, tmp_path, payload):
        from json import dumps

        p = tmp_path / ".dockerconfigjson"
        p.write_text(dumps(payload))
        return str(p)

    def test_base64_auth_field_wins(self, tmp_path):
        from app.auth_dockerconfigjson import resolve_basic_pair

        encoded = base64.b64encode(b"alice:s3cr3t!").decode()
        path = self._write_config(
            tmp_path,
            {
                "auths": {
                    "artifactory.example.com": {"auth": encoded},
                }
            },
        )
        assert resolve_basic_pair(path, "artifactory.example.com") == ("alice", "s3cr3t!")

    def test_explicit_username_password_fallback(self, tmp_path):
        from app.auth_dockerconfigjson import resolve_basic_pair

        path = self._write_config(
            tmp_path,
            {
                "auths": {
                    "ghcr.io": {"username": "u", "password": "p"},
                }
            },
        )
        assert resolve_basic_pair(path, "ghcr.io") == ("u", "p")

    def test_auth_field_preferred_over_username_password(self, tmp_path):
        """Docker CLI writes ``auth``; if both encodings appear, base64
        is canonical. Match that behavior."""
        from app.auth_dockerconfigjson import resolve_basic_pair

        encoded = base64.b64encode(b"from-auth:pwd1").decode()
        path = self._write_config(
            tmp_path,
            {
                "auths": {
                    "example.com": {
                        "auth": encoded,
                        "username": "from-fields",
                        "password": "pwd2",
                    },
                }
            },
        )
        assert resolve_basic_pair(path, "example.com") == ("from-auth", "pwd1")

    def test_missing_host_returns_none(self, tmp_path):
        from app.auth_dockerconfigjson import resolve_basic_pair

        path = self._write_config(
            tmp_path,
            {"auths": {"artifactory.example.com": {"username": "u", "password": "p"}}},
        )
        assert resolve_basic_pair(path, "ghcr.io") is None

    def test_missing_file_returns_none(self, tmp_path):
        from app.auth_dockerconfigjson import resolve_basic_pair

        assert resolve_basic_pair(str(tmp_path / "nope.json"), "x.com") is None

    def test_empty_path_returns_none(self):
        from app.auth_dockerconfigjson import resolve_basic_pair

        assert resolve_basic_pair("", "x.com") is None

    def test_malformed_json_returns_none(self, tmp_path):
        from app.auth_dockerconfigjson import resolve_basic_pair

        p = tmp_path / ".dockerconfigjson"
        p.write_text("not-valid-json{")
        assert resolve_basic_pair(str(p), "x.com") is None

    def test_malformed_base64_auth_returns_none(self, tmp_path):
        from app.auth_dockerconfigjson import resolve_basic_pair

        path = self._write_config(
            tmp_path,
            {"auths": {"x.com": {"auth": "***-not-base64-***"}}},
        )
        assert resolve_basic_pair(path, "x.com") is None

    def test_auth_without_colon_returns_none(self, tmp_path):
        """``auth`` must decode to ``user:password``; otherwise it's not
        a Basic credential and we shouldn't pretend it is."""
        from app.auth_dockerconfigjson import resolve_basic_pair

        encoded = base64.b64encode(b"no-colon-here").decode()
        path = self._write_config(tmp_path, {"auths": {"x.com": {"auth": encoded}}})
        assert resolve_basic_pair(path, "x.com") is None

    def test_empty_user_or_pwd_returns_none(self, tmp_path):
        from app.auth_dockerconfigjson import resolve_basic_pair

        encoded_empty_user = base64.b64encode(b":pwd").decode()
        path = self._write_config(tmp_path, {"auths": {"x.com": {"auth": encoded_empty_user}}})
        assert resolve_basic_pair(path, "x.com") is None

    def test_resolve_from_env_reads_path_from_env_var(self, tmp_path, monkeypatch):
        from app.auth_dockerconfigjson import resolve_basic_pair_from_env

        path = self._write_config(
            tmp_path, {"auths": {"x.com": {"username": "u", "password": "p"}}}
        )
        monkeypatch.setenv("MY_DC_PATH", path)
        assert resolve_basic_pair_from_env("MY_DC_PATH", "x.com") == ("u", "p")

    def test_resolve_from_env_unset_returns_none(self, monkeypatch):
        from app.auth_dockerconfigjson import resolve_basic_pair_from_env

        monkeypatch.delenv("MISSING_DC", raising=False)
        assert resolve_basic_pair_from_env("MISSING_DC", "x.com") is None

    def test_resolve_from_env_empty_name_returns_none(self):
        from app.auth_dockerconfigjson import resolve_basic_pair_from_env

        assert resolve_basic_pair_from_env("", "x.com") is None


# ---------------------------------------------------------------------------
# SourceAuth + GitAuth dockerconfigjson_env validators
# ---------------------------------------------------------------------------
class TestDockerconfigjsonValidators:
    def test_source_auth_dockerconfigjson_alone_ok(self):
        a = SourceAuth(dockerconfigjson_env="JCR_DOCKERCONFIGJSON")
        assert a.dockerconfigjson_env == "JCR_DOCKERCONFIGJSON"

    def test_source_auth_dockerconfigjson_plus_token_rejected(self):
        with pytest.raises(pydantic.ValidationError) as exc:
            SourceAuth(token_env="T", dockerconfigjson_env="DC")
        assert "AT MOST ONE" in str(exc.value)

    def test_source_auth_dockerconfigjson_plus_basic_rejected(self):
        with pytest.raises(pydantic.ValidationError) as exc:
            SourceAuth(user_env="U", pass_env="P", dockerconfigjson_env="DC")
        assert "AT MOST ONE" in str(exc.value)

    def test_git_auth_dockerconfigjson_alone_ok(self):
        from app.config import GitAuth

        a = GitAuth(dockerconfigjson_env="GIT_DC")
        assert a.dockerconfigjson_env == "GIT_DC"

    def test_git_auth_dockerconfigjson_plus_token_rejected(self):
        from app.config import GitAuth

        with pytest.raises(pydantic.ValidationError):
            GitAuth(token_env="T", dockerconfigjson_env="DC")


# ---------------------------------------------------------------------------
# OCISource._resolve_auth_header — dockerconfigjson mode
# ---------------------------------------------------------------------------
class TestOCISourceDockerconfigjsonAuth:
    """OCI-source-level integration of the lookup helper.

    Coverage notes:

    - Happy path: env var points at a file, host present, returns Basic.
    - Mode is "basic" — the bearer-realm dance behavior is shared with
      the explicit user_env+pass_env code path. Once resolved, the
      catalog can't tell the two apart, which is intentional.
    - Soft-fallback on every "can't resolve" case (missing image_registry,
      malformed image_registry, env unset, file missing, host not in
      file). The catalog should degrade to anonymous so a partial config
      against public sources still works, not hard-fail the whole poll.
    """

    def _write_config(self, tmp_path, payload):
        from json import dumps

        p = tmp_path / ".dockerconfigjson"
        p.write_text(dumps(payload))
        return str(p)

    def test_resolves_basic_when_host_present(self, tmp_path, monkeypatch):
        encoded = base64.b64encode(b"alice:s3cr3t!").decode()
        path = self._write_config(
            tmp_path,
            {"auths": {"artifactory.example.com": {"auth": encoded}}},
        )
        monkeypatch.setenv("JCR_DC", path)
        header, mode = OCISource._resolve_auth_header(
            {
                "slug": "x",
                "image_registry": "artifactory.example.com/docker-ghcr/rw/foo",
                "_source_auth": {"dockerconfigjson_env": "JCR_DC"},
            }
        )
        assert mode == "basic"
        assert header == "Basic " + encoded

    def test_host_miss_falls_back_to_anonymous(self, tmp_path, monkeypatch):
        path = self._write_config(
            tmp_path,
            {"auths": {"some-other-host.example.com": {"username": "u", "password": "p"}}},
        )
        monkeypatch.setenv("JCR_DC", path)
        header, mode = OCISource._resolve_auth_header(
            {
                "slug": "x",
                "image_registry": "artifactory.example.com/docker-ghcr/rw/foo",
                "_source_auth": {"dockerconfigjson_env": "JCR_DC"},
            }
        )
        assert mode == "anonymous"
        assert header is None

    def test_env_var_unset_falls_back_to_anonymous(self, monkeypatch):
        monkeypatch.delenv("JCR_DC", raising=False)
        header, mode = OCISource._resolve_auth_header(
            {
                "slug": "x",
                "image_registry": "artifactory.example.com/docker-ghcr/rw/foo",
                "_source_auth": {"dockerconfigjson_env": "JCR_DC"},
            }
        )
        assert mode == "anonymous"

    def test_missing_image_registry_falls_back_to_anonymous(self, tmp_path, monkeypatch):
        path = self._write_config(
            tmp_path,
            {"auths": {"x.com": {"username": "u", "password": "p"}}},
        )
        monkeypatch.setenv("JCR_DC", path)
        header, mode = OCISource._resolve_auth_header(
            {
                "slug": "x",
                # No image_registry — we can't derive a host to look up.
                "_source_auth": {"dockerconfigjson_env": "JCR_DC"},
            }
        )
        assert mode == "anonymous"

    def test_malformed_image_registry_falls_back_to_anonymous(self, tmp_path, monkeypatch):
        path = self._write_config(
            tmp_path,
            {"auths": {"x.com": {"username": "u", "password": "p"}}},
        )
        monkeypatch.setenv("JCR_DC", path)
        header, mode = OCISource._resolve_auth_header(
            {
                "slug": "x",
                "image_registry": "no-slash-host-only",  # _split_registry_url raises
                "_source_auth": {"dockerconfigjson_env": "JCR_DC"},
            }
        )
        assert mode == "anonymous"

    @respx.mock
    def test_end_to_end_dockerconfigjson_sends_basic_header(self, tmp_path, monkeypatch):
        """Full discover_refs path uses the resolved Basic header on the
        first /tags/list request (same as explicit user_env+pass_env).
        """
        encoded = base64.b64encode(b"alice:s3cr3t!").decode()
        path = self._write_config(
            tmp_path,
            {"auths": {"artifactory.example.com": {"auth": encoded}}},
        )
        monkeypatch.setenv("JCR_DC", path)
        src = OCISource()
        cc = {
            "slug": "rw-cli-codecollection",
            "image_registry": (
                "artifactory.example.com/docker-ghcr/runwhen-contrib/rw-cli-codecollection"
            ),
            "_source_auth": {"dockerconfigjson_env": "JCR_DC"},
        }
        route = respx.get(
            "https://artifactory.example.com/v2/docker-ghcr/runwhen-contrib/"
            "rw-cli-codecollection/tags/list"
        ).mock(return_value=httpx.Response(200, json={"tags": ["main-c1a2b3d-e4f5a6b"]}))

        refs = src.discover_refs(cc)

        assert len(refs) == 1
        assert route.call_count == 1
        assert route.calls[0].request.headers["authorization"] == "Basic " + encoded


# ---------------------------------------------------------------------------
# git_mirror._git_auth_args — dockerconfigjson mode
# ---------------------------------------------------------------------------
class TestGitAuthArgsDockerconfigjson:
    """``_git_auth_args`` needs an upstream_url to derive the host for
    the dockerconfigjson lookup. The other auth modes (token_env,
    user_env+pass_env) ignore upstream_url — covered here for regression
    safety.
    """

    def _write_config(self, tmp_path, payload):
        from json import dumps

        p = tmp_path / ".dockerconfigjson"
        p.write_text(dumps(payload))
        return str(p)

    def test_resolves_basic_for_known_host(self, tmp_path, monkeypatch):
        from app.config import GitAuth
        from app.services.git_mirror import _git_auth_args

        encoded = base64.b64encode(b"alice:s3cr3t!").decode()
        path = self._write_config(tmp_path, {"auths": {"git.example.com": {"auth": encoded}}})
        monkeypatch.setenv("GIT_DC", path)
        args = _git_auth_args(
            GitAuth(dockerconfigjson_env="GIT_DC"),
            upstream_url="https://git.example.com/runwhen/x.git",
        )
        assert args == [
            "-c",
            f"http.extraHeader=Authorization: Basic {encoded}",
        ]

    def test_unknown_host_falls_back_to_no_auth(self, tmp_path, monkeypatch):
        from app.config import GitAuth
        from app.services.git_mirror import _git_auth_args

        path = self._write_config(
            tmp_path, {"auths": {"git.example.com": {"username": "u", "password": "p"}}}
        )
        monkeypatch.setenv("GIT_DC", path)
        args = _git_auth_args(
            GitAuth(dockerconfigjson_env="GIT_DC"),
            upstream_url="https://github.com/runwhen/x.git",
        )
        assert args == []

    def test_missing_upstream_url_falls_back_to_no_auth(self, tmp_path, monkeypatch):
        """rev-parse and other local ops call without upstream_url; that
        path must not crash and must not block local-only operations."""
        from app.config import GitAuth
        from app.services.git_mirror import _git_auth_args

        path = self._write_config(
            tmp_path, {"auths": {"git.example.com": {"username": "u", "password": "p"}}}
        )
        monkeypatch.setenv("GIT_DC", path)
        args = _git_auth_args(GitAuth(dockerconfigjson_env="GIT_DC"))
        assert args == []

    def test_token_env_still_works_when_upstream_url_passed(self, monkeypatch):
        """Regression guard: existing token_env path must ignore the new
        upstream_url parameter."""
        from app.config import GitAuth
        from app.services.git_mirror import _git_auth_args

        monkeypatch.setenv("GH_TOKEN", "ghp_abc")
        args = _git_auth_args(
            GitAuth(token_env="GH_TOKEN"),
            upstream_url="https://github.com/runwhen/x.git",
        )
        # token path encodes as Basic x-access-token:<token>
        expected = base64.b64encode(b"x-access-token:ghp_abc").decode()
        assert args == [
            "-c",
            f"http.extraHeader=Authorization: Basic {expected}",
        ]

    def test_basic_pair_still_works_when_upstream_url_passed(self, monkeypatch):
        from app.config import GitAuth
        from app.services.git_mirror import _git_auth_args

        monkeypatch.setenv("GIT_USER", "alice")
        monkeypatch.setenv("GIT_PASS", "s3cr3t!")
        args = _git_auth_args(
            GitAuth(user_env="GIT_USER", pass_env="GIT_PASS"),
            upstream_url="https://github.com/runwhen/x.git",
        )
        expected = base64.b64encode(b"alice:s3cr3t!").decode()
        assert args == [
            "-c",
            f"http.extraHeader=Authorization: Basic {expected}",
        ]
