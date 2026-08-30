"""OpenTelemetry setup shared by the Python service's two entry points.

Mirrors Prism.ServiceDefaults on the C# side: exports over OTLP/gRPC to
OTEL_EXPORTER_OTLP_ENDPOINT, which Aspire injects for every AppHost resource
(AddDockerfile for the API, AddPythonApp for the worker - see AppHost.cs).
Verified live: Aspire's dashboard OTLP ingestion port is gRPC (HTTP/2),
default localhost:4317, so this uses the grpc exporter rather than the
HTTP/protobuf one.
"""
import os

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


def init_telemetry(service_name: str) -> trace.Tracer:
    """Configures the global TracerProvider and returns a Tracer for service_name.

    No-ops the exporter (spans are created but not shipped anywhere) when
    OTEL_EXPORTER_OTLP_ENDPOINT isn't set, matching the C# ServiceDefaults
    behavior of only exporting when a collector is actually configured.
    """
    provider = TracerProvider(resource=Resource.create({SERVICE_NAME: service_name}))

    if os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))

    trace.set_tracer_provider(provider)
    return trace.get_tracer(service_name)
