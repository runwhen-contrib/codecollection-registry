"""OpenTelemetry (OTLP) setup for cc-catalog-svc — the *producer* half of the
platform's built-in observability (the collector + OpenObserve are shipped by
the platform chart).

Two rules shape this module:

1. **Off by default.** Nothing here does anything unless the *standard*
   OpenTelemetry environment variables are set: no exporter is constructed, no
   network call is made, no new required config. A deployment that sets nothing
   behaves exactly as it did before this module existed.

2. **Standard env names only, consumed as-is.** The chart sets the same OTel
   variables it sets for every other component — no bespoke ``CC_CATALOG_*``
   switches — and this service works against the platform's documented surface
   with zero extra variables:

   Protocol (default ``http/protobuf``, matching the standard and the chart;
   ``grpc`` is supported for installs that set it)::

       OTEL_EXPORTER_OTLP_PROTOCOL   http/protobuf | grpc

   Signal switches (the value must be ``otlp``; anything else leaves the signal
   off, and unset means off)::

       OTEL_TRACES_EXPORTER    traces  (FastAPI instrumentation + OTLP spans)
       OTEL_LOGS_EXPORTER      logs    (root logging handler -> OTLP)
       OTEL_METRICS_EXPORTER   metrics (MeterProvider -> OTLP)

   Endpoints (the per-signal variable wins over the generic one, for both
   protocols; the collector accepts gRPC on :4317 and HTTP/protobuf on :4318)::

       OTEL_EXPORTER_OTLP_TRACES_ENDPOINT   / OTEL_EXPORTER_OTLP_ENDPOINT
       OTEL_EXPORTER_OTLP_LOGS_ENDPOINT     / OTEL_EXPORTER_OTLP_ENDPOINT
       OTEL_EXPORTER_OTLP_METRICS_ENDPOINT  / OTEL_EXPORTER_OTLP_ENDPOINT

   For HTTP the SDK's endpoint rule is reproduced here: a *per-signal*
   endpoint is used verbatim (the chart's already end in ``/v1/<signal>``),
   while the *generic* endpoint gets the signal path appended. Getting this
   wrong would double the path (``/v1/traces/v1/traces``).

   ``OTEL_SERVICE_NAME`` is the per-component name and wins over the in-code
   default (``resolve_service_name`` below is the single source of truth for it,
   so traces/logs/metrics can never disagree). ``OTEL_RESOURCE_ATTRIBUTES``,
   ``OTEL_TRACES_SAMPLER`` (and ``_ARG``) and ``OTEL_SDK_DISABLED`` are honored
   where the SDK reads them itself.

Every exporter/provider is built inside ``try/except``: this runs on the
startup path and telemetry must never be the reason the service fails to boot.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Optional

from opentelemetry import metrics, trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import (
    DEPLOYMENT_ENVIRONMENT,
    SERVICE_NAME,
    SERVICE_VERSION,
    Resource,
)
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from app import __version__

logger = logging.getLogger(__name__)

# The name this process reports when nothing overrides it. OTEL_SERVICE_NAME
# (set per component by the chart) takes precedence — see resolve_service_name.
DEFAULT_SERVICE_NAME = "cc-catalog-svc"

# OTLP transport. The standard default is http/protobuf and that is what the
# platform chart sets; grpc is honored for installs that prefer it.
DEFAULT_PROTOCOL = "http/protobuf"
_PROTOCOL_GRPC = "grpc"

# Signal -> the path the HTTP exporter appends to a *generic* endpoint. (A
# per-signal endpoint is used verbatim; see _resolve_endpoint.)
_SIGNAL_PATHS = {"TRACES": "v1/traces", "LOGS": "v1/logs", "METRICS": "v1/metrics"}

# Trace goes through the OTel global (trace.set_tracer_provider); the log and
# metric providers are process-global singletons kept here so shutdown can
# flush whatever their batch processors still hold.
_logger_provider: Any = None
_meter_provider: Any = None


def _env(name: str) -> str:
    """Read an env var as a stripped string (``""`` when unset)."""
    return (os.environ.get(name) or "").strip()


def _sdk_disabled() -> bool:
    """Standard ``OTEL_SDK_DISABLED`` kill-switch (the chart sets it "false")."""
    return _env("OTEL_SDK_DISABLED").lower() in {"1", "true", "yes"}


def _signal_enabled(exporter_var: str) -> bool:
    """A signal is on only when its standard exporter switch literally says
    ``otlp``, so an empty environment configures nothing."""
    return _env(exporter_var).lower() == "otlp"


def _protocol() -> str:
    """Resolve the OTLP transport: ``grpc`` or ``http/protobuf``.

    ``OTEL_EXPORTER_OTLP_PROTOCOL`` is the standard switch; anything that is
    not ``grpc`` (including unset, the ``http/protobuf`` default, and the
    unsupported ``http/json``) falls back to ``http/protobuf``, which is the
    only HTTP flavor we ship.
    """
    raw = _env("OTEL_EXPORTER_OTLP_PROTOCOL").lower()
    return _PROTOCOL_GRPC if raw == _PROTOCOL_GRPC else DEFAULT_PROTOCOL


def _is_grpc() -> bool:
    return _protocol() == _PROTOCOL_GRPC


def _append_signal_path(endpoint: str, path: str) -> str:
    """Append the signal path the way the SDK's HTTP exporter does."""
    if endpoint.endswith("/"):
        return endpoint + path
    return f"{endpoint}/{path}"


def _resolve_endpoint(signal: str) -> Optional[str]:
    """Resolve a signal's final OTLP URL (``signal`` is TRACES/LOGS/METRICS).

    The per-signal variable wins over the generic one, for both protocols.
    Returns ``None`` when neither is set — the caller treats that as "nothing
    to ship to".

    For HTTP the SDK's endpoint rule is reproduced: a per-signal endpoint is
    used verbatim, while a generic endpoint gets ``/v1/<signal>`` appended.
    (gRPC endpoints are host:port and never get a path.) We resolve rather than
    let the exporter read the env itself because the exporter can only fall
    back to one endpoint — this keeps precedence and the on/off decision in one
    testable place.
    """
    specific = _env(f"OTEL_EXPORTER_OTLP_{signal}_ENDPOINT")
    if specific:
        # Verbatim: the chart's per-signal endpoints already carry the path.
        return specific

    generic = _env("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not generic:
        return None
    if _is_grpc():
        return generic
    return _append_signal_path(generic, _SIGNAL_PATHS[signal])


def _insecure(endpoint: str) -> bool:
    """gRPC credentials follow the scheme: only ``https://`` is TLS."""
    return not endpoint.lower().startswith("https://")


def _make_span_exporter(endpoint: str) -> Any:
    """Build the OTLP span exporter matching the configured protocol."""
    if _is_grpc():
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )

        return OTLPSpanExporter(endpoint=endpoint, insecure=_insecure(endpoint))

    from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
        OTLPSpanExporter,
    )

    return OTLPSpanExporter(endpoint=endpoint)


def _make_log_exporter(endpoint: str) -> Any:
    """Build the OTLP log exporter matching the configured protocol."""
    if _is_grpc():
        from opentelemetry.exporter.otlp.proto.grpc._log_exporter import (
            OTLPLogExporter,
        )

        return OTLPLogExporter(endpoint=endpoint, insecure=_insecure(endpoint))

    from opentelemetry.exporter.otlp.proto.http._log_exporter import (
        OTLPLogExporter,
    )

    return OTLPLogExporter(endpoint=endpoint)


def _make_metric_exporter(endpoint: str) -> Any:
    """Build the OTLP metric exporter matching the configured protocol."""
    if _is_grpc():
        from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
            OTLPMetricExporter,
        )

        return OTLPMetricExporter(endpoint=endpoint, insecure=_insecure(endpoint))

    from opentelemetry.exporter.otlp.proto.http.metric_exporter import (
        OTLPMetricExporter,
    )

    return OTLPMetricExporter(endpoint=endpoint)


def resolve_service_name(explicit: Optional[str] = None) -> str:
    """Resolve the OTel ``service.name`` — the ONE rule every signal uses.

    Precedence:
      1. ``OTEL_SERVICE_NAME`` — the standard operator override, set per
         component by the chart, and what the rest of the platform reports.
      2. ``explicit`` — the in-code default a caller passes.
      3. ``FASTAPI_SERVICE``.
      4. ``DEFAULT_SERVICE_NAME``.

    Keeping this in one place is what stops traces, logs and metrics from
    landing under different service names in OpenObserve.
    """
    return (
        _env("OTEL_SERVICE_NAME")
        or explicit
        or _env("FASTAPI_SERVICE")
        or DEFAULT_SERVICE_NAME
    )


def _deployment_environment() -> str:
    """``deployment.environment`` from the standard ``OTEL_RESOURCE_ATTRIBUTES``
    (e.g. ``deployment.environment=staging``), else ``unknown``."""
    for part in _env("OTEL_RESOURCE_ATTRIBUTES").split(","):
        key, _, value = part.partition("=")
        if key.strip() == "deployment.environment" and value.strip():
            return value.strip()
    return "unknown"


def _build_resource(name: str, service_version: str) -> Resource:
    """The one Resource shared by traces, logs and metrics.

    Keeping a single builder means all three signals carry the same
    service.name/version/environment, so OpenObserve can correlate them. The
    SDK additionally merges anything in ``OTEL_RESOURCE_ATTRIBUTES``.
    """
    return Resource.create(
        {
            SERVICE_NAME: name,
            SERVICE_VERSION: service_version,
            DEPLOYMENT_ENVIRONMENT: _deployment_environment(),
        }
    )


def _traces_active() -> bool:
    """Traces need the switch AND an endpoint; otherwise we stay dark."""
    return (
        not _sdk_disabled()
        and _signal_enabled("OTEL_TRACES_EXPORTER")
        and _resolve_endpoint("TRACES") is not None
    )


def setup_telemetry(
    service_name: Optional[str] = None,
    service_version: str = __version__,
) -> Optional[TracerProvider]:
    """Configure OTLP tracing (and prove the tracer provider exists).

    Returns the :class:`TracerProvider` when tracing is on, or ``None`` on the
    no-op path (disabled, no endpoint, or a build failure). Never raises.
    """
    if not _traces_active():
        logger.debug("otel traces off (OTEL_TRACES_EXPORTER != otlp or no endpoint)")
        return None

    endpoint = _resolve_endpoint("TRACES")
    # Wrapped because this runs on a startup path: a broken exporter must
    # degrade telemetry, not stop the service.
    try:
        name = resolve_service_name(service_name)
        provider = TracerProvider(resource=_build_resource(name, service_version))
        provider.add_span_processor(
            BatchSpanProcessor(_make_span_exporter(endpoint))
        )
        trace.set_tracer_provider(provider)
    except Exception:
        logger.exception("otel trace setup failed; continuing without telemetry")
        return None

    logger.info(
        "otel traces enabled (service.name=%s protocol=%s endpoint=%s)",
        name,
        _protocol(),
        endpoint,
    )
    return provider


def instrument_fastapi(app: Any) -> None:
    """Instrument a FastAPI app — only when tracing is actually on, so an
    unconfigured deployment gets the same middleware stack as before."""
    if not _traces_active():
        return
    try:
        FastAPIInstrumentor.instrument_app(app)
    except Exception:
        logger.exception("otel fastapi instrumentation failed; continuing")
    else:
        logger.info("otel fastapi instrumented")


def setup_logging_export(
    service_name: Optional[str] = None,
    service_version: str = __version__,
) -> Any:
    """Ship this process's logs over OTLP.

    Off unless the standard ``OTEL_LOGS_EXPORTER`` is ``otlp`` and a log
    endpoint exists — no extra variable. cc-catalog-svc logs through the stdlib
    (``logging.basicConfig``), so one root handler captures everything; the SDK
    handler stamps each record with the active span's trace/span id, which is
    what lets OpenObserve correlate logs to traces.

    Returns the LoggerProvider, or ``None`` when disabled/unconfigured.
    """
    global _logger_provider

    if _sdk_disabled():
        return None
    if not _signal_enabled("OTEL_LOGS_EXPORTER"):
        return None
    endpoint = _resolve_endpoint("LOGS")
    if endpoint is None:
        # Same rule as tracing: no endpoint means nothing to ship to.
        return None
    if _logger_provider is not None:
        return _logger_provider

    # Wrapped because this runs on a startup path.
    try:
        from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
        from opentelemetry.sdk._logs.export import BatchLogRecordProcessor

        name = resolve_service_name(service_name)
        provider = LoggerProvider(resource=_build_resource(name, service_version))
        provider.add_log_record_processor(
            BatchLogRecordProcessor(_make_log_exporter(endpoint))
        )
        # Root logger: captures every record the stdlib pipeline emits.
        logging.getLogger().addHandler(LoggingHandler(logger_provider=provider))
    except Exception:
        logger.exception("otel log setup failed; continuing without log export")
        return None

    _logger_provider = provider
    logger.info(
        "otel log export enabled (service.name=%s protocol=%s endpoint=%s)",
        name,
        _protocol(),
        endpoint,
    )
    return provider


def setup_metrics(
    service_name: Optional[str] = None,
    service_version: str = __version__,
) -> Any:
    """Export metrics over OTLP.

    Off unless the standard ``OTEL_METRICS_EXPORTER`` is ``otlp`` and a metrics
    endpoint exists. A MeterProvider is enough for the FastAPI instrumentor
    already installed here to emit its standard HTTP metrics; no extra
    instrumentation package is needed.
    """
    global _meter_provider

    if _sdk_disabled():
        return None
    if not _signal_enabled("OTEL_METRICS_EXPORTER"):
        return None
    endpoint = _resolve_endpoint("METRICS")
    if endpoint is None:
        return None
    if _meter_provider is not None:
        return _meter_provider

    # Wrapped because this runs on a startup path.
    try:
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader

        name = resolve_service_name(service_name)
        # export_interval_millis is deliberately NOT passed: the SDK's
        # PeriodicExportingMetricReader already reads OTEL_METRIC_EXPORT_INTERVAL
        # itself, and parsing it here would turn a typo'd env var into a
        # ValueError on a startup path.
        provider = MeterProvider(
            resource=_build_resource(name, service_version),
            metric_readers=[
                PeriodicExportingMetricReader(_make_metric_exporter(endpoint))
            ],
        )
        metrics.set_meter_provider(provider)
    except Exception:
        logger.exception("otel metric setup failed; continuing without metrics")
        return None

    _meter_provider = provider
    logger.info(
        "otel metrics enabled (service.name=%s protocol=%s endpoint=%s)",
        name,
        _protocol(),
        endpoint,
    )
    return provider


def get_tracer(name: str) -> trace.Tracer:
    """Get a tracer for the given module/component name."""
    return trace.get_tracer(name)


def shutdown_telemetry() -> None:
    """Flush and shut down every provider this module configured.

    Runs on the way out; a failure here must not mask the real exit, hence the
    per-provider try/except.
    """
    global _logger_provider, _meter_provider

    for provider in (trace.get_tracer_provider(), _logger_provider, _meter_provider):
        if provider is None:
            continue
        shutdown = getattr(provider, "shutdown", None)
        if shutdown is None:
            continue
        try:
            shutdown()
        except Exception:
            logger.exception(
                "otel provider shutdown failed (%s)", type(provider).__name__
            )

    _logger_provider = None
    _meter_provider = None
    logger.info("otel shutdown complete")
