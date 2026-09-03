import os
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor

def configure_tracing(exporter=None):
    provider = TracerProvider(resource=Resource.create({"service.name": "catalog-service"}))
    if os.getenv("OTEL_SDK_DISABLED", "false").lower() == "true":
        pass
    elif exporter is None:
        exporter = OTLPSpanExporter(endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317"), insecure=True)
        provider.add_span_processor(BatchSpanProcessor(exporter))
    else:
        provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider
