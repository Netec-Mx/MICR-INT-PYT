# Práctica 5 — Montar un Volumen Persistente para un Servicio Python

## Metadatos

| Campo | Valor |
|-------|-------|
| **Duración** | 64 minutos |
| **Complejidad** | Alta |
| **Nivel Bloom** | Aplicar |

## Descripción General

En esta práctica transformarás el `products-service` para que persista sus datos en un archivo JSON montado sobre un volumen persistente de Kubernetes, en lugar de utilizar un diccionario en memoria que se pierde con cada reinicio del Pod. Crearás los recursos de almacenamiento necesarios (StorageClass, PersistentVolume, PersistentVolumeClaim), actualizarás el Deployment, verificarás la durabilidad de los datos ante la eliminación de Pods e implementarás un CronJob de backup automático.

## Objetivos de Aprendizaje

- [ ] Comprender las diferencias entre almacenamiento efímero y persistente y justificar la elección de PV/PVC para el caso de uso
- [ ] Crear y configurar StorageClass, PersistentVolume y PersistentVolumeClaim para el `products-service`
- [ ] Modificar el código Python y el Deployment para persistir datos en `/app/data/products.json`
- [ ] Verificar la persistencia de datos simulando fallos y recreación de Pods
- [ ] Implementar un CronJob de backup periódico del archivo de datos

## Prerrequisitos

### Conocimientos Previos

- Práctica 04-00-01 completada: clúster minikube operativo con `products-service` desplegado en el namespace `microservicios-curso`
- Familiaridad con manifiestos YAML de Kubernetes (Deployment, Service)
- Conocimientos básicos de Python y FastAPI
- Uso de Docker para construir y publicar imágenes

### Acceso y Recursos

- Clúster minikube en ejecución con al menos 4 GB de RAM asignados
- Docker Engine 26.1.3 operativo
- Cuenta de Docker Hub activa (sustituir `[dockerhub-usuario]` por tu usuario real en todos los comandos)
- Manifiestos existentes en `~/microservicios-curso/k8s/products-service/`
- Código fuente en `~/microservicios-curso/products-service/`

## Entorno del Laboratorio

### Software Requerido

| Herramienta | Versión | Propósito |
|-------------|---------|-----------|
| Python | 3.12.3 | Modificar el código del microservicio |
| FastAPI | 0.111.0 | Framework del microservicio |
| Docker Engine | 26.1.3 | Reconstruir la imagen v2.0.0 |
| minikube | 1.33.1 | Clúster Kubernetes local |
| kubectl | 1.30.1 | Gestión de recursos del clúster |

### Verificación Inicial del Entorno

```bash
# Confirmar que minikube está corriendo
minikube status

# Verificar el namespace del curso
kubectl get ns microservicios-curso

# Confirmar que el deployment actual funciona
kubectl get pods -n microservicios-curso

# Verificar la estructura de directorios
ls ~/microservicios-curso/products-service/
ls ~/microservicios-curso/k8s/products-service/
```

---

## Paso a Paso

### Paso 1 — Modificar el Código Python para Persistencia en Archivo JSON

**Objetivo:** Reemplazar el almacenamiento en memoria (diccionario Python) por lectura/escritura en un archivo JSON ubicado en `/app/data/products.json`.

**Instrucciones:**

1. Navega al directorio del servicio:

```bash
cd ~/microservicios-curso/products-service
```

2. Crea el directorio de datos local para pruebas:

```bash
mkdir -p data
```

3. Reemplaza el contenido de `main.py` con la siguiente versión que usa persistencia en archivo:

```python
"""Products Service v2.0.0 - Persistencia en archivo JSON."""

import json
import os
from pathlib import Path
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Products Service", version="2.0.0")

# Ruta del archivo de persistencia (configurable via variable de entorno)
DATA_DIR = Path(os.getenv("DATA_DIR", "/app/data"))
DATA_FILE = DATA_DIR / "products.json"


class Product(BaseModel):
    """Modelo de producto."""
    name: str
    price: float
    description: str = ""


class ProductOut(Product):
    """Modelo de producto con ID para respuestas."""
    id: int


def _ensure_data_file() -> None:
    """Crea el directorio y archivo de datos si no existen."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not DATA_FILE.exists():
        DATA_FILE.write_text(json.dumps({"products": [], "next_id": 1}))


def _load_data() -> dict:
    """Carga los datos desde el archivo JSON."""
    _ensure_data_file()
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_data(data: dict) -> None:
    """Guarda los datos en el archivo JSON."""
    _ensure_data_file()
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


@app.get("/health")
def health_check():
    """Endpoint de salud."""
    return {"status": "healthy", "version": "2.0.0", "storage": "persistent"}


@app.get("/products", response_model=list[ProductOut])
def list_products():
    """Lista todos los productos."""
    data = _load_data()
    return data["products"]


@app.get("/products/{product_id}", response_model=ProductOut)
def get_product(product_id: int):
    """Obtiene un producto por ID."""
    data = _load_data()
    for product in data["products"]:
        if product["id"] == product_id:
            return product
    raise HTTPException(status_code=404, detail="Producto no encontrado")


@app.post("/products", response_model=ProductOut, status_code=201)
def create_product(product: Product):
    """Crea un nuevo producto."""
    data = _load_data()
    new_product = {
        "id": data["next_id"],
        "name": product.name,
        "price": product.price,
        "description": product.description,
    }
    data["products"].append(new_product)
    data["next_id"] += 1
    _save_data(data)
    return new_product


@app.delete("/products/{product_id}", status_code=204)
def delete_product(product_id: int):
    """Elimina un producto por ID."""
    data = _load_data()
    original_len = len(data["products"])
    data["products"] = [p for p in data["products"] if p["id"] != product_id]
    if len(data["products"]) == original_len:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    _save_data(data)
    return None
```

4. Verifica que el archivo `requirements.txt` contiene las dependencias necesarias:

```bash
cat requirements.txt
```

Si no existe o necesita actualización, créalo:

```bash
cat > requirements.txt << 'EOF'
fastapi==0.111.0
uvicorn==0.30.1
pydantic==2.7.1
EOF
```

5. Prueba localmente (opcional pero recomendado):

```bash
DATA_DIR=./data python -m uvicorn main:app --host 0.0.0.0 --port 8000 &
sleep 2
curl -s http://localhost:8000/health
curl -s -X POST http://localhost:8000/products \
  -H "Content-Type: application/json" \
  -d '{"name":"Test","price":9.99,"description":"Prueba local"}'
cat data/products.json
kill %1
```

**Salida esperada del health check:**

```json
{"status":"healthy","version":"2.0.0","storage":"persistent"}
```

**Verificación:**

```bash
# Confirmar que el archivo JSON se creó correctamente
cat data/products.json | python -m json.tool
```

Debes ver una estructura JSON con el producto creado y `next_id` incrementado.

---

### Paso 2 — Reconstruir y Publicar la Imagen Docker v2.0.0

**Objetivo:** Construir una nueva imagen Docker con el código actualizado y publicarla como versión 2.0.0.

**Instrucciones:**

1. Verifica que el `Dockerfile` existe y es adecuado. Si necesitas crearlo o actualizarlo:

```bash
cd ~/microservicios-curso/products-service

cat > Dockerfile << 'EOF'
FROM python:3.12-slim

WORKDIR /app

# Crear usuario no-root
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Instalar dependencias
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código fuente
COPY main.py .

# Crear directorio de datos con permisos adecuados
RUN mkdir -p /app/data && chown -R appuser:appuser /app/data

# Cambiar a usuario no-root
USER appuser

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
EOF
```

2. Construye la imagen con la etiqueta local:

```bash
docker build -t microservicios-curso/products-service:2.0.0 .
```

3. Etiqueta la imagen para Docker Hub (sustituye `[dockerhub-usuario]` por tu usuario):

```bash
docker tag microservicios-curso/products-service:2.0.0 \
  [dockerhub-usuario]/products-service:2.0.0
```

4. Publica la imagen:

```bash
docker login
docker push [dockerhub-usuario]/products-service:2.0.0
```

5. Si usas minikube con driver Docker, carga la imagen directamente en minikube (alternativa a Docker Hub):

```bash
minikube image load microservicios-curso/products-service:2.0.0
```

**Salida esperada (build):**

```
Successfully built a1b2c3d4e5f6
Successfully tagged microservicios-curso/products-service:2.0.0
```

**Verificación:**

```bash
docker images | grep products-service
```

Debes ver la imagen con la etiqueta `2.0.0`.

---

### Paso 3 — Crear el StorageClass

**Objetivo:** Definir un StorageClass llamado `local-storage` que utilice aprovisionamiento local con binding diferido.

**Instrucciones:**

1. Navega al directorio de manifiestos:

```bash
cd ~/microservicios-curso/k8s/products-service
```

2. Crea el archivo `storageclass.yaml`:

```bash
cat > storageclass.yaml << 'EOF'
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: local-storage
provisioner: kubernetes.io/no-provisioner
volumeBindingMode: WaitForFirstConsumer
reclaimPolicy: Retain
EOF
```

3. Aplica el manifiesto:

```bash
kubectl apply -f storageclass.yaml
```

**Salida esperada:**

```
storageclass.storage.k8s.io/local-storage created
```

**Verificación:**

```bash
kubectl get storageclass local-storage
```

```
NAME            PROVISIONER                    RECLAIMPOLICY   VOLUMEBINDINGMODE      ALLOWVOLUMEEXPANSION
local-storage   kubernetes.io/no-provisioner   Retain          WaitForFirstConsumer   false
```

---

### Paso 4 — Crear el PersistentVolume

**Objetivo:** Crear un PersistentVolume de 1Gi con hostPath apuntando a `/mnt/data/products-service` en el nodo de minikube.

**Instrucciones:**

1. Primero, crea el directorio en el nodo de minikube:

```bash
minikube ssh -- sudo mkdir -p /mnt/data/products-service
minikube ssh -- sudo chmod 777 /mnt/data/products-service
```

2. Crea el archivo `persistentvolume.yaml`:

```bash
cat > persistentvolume.yaml << 'EOF'
apiVersion: v1
kind: PersistentVolume
metadata:
  name: products-pv
  labels:
    app: products-service
    type: local
spec:
  capacity:
    storage: 1Gi
  accessModes:
    - ReadWriteOnce
  persistentVolumeReclaimPolicy: Retain
  storageClassName: local-storage
  hostPath:
    path: /mnt/data/products-service
    type: DirectoryOrCreate
  nodeAffinity:
    required:
      nodeSelectorTerms:
        - matchExpressions:
            - key: kubernetes.io/hostname
              operator: In
              values:
                - minikube
EOF
```

3. Aplica el manifiesto:

```bash
kubectl apply -f persistentvolume.yaml
```

**Salida esperada:**

```
persistentvolume/products-pv created
```

**Verificación:**

```bash
kubectl get pv products-pv
```

```
NAME          CAPACITY   ACCESS MODES   RECLAIM POLICY   STATUS      CLAIM   STORAGECLASS    REASON   AGE
products-pv   1Gi        RWO            Retain           Available           local-storage            5s
```

El estado debe ser `Available` (aún no hay PVC vinculado).

---

### Paso 5 — Crear el PersistentVolumeClaim

**Objetivo:** Crear un PVC que solicite 500Mi de almacenamiento de la StorageClass `local-storage`.

**Instrucciones:**

1. Crea el archivo `persistentvolumeclaim.yaml`:

```bash
cat > persistentvolumeclaim.yaml << 'EOF'
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: products-pvc
  namespace: microservicios-curso
  labels:
    app: products-service
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: local-storage
  resources:
    requests:
      storage: 500Mi
EOF
```

2. Aplica el manifiesto:

```bash
kubectl apply -f persistentvolumeclaim.yaml
```

**Salida esperada:**

```
persistentvolumeclaim/products-pvc created
```

**Verificación:**

```bash
kubectl get pvc products-pvc -n microservicios-curso
```

```
NAME           STATUS    VOLUME   CAPACITY   ACCESS MODES   STORAGECLASS    AGE
products-pvc   Pending                                      local-storage   5s
```

> **Nota:** El estado `Pending` es esperado porque `volumeBindingMode: WaitForFirstConsumer` espera a que un Pod consuma el PVC antes de vincularlo al PV. Se vinculará automáticamente cuando despleguemos el Deployment actualizado en el siguiente paso.

---

### Paso 6 — Actualizar el Deployment para Montar el Volumen

**Objetivo:** Modificar el Deployment del `products-service` para montar el PVC en `/app/data` y usar la imagen v2.0.0.

**Instrucciones:**

1. Crea o actualiza el archivo `deployment.yaml`:

```bash
cat > deployment.yaml << 'EOF'
apiVersion: apps/v1
kind: Deployment
metadata:
  name: products-service
  namespace: microservicios-curso
  labels:
    app: products-service
    version: 2.0.0
spec:
  replicas: 1
  selector:
    matchLabels:
      app: products-service
  template:
    metadata:
      labels:
        app: products-service
        version: 2.0.0
    spec:
      containers:
        - name: products-service
          image: microservicios-curso/products-service:2.0.0
          imagePullPolicy: IfNotPresent
          ports:
            - containerPort: 8000
              protocol: TCP
          env:
            - name: DATA_DIR
              value: "/app/data"
          volumeMounts:
            - name: products-data
              mountPath: /app/data
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
          resources:
            requests:
              memory: "128Mi"
              cpu: "100m"
            limits:
              memory: "256Mi"
              cpu: "250m"
      volumes:
        - name: products-data
          persistentVolumeClaim:
            claimName: products-pvc
EOF
```

2. Aplica el Deployment actualizado:

```bash
kubectl apply -f deployment.yaml
```

**Salida esperada:**

```
deployment.apps/products-service configured
```

3. Espera a que el Pod esté listo:

```bash
kubectl rollout status deployment/products-service -n microservicios-curso --timeout=120s
```

**Salida esperada:**

```
deployment "products-service" successfully rolled out
```

**Verificación:**

```bash
# Verificar que el Pod está Running
kubectl get pods -n microservicios-curso -l app=products-service

# Verificar que el PVC ahora está Bound
kubectl get pvc products-pvc -n microservicios-curso

# Verificar que el PV está Bound
kubectl get pv products-pv
```

El PVC debe mostrar estado `Bound` y el PV debe mostrar `Bound` con la referencia al claim `microservicios-curso/products-pvc`.

---

### Paso 7 — Verificar la Persistencia de Datos

**Objetivo:** Crear productos, eliminar el Pod, y confirmar que los datos sobreviven al reinicio.

**Instrucciones:**

1. Expón el servicio para pruebas (si no hay Service existente):

```bash
# Verificar si ya existe un Service
kubectl get svc -n microservicios-curso products-service

# Si no existe, crear un port-forward temporal
kubectl port-forward -n microservicios-curso svc/products-service 8080:8000 &
PF_PID=$!
sleep 2
```

Si necesitas crear el Service:

```bash
cat > service.yaml << 'EOF'
apiVersion: v1
kind: Service
metadata:
  name: products-service
  namespace: microservicios-curso
  labels:
    app: products-service
spec:
  type: ClusterIP
  selector:
    app: products-service
  ports:
    - port: 8000
      targetPort: 8000
      protocol: TCP
EOF
kubectl apply -f service.yaml
kubectl port-forward -n microservicios-curso svc/products-service 8080:8000 &
PF_PID=$!
sleep 2
```

2. Crea varios productos:

```bash
curl -s -X POST http://localhost:8080/products \
  -H "Content-Type: application/json" \
  -d '{"name":"Laptop HP","price":899.99,"description":"Laptop 15 pulgadas"}' | python -m json.tool

curl -s -X POST http://localhost:8080/products \
  -H "Content-Type: application/json" \
  -d '{"name":"Mouse Logitech","price":29.99,"description":"Mouse inalámbrico"}' | python -m json.tool

curl -s -X POST http://localhost:8080/products \
  -H "Content-Type: application/json" \
  -d '{"name":"Teclado Mecánico","price":79.99,"description":"Switches Cherry MX"}' | python -m json.tool
```

3. Verifica que los productos existen:

```bash
curl -s http://localhost:8080/products | python -m json.tool
```

4. Detén el port-forward:

```bash
kill $PF_PID 2>/dev/null
```

5. Elimina el Pod actual (simular un fallo):

```bash
kubectl delete pod -n microservicios-curso -l app=products-service
```

6. Espera a que el nuevo Pod esté listo:

```bash
kubectl wait --for=condition=ready pod -n microservicios-curso -l app=products-service --timeout=60s
```

7. Restablece el port-forward y verifica los datos:

```bash
kubectl port-forward -n microservicios-curso svc/products-service 8080:8000 &
PF_PID=$!
sleep 3

curl -s http://localhost:8080/products | python -m json.tool

kill $PF_PID 2>/dev/null
```

**Salida esperada:**

Los tres productos creados anteriormente deben aparecer en la respuesta, demostrando que los datos sobrevivieron a la eliminación del Pod.

```json
[
    {
        "name": "Laptop HP",
        "price": 899.99,
        "description": "Laptop 15 pulgadas",
        "id": 1
    },
    {
        "name": "Mouse Logitech",
        "price": 29.99,
        "description": "Mouse inalámbrico",
        "id": 2
    },
    {
        "name": "Teclado Mecánico",
        "price": 79.99,
        "description": "Switches Cherry MX",
        "id": 3
    }
]
```

**Verificación adicional — inspeccionar el archivo en el nodo:**

```bash
minikube ssh -- cat /mnt/data/products-service/products.json
```

Debes ver el contenido JSON con los tres productos almacenados directamente en el filesystem del nodo.

---

### Paso 8 — Implementar CronJob de Backup

**Objetivo:** Crear un CronJob que copie el archivo `products.json` a un directorio de backups cada 6 horas con marca de tiempo.

**Instrucciones:**

1. Crea el directorio de backups en el nodo:

```bash
minikube ssh -- sudo mkdir -p /mnt/data/products-backups
minikube ssh -- sudo chmod 777 /mnt/data/products-backups
```

2. Crea un PV y PVC para los backups:

```bash
cat > pv-backup.yaml << 'EOF'
apiVersion: v1
kind: PersistentVolume
metadata:
  name: products-backup-pv
  labels:
    app: products-service
    type: backup
spec:
  capacity:
    storage: 1Gi
  accessModes:
    - ReadWriteOnce
  persistentVolumeReclaimPolicy: Retain
  storageClassName: local-storage
  hostPath:
    path: /mnt/data/products-backups
    type: DirectoryOrCreate
  nodeAffinity:
    required:
      nodeSelectorTerms:
        - matchExpressions:
            - key: kubernetes.io/hostname
              operator: In
              values:
                - minikube
EOF

cat > pvc-backup.yaml << 'EOF'
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: products-backup-pvc
  namespace: microservicios-curso
  labels:
    app: products-service
    component: backup
spec:
  accessModes:
    - ReadWriteOnce
  storageClassName: local-storage
  resources:
    requests:
      storage: 500Mi
EOF

kubectl apply -f pv-backup.yaml
kubectl apply -f pvc-backup.yaml
```

3. Crea el archivo `cronjob-backup.yaml`:

```bash
cat > cronjob-backup.yaml << 'EOF'
apiVersion: batch/v1
kind: CronJob
metadata:
  name: products-backup
  namespace: microservicios-curso
  labels:
    app: products-service
    component: backup
spec:
  schedule: "0 */6 * * *"
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 1
  concurrencyPolicy: Forbid
  jobTemplate:
    spec:
      template:
        spec:
          restartPolicy: OnFailure
          containers:
            - name: backup
              image: busybox:1.36
              command:
                - /bin/sh
                - -c
                - |
                  TIMESTAMP=$(date +%Y%m%d-%H%M%S)
                  if [ -f /source/products.json ]; then
                    cp /source/products.json /backup/products-${TIMESTAMP}.json
                    echo "Backup completado: products-${TIMESTAMP}.json"
                    # Mantener solo los últimos 10 backups
                    ls -t /backup/products-*.json | tail -n +11 | xargs rm -f 2>/dev/null
                    echo "Limpieza de backups antiguos completada"
                  else
                    echo "ERROR: Archivo fuente /source/products.json no encontrado"
                    exit 1
                  fi
              volumeMounts:
                - name: products-data
                  mountPath: /source
                  readOnly: true
                - name: backup-data
                  mountPath: /backup
          volumes:
            - name: products-data
              persistentVolumeClaim:
                claimName: products-pvc
            - name: backup-data
              persistentVolumeClaim:
                claimName: products-backup-pvc
EOF
```

4. Aplica el CronJob:

```bash
kubectl apply -f cronjob-backup.yaml
```

**Salida esperada:**

```
cronjob.batch/products-backup created
```

5. Ejecuta manualmente el Job para verificar que funciona:

```bash
kubectl create job --from=cronjob/products-backup products-backup-manual-test -n microservicios-curso
```

6. Espera a que el Job termine:

```bash
kubectl wait --for=condition=complete job/products-backup-manual-test -n microservicios-curso --timeout=60s
```

7. Revisa los logs del Job:

```bash
kubectl logs -n microservicios-curso job/products-backup-manual-test
```

**Salida esperada:**

```
Backup completado: products-20240615-143022.json
Limpieza de backups antiguos completada
```

**Verificación:**

```bash
# Verificar el CronJob
kubectl get cronjob -n microservicios-curso

# Verificar que el backup se creó en el nodo
minikube ssh -- ls -la /mnt/data/products-backups/

# Verificar el contenido del backup
minikube ssh -- cat /mnt/data/products-backups/products-*.json
```

8. Limpia el Job manual de prueba:

```bash
kubectl delete job products-backup-manual-test -n microservicios-curso
```

---

## Verificación Final del Laboratorio

Ejecuta los siguientes comandos para confirmar que todos los componentes están correctamente configurados:

```bash
echo "=== StorageClass ==="
kubectl get storageclass local-storage

echo ""
echo "=== PersistentVolumes ==="
kubectl get pv

echo ""
echo "=== PersistentVolumeClaims ==="
kubectl get pvc -n microservicios-curso

echo ""
echo "=== Deployment ==="
kubectl get deployment products-service -n microservicios-curso

echo ""
echo "=== Pods ==="
kubectl get pods -n microservicios-curso -l app=products-service

echo ""
echo "=== CronJob ==="
kubectl get cronjob -n microservicios-curso

echo ""
echo "=== Verificar montaje del volumen en el Pod ==="
POD_NAME=$(kubectl get pods -n microservicios-curso -l app=products-service -o jsonpath='{.items[0].metadata.name}')
kubectl exec -n microservicios-curso $POD_NAME -- ls -la /app/data/

echo ""
echo "=== Contenido del archivo de datos ==="
kubectl exec -n microservicios-curso $POD_NAME -- cat /app/data/products.json
```

**Criterios de éxito:**

| Recurso | Estado Esperado |
|---------|----------------|
| StorageClass `local-storage` | Creado con provisioner `no-provisioner` |
| PV `products-pv` | `Bound` |
| PVC `products-pvc` | `Bound` |
| Deployment `products-service` | 1/1 Ready |
| Pod | Running con volumen montado en `/app/data` |
| CronJob `products-backup` | Programado (`0 */6 * * *`) |
| Datos persistentes | Sobreviven a la eliminación del Pod |

---

## Limpieza (Opcional)

Si deseas eliminar los recursos creados en este laboratorio:

```bash
# Eliminar CronJob
kubectl delete cronjob products-backup -n microservicios-curso

# Eliminar Deployment
kubectl delete deployment products-service -n microservicios-curso

# Eliminar Service
kubectl delete svc products-service -n microservicios-curso

# Eliminar PVCs
kubectl delete pvc products-pvc products-backup-pvc -n microservicios-curso

# Eliminar PVs
kubectl delete pv products-pv products-backup-pv

# Eliminar StorageClass
kubectl delete storageclass local-storage

# Limpiar datos del nodo
minikube ssh -- sudo rm -rf /mnt/data/products-service /mnt/data/products-backups
```

> **Nota:** No ejecutes la limpieza si vas a continuar con la siguiente práctica del curso, ya que depende de estos recursos.

---

## Solución de Problemas Comunes

| Problema | Causa Probable | Solución |
|----------|---------------|----------|
| PVC permanece en `Pending` | El PV no coincide con los requisitos del PVC o el Pod no se ha programado | Verificar que `storageClassName`, `accessModes` y `capacity` coincidan. Verificar que el Deployment esté aplicado |
| Pod en `CrashLoopBackOff` | Permisos insuficientes en el directorio montado | Ejecutar `minikube ssh -- sudo chmod 777 /mnt/data/products-service` |
| Imagen no encontrada | La imagen no se cargó en minikube | Ejecutar `minikube image load microservicios-curso/products-service:2.0.0` |
| Error `json.decoder.JSONDecodeError` | Archivo JSON corrupto | Eliminar el archivo y dejar que la aplicación lo recree: `minikube ssh -- rm /mnt/data/products-service/products.json` |
| CronJob no se ejecuta | Schedule incorrecto o PVC no disponible | Verificar con `kubectl describe cronjob` y ejecutar manualmente con `kubectl create job --from=cronjob/...` |

---

## Resumen de Recursos Creados

```
~/microservicios-curso/k8s/products-service/
├── storageclass.yaml
├── persistentvolume.yaml
├── persistentvolumeclaim.yaml
├── pv-backup.yaml
├── pvc-backup.yaml
├── deployment.yaml
├── service.yaml
└── cronjob-backup.yaml
```

## Conceptos Clave Reforzados

1. **Almacenamiento efímero vs. persistente:** Sin PV/PVC, los datos dentro de un contenedor se pierden al reiniciar el Pod. Los volúmenes persistentes desacoplan el ciclo de vida de los datos del ciclo de vida del Pod.

2. **StorageClass:** Define la "clase" de almacenamiento disponible. Con `WaitForFirstConsumer`, el binding se retrasa hasta que un Pod necesite el volumen, mejorando la localidad del scheduling.

3. **PV/PVC:** El PV es el recurso de almacenamiento físico; el PVC es la solicitud del usuario. Esta separación permite a los administradores gestionar el almacenamiento independientemente de los desarrolladores.

4. **ReclaimPolicy: Retain:** Los datos persisten incluso después de eliminar el PVC, evitando pérdida accidental de datos en producción.

5. **CronJobs para operaciones de mantenimiento:** Automatizar backups, limpieza y otras tareas periódicas es una práctica esencial en entornos productivos.
