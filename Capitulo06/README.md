# Práctica 6 — Crear un Chart de Helm y Escalar un Deployment

## Metadatos

| Campo | Valor |
|-------|-------|
| **Duración** | 63 minutos |
| **Complejidad** | Media |
| **Nivel Bloom** | Crear |

## Descripción General

En esta práctica crearás desde cero un Helm chart completo para empaquetar el microservicio `inventory-service` (FastAPI/Python). Configurarás templates parametrizados para Deployment, Service, ConfigMap y HPA, desplegarás el chart en Minikube, y validarás el autoescalado horizontal generando carga artificial. Al finalizar, tendrás un chart reutilizable que servirá como base para los laboratorios 7, 9 y 10 del curso.

## Objetivos de Aprendizaje

- [ ] Crear un Helm chart completo con templates de Deployment, Service, HPA y ConfigMap para empaquetar un microservicio Python existente
- [ ] Configurar el Horizontal Pod Autoscaler (HPA) para escalar automáticamente entre 2 y 6 réplicas basándose en uso de CPU al 50%
- [ ] Implementar estrategia de despliegue RollingUpdate con parámetros `maxSurge` y `maxUnavailable` para actualizaciones sin downtime
- [ ] Validar el balanceo de carga entre réplicas usando Services de tipo ClusterIP y NodePort

## Prerrequisitos

### Conocimientos Previos

- Familiaridad con manifiestos YAML de Kubernetes (Deployment, Service)
- Comprensión básica de contenedores Docker y construcción de imágenes
- Experiencia con FastAPI y Python 3.12
- Conceptos de autoescalado horizontal vistos en la lección 6.1

### Acceso y Herramientas

| Herramienta | Versión | Verificación |
|-------------|---------|--------------|
| Minikube | 1.33.1 | `minikube version` |
| kubectl | 1.30.x | `kubectl version --client` |
| Helm | 3.15.x | `helm version` |
| Docker Engine | 26.1.x | `docker --version` |
| Python | 3.12.3 | `python3 --version` |

## Entorno del Laboratorio

### Preparación del Clúster

```bash
# Iniciar Minikube con recursos suficientes (si no está corriendo)
minikube start --cpus=4 --memory=8192 --driver=docker

# Habilitar metrics-server (requerido para HPA)
minikube addons enable metrics-server

# Verificar que metrics-server está activo
kubectl get pods -n kube-system | grep metrics-server

# Crear namespace del curso
kubectl create namespace microservicios-curso --dry-run=client -o yaml | kubectl apply -f -

# Configurar namespace por defecto para esta sesión
kubectl config set-context --current --namespace=microservicios-curso
```

### Preparación del Microservicio inventory-service

Antes de crear el Helm chart, necesitamos el código fuente y la imagen Docker del servicio.

```bash
# Crear directorio de trabajo
mkdir -p ~/microservicios-curso/inventory-service
cd ~/microservicios-curso/inventory-service
```

Crear el archivo `main.py`:

```python
# ~/microservicios-curso/inventory-service/main.py
from fastapi import FastAPI
from pydantic import BaseModel
import os
import socket

app = FastAPI(title="Inventory Service", version="1.0.0")


class HealthResponse(BaseModel):
    status: str
    hostname: str
    version: str


class InventoryItem(BaseModel):
    id: int
    name: str
    quantity: int
    price: float


# Datos en memoria para el laboratorio
INVENTORY = [
    InventoryItem(id=1, name="Widget A", quantity=100, price=9.99),
    InventoryItem(id=2, name="Widget B", quantity=50, price=19.99),
    InventoryItem(id=3, name="Widget C", quantity=200, price=4.99),
]


@app.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(
        status="healthy",
        hostname=socket.gethostname(),
        version=os.getenv("APP_VERSION", "1.0.0"),
    )


@app.get("/api/v1/inventory", response_model=list[InventoryItem])
def list_inventory():
    return INVENTORY


@app.get("/api/v1/inventory/{item_id}", response_model=InventoryItem)
def get_item(item_id: int):
    for item in INVENTORY:
        if item.id == item_id:
            return item
    from fastapi import HTTPException
    raise HTTPException(status_code=404, detail="Item not found")


@app.get("/api/v1/stress")
def stress():
    """Endpoint para generar carga de CPU (usado en pruebas de autoescalado)."""
    total = 0
    for i in range(1_000_000):
        total += i * i
    return {"result": total, "hostname": socket.gethostname()}
```

Crear el archivo `requirements.txt`:

```text
fastapi==0.111.0
uvicorn==0.30.1
```

Crear el `Dockerfile`:

```dockerfile
# ~/microservicios-curso/inventory-service/Dockerfile
FROM python:3.12.3-slim AS base

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

EXPOSE 8000

USER nobody

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Construir la imagen Docker:

```bash
# Configurar Docker para usar el daemon de Minikube
eval $(minikube docker-env)

# Construir la imagen
docker build -t inventory-service:1.0.0 .

# Verificar que la imagen existe
docker images | grep inventory-service
```

**Salida esperada:**

```
inventory-service   1.0.0   abc123def456   5 seconds ago   185MB
```

---

## Paso a Paso

### Paso 1: Crear la Estructura del Helm Chart

**Objetivo:** Generar la estructura base del chart usando `helm create` y limpiar los archivos innecesarios para personalizarlo.

**Instrucciones:**

1. Crear el directorio para charts de Helm:

```bash
mkdir -p ~/microservicios-curso/helm-charts
cd ~/microservicios-curso/helm-charts
```

2. Generar el chart base:

```bash
helm create inventory-service
```

3. Explorar la estructura generada:

```bash
tree inventory-service/
```

4. Limpiar los archivos de ejemplo que no usaremos (los reescribiremos):

```bash
# Eliminar templates de ejemplo
rm -f inventory-service/templates/ingress.yaml
rm -f inventory-service/templates/serviceaccount.yaml
rm -rf inventory-service/templates/tests/

# Limpiar el archivo NOTES.txt para personalizarlo después
cat /dev/null > inventory-service/templates/NOTES.txt
```

5. Editar el archivo `Chart.yaml`:

```yaml
# ~/microservicios-curso/helm-charts/inventory-service/Chart.yaml
apiVersion: v2
name: inventory-service
description: Helm chart para el microservicio inventory-service (FastAPI/Python)
type: application
version: 0.1.0
appVersion: "1.0.0"
maintainers:
  - name: Estudiante
    email: estudiante@curso-microservicios.dev
keywords:
  - fastapi
  - microservicio
  - inventario
```

**Salida esperada** (estructura del directorio):

```
inventory-service/
├── Chart.yaml
├── charts/
├── templates/
│   ├── NOTES.txt
│   ├── _helpers.tpl
│   ├── deployment.yaml
│   ├── hpa.yaml
│   └── service.yaml
└── values.yaml
```

**Verificación:**

```bash
helm lint inventory-service/
```

Debe mostrar: `1 chart(s) linted, 0 chart(s) failed`

---

### Paso 2: Configurar values.yaml con Parámetros del Microservicio

**Objetivo:** Definir todos los valores parametrizables del chart en `values.yaml`, incluyendo imagen, réplicas, recursos, puertos y configuración del HPA.

**Instrucciones:**

1. Reemplazar el contenido completo de `values.yaml`:

```yaml
# ~/microservicios-curso/helm-charts/inventory-service/values.yaml

# Configuración de la imagen Docker
image:
  repository: inventory-service
  tag: "1.0.0"
  pullPolicy: IfNotPresent

# Réplicas base (será sobreescrito por HPA cuando esté activo)
replicaCount: 2

# Configuración del contenedor
container:
  port: 8000

# Configuración del Service
service:
  type: NodePort
  port: 80
  targetPort: 8000
  nodePort: 30080

# Recursos del contenedor (requests y limits)
resources:
  requests:
    cpu: "100m"
    memory: "128Mi"
  limits:
    cpu: "300m"
    memory: "256Mi"

# Configuración del HPA
autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 6
  targetCPUUtilizationPercentage: 50

# Estrategia de despliegue
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxSurge: 1
    maxUnavailable: 0

# Variables de entorno desde ConfigMap
config:
  appVersion: "1.0.0"
  logLevel: "info"
  environment: "development"

# Health checks
probes:
  liveness:
    path: /health
    initialDelaySeconds: 10
    periodSeconds: 15
  readiness:
    path: /health
    initialDelaySeconds: 5
    periodSeconds: 10

# Labels adicionales
labels:
  team: "platform"
  course: "microservicios-curso"
```

**Verificación:**

```bash
# Validar que el YAML es correcto
python3 -c "import yaml; yaml.safe_load(open('inventory-service/values.yaml'))" && echo "YAML válido"
```

---

### Paso 3: Crear el Template del ConfigMap

**Objetivo:** Crear un template de ConfigMap que inyecte configuración al microservicio como variables de entorno.

**Instrucciones:**

1. Crear el archivo `templates/configmap.yaml`:

```yaml
# ~/microservicios-curso/helm-charts/inventory-service/templates/configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: {{ include "inventory-service.fullname" . }}-config
  namespace: {{ .Release.Namespace }}
  labels:
    {{- include "inventory-service.labels" . | nindent 4 }}
data:
  APP_VERSION: {{ .Values.config.appVersion | quote }}
  LOG_LEVEL: {{ .Values.config.logLevel | quote }}
  ENVIRONMENT: {{ .Values.config.environment | quote }}
```

**Verificación:**

```bash
helm template inventory-service/ --set config.appVersion="1.0.0" | grep -A 10 "kind: ConfigMap"
```

Debe mostrar el ConfigMap renderizado con los valores definidos.

---

### Paso 4: Crear el Template del Deployment con RollingUpdate

**Objetivo:** Definir el template del Deployment con estrategia RollingUpdate, health checks, recursos limitados y referencia al ConfigMap.

**Instrucciones:**

1. Reemplazar el contenido de `templates/deployment.yaml`:

```yaml
# ~/microservicios-curso/helm-charts/inventory-service/templates/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "inventory-service.fullname" . }}
  namespace: {{ .Release.Namespace }}
  labels:
    {{- include "inventory-service.labels" . | nindent 4 }}
spec:
  {{- if not .Values.autoscaling.enabled }}
  replicas: {{ .Values.replicaCount }}
  {{- end }}
  selector:
    matchLabels:
      {{- include "inventory-service.selectorLabels" . | nindent 6 }}
  strategy:
    type: {{ .Values.strategy.type }}
    {{- if eq .Values.strategy.type "RollingUpdate" }}
    rollingUpdate:
      maxSurge: {{ .Values.strategy.rollingUpdate.maxSurge }}
      maxUnavailable: {{ .Values.strategy.rollingUpdate.maxUnavailable }}
    {{- end }}
  template:
    metadata:
      labels:
        {{- include "inventory-service.selectorLabels" . | nindent 8 }}
      annotations:
        rollme: {{ randAlphaNum 5 | quote }}
    spec:
      containers:
        - name: {{ .Chart.Name }}
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
          imagePullPolicy: {{ .Values.image.pullPolicy }}
          ports:
            - name: http
              containerPort: {{ .Values.container.port }}
              protocol: TCP
          envFrom:
            - configMapRef:
                name: {{ include "inventory-service.fullname" . }}-config
          resources:
            requests:
              cpu: {{ .Values.resources.requests.cpu | quote }}
              memory: {{ .Values.resources.requests.memory | quote }}
            limits:
              cpu: {{ .Values.resources.limits.cpu | quote }}
              memory: {{ .Values.resources.limits.memory | quote }}
          livenessProbe:
            httpGet:
              path: {{ .Values.probes.liveness.path }}
              port: http
            initialDelaySeconds: {{ .Values.probes.liveness.initialDelaySeconds }}
            periodSeconds: {{ .Values.probes.liveness.periodSeconds }}
          readinessProbe:
            httpGet:
              path: {{ .Values.probes.readiness.path }}
              port: http
            initialDelaySeconds: {{ .Values.probes.readiness.initialDelaySeconds }}
            periodSeconds: {{ .Values.probes.readiness.periodSeconds }}
```

**Verificación:**

```bash
helm template inventory-service/ | grep -A 5 "strategy:"
```

**Salida esperada:**

```yaml
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
```

---

### Paso 5: Crear el Template del Service

**Objetivo:** Definir un Service que exponga el microservicio con tipo NodePort para acceso externo y ClusterIP interno.

**Instrucciones:**

1. Reemplazar el contenido de `templates/service.yaml`:

```yaml
# ~/microservicios-curso/helm-charts/inventory-service/templates/service.yaml
apiVersion: v1
kind: Service
metadata:
  name: {{ include "inventory-service.fullname" . }}
  namespace: {{ .Release.Namespace }}
  labels:
    {{- include "inventory-service.labels" . | nindent 4 }}
spec:
  type: {{ .Values.service.type }}
  ports:
    - port: {{ .Values.service.port }}
      targetPort: {{ .Values.service.targetPort }}
      protocol: TCP
      name: http
      {{- if and (eq .Values.service.type "NodePort") .Values.service.nodePort }}
      nodePort: {{ .Values.service.nodePort }}
      {{- end }}
  selector:
    {{- include "inventory-service.selectorLabels" . | nindent 4 }}
```

**Verificación:**

```bash
helm template inventory-service/ | grep -A 12 "kind: Service"
```

---

### Paso 6: Crear el Template del HPA

**Objetivo:** Configurar el Horizontal Pod Autoscaler para escalar entre 2 y 6 réplicas con target de CPU al 50%.

**Instrucciones:**

1. Reemplazar el contenido de `templates/hpa.yaml`:

```yaml
# ~/microservicios-curso/helm-charts/inventory-service/templates/hpa.yaml
{{- if .Values.autoscaling.enabled }}
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: {{ include "inventory-service.fullname" . }}
  namespace: {{ .Release.Namespace }}
  labels:
    {{- include "inventory-service.labels" . | nindent 4 }}
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: {{ include "inventory-service.fullname" . }}
  minReplicas: {{ .Values.autoscaling.minReplicas }}
  maxReplicas: {{ .Values.autoscaling.maxReplicas }}
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: {{ .Values.autoscaling.targetCPUUtilizationPercentage }}
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 30
      policies:
        - type: Pods
          value: 2
          periodSeconds: 60
    scaleDown:
      stabilizationWindowSeconds: 120
      policies:
        - type: Pods
          value: 1
          periodSeconds: 60
{{- end }}
```

**Verificación:**

```bash
helm template inventory-service/ | grep -A 25 "kind: HorizontalPodAutoscaler"
```

**Salida esperada** (fragmento):

```yaml
  minReplicas: 2
  maxReplicas: 6
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 50
```

---

### Paso 7: Actualizar el Helper Template

**Objetivo:** Asegurar que los helpers de nombres y labels están correctamente definidos para todos los templates.

**Instrucciones:**

1. Reemplazar el contenido de `templates/_helpers.tpl`:

```yaml
{{/*
Nombre completo del release
*/}}
{{- define "inventory-service.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Nombre del chart
*/}}
{{- define "inventory-service.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Labels comunes
*/}}
{{- define "inventory-service.labels" -}}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version | replace "+" "_" }}
{{ include "inventory-service.selectorLabels" . }}
app.kubernetes.io/version: {{ .Values.image.tag | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- if .Values.labels }}
{{ toYaml .Values.labels }}
{{- end }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "inventory-service.selectorLabels" -}}
app.kubernetes.io/name: {{ include "inventory-service.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
```

**Verificación:**

```bash
helm lint inventory-service/
```

**Salida esperada:**

```
==> Linting inventory-service/
[INFO] Chart.yaml: icon is recommended
1 chart(s) linted, 0 chart(s) failed
```

---

### Paso 8: Validar y Renderizar el Chart Completo

**Objetivo:** Verificar que todo el chart se renderiza correctamente antes del despliegue.

**Instrucciones:**

1. Renderizar todos los templates con valores por defecto:

```bash
helm template mi-inventario inventory-service/ \
  --namespace microservicios-curso \
  > /tmp/rendered-chart.yaml

# Revisar el archivo completo
cat /tmp/rendered-chart.yaml
```

2. Verificar que contiene los 4 recursos esperados:

```bash
grep "^kind:" /tmp/rendered-chart.yaml | sort
```

**Salida esperada:**

```
kind: ConfigMap
kind: Deployment
kind: HorizontalPodAutoscaler
kind: Service
```

3. Validar con dry-run contra el clúster:

```bash
helm install mi-inventario inventory-service/ \
  --namespace microservicios-curso \
  --dry-run --debug 2>&1 | tail -20
```

**Verificación:** El comando no debe mostrar errores. Debe terminar con los manifiestos renderizados.

---

### Paso 9: Desplegar el Chart en Minikube

**Objetivo:** Instalar el Helm chart en el clúster y verificar que todos los recursos se crean correctamente.

**Instrucciones:**

1. Instalar el chart:

```bash
helm install mi-inventario inventory-service/ \
  --namespace microservicios-curso \
  --wait --timeout 120s
```

2. Verificar el release:

```bash
helm list -n microservicios-curso
```

**Salida esperada:**

```
NAME            NAMESPACE               REVISION  STATUS    CHART                    APP VERSION
mi-inventario   microservicios-curso    1         deployed  inventory-service-0.1.0  1.0.0
```

3. Verificar los recursos creados:

```bash
# Pods (deben ser 2 réplicas mínimas del HPA)
kubectl get pods -n microservicios-curso -l app.kubernetes.io/name=inventory-service

# Service
kubectl get svc -n microservicios-curso

# HPA
kubectl get hpa -n microservicios-curso

# ConfigMap
kubectl get configmap -n microservicios-curso
```

4. Esperar a que todos los Pods estén en estado Running:

```bash
kubectl wait --for=condition=ready pod \
  -l app.kubernetes.io/name=inventory-service \
  -n microservicios-curso \
  --timeout=90s
```

**Salida esperada:**

```
pod/mi-inventario-inventory-service-xxxxx condition met
pod/mi-inventario-inventory-service-yyyyy condition met
```

**Verificación:**

```bash
kubectl get hpa -n microservicios-curso
```

Debe mostrar `TARGETS` con un valor de CPU (puede mostrar `<unknown>/50%` durante los primeros 60 segundos mientras metrics-server recolecta datos).

---

### Paso 10: Verificar el Balanceo de Carga entre Réplicas

**Objetivo:** Confirmar que el Service distribuye el tráfico entre los diferentes Pods, observando diferentes hostnames en las respuestas.

**Instrucciones:**

1. Obtener la URL del servicio:

```bash
export SERVICE_URL=$(minikube service mi-inventario-inventory-service \
  -n microservicios-curso --url)
echo "Service URL: $SERVICE_URL"
```

2. Realizar múltiples peticiones y observar el hostname:

```bash
echo "=== Prueba de balanceo de carga ==="
for i in $(seq 1 10); do
  curl -s "$SERVICE_URL/health" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Request {$i}: hostname={d[\"hostname\"]}')"
done
```

**Salida esperada** (los hostnames deben alternar entre los Pods):

```
=== Prueba de balanceo de carga ===
Request 1: hostname=mi-inventario-inventory-service-abc12
Request 2: hostname=mi-inventario-inventory-service-def34
Request 3: hostname=mi-inventario-inventory-service-abc12
Request 4: hostname=mi-inventario-inventory-service-def34
...
```

3. Verificar que la API funciona correctamente:

```bash
curl -s "$SERVICE_URL/api/v1/inventory" | python3 -m json.tool
```

**Verificación:** Las respuestas deben provenir de al menos 2 hostnames diferentes, confirmando el balanceo de carga.

---

### Paso 11: Generar Carga y Observar el Autoescalado

**Objetivo:** Provocar un aumento de uso de CPU para que el HPA escale el número de réplicas de 2 hacia el máximo de 6.

**Instrucciones:**

1. Abrir una segunda terminal para monitorear el HPA en tiempo real:

```bash
# Terminal 2 - Monitoreo continuo
kubectl get hpa -n microservicios-curso --watch
```

2. En la primera terminal, generar carga con un bucle de peticiones al endpoint de stress:

```bash
# Terminal 1 - Generación de carga
echo "Generando carga de CPU... (Ctrl+C para detener)"
export SERVICE_URL=$(minikube service mi-inventario-inventory-service \
  -n microservicios-curso --url)

# Ejecutar múltiples peticiones concurrentes
for i in $(seq 1 4); do
  while true; do
    curl -s "$SERVICE_URL/api/v1/stress" > /dev/null
  done &
done

# Guardar PIDs para poder detenerlos después
echo "PIDs de carga: $(jobs -p)"
```

3. Observar el escalado (esperar 1-3 minutos):

```bash
# En otra terminal, verificar periódicamente
kubectl get hpa -n microservicios-curso
kubectl get pods -n microservicios-curso -l app.kubernetes.io/name=inventory-service
```

**Salida esperada** (después de 1-2 minutos):

```
NAME                              REFERENCE                                    TARGETS    MINPODS   MAXPODS   REPLICAS   AGE
mi-inventario-inventory-service   Deployment/mi-inventario-inventory-service   78%/50%    2         6         4          5m
```

4. Detener la carga:

```bash
# Matar todos los procesos de carga en background
kill $(jobs -p) 2>/dev/null
wait 2>/dev/null
```

5. Observar el scale-down (esperar 2-3 minutos por la ventana de estabilización de 120s):

```bash
# Monitorear hasta que vuelva a 2 réplicas
watch -n 10 "kubectl get hpa -n microservicios-curso && echo '---' && kubectl get pods -n microservicios-curso -l app.kubernetes.io/name=inventory-service"
```

**Verificación:**

```bash
kubectl describe hpa mi-inventario-inventory-service -n microservicios-curso | grep -A 5 "Events:"
```

Debe mostrar eventos de tipo `SuccessfulRescale` indicando el escalado hacia arriba y eventualmente hacia abajo.

---

### Paso 12: Probar Actualización con RollingUpdate

**Objetivo:** Realizar un upgrade del chart cambiando la versión de la aplicación y verificar que no hay downtime.

**Instrucciones:**

1. En una terminal, iniciar un monitoreo continuo de disponibilidad:

```bash
# Terminal de monitoreo
export SERVICE_URL=$(minikube service mi-inventario-inventory-service \
  -n microservicios-curso --url)

while true; do
  RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" "$SERVICE_URL/health" 2>/dev/null)
  echo "$(date +%H:%M:%S) - HTTP $RESPONSE"
  sleep 1
done
```

2. En otra terminal, realizar el upgrade:

```bash
helm upgrade mi-inventario inventory-service/ \
  --namespace microservicios-curso \
  --set config.appVersion="1.1.0" \
  --set config.environment="staging" \
  --wait --timeout 120s
```

3. Verificar el rollout:

```bash
kubectl rollout status deployment/mi-inventario-inventory-service \
  -n microservicios-curso
```

**Salida esperada:**

```
deployment "mi-inventario-inventory-service" successfully rolled out
```

4. Verificar que la nueva configuración está aplicada:

```bash
curl -s "$SERVICE_URL/health" | python3 -m json.tool
```

**Salida esperada:**

```json
{
    "status": "healthy",
    "hostname": "mi-inventario-inventory-service-xxxxx",
    "version": "1.1.0"
}
```

5. Detener el monitoreo de disponibilidad (Ctrl+C) y verificar que no hubo respuestas HTTP distintas de 200.

**Verificación:**

```bash
helm history mi-inventario -n microservicios-curso
```

Debe mostrar 2 revisiones: la instalación original y el upgrade.

---

### Paso 13: Commit de los Artefactos al Repositorio

**Objetivo:** Guardar todo el trabajo en el repositorio Git del curso.

**Instrucciones:**

1. Asegurar que el repositorio existe:

```bash
cd ~/microservicios-curso
git init 2>/dev/null || true
```

2. Agregar los archivos nuevos:

```bash
git add inventory-service/
git add helm-charts/inventory-service/
```

3. Crear el commit:

```bash
git commit -m "[lab06] Crear Helm chart para inventory-service con HPA y RollingUpdate"
```

**Verificación:**

```bash
git log --oneline -1
```

---

## Validación y Testing

Ejecutar la siguiente secuencia de comandos para validar que todos los objetivos del laboratorio se cumplen:

```bash
echo "========================================="
echo "  VALIDACIÓN COMPLETA DEL LABORATORIO 06"
echo "========================================="

echo ""
echo "1. Verificando Helm release..."
helm status mi-inventario -n microservicios-curso | grep "STATUS: deployed" && echo "✅ Release desplegado" || echo "❌ Release no encontrado"

echo ""
echo "2. Verificando recursos del chart..."
RESOURCES=$(kubectl get all -n microservicios-curso -l app.kubernetes.io/instance=mi-inventario -o name | wc -l)
echo "   Recursos encontrados: $RESOURCES"
[ "$RESOURCES" -ge 4 ] && echo "✅ Recursos suficientes" || echo "❌ Faltan recursos"

echo ""
echo "3. Verificando HPA configurado..."
HPA_MAX=$(kubectl get hpa mi-inventario-inventory-service -n microservicios-curso -o jsonpath='{.spec.maxReplicas}')
HPA_MIN=$(kubectl get hpa mi-inventario-inventory-service -n microservicios-curso -o jsonpath='{.spec.minReplicas}')
echo "   HPA: min=$HPA_MIN, max=$HPA_MAX"
[ "$HPA_MIN" = "2" ] && [ "$HPA_MAX" = "6" ] && echo "✅ HPA correctamente configurado" || echo "❌ HPA mal configurado"

echo ""
echo "4. Verificando estrategia RollingUpdate..."
STRATEGY=$(kubectl get deployment mi-inventario-inventory-service -n microservicios-curso -o jsonpath='{.spec.strategy.type}')
MAX_SURGE=$(kubectl get deployment mi-inventario-inventory-service -n microservicios-curso -o jsonpath='{.spec.strategy.rollingUpdate.maxSurge}')
MAX_UNAVAIL=$(kubectl get deployment mi-inventario-inventory-service -n microservicios-curso -o jsonpath='{.spec.strategy.rollingUpdate.maxUnavailable}')
echo "   Strategy: $STRATEGY, maxSurge=$MAX_SURGE, maxUnavailable=$MAX_UNAVAIL"
[ "$STRATEGY" = "RollingUpdate" ] && [ "$MAX_UNAVAIL" = "0" ] && echo "✅ RollingUpdate sin downtime" || echo "❌ Estrategia incorrecta"

echo ""
echo "5. Verificando Service NodePort..."
SVC_TYPE=$(kubectl get svc mi-inventario-inventory-service -n microservicios-curso -o jsonpath='{.spec.type}')
NODE_PORT=$(kubectl get svc mi-inventario-inventory-service -n microservicios-curso -o jsonpath='{.spec.ports[0].nodePort}')
echo "   Service type=$SVC_TYPE, nodePort=$NODE_PORT"
[ "$SVC_TYPE" = "NodePort" ] && [ "$NODE_PORT" = "30080" ] && echo "✅ Service correctamente configurado" || echo "❌ Service mal configurado"

echo ""
echo "6. Verificando Pods saludables..."
READY_PODS=$(kubectl get pods -n microservicios-curso -l app.kubernetes.io/name=inventory-service --field-selector=status.phase=Running -o name | wc -l)
echo "   Pods Running: $READY_PODS"
[ "$READY_PODS" -ge 2 ] && echo "✅ Mínimo 2 réplicas activas" || echo "❌ Menos de 2 réplicas"

echo ""
echo "7. Verificando endpoint de salud..."
SERVICE_URL=$(minikube service mi-inventario-inventory-service -n microservicios-curso --url 2>/dev/null)
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$SERVICE_URL/health" 2>/dev/null)
echo "   Health check HTTP: $HTTP_CODE"
[ "$HTTP_CODE" = "200" ] && echo "✅ Servicio respondiendo correctamente" || echo "❌ Servicio no responde"

echo ""
echo "========================================="
echo "  VALIDACIÓN COMPLETADA"
echo "========================================="
```

---

## Solución de Problemas

### Problema 1: HPA muestra `<unknown>/50%` en TARGETS indefinidamente

**Síntomas:**

```bash
$ kubectl get hpa -n microservicios-curso
NAME                              REFERENCE                                    TARGETS         MINPODS   MAXPODS   REPLICAS
mi-inventario-inventory-service   Deployment/mi-inventario-inventory-service   <unknown>/50%   2         6         2
```

El valor `<unknown>` persiste más de 2-3 minutos después del despliegue.

**Causa:** El metrics-server no está recolectando métricas de los Pods. Esto ocurre cuando:
- El addon metrics-server no está habilitado en Minikube.
- El Deployment no tiene `resources.requests.cpu` definido (el HPA necesita requests para calcular el porcentaje de utilización).

**Solución:**

```bash
# Verificar que metrics-server está corriendo
kubectl get pods -n kube-system | grep metrics-server

# Si no está, habilitarlo
minikube addons enable metrics-server

# Esperar 60 segundos y verificar que hay métricas disponibles
kubectl top pods -n microservicios-curso

# Si los pods no tienen resources.requests, verificar el values.yaml
helm get values mi-inventario -n microservicios-curso | grep -A 4 "resources"

# Si falta, hacer upgrade con los recursos explícitos
helm upgrade mi-inventario inventory-service/ \
  --namespace microservicios-curso \
  --set resources.requests.cpu="100m" \
  --wait
```

---

### Problema 2: Error `ImagePullBackOff` al desplegar el chart

**Síntomas:**

```bash
$ kubectl get pods -n microservicios-curso
NAME                                               READY   STATUS             RESTARTS   AGE
mi-inventario-inventory-service-xxx                0/1     ImagePullBackOff   0          30s
```

**Causa:** La imagen `inventory-service:1.0.0` fue construida en el daemon Docker del host, pero Minikube usa su propio daemon Docker. Kubernetes no puede encontrar la imagen localmente porque no se usó `eval $(minikube docker-env)` antes de construir.

**Solución:**

```bash
# Configurar el shell para usar el Docker de Minikube
eval $(minikube docker-env)

# Verificar que NO existe la imagen en el daemon de Minikube
docker images | grep inventory-service

# Si no aparece, reconstruir dentro del contexto de Minikube
cd ~/microservicios-curso/inventory-service
docker build -t inventory-service:1.0.0 .

# Verificar que imagePullPolicy es IfNotPresent (no Always)
kubectl get deployment mi-inventario-inventory-service -n microservicios-curso \
  -o jsonpath='{.spec.template.spec.containers[0].imagePullPolicy}'

# Si necesitas forzar el re-pull, reiniciar los pods
kubectl rollout restart deployment/mi-inventario-inventory-service -n microservicios-curso
```

---

## Limpieza

Ejecutar los siguientes comandos para liberar recursos del clúster al finalizar la práctica:

```bash
# Desinstalar el release de Helm
helm uninstall mi-inventario -n microservicios-curso

# Verificar que los recursos fueron eliminados
kubectl get all -n microservicios-curso

# (Opcional) Si no continuarás con el siguiente laboratorio inmediatamente:
# minikube stop

# Restaurar el contexto Docker al host (si se usó minikube docker-env)
eval $(minikube docker-env -u)
```

> **Nota:** NO eliminar el namespace `microservicios-curso` ni la imagen Docker `inventory-service:1.0.0`, ya que se reutilizarán en los laboratorios 7, 9 y 10.

---

## Resumen

En este laboratorio has completado las siguientes tareas:

| Logro | Detalle |
|-------|---------|
| **Helm chart creado** | Estructura completa con `Chart.yaml`, `values.yaml` y 4 templates |
| **Deployment con RollingUpdate** | `maxSurge: 1`, `maxUnavailable: 0` para zero-downtime |
| **HPA configurado** | Escalado automático 2→6 réplicas al 50% CPU |
| **Service NodePort** | Acceso externo en puerto 30080 con balanceo de carga |
| **ConfigMap parametrizado** | Variables de entorno inyectadas desde `values.yaml` |
| **Autoescalado validado** | Generación de carga y observación del scale-up/scale-down |

### Conceptos Clave Aplicados

- La fórmula del HPA: `réplicas_deseadas = ceil(réplicas_actuales × métrica_actual / métrica_objetivo)`
- La ventana de estabilización (`stabilizationWindowSeconds`) evita el *flapping* de réplicas
- `maxUnavailable: 0` garantiza que nunca hay menos Pods disponibles que los actuales durante un rollout
- `imagePullPolicy: IfNotPresent` es esencial para imágenes locales en Minikube

### Recursos Adicionales

- [Documentación oficial de Helm Charts](https://helm.sh/docs/topics/charts/)
- [Kubernetes HPA Walkthrough](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale-walkthrough/)
- [Best Practices for Helm Charts](https://helm.sh/docs/chart_best_practices/)
- [Kubernetes Deployment Strategies](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/#strategy)
