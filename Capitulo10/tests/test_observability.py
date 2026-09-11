import os
os.environ["OTEL_SDK_DISABLED"] = "true"

from fastapi.testclient import TestClient
from app.main import app, create_app
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

client = TestClient(app)

def test_health():
    assert client.get("/health").json() == {"status": "healthy"}

def test_success_metric_is_exposed():
    client.get("/products/p-1")
    body = client.get("/metrics").text
    assert 'catalog_http_requests_total{method="GET",route="/products/{product_id}",status="200"}' in body

def test_not_found_metric_is_exposed():
    assert client.get("/products/missing").status_code == 404
    body = client.get("/metrics").text
    assert 'route="/products/{product_id}",status="404"' in body

def test_unhandled_error_is_counted_as_500():
    failing_client = TestClient(app, raise_server_exceptions=False)
    assert failing_client.get("/fail").status_code == 500
    assert 'route="/fail",status="500"' in client.get("/metrics").text

def test_histogram_and_request_id_are_traced():
    body = client.get("/metrics").text
    assert "catalog_http_request_duration_seconds_bucket" in body
    exporter = InMemorySpanExporter()
    os.environ["OTEL_SDK_DISABLED"] = "false"
    traced_app = create_app(exporter)
    TestClient(traced_app).get("/products/p-1", headers={"x-request-id": "lab-10"})
    spans = exporter.get_finished_spans()
    lookup = next(span for span in spans if span.name == "catalog.lookup")
    assert lookup.attributes["request.id"] == "lab-10"
