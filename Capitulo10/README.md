# Instrumentar servicio con Prometheus, Grafana y Jaeger

## 1. Metadatos

| Campo | Valor |
|-------|-------|
| **Duración** | 64 minutos |
| **Complejidad** | Alta |
| **Nivel Bloom** | Aplicar |

## 2. Descripción General

En este laboratorio instrumentarás el `catalog-service` (construido en labs anteriores) con métricas Prometheus custom, tracing distribuido con OpenTelemetry/Jaeger y desplegarás el stack completo de observabilidad en Kubernetes. Al finalizar, dispondrás de dashboards Grafana con 6 paneles operativos, trazas end-to-end que cubren FastAPI → Redis → PostgreSQL, y alertas Prometheus para SLOs de latencia y error rate.

## 3. Objetivos de Aprendizaje

- [ ] Instrumentar `catalog-service` con `prometheus-client` exponiendo métricas custom de negocio (cache hit/miss) y técnicas (latencia, errores, conexiones DB)
- [ ] Desplegar Prometheus, Grafana y Jaeger en Kubernetes mediante Helm charts oficiales
- [ ] Configurar ServiceMonitor para scraping automático y crear un dashboard Grafana con 6 paneles PromQL
- [ ] Implementar tracing distribuido con OpenTelemetry SDK exportando trazas a Jaeger con spans para PostgreSQL y Redis
- [ ] Definir alertas Prometheus para error_rate > 5% y latencia P95 > 500ms

## 4. Prerrequisitos

### Conocimientos previos
- Familiaridad con FastAPI, Docker y Kubernetes (labs 01-09 completados)
- Comprensión básica de PromQL y tipos de métricas Prometheus (Lección 10.1)
- Experiencia con Helm para despliegue de charts

### Acceso y recursos
- Minikube corriendo con al menos 4 GB de RAM asignados al cluster
- Helm 3.15+ instalado y configurado
- Ecosistema de labs 06-09 operativo (catalog-service con Redis y PostgreSQL)
- Conexión a Internet para descargar charts e imágenes

## 5. Entorno del Laboratorio

### Software requerido

| Herramienta | Versión | Propósito |
|-------------|---------|-----------|
| Python | 3.12.3 | Runtime del servicio |
| prometheus-client | 0.20.0 | Instrumentación de métricas |
| opentelemetry-sdk | 1.25.0 | Tracing distribuido |
| opentelemetry-instrumentation-fastapi | 0.46b0 | Auto-instrumentación FastAPI |
| opentelemetry-instrumentation-sqlalchemy | 0.46b0 | Trazas PostgreSQL |
| opentelemetry-exporter-jaeger | 1.21.0 | Exportación de trazas |
| Helm | 3.15.2 | Despliegue de charts |
| Minikube | 1.33.1 | Cluster Kubernetes local |

### Configuración inicial del entorno

```bash
# Verificar que Minikube está corriendo
minikube status

# Asegurar suficiente memoria (reiniciar si es necesario)
# minikube start --memory=6144 --cpus=4

# Crear directorio de trabajo
mkdir -p ~/microservicios-curso/lab10
cd ~/microservicios-curso/lab10

# Crear namespace de monitoring
kubectl create namespace monitoring --dry-run=client -o yaml | kubectl apply -f -

# Verificar namespace microservicios-curso existe
kubectl get namespace microservicios-curso

# Agregar repositorios Helm necesarios
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add grafana https://grafana.github.io/helm-charts
helm repo add jaegertracing https://jaegertracing.github.io/helm-charts
helm repo update
```

## 6. Pasos del Laboratorio

---

### Paso 1: Instrumentar catalog-service con métricas Prometheus

**Objetivo:** Añadir métricas custom de negocio y técnicas al catalog-service usando `prometheus-client`.

**Instrucciones:**

1. Navega al directorio del catalog-service y crea el módulo de métricas:

```bash
cd ~/microservicios-curso/lab10
mkdir -p catalog-service
cd catalog-service
```

2. Crea el archivo `requirements.txt` con las dependencias de observabilidad:

```bash
cat > requirements.txt << 'EOF'
fastapi==0.111.0
uvicorn==0.30.1
pydantic==2.7.1
redis==5.0.4
sqlalchemy==2.0.30
psycopg2-binary==2.9.9
prometheus-client==0.20.0
opentelemetry-sdk==1.25.0
opentelemetry-api==1.25.0
opentelemetry-instrumentation-fastapi==0.46b0
opentelemetry-instrumentation-sqlalchemy==0.46b0
opentelemetry-instrumentation-redis==0.46b0
opentelemetry-exporter-jaeger==1.21.0
httpx==0.27.0
EOF
```

3. Crea el módulo de métricas `metrics.py`:

```bash
cat > metrics.py << 'EOF'
"""Módulo de métricas Prometheus para catalog-service."""
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

# --- Métricas técnicas ---
REQUEST_COUNT = Counter(
    "catalog_http_requests_total",
    "Total de peticiones HTTP al catalog-service",
    ["method", "endpoint", "status_code"]
)

REQUEST_LATENCY = Histogram(
    "catalog_http_request_duration_seconds",
    "Latencia de peticiones HTTP en segundos",
    ["method", "endpoint"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
)

ERROR_COUNT = Counter(
    "catalog_errors_total",
    "Total de errores en catalog-service",
    ["type", "endpoint"]
)

# --- Métricas de negocio (cache) ---
CACHE_HIT_TOTAL = Counter(
    "catalog_cache_hit_total",
    "Total de cache hits en Redis",
    ["operation"]
)

CACHE_MISS_TOTAL = Counter(
    "catalog_cache_miss_total",
    "Total de cache misses en Redis",
    ["operation"]
)

# --- Métricas de infraestructura ---
DB_CONNECTIONS_ACTIVE = Gauge(
    "catalog_db_connections_active",
    "Conexiones activas al pool de PostgreSQL"
)

DB_OPERATION_DURATION = Histogram(
    "catalog_db_operation_duration_seconds",
    "Duración de operaciones de base de datos",
    ["operation", "table"],
    buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0]
)

ACTIVE_REQUESTS = Gauge(
    "catalog_active_requests",
    "Número de requests activas en procesamiento"
)
EOF
```

4. Crea el archivo principal `main.py` con el middleware de métricas:

```bash
cat > main.py << 'EOF'
"""catalog-service con instrumentación Prometheus y OpenTelemetry."""
import time
import json
import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from metrics import (
    REQUEST_COUNT, REQUEST_LATENCY, ERROR_COUNT,
    CACHE_HIT_TOTAL, CACHE_MISS_TOTAL,
    DB_CONNECTIONS_ACTIVE, DB_OPERATION_DURATION, ACTIVE_REQUESTS
)
from tracing import setup_tracing

# Configuración
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://catalog:catalog@localhost:5432/catalog")
JAEGER_ENDPOINT = os.getenv("JAEGER_ENDPOINT", "http://localhost:14268/api/traces")
SERVICE_NAME = "catalog-service"

# Simulación de cache y DB para demostración
import redis
import sqlalchemy
from sqlalchemy import create_engine, Column, Integer, String, Float, text
from sqlalchemy.orm import sessionmaker, declarative_base

Base = declarative_base()


class Product(BaseModel):
    id: Optional[int] = None
    name: str
    price: float
    category: str


class ProductDB(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    price = Column(Float, nullable=False)
    category = Column(String(100), nullable=False)


# Inicialización
redis_client = None
engine = None
SessionLocal = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ciclo de vida de la aplicación."""
    global redis_client, engine, SessionLocal

    # Conectar Redis
    try:
        redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        redis_client.ping()
        print(f"✓ Conectado a Redis: {REDIS_URL}")
    except Exception as e:
        print(f"⚠ Redis no disponible: {e}. Continuando sin cache.")
        redis_client = None

    # Conectar PostgreSQL
    try:
        engine = create_engine(DATABASE_URL, pool_size=5, max_overflow=10)
        SessionLocal = sessionmaker(bind=engine)
        Base.metadata.create_all(engine)
        print(f"✓ Conectado a PostgreSQL: {DATABASE_URL}")
    except Exception as e:
        print(f"⚠ PostgreSQL no disponible: {e}. Usando almacenamiento en memoria.")
        engine = None

    # Setup tracing
    setup_tracing(SERVICE_NAME, JAEGER_ENDPOINT)

    yield

    # Cleanup
    if redis_client:
        redis_client.close()
    if engine:
        engine.dispose()


app = FastAPI(title="catalog-service", version="3.0.0", lifespan=lifespan)


@app.middleware("http")
async def observability_middleware(request: Request, call_next):
    """Middleware que registra métricas de cada petición."""
    if request.url.path == "/metrics":
        return await call_next(request)

    ACTIVE_REQUESTS.inc()
    start_time = time.time()

    try:
        response = await call_next(request)
        duration = time.time() - start_time

        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=request.url.path,
            status_code=response.status_code
        ).inc()

        REQUEST_LATENCY.labels(
            method=request.method,
            endpoint=request.url.path
        ).observe(duration)

        if response.status_code >= 500:
            ERROR_COUNT.labels(
                type="http_5xx",
                endpoint=request.url.path
            ).inc()

        return response
    except Exception as exc:
        duration = time.time() - start_time
        ERROR_COUNT.labels(type="unhandled", endpoint=request.url.path).inc()
        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=request.url.path,
            status_code=500
        ).inc()
        REQUEST_LATENCY.labels(
            method=request.method,
            endpoint=request.url.path
        ).observe(duration)
        raise exc
    finally:
        ACTIVE_REQUESTS.dec()


@app.get("/metrics")
def prometheus_metrics():
    """Endpoint de métricas para scraping de Prometheus."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/health")
def health_check():
    """Endpoint de salud."""
    return {"status": "healthy", "service": SERVICE_NAME}


@app.get("/products")
def list_products():
    """Listar productos con cache Redis."""
    from opentelemetry import trace
    tracer = trace.get_tracer(__name__)

    with tracer.start_as_current_span("list_products"):
        # Intentar cache
        if redis_client:
            with tracer.start_as_current_span("redis_get"):
                cached = redis_client.get("products:all")
                if cached:
                    CACHE_HIT_TOTAL.labels(operation="list_products").inc()
                    return {"products": json.loads(cached), "source": "cache"}
                CACHE_MISS_TOTAL.labels(operation="list_products").inc()

        # Consultar DB
        if engine:
            with tracer.start_as_current_span("db_query_products"):
                start_db = time.time()
                session = SessionLocal()
                try:
                    # Actualizar gauge de conexiones
                    pool_status = engine.pool.status()
                    DB_CONNECTIONS_ACTIVE.set(engine.pool.checkedout())

                    products = session.query(ProductDB).all()
                    result = [
                        {"id": p.id, "name": p.name, "price": p.price, "category": p.category}
                        for p in products
                    ]

                    DB_OPERATION_DURATION.labels(
                        operation="SELECT", table="products"
                    ).observe(time.time() - start_db)

                    # Guardar en cache
                    if redis_client:
                        with tracer.start_as_current_span("redis_set"):
                            redis_client.setex("products:all", 60, json.dumps(result))

                    return {"products": result, "source": "database"}
                finally:
                    session.close()

        return {"products": [], "source": "empty"}


@app.post("/products", status_code=201)
def create_product(product: Product):
    """Crear producto e invalidar cache."""
    from opentelemetry import trace
    tracer = trace.get_tracer(__name__)

    with tracer.start_as_current_span("create_product"):
        if engine:
            with tracer.start_as_current_span("db_insert_product"):
                start_db = time.time()
                session = SessionLocal()
                try:
                    db_product = ProductDB(
                        name=product.name,
                        price=product.price,
                        category=product.category
                    )
                    session.add(db_product)
                    session.commit()
                    session.refresh(db_product)

                    DB_OPERATION_DURATION.labels(
                        operation="INSERT", table="products"
                    ).observe(time.time() - start_db)

                    # Invalidar cache
                    if redis_client:
                        with tracer.start_as_current_span("redis_delete"):
                            redis_client.delete("products:all")

                    return {
                        "id": db_product.id,
                        "name": db_product.name,
                        "price": db_product.price,
                        "category": db_product.category
                    }
                finally:
                    session.close()

        raise HTTPException(status_code=503, detail="Database not available")


@app.get("/products/{product_id}")
def get_product(product_id: int):
    """Obtener producto por ID con cache."""
    from opentelemetry import trace
    tracer = trace.get_tracer(__name__)

    with tracer.start_as_current_span("get_product", attributes={"product.id": product_id}):
        cache_key = f"products:{product_id}"

        if redis_client:
            with tracer.start_as_current_span("redis_get"):
                cached = redis_client.get(cache_key)
                if cached:
                    CACHE_HIT_TOTAL.labels(operation="get_product").inc()
                    return {"product": json.loads(cached), "source": "cache"}
                CACHE_MISS_TOTAL.labels(operation="get_product").inc()

        if engine:
            with tracer.start_as_current_span("db_query_product_by_id"):
                start_db = time.time()
                session = SessionLocal()
                try:
                    product = session.query(ProductDB).filter(
                        ProductDB.id == product_id
                    ).first()

                    DB_OPERATION_DURATION.labels(
                        operation="SELECT", table="products"
                    ).observe(time.time() - start_db)

                    if not product:
                        raise HTTPException(status_code=404, detail="Product not found")

                    result = {
                        "id": product.id,
                        "name": product.name,
                        "price": product.price,
                        "category": product.category
                    }

                    if redis_client:
                        redis_client.setex(cache_key, 60, json.dumps(result))

                    return {"product": result, "source": "database"}
                finally:
                    session.close()

        raise HTTPException(status_code=503, detail="Database not available")
EOF
```

5. Crea el módulo de tracing `tracing.py`:

```bash
cat > tracing.py << 'EOF'
"""Configuración de OpenTelemetry tracing para catalog-service."""
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor


def setup_tracing(service_name: str, jaeger_endpoint: str):
    """Inicializa OpenTelemetry con exportador Jaeger."""
    resource = Resource.create({
        "service.name": service_name,
        "service.version": "3.0.0",
        "deployment.environment": "kubernetes"
    })

    provider = TracerProvider(resource=resource)

    # Configurar exportador Jaeger
    jaeger_exporter = JaegerExporter(
        collector_endpoint=jaeger_endpoint,
    )
    processor = BatchSpanProcessor(jaeger_exporter)
    provider.add_span_processor(processor)

    trace.set_tracer_provider(provider)

    # Auto-instrumentación
    RedisInstrumentor().instrument()
    SQLAlchemyInstrumentor().instrument()

    print(f"✓ Tracing configurado: exportando a {jaeger_endpoint}")
EOF
```

**Salida esperada:**

Archivos creados en `~/microservicios-curso/lab10/catalog-service/`:
- `requirements.txt`
- `metrics.py`
- `main.py`
- `tracing.py`

**Verificación:**

```bash
ls -la ~/microservicios-curso/lab10/catalog-service/
# Debe mostrar los 4 archivos creados
```

---

### Paso 2: Construir imagen Docker del catalog-service instrumentado

**Objetivo:** Crear un Dockerfile optimizado y construir la imagen con todas las dependencias de observabilidad.

**Instrucciones:**

1. Crea el Dockerfile:

```bash
cd ~/microservicios-curso/lab10/catalog-service

cat > Dockerfile << 'EOF'
FROM python:3.12-slim AS builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.12-slim

WORKDIR /app

# Copiar dependencias instaladas
COPY --from=builder /install /usr/local

# Copiar código fuente
COPY metrics.py .
COPY tracing.py .
COPY main.py .

# Usuario no-root
RUN useradd -m -r appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
EOF
```

2. Construye la imagen dentro de Minikube:

```bash
# Usar el Docker daemon de Minikube
eval $(minikube docker-env)

# Construir imagen
docker build -t microservicios-curso/catalog-service:3.0.0 .
```

3. Verifica la imagen:

```bash
docker images | grep catalog-service
```

**Salida esperada:**

```
microservicios-curso/catalog-service   3.0.0   abc123def456   5 seconds ago   185MB
```

**Verificación:**

```bash
# Verificar que la imagen se construyó correctamente
docker run --rm microservicios-curso/catalog-service:3.0.0 python -c "import prometheus_client, opentelemetry; print('OK')"
```

---

### Paso 3: Desplegar stack de observabilidad con Helm

**Objetivo:** Instalar Prometheus, Grafana y Jaeger en el namespace `monitoring` usando Helm charts oficiales.

**Instrucciones:**

1. Crea el archivo de valores para Prometheus:

```bash
cd ~/microservicios-curso/lab10
mkdir -p helm-values

cat > helm-values/prometheus-values.yaml << 'EOF'
server:
  global:
    scrape_interval: 15s
    evaluation_interval: 15s
  persistentVolume:
    enabled: false
  service:
    type: NodePort
    nodePort: 30090

alertmanager:
  enabled: true
  persistentVolume:
    enabled: false

pushgateway:
  enabled: false

# Habilitar ServiceMonitor CRD
serverFiles:
  alerting_rules.yml:
    groups:
      - name: catalog-service-alerts
        rules:
          - alert: HighErrorRate
            expr: |
              (
                sum(rate(catalog_http_requests_total{status_code=~"5.."}[5m]))
                /
                sum(rate(catalog_http_requests_total[5m]))
              ) > 0.05
            for: 2m
            labels:
              severity: critical
            annotations:
              summary: "Error rate alto en catalog-service"
              description: "Error rate supera 5% durante 2 minutos"
          - alert: HighLatencyP95
            expr: |
              histogram_quantile(0.95, 
                sum(rate(catalog_http_request_duration_seconds_bucket[5m])) by (le)
              ) > 0.5
            for: 2m
            labels:
              severity: warning
            annotations:
              summary: "Latencia P95 alta en catalog-service"
              description: "Latencia P95 supera 500ms durante 2 minutos"

extraScrapeConfigs: |
  - job_name: 'catalog-service'
    kubernetes_sd_configs:
      - role: pod
        namespaces:
          names:
            - microservicios-curso
    relabel_configs:
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
        action: keep
        regex: true
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_port]
        action: replace
        target_label: __address__
        regex: (.+)
        replacement: ${1}:8000
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_path]
        action: replace
        target_label: __metrics_path__
        regex: (.+)
EOF
```

2. Crea el archivo de valores para Grafana:

```bash
cat > helm-values/grafana-values.yaml << 'EOF'
adminUser: admin
adminPassword: observability2024

service:
  type: NodePort
  nodePort: 30030

persistence:
  enabled: false

datasources:
  datasources.yaml:
    apiVersion: 1
    datasources:
      - name: Prometheus
        type: prometheus
        url: http://prometheus-server.monitoring.svc.cluster.local:80
        access: proxy
        isDefault: true
      - name: Jaeger
        type: jaeger
        url: http://jaeger-query.monitoring.svc.cluster.local:16686
        access: proxy

dashboardProviders:
  dashboardproviders.yaml:
    apiVersion: 1
    providers:
      - name: 'default'
        orgId: 1
        folder: 'Microservicios'
        type: file
        disableDeletion: false
        editable: true
        options:
          path: /var/lib/grafana/dashboards/default

dashboardsConfigMaps:
  default: grafana-catalog-dashboard
EOF
```

3. Instala Prometheus:

```bash
helm install prometheus prometheus-community/prometheus \
  --namespace monitoring \
  --values helm-values/prometheus-values.yaml \
  --version 25.21.0 \
  --wait --timeout 5m
```

4. Instala Jaeger all-in-one:

```bash
cat > helm-values/jaeger-values.yaml << 'EOF'
provisionDataStore:
  cassandra: false

allInOne:
  enabled: true
  image:
    tag: "1.57.0"
  extraEnv:
    - name: COLLECTOR_OTLP_ENABLED
      value: "true"

storage:
  type: memory

collector:
  enabled: false

query:
  enabled: false
  service:
    type: NodePort
    nodePort: 30086

agent:
  enabled: false
EOF

helm install jaeger jaegertracing/jaeger \
  --namespace monitoring \
  --values helm-values/jaeger-values.yaml \
  --version 3.1.1 \
  --wait --timeout 3m
```

5. Crea el ConfigMap del dashboard de Grafana antes de instalar:

```bash
cat > grafana-dashboard.json << 'EOF'
{
  "annotations": {"list": []},
  "editable": true,
  "fiscalYearStartMonth": 0,
  "graphTooltip": 0,
  "id": null,
  "links": [],
  "panels": [
    {
      "title": "Requests Per Second (RPS)",
      "type": "timeseries",
      "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0},
      "targets": [
        {
          "expr": "sum(rate(catalog_http_requests_total[5m])) by (endpoint)",
          "legendFormat": "{{endpoint}}"
        }
      ]
    },
    {
      "title": "Latencia P50 / P95 / P99",
      "type": "timeseries",
      "gridPos": {"h": 8, "w": 12, "x": 12, "y": 0},
      "targets": [
        {
          "expr": "histogram_quantile(0.50, sum(rate(catalog_http_request_duration_seconds_bucket[5m])) by (le))",
          "legendFormat": "P50"
        },
        {
          "expr": "histogram_quantile(0.95, sum(rate(catalog_http_request_duration_seconds_bucket[5m])) by (le))",
          "legendFormat": "P95"
        },
        {
          "expr": "histogram_quantile(0.99, sum(rate(catalog_http_request_duration_seconds_bucket[5m])) by (le))",
          "legendFormat": "P99"
        }
      ]
    },
    {
      "title": "Error Rate (%)",
      "type": "stat",
      "gridPos": {"h": 8, "w": 6, "x": 0, "y": 8},
      "targets": [
        {
          "expr": "sum(rate(catalog_http_requests_total{status_code=~\"5..\"}[5m])) / sum(rate(catalog_http_requests_total[5m])) * 100",
          "legendFormat": "Error %"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "thresholds": {
            "steps": [
              {"color": "green", "value": null},
              {"color": "yellow", "value": 2},
              {"color": "red", "value": 5}
            ]
          }
        }
      }
    },
    {
      "title": "Cache Hit Ratio",
      "type": "gauge",
      "gridPos": {"h": 8, "w": 6, "x": 6, "y": 8},
      "targets": [
        {
          "expr": "sum(rate(catalog_cache_hit_total[5m])) / (sum(rate(catalog_cache_hit_total[5m])) + sum(rate(catalog_cache_miss_total[5m]))) * 100",
          "legendFormat": "Hit %"
        }
      ],
      "fieldConfig": {
        "defaults": {
          "max": 100,
          "min": 0,
          "thresholds": {
            "steps": [
              {"color": "red", "value": null},
              {"color": "yellow", "value": 50},
              {"color": "green", "value": 80}
            ]
          }
        }
      }
    },
    {
      "title": "DB Connection Pool",
      "type": "timeseries",
      "gridPos": {"h": 8, "w": 6, "x": 12, "y": 8},
      "targets": [
        {
          "expr": "catalog_db_connections_active",
          "legendFormat": "Active Connections"
        }
      ]
    },
    {
      "title": "Pod Count",
      "type": "stat",
      "gridPos": {"h": 8, "w": 6, "x": 18, "y": 8},
      "targets": [
        {
          "expr": "count(up{job=\"catalog-service\"} == 1)",
          "legendFormat": "Running Pods"
        }
      ]
    }
  ],
  "schemaVersion": 39,
  "tags": ["microservicios", "catalog"],
  "templating": {"list": []},
  "time": {"from": "now-15m", "to": "now"},
  "title": "Catalog Service - Observability",
  "uid": "catalog-obs-001"
}
EOF

# Crear ConfigMap en Kubernetes
kubectl create configmap grafana-catalog-dashboard \
  --from-file=catalog-dashboard.json=grafana-dashboard.json \
  --namespace monitoring \
  --dry-run=client -o yaml | kubectl apply -f -
```

6. Instala Grafana:

```bash
helm install grafana grafana/grafana \
  --namespace monitoring \
  --values helm-values/grafana-values.yaml \
  --version 8.0.0 \
  --wait --timeout 3m
```

**Salida esperada:**

```
NAME: prometheus
STATUS: deployed

NAME: jaeger
STATUS: deployed

NAME: grafana
STATUS: deployed
```

**Verificación:**

```bash
# Verificar todos los pods en monitoring
kubectl get pods -n monitoring
# Todos deben estar en Running/Ready

# Verificar servicios
kubectl get svc -n monitoring
```

---

### Paso 4: Desplegar catalog-service con manifiesto Kubernetes

**Objetivo:** Desplegar el catalog-service instrumentado con las anotaciones de Prometheus y variables de entorno para Jaeger.

**Instrucciones:**

1. Crea los manifiestos de Kubernetes:

```bash
cd ~/microservicios-curso/lab10
mkdir -p k8s

cat > k8s/catalog-deployment.yaml << 'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: catalog-service
  namespace: microservicios-curso
  labels:
    app: catalog-service
    version: "3.0.0"
spec:
  replicas: 2
  selector:
    matchLabels:
      app: catalog-service
  template:
    metadata:
      labels:
        app: catalog-service
        version: "3.0.0"
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8000"
        prometheus.io/path: "/metrics"
    spec:
      containers:
        - name: catalog-service
          image: microservicios-curso/catalog-service:3.0.0
          imagePullPolicy: Never
          ports:
            - containerPort: 8000
              name: http
          env:
            - name: REDIS_URL
              value: "redis://redis-service.microservicios-curso.svc.cluster.local:6379/0"
            - name: DATABASE_URL
              value: "postgresql://catalog:catalog@postgres-service.microservicios-curso.svc.cluster.local:5432/catalog"
            - name: JAEGER_ENDPOINT
              value: "http://jaeger-collector.monitoring.svc.cluster.local:14268/api/traces"
          resources:
            requests:
              memory: "128Mi"
              cpu: "100m"
            limits:
              memory: "256Mi"
              cpu: "500m"
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 10
            periodSeconds: 30
          readinessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: catalog-service
  namespace: microservicios-curso
  labels:
    app: catalog-service
spec:
  type: NodePort
  selector:
    app: catalog-service
  ports:
    - port: 8000
      targetPort: 8000
      nodePort: 30080
      name: http
EOF
```

2. Crea manifiestos para Redis y PostgreSQL (si no existen de labs anteriores):

```bash
cat > k8s/dependencies.yaml << 'EOF'
# Redis
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
  namespace: microservicios-curso
spec:
  replicas: 1
  selector:
    matchLabels:
      app: redis
  template:
    metadata:
      labels:
        app: redis
    spec:
      containers:
        - name: redis
          image: redis:7-alpine
          ports:
            - containerPort: 6379
          resources:
            requests:
              memory: "64Mi"
              cpu: "50m"
            limits:
              memory: "128Mi"
              cpu: "200m"
---
apiVersion: v1
kind: Service
metadata:
  name: redis-service
  namespace: microservicios-curso
spec:
  selector:
    app: redis
  ports:
    - port: 6379
      targetPort: 6379
---
# PostgreSQL
apiVersion: apps/v1
kind: Deployment
metadata:
  name: postgres
  namespace: microservicios-curso
spec:
  replicas: 1
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
        - name: postgres
          image: postgres:16-alpine
          ports:
            - containerPort: 5432
          env:
            - name: POSTGRES_USER
              value: "catalog"
            - name: POSTGRES_PASSWORD
              value: "catalog"
            - name: POSTGRES_DB
              value: "catalog"
          resources:
            requests:
              memory: "128Mi"
              cpu: "100m"
            limits:
              memory: "256Mi"
              cpu: "500m"
---
apiVersion: v1
kind: Service
metadata:
  name: postgres-service
  namespace: microservicios-curso
spec:
  selector:
    app: postgres
  ports:
    - port: 5432
      targetPort: 5432
EOF
```

3. Aplica los manifiestos:

```bash
# Asegurar namespace existe
kubectl create namespace microservicios-curso --dry-run=client -o yaml | kubectl apply -f -

# Desplegar dependencias primero
kubectl apply -f k8s/dependencies.yaml

# Esperar a que estén listos
kubectl wait --for=condition=ready pod -l app=redis -n microservicios-curso --timeout=60s
kubectl wait --for=condition=ready pod -l app=postgres -n microservicios-curso --timeout=60s

# Desplegar catalog-service
kubectl apply -f k8s/catalog-deployment.yaml

# Esperar a que esté listo
kubectl wait --for=condition=ready pod -l app=catalog-service -n microservicios-curso --timeout=90s
```

**Salida esperada:**

```
deployment.apps/redis created
service/redis-service created
deployment.apps/postgres created
service/postgres-service created
deployment.apps/catalog-service created
service/catalog-service created
pod/catalog-service-xxxxx condition met
```

**Verificación:**

```bash
# Ver todos los pods
kubectl get pods -n microservicios-curso

# Verificar que el endpoint /metrics responde
kubectl port-forward svc/catalog-service 8000:8000 -n microservicios-curso &
sleep 2
curl -s http://localhost:8000/metrics | head -20
kill %1
```

---

### Paso 5: Generar tráfico y verificar métricas en Prometheus

**Objetivo:** Generar tráfico al servicio y confirmar que Prometheus está recopilando las métricas custom.

**Instrucciones:**

1. Crea un script de generación de tráfico:

```bash
cd ~/microservicios-curso/lab10

cat > generate-traffic.sh << 'EOF'
#!/bin/bash
# Script para generar tráfico al catalog-service
SERVICE_URL=$(minikube service catalog-service -n microservicios-curso --url)
echo "Generando tráfico a: $SERVICE_URL"

# Crear productos
for i in $(seq 1 10); do
  curl -s -X POST "$SERVICE_URL/products" \
    -H "Content-Type: application/json" \
    -d "{\"name\": \"Producto $i\", \"price\": $((RANDOM % 100 + 1)).99, \"category\": \"cat-$((i % 3))\"}" > /dev/null
  echo "Producto $i creado"
done

# Generar lecturas (para cache hits/misses)
echo "Generando lecturas..."
for i in $(seq 1 50); do
  curl -s "$SERVICE_URL/products" > /dev/null
  curl -s "$SERVICE_URL/products/$((RANDOM % 10 + 1))" > /dev/null 2>&1
  sleep 0.2
done

# Generar algunos errores 404
echo "Generando requests con errores..."
for i in $(seq 1 5); do
  curl -s "$SERVICE_URL/products/999" > /dev/null 2>&1
done

echo "✓ Tráfico generado: 10 creates, 50 lists, 50 gets, 5 not-found"
EOF

chmod +x generate-traffic.sh
./generate-traffic.sh
```

2. Verifica las métricas en Prometheus:

```bash
# Port-forward a Prometheus
kubectl port-forward svc/prometheus-server 9090:80 -n monitoring &
sleep 2

# Consultar métricas del catalog-service
curl -s "http://localhost:9090/api/v1/query?query=catalog_http_requests_total" | python3 -m json.tool | head -30

# Verificar cache metrics
curl -s "http://localhost:9090/api/v1/query?query=catalog_cache_hit_total" | python3 -m json.tool

# Verificar latencia
curl -s "http://localhost:9090/api/v1/query?query=histogram_quantile(0.95,sum(rate(catalog_http_request_duration_seconds_bucket[5m]))by(le))" | python3 -m json.tool

kill %1
```

**Salida esperada:**

```json
{
  "status": "success",
  "data": {
    "resultType": "vector",
    "result": [
      {
        "metric": {
          "__name__": "catalog_http_requests_total",
          "endpoint": "/products",
          "method": "GET",
          "status_code": "200"
        },
        "value": [1717000000, "50"]
      }
    ]
  }
}
```

**Verificación:**

```bash
# Verificar que Prometheus tiene targets activos
curl -s "http://localhost:9090/api/v1/targets" | python3 -c "
import json, sys
data = json.load(sys.stdin)
targets = data['data']['activeTargets']
catalog_targets = [t for t in targets if 'catalog' in str(t.get('labels', {}))]
print(f'Targets de catalog-service encontrados: {len(catalog_targets)}')
for t in catalog_targets:
    print(f'  - {t[\"scrapeUrl\"]} -> {t[\"health\"]}')
"
```

---

### Paso 6: Verificar trazas en Jaeger

**Objetivo:** Confirmar que las trazas distribuidas se exportan correctamente a Jaeger y muestran spans de FastAPI, Redis y PostgreSQL.

**Instrucciones:**

1. Accede a la UI de Jaeger:

```bash
# Port-forward a Jaeger Query
kubectl port-forward svc/jaeger-query 16686:16686 -n monitoring &
sleep 2

echo "Jaeger UI disponible en: http://localhost:16686"
```

2. Genera tráfico adicional para crear trazas:

```bash
SERVICE_URL=$(minikube service catalog-service -n microservicios-curso --url)

# Crear un producto (generará spans: FastAPI -> DB INSERT -> Redis DELETE)
curl -s -X POST "$SERVICE_URL/products" \
  -H "Content-Type: application/json" \
  -d '{"name": "Producto Traced", "price": 29.99, "category": "electronics"}'

# Leer productos (generará spans: FastAPI -> Redis GET -> DB SELECT -> Redis SET)
curl -s "$SERVICE_URL/products"

# Segunda lectura (generará: FastAPI -> Redis GET [cache hit])
sleep 1
curl -s "$SERVICE_URL/products"
```

3. Consulta las trazas via API de Jaeger:

```bash
# Buscar trazas del catalog-service
curl -s "http://localhost:16686/api/traces?service=catalog-service&limit=5" | python3 -c "
import json, sys
data = json.load(sys.stdin)
traces = data.get('data', [])
print(f'Trazas encontradas: {len(traces)}')
for trace in traces[:3]:
    spans = trace.get('spans', [])
    print(f'  Trace ID: {trace[\"traceID\"][:16]}... ({len(spans)} spans)')
    for span in spans[:5]:
        print(f'    - {span[\"operationName\"]} ({span[\"duration\"]/1000:.1f}ms)')
"
```

**Salida esperada:**

```
Trazas encontradas: 5
  Trace ID: abc123def456789... (4 spans)
    - create_product (15.2ms)
    - db_insert_product (8.1ms)
    - redis_delete (1.3ms)
    - POST /products (16.5ms)
  Trace ID: def456abc789012... (5 spans)
    - list_products (12.8ms)
    - redis_get (0.8ms)
    - db_query_products (9.2ms)
    - redis_set (1.1ms)
    - GET /products (13.5ms)
```

**Verificación:**

```bash
# Verificar que los servicios están registrados en Jaeger
curl -s "http://localhost:16686/api/services" | python3 -c "
import json, sys
data = json.load(sys.stdin)
services = data.get('data', [])
print('Servicios registrados en Jaeger:')
for svc in services:
    print(f'  ✓ {svc}')
assert 'catalog-service' in services, 'catalog-service no encontrado en Jaeger'
print('\n✓ catalog-service registrado correctamente')
"

kill %1  # Cerrar port-forward de Jaeger
```

---

### Paso 7: Acceder a Grafana y verificar el dashboard

**Objetivo:** Confirmar que el dashboard con los 6 paneles se cargó correctamente y muestra datos.

**Instrucciones:**

1. Accede a Grafana:

```bash
# Port-forward a Grafana
kubectl port-forward svc/grafana 3000:80 -n monitoring &
sleep 2

echo "Grafana disponible en: http://localhost:3000"
echo "Usuario: admin"
echo "Password: observability2024"
```

2. Verifica el dashboard via API:

```bash
# Login y obtener token
GRAFANA_TOKEN=$(curl -s -X POST "http://localhost:3000/api/auth/keys" \
  -H "Content-Type: application/json" \
  -u admin:observability2024 \
  -d '{"name":"lab-verify","role":"Admin"}' | python3 -c "import json,sys; print(json.load(sys.stdin).get('key',''))")

# Si el token falla, usar basic auth
# Verificar dashboard existe
curl -s -u admin:observability2024 \
  "http://localhost:3000/api/dashboards/uid/catalog-obs-001" | python3 -c "
import json, sys
data = json.load(sys.stdin)
dashboard = data.get('dashboard', {})
panels = dashboard.get('panels', [])
print(f'Dashboard: {dashboard.get(\"title\", \"N/A\")}')
print(f'Paneles encontrados: {len(panels)}')
for panel in panels:
    print(f'  - {panel[\"title\"]} ({panel[\"type\"]})')
assert len(panels) == 6, f'Se esperaban 6 paneles, encontrados {len(panels)}'
print('\n✓ Dashboard con 6 paneles verificado')
"
```

3. Verifica que los datasources están configurados:

```bash
curl -s -u admin:observability2024 \
  "http://localhost:3000/api/datasources" | python3 -c "
import json, sys
datasources = json.load(sys.stdin)
print('Datasources configurados:')
for ds in datasources:
    print(f'  ✓ {ds[\"name\"]} ({ds[\"type\"]}) -> {ds[\"url\"]}')
"
```

**Salida esperada:**

```
Dashboard: Catalog Service - Observability
Paneles encontrados: 6
  - Requests Per Second (RPS) (timeseries)
  - Latencia P50 / P95 / P99 (timeseries)
  - Error Rate (%) (stat)
  - Cache Hit Ratio (gauge)
  - DB Connection Pool (timeseries)
  - Pod Count (stat)

✓ Dashboard con 6 paneles verificado

Datasources configurados:
  ✓ Prometheus (prometheus) -> http://prometheus-server.monitoring.svc.cluster.local:80
  ✓ Jaeger (jaeger) -> http://jaeger-query.monitoring.svc.cluster.local:16686
```

**Verificación:**

```bash
# Verificar que Prometheus responde desde Grafana
curl -s -u admin:observability2024 \
  "http://localhost:3000/api/datasources/proxy/1/api/v1/query?query=up" | python3 -c "
import json, sys
data = json.load(sys.stdin)
print(f'Prometheus responde via Grafana: status={data[\"status\"]}')
print(f'Targets activos: {len(data[\"data\"][\"result\"])}')
"

kill %1  # Cerrar port-forward de Grafana
```

---

### Paso 8: Verificar alertas de Prometheus

**Objetivo:** Confirmar que las reglas de alerta están configuradas y evalúan correctamente.

**Instrucciones:**

1. Verifica las reglas de alerta:

```bash
kubectl port-forward svc/prometheus-server 9090:80 -n monitoring &
sleep 2

# Listar reglas de alerta
curl -s "http://localhost:9090/api/v1/rules" | python3 -c "
import json, sys
data = json.load(sys.stdin)
groups = data['data']['groups']
print('Grupos de reglas de alerta:')
for group in groups:
    print(f'\n  Grupo: {group[\"name\"]}')
    for rule in group.get('rules', []):
        state = rule.get('state', 'N/A')
        print(f'    - {rule[\"name\"]} [{state}]')
        print(f'      Expr: {rule[\"query\"][:80]}...')
"
```

2. Verifica el estado actual de las alertas:

```bash
curl -s "http://localhost:9090/api/v1/alerts" | python3 -c "
import json, sys
data = json.load(sys.stdin)
alerts = data['data']['alerts']
if not alerts:
    print('✓ No hay alertas activas (sistema saludable)')
else:
    for alert in alerts:
        print(f'⚠ Alerta: {alert[\"labels\"][\"alertname\"]} - Estado: {alert[\"state\"]}')
"

kill %1
```

**Salida esperada:**

```
Grupos de reglas de alerta:

  Grupo: catalog-service-alerts
    - HighErrorRate [inactive]
      Expr: (sum(rate(catalog_http_requests_total{status_code=~"5.."}[5m]))...
    - HighLatencyP95 [inactive]
      Expr: histogram_quantile(0.95, sum(rate(catalog_http_request_duration_se...

✓ No hay alertas activas (sistema saludable)
```

---

### Paso 9: Commit final al repositorio

**Objetivo:** Guardar todo el trabajo en el repositorio Git con un commit descriptivo.

**Instrucciones:**

1. Realiza el commit:

```bash
cd ~/microservicios-curso

# Agregar archivos del lab 10
git add lab10/

# Commit
git commit -m "[lab10] Instrumentar catalog-service con Prometheus, Grafana y Jaeger

- Añadidas métricas custom: requests, latencia, errores, cache hit/miss, DB connections
- Configurado OpenTelemetry con exportación a Jaeger (spans para Redis y PostgreSQL)
- Desplegado stack observabilidad: Prometheus + Grafana + Jaeger via Helm
- Dashboard Grafana con 6 paneles: RPS, latencia percentiles, error rate, cache ratio, DB pool, pod count
- Alertas Prometheus: error_rate > 5%, latencia P95 > 500ms
- Manifiestos Kubernetes con anotaciones de scraping"
```

**Salida esperada:**

```
[main abc1234] [lab10] Instrumentar catalog-service con Prometheus, Grafana y Jaeger
 8 files changed, 450 insertions(+)
 create mode 100644 lab10/catalog-service/Dockerfile
 create mode 100644 lab10/catalog-service/main.py
 create mode 100644 lab10/catalog-service/metrics.py
 create mode 100644 lab10/catalog-service/tracing.py
 create mode 100644 lab10/catalog-service/requirements.txt
 create mode 100644 lab10/helm-values/prometheus-values.yaml
 create mode 100644 lab10/helm-values/grafana-values.yaml
 create mode 100644 lab10/helm-values/jaeger-values.yaml
 create mode 100644 lab10/k8s/catalog-deployment.yaml
 create mode 100644 lab10/k8s/dependencies.yaml
 create mode 100644 lab10/grafana-dashboard.json
 create mode 100755 lab10/generate-traffic.sh
```

## 7. Validación y Testing

Ejecuta esta verificación integral para confirmar que todo el stack funciona:

```bash
cd ~/microservicios-curso/lab10

cat > validate-lab.sh << 'EOF'
#!/bin/bash
set -e

echo "═══════════════════════════════════════════════"
echo "  VALIDACIÓN INTEGRAL - Lab 10 Observabilidad"
echo "═══════════════════════════════════════════════"

PASS=0
FAIL=0

check() {
  if eval "$2" > /dev/null 2>&1; then
    echo "  ✓ $1"
    PASS=$((PASS + 1))
  else
    echo "  ✗ $1"
    FAIL=$((FAIL + 1))
  fi
}

echo ""
echo "1. Verificando pods en microservicios-curso..."
check "catalog-service running" "kubectl get pods -n microservicios-curso -l app=catalog-service --field-selector=status.phase=Running | grep -q Running"
check "redis running" "kubectl get pods -n microservicios-curso -l app=redis --field-selector=status.phase=Running | grep -q Running"
check "postgres running" "kubectl get pods -n microservicios-curso -l app=postgres --field-selector=status.phase=Running | grep -q Running"

echo ""
echo "2. Verificando stack de observabilidad en monitoring..."
check "prometheus-server running" "kubectl get pods -n monitoring -l app.kubernetes.io/name=prometheus,app.kubernetes.io/component=server --field-selector=status.phase=Running | grep -q Running"
check "grafana running" "kubectl get pods -n monitoring -l app.kubernetes.io/name=grafana --field-selector=status.phase=Running | grep -q Running"
check "jaeger running" "kubectl get pods -n monitoring -l app.kubernetes.io/name=jaeger --field-selector=status.phase=Running | grep -q Running"

echo ""
echo "3. Verificando endpoint /metrics..."
SERVICE_URL=$(minikube service catalog-service -n microservicios-curso --url 2>/dev/null)
check "endpoint /metrics responde" "curl -sf $SERVICE_URL/metrics | grep -q catalog_http_requests_total"
check "métricas de cache presentes" "curl -sf $SERVICE_URL/metrics | grep -q catalog_cache_hit_total"
check "métricas de DB presentes" "curl -sf $SERVICE_URL/metrics | grep -q catalog_db_operation_duration"
check "métricas de latencia presentes" "curl -sf $SERVICE_URL/metrics | grep -q catalog_http_request_duration_seconds"

echo ""
echo "4. Verificando archivos del laboratorio..."
check "main.py existe" "test -f ~/microservicios-curso/lab10/catalog-service/main.py"
check "metrics.py existe" "test -f ~/microservicios-curso/lab10/catalog-service/metrics.py"
check "tracing.py existe" "test -f ~/microservicios-curso/lab10/catalog-service/tracing.py"
check "Dockerfile existe" "test -f ~/microservicios-curso/lab10/catalog-service/Dockerfile"
check "grafana-dashboard.json existe" "test -f ~/microservicios-curso/lab10/grafana-dashboard.json"
check "prometheus-values.yaml existe" "test -f ~/microservicios-curso/lab10/helm-values/prometheus-values.yaml"

echo ""
echo "5. Verificando Git..."
check "commit de lab10 existe" "cd ~/microservicios-curso && git log --oneline | grep -q '\[lab10\]'"

echo ""
echo "═══════════════════════════════════════════════"
echo "  RESULTADO: $PASS passed, $FAIL failed"
echo "═══════════════════════════════════════════════"

if [ $FAIL -eq 0 ]; then
  echo "  🎉 ¡Laboratorio completado exitosamente!"
else
  echo "  ⚠  Revisa los puntos fallidos"
fi
EOF

chmod +x validate-lab.sh
./validate-lab.sh
```

**Resultado esperado:** Todos los checks pasan (16/16 ✓).

## 8. Solución de Problemas

### Problema 1: Prometheus no scrape las métricas del catalog-service

**Síntomas:**
- En Prometheus UI (`/targets`), el target de catalog-service aparece como `DOWN` o no aparece
- Las métricas `catalog_*` no se encuentran al consultar PromQL

**Causa:**
El scrape config de Prometheus no puede resolver las IPs de los pods en el namespace `microservicios-curso`, o las anotaciones del pod no coinciden con la configuración de relabeling.

**Solución:**

```bash
# 1. Verificar que las anotaciones están en el pod
kubectl get pods -n microservicios-curso -l app=catalog-service -o jsonpath='{.items[0].metadata.annotations}'

# Debe mostrar: prometheus.io/scrape:"true", prometheus.io/port:"8000", prometheus.io/path:"/metrics"

# 2. Si faltan anotaciones, re-aplicar el deployment
kubectl apply -f k8s/catalog-deployment.yaml

# 3. Verificar que Prometheus tiene permisos RBAC para leer pods del namespace
kubectl get clusterrole prometheus-server -o yaml | grep -A5 "pods"

# 4. Si el problema persiste, verificar conectividad directa
CATALOG_POD_IP=$(kubectl get pods -n microservicios-curso -l app=catalog-service -o jsonpath='{.items[0].status.podIP}')
kubectl run --rm -it debug --image=curlimages/curl --restart=Never -n monitoring -- curl -s http://$CATALOG_POD_IP:8000/metrics | head -5

# 5. Reiniciar Prometheus para forzar re-descubrimiento
kubectl rollout restart deployment prometheus-server -n monitoring
```

### Problema 2: Las trazas no aparecen en Jaeger

**Síntomas:**
- En Jaeger UI, el servicio `catalog-service` no aparece en el dropdown de servicios
- Al buscar trazas, el resultado está vacío aunque se genera tráfico

**Causa:**
El exportador Jaeger no puede conectar con el collector porque el endpoint está mal configurado o el servicio DNS de Jaeger tiene un nombre diferente al esperado.

**Solución:**

```bash
# 1. Verificar el nombre del servicio Jaeger en el namespace monitoring
kubectl get svc -n monitoring | grep jaeger

# 2. Verificar que el collector está escuchando en el puerto correcto
kubectl get svc jaeger-collector -n monitoring -o jsonpath='{.spec.ports[*].port}'
# Debe incluir 14268 (HTTP Thrift)

# 3. Si el nombre del servicio es diferente, actualizar la variable de entorno
# Por ejemplo, si se llama "jaeger-jaeger-collector":
kubectl set env deployment/catalog-service -n microservicios-curso \
  JAEGER_ENDPOINT="http://jaeger-jaeger-collector.monitoring.svc.cluster.local:14268/api/traces"

# 4. Verificar conectividad desde el pod del catalog-service
kubectl exec -it $(kubectl get pods -n microservicios-curso -l app=catalog-service -o jsonpath='{.items[0].metadata.name}') \
  -n microservicios-curso -- python -c "
import urllib.request
try:
    urllib.request.urlopen('http://jaeger-collector.monitoring.svc.cluster.local:14268/')
    print('✓ Jaeger collector alcanzable')
except Exception as e:
    print(f'✗ Error: {e}')
"

# 5. Verificar logs del catalog-service para errores de tracing
kubectl logs -n microservicios-curso -l app=catalog-service --tail=20 | grep -i "trace\|jaeger\|otel"
```

## 9. Limpieza

Para liberar recursos al finalizar el laboratorio:

```bash
# Eliminar catalog-service y dependencias
kubectl delete -f ~/microservicios-curso/lab10/k8s/ --ignore-not-found

# Desinstalar stack de observabilidad
helm uninstall prometheus -n monitoring
helm uninstall grafana -n monitoring
helm uninstall jaeger -n monitoring

# Eliminar ConfigMap del dashboard
kubectl delete configmap grafana-catalog-dashboard -n monitoring --ignore-not-found

# Eliminar namespace monitoring (opcional, si no se necesita para otros labs)
# kubectl delete namespace monitoring

# Eliminar imagen Docker del cache de Minikube (opcional)
eval $(minikube docker-env)
docker rmi microservicios-curso/catalog-service:3.0.0 2>/dev/null || true

# Cerrar port-forwards activos
pkill -f "kubectl port-forward" 2>/dev/null || true

echo "✓ Limpieza completada"
```

## 10. Resumen

### Lo que has logrado

En este laboratorio has implementado observabilidad completa para un microservicio en producción:

| Componente | Herramienta | Resultado |
|------------|-------------|-----------|
| **Métricas** | Prometheus + prometheus-client | 6 métricas custom (Counter, Histogram, Gauge) con labels multidimensionales |
| **Visualización** | Grafana | Dashboard con 6 paneles: RPS, latencia percentiles, error rate, cache ratio, DB pool, pod count |
| **Tracing** | OpenTelemetry + Jaeger | Trazas distribuidas con spans para FastAPI, Redis y PostgreSQL |
| **Alertas** | Prometheus AlertManager | 2 reglas: error_rate > 5% y latencia P95 > 500ms |
| **Despliegue** | Helm + Kubernetes | Stack completo en namespace `monitoring` con scraping automático |

### Conceptos clave aplicados

- **Modelo pull-based** de Prometheus con anotaciones Kubernetes para service discovery
- **Tipos de métricas**: Counter para totales acumulativos, Histogram para distribuciones de latencia, Gauge para valores instantáneos
- **PromQL** para queries de dashboards y reglas de alerta
- **Context propagation** de OpenTelemetry para correlacionar spans entre servicios
- **Helm values** para configuración declarativa de infraestructura de observabilidad

### Recursos adicionales

- [Prometheus Best Practices — Naming conventions](https://prometheus.io/docs/practices/naming/)
- [OpenTelemetry Python — Getting Started](https://opentelemetry.io/docs/languages/python/getting-started/)
- [Grafana Dashboard Best Practices](https://grafana.com/docs/grafana/latest/dashboards/build-dashboards/best-practices/)
- [USE Method (Utilization, Saturation, Errors)](https://www.brendangregg.com/usemethod.html)
- [RED Method (Rate, Errors, Duration)](https://grafana.com/blog/2018/08/02/the-red-method-how-to-instrument-your-services/)
