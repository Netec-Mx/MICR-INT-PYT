# Instrumentar un servicio con Prometheus, Grafana y Jaeger

## Información de la práctica

| Campo | Valor |
|---|---|
| Duración contractual | **42 minutos** |
| Servicio | `catalog-service` de demostración |
| Tecnologías | Prometheus, Grafana, Jaeger y OpenTelemetry |
| Recursos | Aplicación instrumentada, Compose, configuración y dashboard provisionado |
| Resultado | Métricas consultables, panel RED y una traza con spans relacionados |

## Objetivo

Instrumentar un servicio Python para exponer métricas Prometheus y exportar trazas mediante OTLP a Jaeger; configurar Prometheus como fuente de Grafana y correlacionar una petición entre las tres herramientas.

Cada señal responde preguntas diferentes:

- **Métricas:** tendencias agregadas como tasa, errores y duración.
- **Trazas:** recorrido y tiempos de una petición concreta.
- **Logs:** eventos discretos; se mantienen estructurados, pero ELK/EFK pertenece al contenido teórico y no al objetivo contractual de este laboratorio.

## Mapa del laboratorio

```mermaid
flowchart LR
    A[Generador de tráfico] --> B[catalog-service instrumentado]
    B --> C[/metrics]
    B --> D[Spans OpenTelemetry<br/>por OTLP/gRPC]
    B --> E[Logs estructurados]
    F[Prometheus] -->|scrape periódico| C
    D --> G[Collector / Jaeger]
    F --> H[Grafana: panel RED]
    H --> I[Tasa]
    H --> J[Errores]
    H --> K[Duración]
    G --> L[Traza de una petición<br/>y spans relacionados]
    I & J & K & L --> M{Correlacionar anomalía}
    M --> N[[Explicar qué ocurrió<br/>y dónde se consumió tiempo]]
    E -. contexto adicional .-> M
```

Se espera seguir una petición desde la generación de tráfico hasta dos vistas complementarias: tendencias RED en Grafana y detalle causal de spans en Jaeger.

## Presupuesto temporal

| Actividad | Minutos |
|---|---:|
| Preparación del stack | 8 |
| Métricas Prometheus | 9 |
| Trazas OpenTelemetry/Jaeger | 9 |
| Prometheus y Grafana | 8 |
| Tráfico y correlación | 6 |
| Cierre | 2 |
| **TOTAL** | **42** |

## Prerrequisitos

- Python 3.12 y Docker Compose.
- Puertos `8000`, `9090`, `3000`, `16686` y `4317` libres.
- Al menos 4 GB disponibles para Docker.

El proyecto inicial ya está incluido. No reconstruya Kubernetes, Helm, Redis o PostgreSQL: hacerlo impediría completar la práctica en 42 minutos.

## Arquitectura

```text
cliente --> catalog-service
              |       |
       /metrics       OTLP/gRPC
              |       |
         Prometheus  Jaeger
              |
           Grafana
```

Prometheus extrae métricas; el servicio envía spans al collector. Grafana consulta Prometheus, pero no almacena métricas.

## Paso 1 — Preparar el stack (8 min)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
docker compose up -d --build --wait
docker compose ps
```

En PowerShell active con `\.venv\Scripts\Activate.ps1`.

Comprobaciones:

```bash
curl http://localhost:8000/health
curl http://localhost:9090/-/ready
curl http://localhost:3000/api/health
curl http://localhost:16686/
```

## Paso 2 — Instrumentar métricas (9 min)

Revise los marcadores `LAB-METRIC` en `app/main.py`:

1. `catalog_http_requests_total` cuenta peticiones por método, ruta y estado;
2. `catalog_http_request_duration_seconds` observa duración por ruta;
3. el middleware usa reloj monotónico y registra respuestas normales y excepciones como 500;
4. `/metrics` publica el formato de exposición de Prometheus.

No use identificadores de usuario o producto como labels: su cardinalidad crecería sin límite.

```bash
curl http://localhost:8000/products/p-1
curl http://localhost:8000/products/missing
curl http://localhost:8000/fail
curl http://localhost:8000/metrics | grep '^catalog_http'
```

## Paso 3 — Crear trazas (9 min)

Revise `app/tracing.py` y los marcadores `LAB-TRACE` de `app/main.py`:

- el recurso identifica `catalog-service`;
- `BatchSpanProcessor` exporta por OTLP/gRPC;
- el span HTTP automático contiene un span hijo `catalog.lookup`;
- los errores se reflejan mediante estado y atributos, no con datos sensibles.

El exportador Jaeger Thrift de la guía original se sustituye por OTLP, evitando acoplar la aplicación a un backend concreto.

```bash
curl -H "x-request-id: lab-10" http://localhost:8000/products/p-1
```

Abra `http://localhost:16686`, seleccione `catalog-service` y busque la traza. Debe mostrar el span servidor y `catalog.lookup`.

## Paso 4 — Verificar Prometheus y Grafana (8 min)

Abra `http://localhost:9090/targets`: `catalog-service` debe estar `UP`. Ejecute:

```promql
sum(rate(catalog_http_requests_total[1m])) by (route, status)
```

Abra `http://localhost:3000` con `admin` / `admin-lab`. El dashboard **Catalog RED** ya está provisionado y muestra:

- rate de peticiones;
- tasa de errores 5xx;
- latencia P95 calculada desde el histograma.

El generador incluye respuestas 500 controladas para alimentar el panel de errores. Un panel vacío no implica automáticamente un fallo: genere tráfico y amplíe el rango temporal.

## Paso 5 — Generar tráfico y correlacionar (6 min)

```bash
python scripts/generate_traffic.py
pytest -q
```

Compruebe el mismo intervalo temporal en Grafana y Jaeger. Use métricas para detectar una ruta lenta o errónea y trazas para inspeccionar una petición representativa. No espere correspondencia uno-a-uno: las métricas son agregadas.

Las pruebas verifican salud, métricas 200/404/500, histograma y propagación de `x-request-id` al span `catalog.lookup` con un exportador en memoria.

## Validación final (2 min)

- [ ] Compose muestra los cuatro servicios como `healthy`.
- [ ] Prometheus muestra el target `UP`.
- [ ] `/metrics` incluye contador e histograma propios.
- [ ] Grafana muestra rate, errores y P95.
- [ ] Jaeger contiene `catalog.lookup` dentro de la petición.
- [ ] Puede explicar por qué métricas y trazas se complementan.

## Resultado esperado

Una petición produce métricas Prometheus y una traza OpenTelemetry exportada a Jaeger; Grafana representa las métricas RED sin confundir fuente, almacenamiento y visualización.

## Solución rápida de problemas

- **Target DOWN:** compruebe `http://catalog-service:8000/metrics` desde la red Compose y revise `prometheus/prometheus.yml`.
- **Sin trazas:** revise `docker compose logs catalog-service jaeger` y `OTEL_EXPORTER_OTLP_ENDPOINT`.
- **Grafana vacío:** genere tráfico y seleccione los últimos cinco minutos.
- **Puerto ocupado:** cambie solamente el puerto publicado en Compose.

## Limpieza

```bash
docker compose down
```

La guía original con Minikube, tres instalaciones Helm, dependencias de datos y alertas se conserva en `revision_labs/backups/chapter10/README.before.md` como ampliación fuera del recorrido contractual.

