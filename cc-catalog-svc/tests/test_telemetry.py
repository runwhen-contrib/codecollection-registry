"""Tests for app/telemetry.py — the OTLP producer wiring.

The contract these lock in:

  * nothing configured -> no exporter is constructed and nothing raises;
  * traces enabled (``OTEL_TRACES_EXPORTER=otlp`` + endpoint) -> a
    TracerProvider is built with the resolved ``service.name``;
  * a broken exporter degrades to "no telemetry" instead of raising on the
    startup path.

Every exporter is patched, so no test does network I/O.
"""

from __future__ import annotations

import logging
import os
from unittest.mock import MagicMock, patch

import pytest
from opentelemetry.sdk.resources import (
    DEPLOYMENT_ENVIRONMENT,
    SERVICE_NAME,
    SERVICE_VERSION,
    Resource,
)
from opentelemetry.sdk.trace import TracerProvider

from app import __version__, telemetry


@pytest.fixture(autouse=True)
def _clean_otel_env(monkeypatch):
    """Neither a developer shell nor a previous test may leak OTEL_* config."""
    for key in list(os.environ):
        if key.startswith("OTEL_"):
            monkeypatch.delenv(key, raising=False)
    telemetry._logger_provider = None
    telemetry._meter_provider = None
    yield
    telemetry._logger_provider = None
    telemetry._meter_provider = None


# ---------------------------------------------------------------------------
# resolve_service_name / resource
# ---------------------------------------------------------------------------
def test_resolve_service_name_prefers_otel_service_name(monkeypatch):
    monkeypatch.setenv("OTEL_SERVICE_NAME", "rw-mini-cc-catalog")
    monkeypatch.setenv("FASTAPI_SERVICE", "ignored")
    assert telemetry.resolve_service_name("in-code") == "rw-mini-cc-catalog"


def test_resolve_service_name_falls_back_to_in_code_then_default(monkeypatch):
    assert telemetry.resolve_service_name("in-code") == "in-code"
    monkeypatch.setenv("FASTAPI_SERVICE", "from-fastapi")
    assert telemetry.resolve_service_name() == "from-fastapi"
    monkeypatch.delenv("FASTAPI_SERVICE")
    assert telemetry.resolve_service_name() == telemetry.DEFAULT_SERVICE_NAME


def test_build_resource_carries_the_shared_attributes(monkeypatch):
    monkeypatch.setenv("OTEL_RESOURCE_ATTRIBUTES", "deployment.environment=staging")
    resource = telemetry._build_resource("cc-catalog-svc", "1.2.3")
    assert resource.attributes[SERVICE_NAME] == "cc-catalog-svc"
    assert resource.attributes[SERVICE_VERSION] == "1.2.3"
    assert resource.attributes[DEPLOYMENT_ENVIRONMENT] == "staging"


def test_deployment_environment_defaults_to_unknown():
    assert telemetry._deployment_environment() == "unknown"


# ---------------------------------------------------------------------------
# Off-by-default contract
# ---------------------------------------------------------------------------
def test_nothing_configured_is_a_noop():
    with patch("app.telemetry.OTLPSpanExporter") as exporter, patch(
        "app.telemetry.FastAPIInstrumentor"
    ) as instrumentor:
        assert telemetry.setup_telemetry() is None
        assert telemetry.setup_logging_export() is None
        assert telemetry.setup_metrics() is None

        app = MagicMock()
        telemetry.instrument_fastapi(app)

    exporter.assert_not_called()
    instrumentor.instrument_app.assert_not_called()


def test_trace_switch_without_endpoint_stays_off(monkeypatch):
    monkeypatch.setenv("OTEL_TRACES_EXPORTER", "otlp")
    with patch("app.telemetry.OTLPSpanExporter") as exporter:
        assert telemetry.setup_telemetry() is None
    exporter.assert_not_called()


def test_otel_sdk_disabled_kills_every_signal(monkeypatch):
    monkeypatch.setenv("OTEL_SDK_DISABLED", "true")
    monkeypatch.setenv("OTEL_TRACES_EXPORTER", "otlp")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "http://collector:4317")
    monkeypatch.setenv("OTEL_LOGS_EXPORTER", "otlp")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_LOGS_ENDPOINT", "http://collector:4317")
    monkeypatch.setenv("OTEL_METRICS_EXPORTER", "otlp")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_METRICS_ENDPOINT", "http://collector:4317")
    with patch("app.telemetry.OTLPSpanExporter") as exporter:
        assert telemetry.setup_telemetry() is None
        assert telemetry.setup_logging_export() is None
        assert telemetry.setup_metrics() is None
    exporter.assert_not_called()


# ---------------------------------------------------------------------------
# Traces enabled
# ---------------------------------------------------------------------------
def test_traces_enabled_builds_provider_with_expected_service_name(monkeypatch):
    monkeypatch.setenv("OTEL_TRACES_EXPORTER", "otlp")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "http://collector:4317")
    monkeypatch.setenv("OTEL_SERVICE_NAME", "from-env")

    built: list[tuple[str, str]] = []

    def _record(name: str, version: str) -> Resource:
        built.append((name, version))
        return Resource.create({SERVICE_NAME: name})

    with patch("app.telemetry.OTLPSpanExporter") as exporter, patch(
        "app.telemetry._build_resource", side_effect=_record
    ):
        provider = telemetry.setup_telemetry(service_name="in-code")

    try:
        assert isinstance(provider, TracerProvider)
        # OTEL_SERVICE_NAME wins over the in-code default for every signal.
        assert built == [("from-env", __version__)]
        exporter.assert_called_once_with(
            endpoint="http://collector:4317", insecure=True
        )
    finally:
        provider.shutdown()


def test_per_signal_endpoint_wins_over_generic(monkeypatch):
    monkeypatch.setenv("OTEL_TRACES_EXPORTER", "otlp")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://generic:4317")
    monkeypatch.setenv(
        "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "http://traces-host:4317"
    )
    with patch("app.telemetry.OTLPSpanExporter") as exporter:
        provider = telemetry.setup_telemetry()
    try:
        exporter.assert_called_once_with(
            endpoint="http://traces-host:4317", insecure=True
        )
    finally:
        provider.shutdown()


def test_https_endpoint_is_not_insecure(monkeypatch):
    monkeypatch.setenv("OTEL_TRACES_EXPORTER", "otlp")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "https://collector:4317")
    with patch("app.telemetry.OTLPSpanExporter") as exporter:
        provider = telemetry.setup_telemetry()
    try:
        exporter.assert_called_once_with(
            endpoint="https://collector:4317", insecure=False
        )
    finally:
        provider.shutdown()


# ---------------------------------------------------------------------------
# Startup resilience
# ---------------------------------------------------------------------------
def test_broken_trace_exporter_degrades_instead_of_raising(monkeypatch):
    monkeypatch.setenv("OTEL_TRACES_EXPORTER", "otlp")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "http://collector:4317")
    with patch(
        "app.telemetry.OTLPSpanExporter", side_effect=RuntimeError("boom")
    ):
        assert telemetry.setup_telemetry() is None


def test_broken_log_exporter_degrades_instead_of_raising(monkeypatch):
    monkeypatch.setenv("OTEL_LOGS_EXPORTER", "otlp")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_LOGS_ENDPOINT", "http://collector:4317")
    with patch(
        "opentelemetry.exporter.otlp.proto.grpc._log_exporter.OTLPLogExporter",
        side_effect=RuntimeError("boom"),
    ):
        assert telemetry.setup_logging_export() is None


def test_broken_metric_exporter_degrades_instead_of_raising(monkeypatch):
    monkeypatch.setenv("OTEL_METRICS_EXPORTER", "otlp")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_METRICS_ENDPOINT", "http://collector:4317")
    with patch(
        "opentelemetry.exporter.otlp.proto.grpc.metric_exporter.OTLPMetricExporter",
        side_effect=RuntimeError("boom"),
    ):
        assert telemetry.setup_metrics() is None


# ---------------------------------------------------------------------------
# Logs / metrics opt-in
# ---------------------------------------------------------------------------
def test_log_export_installs_a_root_handler_and_is_idempotent(monkeypatch):
    monkeypatch.setenv("OTEL_LOGS_EXPORTER", "otlp")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_LOGS_ENDPOINT", "http://collector:4317")
    root = logging.getLogger()
    before = list(root.handlers)

    with patch("opentelemetry.exporter.otlp.proto.grpc._log_exporter.OTLPLogExporter"):
        provider = telemetry.setup_logging_export(service_name="in-code")

    try:
        assert provider is not None
        added = [h for h in root.handlers if h not in before]
        assert len(added) == 1
        # A second call must not stack a duplicate handler.
        assert telemetry.setup_logging_export(service_name="in-code") is provider
        assert len(root.handlers) == len(before) + 1
    finally:
        for handler in [h for h in root.handlers if h not in before]:
            root.removeHandler(handler)
        provider.shutdown()
        telemetry._logger_provider = None


def test_metrics_export_sets_a_global_meter_provider(monkeypatch):
    monkeypatch.setenv("OTEL_METRICS_EXPORTER", "otlp")
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_METRICS_ENDPOINT", "http://collector:4317")
    with patch(
        "opentelemetry.exporter.otlp.proto.grpc.metric_exporter.OTLPMetricExporter"
    ):
        provider = telemetry.setup_metrics(service_name="in-code")

    try:
        assert provider is not None
        from opentelemetry import metrics

        assert metrics.get_meter_provider() is provider
    finally:
        provider.shutdown()
        telemetry._meter_provider = None


# ---------------------------------------------------------------------------
# FastAPI instrumentation / shutdown
# ---------------------------------------------------------------------------
def test_instrument_fastapi_is_applied_only_when_traces_active(monkeypatch):
    app = MagicMock()
    with patch("app.telemetry.FastAPIInstrumentor") as instrumentor:
        telemetry.instrument_fastapi(app)
        instrumentor.instrument_app.assert_not_called()

        monkeypatch.setenv("OTEL_TRACES_EXPORTER", "otlp")
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT", "http://collector:4317")
        telemetry.instrument_fastapi(app)
        instrumentor.instrument_app.assert_called_once_with(app)


def test_shutdown_never_raises_when_a_provider_fails():
    class Boom:
        def shutdown(self) -> None:
            raise RuntimeError("flush failed")

    telemetry._logger_provider = Boom()
    telemetry._meter_provider = None
    try:
        telemetry.shutdown_telemetry()  # must not raise
    finally:
        telemetry._logger_provider = None
