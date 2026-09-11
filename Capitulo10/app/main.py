from time import perf_counter
from fastapi import FastAPI, Request
from fastapi.responses import Response
from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from app.tracing import configure_tracing

REQUESTS = Counter("catalog_http_requests_total", "Peticiones HTTP", ["method", "route", "status"])
DURATION = Histogram("catalog_http_request_duration_seconds", "Duración HTTP", ["route"])
PRODUCTS = {"p-1": {"id": "p-1", "name": "Keyboard", "stock": 8}}

def create_app(exporter=None):
    tracer_provider = configure_tracing(exporter)
    tracer = tracer_provider.get_tracer(__name__)
    app = FastAPI(title="catalog-service")

    @app.middleware("http")
    async def metrics(request: Request, call_next):
        started = perf_counter()  # LAB-METRIC: reloj monotónico
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            route = request.scope.get("route")
            template = getattr(route, "path", request.url.path)
            REQUESTS.labels(request.method, template, str(status_code)).inc()
            DURATION.labels(template).observe(perf_counter() - started)

    @app.get("/health")
    async def health(): return {"status": "healthy"}

    @app.get("/products/{product_id}")
    async def product(product_id: str, request: Request):
        with tracer.start_as_current_span("catalog.lookup") as span:  # LAB-TRACE
            span.set_attribute("catalog.found", product_id in PRODUCTS)
            request_id = request.headers.get("x-request-id")
            if request_id:
                span.set_attribute("request.id", request_id)
            return PRODUCTS.get(product_id) or Response(status_code=404)

    @app.get("/fail")
    async def controlled_failure():
        raise RuntimeError("controlled lab failure")

    @app.get("/metrics", include_in_schema=False)
    async def prometheus_metrics(): return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    FastAPIInstrumentor.instrument_app(app, tracer_provider=tracer_provider)
    return app

app = create_app()
