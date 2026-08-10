# Práctica 4 — Desplegar servicio Python en un clúster local (minikube/kind)

## Metadatos

| Campo | Valor |
|-------|-------|
| **Duración** | 64 minutos |
| **Complejidad** | Alta |
| **Nivel Bloom** | Aplicar |

## Descripción General

En esta práctica desplegarás el microservicio `products-service` (imagen Docker publicada en la práctica 03-00-01) dentro de un clúster Kubernetes local gestionado por minikube. Crearás manifiestos YAML para Namespace, ConfigMap, Secret, Deployment y Service, aplicarás el modelo declarativo de Kubernetes y verificarás que el servicio es accesible desde el host a través de un NodePort. Esta práctica consolida los conceptos de arquitectura vistos en la lección 4.1 (plano de control, nodos trabajadores, bucle de reconciliación) llevándolos a la ejecución real.

## Objetivos de Aprendizaje

- [ ] Configurar y arrancar un clúster Kubernetes local de un nodo usando minikube 1.33.1 con driver Docker
- [ ] Crear y aplicar manifiestos YAML de Kubernetes (Namespace, Deployment, Service) para el products-service
- [ ] Gestionar configuración de la aplicación mediante ConfigMaps y credenciales sensibles con Secrets
- [ ] Verificar el despliegue, escalar el número de réplicas y probar el acceso al servicio desde el host

## Prerrequisitos

### Conocimientos previos

- Haber completado la práctica 03-00-01 (imagen Docker publicada en Docker Hub)
- Comprensión de la arquitectura de Kubernetes: plano de control, nodos trabajadores, API Server (lección 4.1)
- Familiaridad con YAML y comandos básicos de terminal

### Acceso y software requerido

| Herramienta | Versión | Verificación |
|-------------|---------|--------------|
| Docker Engine | 26.1.3+ | `docker --version` |
| minikube | 1.33.1 | `minikube version` |
| kubectl | 1.30.1 | `kubectl version --client` |
| Git | 2.45.1+ | `git --version` |

### Recursos de hardware

| Recurso | Mínimo requerido |
|---------|-----------------|
| RAM disponible | 4 GB (para el clúster minikube) |
| CPU | 2 núcleos libres |
| Disco | 10 GB libres |

## Entorno del Laboratorio

### Estructura de directorios objetivo

```
~/microservicios-curso/
├── k8s/
│   └── products-service/
│       ├── namespace.yaml
│       ├── configmap.yaml
│       ├── secret.yaml        ← NO se commitea (está en .gitignore)
│       ├── deployment.yaml
│       └── service.yaml
└── ...
```

### Convenciones

| Elemento | Valor |
|----------|-------|
| Namespace Kubernetes | `microservicios-curso` |
| Imagen Docker | `<tu-usuario-dockerhub>/products-service:1.0.0` |
| Puerto interno del contenedor | 8000 |
| NodePort expuesto | 30080 |
| API_SECRET_KEY (base64) | `Y3Vyc28tbWljcm9zZXJ2aWNpb3Mtc2VjcmV0LTIwMjQ=` |

---

## Paso a Paso

### Paso 1 — Iniciar el clúster minikube

**Objetivo:** Levantar un clúster Kubernetes local de un nodo con recursos controlados, utilizando Docker como driver.

**Instrucciones:**

1. Verifica que Docker esté en ejecución:

```bash
docker info | grep "Server Version"
```

2. Si existe un clúster minikube previo que desees reiniciar limpiamente (opcional):

```bash
minikube delete
```

3. Inicia el clúster con la configuración especificada:

```bash
minikube start \
  --driver=docker \
  --kubernetes-version=v1.30.1 \
  --cpus=2 \
  --memory=4096
```

4. Verifica que el clúster esté activo:

```bash
minikube status
```

**Salida esperada:**

```
minikube
type: Control Plane
host: Running
kubelet: Running
apiserver: Running
kubeconfig: Configured
```

**Verificación:**

```bash
kubectl get nodes -o wide
```

Debes ver un nodo con STATUS `Ready` y ROLES `control-plane`. Esto confirma que el plano de control (API Server, etcd, Scheduler, Controller Manager) y el kubelet están operativos en el mismo nodo — exactamente la arquitectura de un nodo estudiada en la lección 4.1.

```bash
# Verificar componentes del plano de control
kubectl get pods -n kube-system
```

Debes observar pods como `etcd-minikube`, `kube-apiserver-minikube`, `kube-scheduler-minikube` y `kube-controller-manager-minikube` en estado `Running`.

---

### Paso 2 — Crear la estructura de directorios para manifiestos

**Objetivo:** Organizar los manifiestos Kubernetes en el directorio estándar del curso.

**Instrucciones:**

1. Crea el directorio para los manifiestos:

```bash
mkdir -p ~/microservicios-curso/k8s/products-service
```

2. Navega al directorio:

```bash
cd ~/microservicios-curso/k8s/products-service
```

3. Asegúrate de que `secret.yaml` esté en el `.gitignore` del repositorio:

```bash
# Desde la raíz del repositorio
cd ~/microservicios-curso
echo "k8s/products-service/secret.yaml" >> .gitignore
```

**Verificación:**

```bash
ls ~/microservicios-curso/k8s/products-service/
grep "secret.yaml" ~/microservicios-curso/.gitignore
```

El directorio debe existir y el `.gitignore` debe contener la línea correspondiente.

---

### Paso 3 — Crear el manifiesto del Namespace

**Objetivo:** Definir un namespace dedicado para aislar todos los recursos del curso, evitando el namespace `default`.

**Instrucciones:**

1. Crea el archivo `namespace.yaml`:

```bash
cat > ~/microservicios-curso/k8s/products-service/namespace.yaml << 'EOF'
apiVersion: v1
kind: Namespace
metadata:
  name: microservicios-curso
  labels:
    project: microservicios-curso
    environment: development
EOF
```

2. Aplica el manifiesto:

```bash
kubectl apply -f ~/microservicios-curso/k8s/products-service/namespace.yaml
```

**Salida esperada:**

```
namespace/microservicios-curso created
```

**Verificación:**

```bash
kubectl get namespaces | grep microservicios-curso
```

Debe aparecer el namespace con STATUS `Active`. Este namespace será el ámbito de todos los recursos que crearemos a continuación.

---

### Paso 4 — Crear el ConfigMap

**Objetivo:** Externalizar la configuración no sensible de la aplicación en un objeto ConfigMap, separando configuración del código (principio de los 12 factores).

**Instrucciones:**

1. Crea el archivo `configmap.yaml`:

```bash
cat > ~/microservicios-curso/k8s/products-service/configmap.yaml << 'EOF'
apiVersion: v1
kind: ConfigMap
metadata:
  name: products-service-config
  namespace: microservicios-curso
  labels:
    app: products-service
data:
  APP_ENV: "production"
  LOG_LEVEL: "info"
  APP_PORT: "8000"
EOF
```

2. Aplica el manifiesto:

```bash
kubectl apply -f ~/microservicios-curso/k8s/products-service/configmap.yaml
```

**Salida esperada:**

```
configmap/products-service-config created
```

**Verificación:**

```bash
kubectl get configmap products-service-config -n microservicios-curso -o yaml
```

Confirma que las tres variables (`APP_ENV`, `LOG_LEVEL`, `APP_PORT`) aparecen en la sección `data`.

---

### Paso 5 — Crear el Secret

**Objetivo:** Almacenar la credencial `API_SECRET_KEY` de forma segura usando un objeto Secret con datos codificados en base64.

**Instrucciones:**

1. Verifica la codificación base64 del secreto:

```bash
echo -n 'curso-microservicios-secret-2024' | base64
```

La salida debe ser: `Y3Vyc28tbWljcm9zZXJ2aWNpb3Mtc2VjcmV0LTIwMjQ=`

2. Crea el archivo `secret.yaml`:

```bash
cat > ~/microservicios-curso/k8s/products-service/secret.yaml << 'EOF'
apiVersion: v1
kind: Secret
metadata:
  name: products-service-secret
  namespace: microservicios-curso
  labels:
    app: products-service
type: Opaque
data:
  API_SECRET_KEY: Y3Vyc28tbWljcm9zZXJ2aWNpb3Mtc2VjcmV0LTIwMjQ=
EOF
```

3. Aplica el manifiesto:

```bash
kubectl apply -f ~/microservicios-curso/k8s/products-service/secret.yaml
```

**Salida esperada:**

```
secret/products-service-secret created
```

**Verificación:**

```bash
kubectl get secret products-service-secret -n microservicios-curso
```

El secret debe aparecer con TYPE `Opaque` y DATA `1`. Recuerda: este archivo **nunca** se commitea al repositorio Git.

---

### Paso 6 — Crear el Deployment

**Objetivo:** Definir el Deployment que gestionará las réplicas del pod `products-service`, inyectando variables de entorno desde ConfigMap y Secret, y configurando probes de salud y límites de recursos.

**Instrucciones:**

1. Crea el archivo `deployment.yaml`. **Reemplaza `<tu-usuario-dockerhub>`** con tu usuario real de Docker Hub:

```bash
cat > ~/microservicios-curso/k8s/products-service/deployment.yaml << 'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: products-service
  namespace: microservicios-curso
  labels:
    app: products-service
spec:
  replicas: 2
  selector:
    matchLabels:
      app: products-service
  template:
    metadata:
      labels:
        app: products-service
    spec:
      containers:
        - name: products-service
          image: <tu-usuario-dockerhub>/products-service:1.0.0
          ports:
            - containerPort: 8000
              protocol: TCP
          envFrom:
            - configMapRef:
                name: products-service-config
          env:
            - name: API_SECRET_KEY
              valueFrom:
                secretKeyRef:
                  name: products-service-secret
                  key: API_SECRET_KEY
          readinessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 10
            timeoutSeconds: 3
            failureThreshold: 3
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 10
            periodSeconds: 15
            timeoutSeconds: 3
            failureThreshold: 3
          resources:
            requests:
              cpu: 100m
              memory: 128Mi
            limits:
              cpu: 500m
              memory: 256Mi
      restartPolicy: Always
EOF
```

2. **Edita el archivo** para reemplazar `<tu-usuario-dockerhub>` con tu usuario real:

```bash
# Ejemplo: si tu usuario es "jperez"
sed -i 's/<tu-usuario-dockerhub>/jperez/' ~/microservicios-curso/k8s/products-service/deployment.yaml
```

3. Aplica el manifiesto:

```bash
kubectl apply -f ~/microservicios-curso/k8s/products-service/deployment.yaml
```

**Salida esperada:**

```
deployment.apps/products-service created
```

**Verificación:**

```bash
kubectl get deployment products-service -n microservicios-curso
```

Espera a que READY muestre `2/2`. Esto indica que el Controller Manager del plano de control ha reconciliado el estado deseado (2 réplicas) con el estado actual, asignando pods a través del Scheduler y ejecutándolos vía el kubelet.

```bash
# Verificar que los pods estén Running
kubectl get pods -n microservicios-curso -l app=products-service
```

**Salida esperada (ejemplo):**

```
NAME                                READY   STATUS    RESTARTS   AGE
products-service-7d8f9b6c4a-abc12   1/1     Running   0          30s
products-service-7d8f9b6c4a-def34   1/1     Running   0          30s
```

> **Nota:** Si los pods quedan en `ImagePullBackOff`, verifica que la imagen exista en Docker Hub y que el nombre sea correcto. Consulta la sección de Troubleshooting.

---

### Paso 7 — Crear el Service (NodePort)

**Objetivo:** Exponer el Deployment al exterior del clúster mediante un Service de tipo NodePort en el puerto 30080.

**Instrucciones:**

1. Crea el archivo `service.yaml`:

```bash
cat > ~/microservicios-curso/k8s/products-service/service.yaml << 'EOF'
apiVersion: v1
kind: Service
metadata:
  name: products-service
  namespace: microservicios-curso
  labels:
    app: products-service
spec:
  type: NodePort
  selector:
    app: products-service
  ports:
    - protocol: TCP
      port: 8000
      targetPort: 8000
      nodePort: 30080
EOF
```

2. Aplica el manifiesto:

```bash
kubectl apply -f ~/microservicios-curso/k8s/products-service/service.yaml
```

**Salida esperada:**

```
service/products-service created
```

**Verificación:**

```bash
kubectl get service products-service -n microservicios-curso
```

**Salida esperada:**

```
NAME               TYPE       CLUSTER-IP      EXTERNAL-IP   PORT(S)          AGE
products-service   NodePort   10.96.xxx.xxx   <none>        8000:30080/TCP   10s
```

El kube-proxy en el nodo trabajador configurará las reglas de red (iptables/IPVS) para enrutar el tráfico del puerto 30080 hacia los pods seleccionados.

---

### Paso 8 — Verificar el despliegue completo

**Objetivo:** Confirmar que todos los recursos están correctamente creados y que el servicio responde.

**Instrucciones:**

1. Lista todos los recursos del namespace:

```bash
kubectl get all -n microservicios-curso
```

2. Describe uno de los pods para verificar la inyección de variables:

```bash
# Obtén el nombre de un pod
POD_NAME=$(kubectl get pods -n microservicios-curso -l app=products-service -o jsonpath='{.items[0].metadata.name}')

# Describe el pod
kubectl describe pod $POD_NAME -n microservicios-curso
```

Verifica en la sección `Environment` que aparezcan las variables `APP_ENV`, `LOG_LEVEL`, `APP_PORT` (del ConfigMap) y `API_SECRET_KEY` (del Secret).

3. Revisa los logs del pod:

```bash
kubectl logs $POD_NAME -n microservicios-curso
```

Debes ver los logs de arranque de Uvicorn/FastAPI indicando que el servidor está escuchando en el puerto 8000.

4. Accede al servicio desde el host:

```bash
minikube service products-service -n microservicios-curso --url
```

Este comando devuelve una URL (por ejemplo, `http://192.168.49.2:30080`). Usa esa URL para probar:

```bash
# Guarda la URL en una variable
SERVICE_URL=$(minikube service products-service -n microservicios-curso --url)

# Prueba el endpoint de salud
curl -s ${SERVICE_URL}/health
```

**Salida esperada:**

```json
{"status":"healthy"}
```

5. Prueba el endpoint principal de productos:

```bash
curl -s ${SERVICE_URL}/products | python3 -m json.tool
```

Debes recibir una respuesta JSON válida (lista de productos o lista vacía según la implementación de la práctica 03-00-01).

---

### Paso 9 — Escalar el Deployment a 3 réplicas

**Objetivo:** Demostrar el escalado horizontal declarativo y verificar que el Controller Manager crea el pod adicional automáticamente.

**Instrucciones:**

1. Escala el deployment:

```bash
kubectl scale deployment products-service -n microservicios-curso --replicas=3
```

**Salida esperada:**

```
deployment.apps/products-service scaled
```

2. Verifica que la tercera réplica se crea:

```bash
kubectl get pods -n microservicios-curso -l app=products-service -w
```

Presiona `Ctrl+C` cuando los 3 pods estén en estado `Running`.

3. Confirma el estado del deployment:

```bash
kubectl get deployment products-service -n microservicios-curso
```

**Salida esperada:**

```
NAME               READY   UP-TO-DATE   AVAILABLE   AGE
products-service   3/3     3            3           5m
```

**Verificación conceptual:** El bucle de reconciliación del ReplicaSet Controller detectó que el estado deseado cambió de 2 a 3 réplicas. Como el estado actual tenía solo 2, el controlador instruyó al Scheduler para planificar un pod adicional, y el kubelet del nodo lo ejecutó.

---

### Paso 10 — Commit de los manifiestos al repositorio

**Objetivo:** Versionar los manifiestos creados en el repositorio Git del curso.

**Instrucciones:**

1. Navega a la raíz del repositorio:

```bash
cd ~/microservicios-curso
```

2. Añade los archivos (excepto `secret.yaml` que está en `.gitignore`):

```bash
git add k8s/products-service/namespace.yaml
git add k8s/products-service/configmap.yaml
git add k8s/products-service/deployment.yaml
git add k8s/products-service/service.yaml
git add .gitignore
```

3. Verifica que `secret.yaml` NO esté incluido:

```bash
git status
```

4. Realiza el commit:

```bash
git commit -m "[lab04] Añadir manifiestos Kubernetes para products-service (Namespace, ConfigMap, Deployment, Service)"
```

**Verificación:**

```bash
git log --oneline -1
```

---

## Validación y Pruebas

Ejecuta la siguiente secuencia completa de validación para confirmar que el laboratorio se completó correctamente:

```bash
echo "=== Validación del Lab 04-00-01 ==="

echo ""
echo "1. Estado del clúster minikube:"
minikube status

echo ""
echo "2. Namespace:"
kubectl get namespace microservicios-curso -o jsonpath='{.status.phase}'
echo ""

echo ""
echo "3. ConfigMap:"
kubectl get configmap products-service-config -n microservicios-curso -o jsonpath='{.data}' | python3 -m json.tool

echo ""
echo "4. Secret (existe):"
kubectl get secret products-service-secret -n microservicios-curso -o jsonpath='{.type}'
echo ""

echo ""
echo "5. Deployment (3 réplicas disponibles):"
kubectl get deployment products-service -n microservicios-curso -o jsonpath='Replicas deseadas: {.spec.replicas}, Disponibles: {.status.availableReplicas}'
echo ""

echo ""
echo "6. Pods Running:"
kubectl get pods -n microservicios-curso -l app=products-service --field-selector=status.phase=Running --no-headers | wc -l

echo ""
echo "7. Service NodePort:"
kubectl get service products-service -n microservicios-curso -o jsonpath='Puerto: {.spec.ports[0].nodePort}'
echo ""

echo ""
echo "8. Health check:"
SERVICE_URL=$(minikube service products-service -n microservicios-curso --url 2>/dev/null)
curl -s --max-time 5 ${SERVICE_URL}/health
echo ""

echo ""
echo "=== Validación completada ==="
```

**Criterios de éxito:**

| Verificación | Resultado esperado |
|---|---|
| Clúster minikube | host: Running, kubelet: Running, apiserver: Running |
| Namespace | `Active` |
| ConfigMap | Contiene APP_ENV, LOG_LEVEL, APP_PORT |
| Secret | Tipo `Opaque` |
| Deployment réplicas | Deseadas: 3, Disponibles: 3 |
| Pods Running | 3 |
| Service NodePort | 30080 |
| Health check | `{"status":"healthy"}` |

---

## Resolución de Problemas

### Problema 1: Pods en estado `ImagePullBackOff` o `ErrImagePull`

**Síntomas:**

```
NAME                                READY   STATUS             RESTARTS   AGE
products-service-7d8f9b6c4a-abc12   0/1     ImagePullBackOff   0          60s
```

Al ejecutar `kubectl describe pod <nombre> -n microservicios-curso`, la sección Events muestra:

```
Failed to pull image "<usuario>/products-service:1.0.0": rpc error: code = NotFound
```

**Causa:** La imagen no existe en Docker Hub con el nombre/tag especificado. Puede deberse a un error tipográfico en el nombre de usuario, nombre de imagen o tag, o a que la imagen no fue publicada correctamente en la práctica 03-00-01.

**Solución:**

1. Verifica que la imagen existe en Docker Hub:

```bash
docker pull <tu-usuario-dockerhub>/products-service:1.0.0
```

2. Si no existe, vuelve a publicarla:

```bash
docker tag microservicios-curso/products-service:1.0.0 <tu-usuario-dockerhub>/products-service:1.0.0
docker push <tu-usuario-dockerhub>/products-service:1.0.0
```

3. Corrige el nombre de imagen en `deployment.yaml` y vuelve a aplicar:

```bash
kubectl apply -f ~/microservicios-curso/k8s/products-service/deployment.yaml
```

4. Elimina los pods con error para forzar la recreación:

```bash
kubectl delete pods -n microservicios-curso -l app=products-service
```

---

### Problema 2: Pods en estado `Running` pero `READY 0/1` (readinessProbe falla)

**Síntomas:**

```
NAME                                READY   STATUS    RESTARTS   AGE
products-service-7d8f9b6c4a-abc12   0/1     Running   0          90s
```

Al describir el pod, los Events muestran:

```
Readiness probe failed: Get "http://10.244.0.5:8000/health": dial tcp 10.244.0.5:8000: connect: connection refused
```

**Causa:** La aplicación no está escuchando en el puerto 8000 dentro del contenedor, o el endpoint `/health` no existe. Esto puede ocurrir si la variable `APP_PORT` no está siendo utilizada por la aplicación, o si hay un error de arranque en FastAPI.

**Solución:**

1. Revisa los logs del contenedor para identificar errores de arranque:

```bash
POD_NAME=$(kubectl get pods -n microservicios-curso -l app=products-service -o jsonpath='{.items[0].metadata.name}')
kubectl logs $POD_NAME -n microservicios-curso
```

2. Si la aplicación usa un puerto diferente, verifica la configuración del Dockerfile y ajusta `containerPort` y las probes en `deployment.yaml`.

3. Si el endpoint `/health` no existe, verifica el código fuente de la práctica 03-00-01. Temporalmente puedes cambiar la probe a `/` o `/docs`:

```yaml
readinessProbe:
  httpGet:
    path: /docs
    port: 8000
```

4. Aplica los cambios:

```bash
kubectl apply -f ~/microservicios-curso/k8s/products-service/deployment.yaml
```

---

## Limpieza

Si necesitas liberar recursos al finalizar la sesión de trabajo (el clúster puede reiniciarse en futuras prácticas):

```bash
# Opción A: Pausar minikube (conserva el estado, libera RAM/CPU)
minikube stop

# Opción B: Eliminar completamente el clúster (deberás recrearlo en la práctica 05-00-01)
# minikube delete
```

> **Recomendación:** Usa `minikube stop` para conservar el clúster y retomarlo en la siguiente práctica. Los manifiestos YAML del directorio `k8s/products-service/` serán extendidos en la práctica 05-00-01 para añadir almacenamiento persistente (PersistentVolume y PersistentVolumeClaim).

Para eliminar solo los recursos del namespace sin destruir el clúster:

```bash
# NO ejecutar si planeas continuar con la práctica 05-00-01
# kubectl delete namespace microservicios-curso
```

---

## Resumen

En esta práctica has aplicado los conceptos de la arquitectura de Kubernetes estudiados en la lección 4.1:

| Concepto teórico | Aplicación práctica |
|---|---|
| Plano de control (API Server, etcd, Scheduler, Controller Manager) | Observado con `kubectl get pods -n kube-system` al iniciar minikube |
| Modelo declarativo | Definición del estado deseado en manifiestos YAML |
| Bucle de reconciliación | Escalado de 2→3 réplicas: el Controller Manager detectó la diferencia y creó el pod faltante |
| kubelet | Ejecutó los contenedores en el nodo |
| kube-proxy | Configuró las reglas de red para el Service NodePort |

**Artefactos generados:**

- `~/microservicios-curso/k8s/products-service/namespace.yaml`
- `~/microservicios-curso/k8s/products-service/configmap.yaml`
- `~/microservicios-curso/k8s/products-service/secret.yaml` (no versionado)
- `~/microservicios-curso/k8s/products-service/deployment.yaml`
- `~/microservicios-curso/k8s/products-service/service.yaml`

**Próximo paso:** En la práctica 05-00-01 extenderás estos manifiestos para añadir PersistentVolumes y PersistentVolumeClaims, garantizando que los datos del servicio persistan entre reinicios de pods.

### Recursos adicionales

- [Documentación oficial de minikube](https://minikube.sigs.k8s.io/docs/)
- [Kubernetes: Deployments](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/)
- [Kubernetes: Services — NodePort](https://kubernetes.io/docs/concepts/services-networking/service/#type-nodeport)
- [Kubernetes: ConfigMaps](https://kubernetes.io/docs/concepts/configuration/configmap/)
- [Kubernetes: Secrets](https://kubernetes.io/docs/concepts/configuration/secret/)
- [Kubernetes: Configure Liveness, Readiness and Startup Probes](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/)
