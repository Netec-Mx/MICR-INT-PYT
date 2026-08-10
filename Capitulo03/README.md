# Construir y publicar una imagen Docker

## Metadatos

| Campo | Valor |
|-------|-------|
| **Duración** | 64 minutos |
| **Complejidad** | Media |
| **Nivel Bloom** | Crear |

## Descripción General

En esta práctica construirás la infraestructura de contenedorización del `products-service` desarrollado en la práctica anterior. Crearás un Dockerfile multi-stage optimizado, aplicarás buenas prácticas de seguridad (usuario no-root) y eficiencia (capas ordenadas, `.dockerignore`), verificarás el funcionamiento del contenedor localmente y publicarás la imagen resultante en Docker Hub para su uso posterior en Kubernetes.

## Objetivos de Aprendizaje

- [ ] Escribir un Dockerfile multi-stage optimizado usando `python:3.12.3-slim` como imagen base
- [ ] Aplicar buenas prácticas de construcción: `.dockerignore`, usuario no-root (UID 1001), ordenamiento eficiente de capas
- [ ] Construir, ejecutar y verificar la imagen Docker del `products-service` localmente
- [ ] Analizar el tamaño y las capas de la imagen con `docker history` y `docker inspect`
- [ ] Etiquetar y publicar la imagen en Docker Hub con la convención `[usuario]/products-service:1.0.0`

## Prerrequisitos

### Conocimientos previos

- Práctica 02-00-01 completada con el `products-service` funcional en `~/microservicios-curso/products-service/`
- Comprensión básica de sistemas de archivos Linux y permisos de usuario
- Familiaridad con los conceptos de imágenes y contenedores Docker (Lección 3.1)

### Acceso requerido

- Docker Engine 26.1.3 instalado y daemon en ejecución
- Cuenta activa en Docker Hub (https://hub.docker.com)
- Conexión a Internet para descargar imágenes base y publicar la imagen

## Entorno del Laboratorio

### Software necesario

| Herramienta | Versión | Verificación |
|-------------|---------|--------------|
| Docker Engine | 26.1.3+ | `docker --version` |
| Docker CLI | 26.1.3+ | `docker info` |
| curl | 8.7.1+ | `curl --version` |
| Git | 2.45.1+ | `git --version` |

### Verificación del entorno

```bash
# Verificar que Docker está operativo
docker info > /dev/null 2>&1 && echo "✓ Docker operativo" || echo "✗ Docker no disponible"

# Verificar que el products-service existe
ls ~/microservicios-curso/products-service/main.py && echo "✓ Código fuente presente" || echo "✗ Falta el código fuente"

# Verificar estructura esperada
ls ~/microservicios-curso/products-service/requirements.txt && echo "✓ requirements.txt presente" || echo "✗ Falta requirements.txt"
```

## Procedimiento Paso a Paso

### Paso 1: Crear el archivo `.dockerignore`

**Objetivo:** Excluir archivos innecesarios del contexto de construcción para reducir el tamaño de la imagen y acelerar el proceso de build.

**Instrucciones:**

1. Navega al directorio del servicio:

```bash
cd ~/microservicios-curso/products-service/
```

2. Crea el archivo `.dockerignore` con las exclusiones necesarias:

```bash
cat > .dockerignore << 'EOF'
# Entorno virtual de Python
.venv/
venv/
env/

# Cache de Python
__pycache__/
*.pyc
*.pyo
*.pyd
.Python

# Tests (no necesarios en producción)
tests/
test_*.py
*_test.py
pytest.ini
.pytest_cache/

# Control de versiones
.git/
.gitignore

# IDE y editores
.vscode/
.idea/
*.swp
*.swo

# Docker
Dockerfile
.dockerignore
docker-compose*.yml

# Documentación
*.md
docs/

# Variables de entorno locales
.env
.env.local
EOF
```

3. Verifica el contenido del archivo:

```bash
cat .dockerignore
```

**Resultado esperado:**

El archivo `.dockerignore` debe mostrar todas las exclusiones listadas, organizadas por categoría con comentarios descriptivos.

**Verificación:**

```bash
# Contar líneas no vacías y no comentadas
grep -v '^#' .dockerignore | grep -v '^$' | wc -l
```

Debe mostrar aproximadamente 20 patrones de exclusión.

---

### Paso 2: Verificar el archivo `requirements.txt`

**Objetivo:** Asegurar que las dependencias del proyecto están correctamente definidas antes de construir la imagen.

**Instrucciones:**

1. Verifica que el archivo `requirements.txt` existe y contiene las dependencias necesarias:

```bash
cat ~/microservicios-curso/products-service/requirements.txt
```

2. Si el archivo no existe o está incompleto, créalo con las dependencias del `products-service`:

```bash
cat > ~/microservicios-curso/products-service/requirements.txt << 'EOF'
fastapi==0.111.0
uvicorn==0.30.1
pydantic==2.7.1
EOF
```

**Resultado esperado:**

```
fastapi==0.111.0
uvicorn==0.30.1
pydantic==2.7.1
```

**Verificación:**

```bash
grep -c "==" requirements.txt
```

Debe mostrar al menos `3` dependencias con versiones fijadas.

---

### Paso 3: Escribir el Dockerfile multi-stage

**Objetivo:** Crear un Dockerfile optimizado con dos stages (builder y runtime) que produzca una imagen ligera y segura.

**Instrucciones:**

1. Crea el Dockerfile en el directorio del servicio:

```bash
cat > ~/microservicios-curso/products-service/Dockerfile << 'EOF'
# ============================================
# Stage 1: Builder - Instalar dependencias
# ============================================
FROM python:3.12.3-slim AS builder

WORKDIR /build

# Copiar solo requirements primero (aprovecha caché de capas)
COPY requirements.txt .

# Instalar dependencias en un directorio aislado
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ============================================
# Stage 2: Runtime - Imagen final optimizada
# ============================================
FROM python:3.12.3-slim AS runtime

# Metadatos de la imagen
LABEL maintainer="estudiante@microservicios-curso"
LABEL version="1.0.0"
LABEL description="Products Service - Microservicios Curso"

# Crear usuario no-root para seguridad
RUN groupadd -g 1001 appgroup && \
    useradd -r -u 1001 -g appgroup -d /app -s /sbin/nologin appuser

# Establecer directorio de trabajo
WORKDIR /app

# Copiar dependencias instaladas desde el stage builder
COPY --from=builder /install /usr/local

# Copiar código fuente de la aplicación
COPY . .

# Cambiar propietario de los archivos al usuario no-root
RUN chown -R appuser:appgroup /app

# Cambiar al usuario no-root
USER appuser

# Exponer el puerto de la aplicación
EXPOSE 8000

# Comando de inicio
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
EOF
```

2. Revisa la estructura del Dockerfile:

```bash
cat -n ~/microservicios-curso/products-service/Dockerfile
```

**Resultado esperado:**

Un Dockerfile con dos stages claramente separados:
- **builder**: usa `python:3.12.3-slim`, instala dependencias con `--prefix=/install`
- **runtime**: usa `python:3.12.3-slim`, crea usuario no-root (UID 1001), copia dependencias del builder, copia código, expone puerto 8000

**Verificación:**

```bash
# Verificar que el Dockerfile tiene dos stages FROM
grep -c "^FROM" Dockerfile
```

Debe mostrar `2`.

```bash
# Verificar usuario no-root
grep "USER appuser" Dockerfile && echo "✓ Usuario no-root configurado"
```

---

### Paso 4: Construir la imagen Docker

**Objetivo:** Ejecutar el build de la imagen Docker y verificar que se construye correctamente con la etiqueta local definida.

**Instrucciones:**

1. Asegúrate de estar en el directorio correcto:

```bash
cd ~/microservicios-curso/products-service/
```

2. Construye la imagen con la etiqueta local:

```bash
docker build -t microservicios-curso/products-service:1.0.0 .
```

3. Observa la salida del build. Deberías ver los dos stages ejecutándose secuencialmente.

4. Verifica que la imagen aparece en el registro local:

```bash
docker images | grep products-service
```

**Resultado esperado:**

```
microservicios-curso/products-service   1.0.0     <hash>    <tiempo>    <tamaño>
```

El tamaño esperado debe estar entre 150-200 MB aproximadamente (gracias al uso de `slim` y multi-stage).

**Verificación:**

```bash
# Verificar que la imagen existe
docker image inspect microservicios-curso/products-service:1.0.0 > /dev/null 2>&1 && \
  echo "✓ Imagen construida exitosamente" || \
  echo "✗ Error: imagen no encontrada"
```

---

### Paso 5: Ejecutar y verificar el contenedor

**Objetivo:** Levantar un contenedor desde la imagen construida y validar que el `products-service` responde correctamente a peticiones HTTP.

**Instrucciones:**

1. Ejecuta el contenedor en modo detached, mapeando el puerto 8000:

```bash
docker run -d \
  --name products-service-test \
  -p 8000:8000 \
  microservicios-curso/products-service:1.0.0
```

2. Verifica que el contenedor está en ejecución:

```bash
docker ps --filter name=products-service-test
```

3. Espera 2 segundos para que Uvicorn inicie y prueba el endpoint de salud o raíz:

```bash
sleep 2
curl -s http://localhost:8000/ | python3 -m json.tool
```

4. Prueba el endpoint de productos (GET):

```bash
curl -s http://localhost:8000/products | python3 -m json.tool
```

5. Prueba crear un producto (POST):

```bash
curl -s -X POST http://localhost:8000/products \
  -H "Content-Type: application/json" \
  -d '{"name": "Laptop", "price": 999.99, "quantity": 10}' | python3 -m json.tool
```

6. Verifica que el contenedor ejecuta con usuario no-root:

```bash
docker exec products-service-test whoami
```

7. Revisa los logs del contenedor:

```bash
docker logs products-service-test
```

**Resultado esperado:**

- El comando `docker ps` muestra el contenedor con estado `Up`
- Los endpoints responden con JSON válido (código HTTP 200)
- El comando `whoami` dentro del contenedor retorna `appuser`
- Los logs muestran Uvicorn iniciado en `0.0.0.0:8000`

**Verificación:**

```bash
# Test completo de conectividad
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/products)
if [ "$HTTP_CODE" = "200" ]; then
  echo "✓ Servicio respondiendo correctamente (HTTP $HTTP_CODE)"
else
  echo "✗ Error: servicio no responde (HTTP $HTTP_CODE)"
fi
```

---

### Paso 6: Analizar capas y tamaño de la imagen

**Objetivo:** Inspeccionar la composición interna de la imagen para comprender la estructura de capas y validar la optimización.

**Instrucciones:**

1. Analiza el historial de capas de la imagen:

```bash
docker history microservicios-curso/products-service:1.0.0
```

2. Para ver los comandos completos sin truncar:

```bash
docker history --no-trunc microservicios-curso/products-service:1.0.0
```

3. Inspecciona los metadatos de la imagen:

```bash
docker inspect microservicios-curso/products-service:1.0.0 | python3 -m json.tool | head -60
```

4. Verifica el usuario configurado en la imagen:

```bash
docker inspect --format='{{.Config.User}}' microservicios-curso/products-service:1.0.0
```

5. Verifica el puerto expuesto:

```bash
docker inspect --format='{{json .Config.ExposedPorts}}' microservicios-curso/products-service:1.0.0
```

6. Compara el tamaño con la imagen base:

```bash
echo "=== Tamaño imagen base ==="
docker images python:3.12.3-slim --format "{{.Size}}"
echo "=== Tamaño products-service ==="
docker images microservicios-curso/products-service:1.0.0 --format "{{.Size}}"
```

**Resultado esperado:**

- `docker history` muestra las capas individuales con sus tamaños
- El usuario configurado es `appuser` (o `1001`)
- El puerto expuesto es `8000/tcp`
- La imagen `products-service:1.0.0` es mayor que la base `python:3.12.3-slim` pero menor que 250 MB

**Verificación:**

```bash
# Verificar que la imagen no excede 250MB
SIZE=$(docker inspect --format='{{.Size}}' microservicios-curso/products-service:1.0.0)
SIZE_MB=$((SIZE / 1024 / 1024))
echo "Tamaño de la imagen: ${SIZE_MB} MB"
if [ "$SIZE_MB" -lt 250 ]; then
  echo "✓ Tamaño optimizado (< 250 MB)"
else
  echo "⚠ Imagen mayor de lo esperado"
fi
```

---

### Paso 7: Detener y eliminar el contenedor de prueba

**Objetivo:** Limpiar el contenedor de prueba antes de proceder con la publicación.

**Instrucciones:**

1. Detén el contenedor de prueba:

```bash
docker stop products-service-test
```

2. Elimina el contenedor:

```bash
docker rm products-service-test
```

3. Verifica que el puerto 8000 está libre:

```bash
docker ps --filter publish=8000 --format "{{.Names}}" | wc -l
```

**Resultado esperado:**

El comando final debe retornar `0`, indicando que no hay contenedores usando el puerto 8000.

---

### Paso 8: Etiquetar la imagen para Docker Hub

**Objetivo:** Crear la etiqueta con el formato requerido para publicar en Docker Hub.

**Instrucciones:**

1. Define tu usuario de Docker Hub como variable (reemplaza `tu-usuario` con tu nombre de usuario real):

```bash
export DOCKERHUB_USER="tu-usuario"
```

2. Etiqueta la imagen con la convención de nombrado del curso:

```bash
docker tag microservicios-curso/products-service:1.0.0 \
  ${DOCKERHUB_USER}/products-service:1.0.0
```

3. Opcionalmente, añade también la etiqueta `latest`:

```bash
docker tag microservicios-curso/products-service:1.0.0 \
  ${DOCKERHUB_USER}/products-service:latest
```

4. Verifica las etiquetas creadas:

```bash
docker images | grep products-service
```

**Resultado esperado:**

```
microservicios-curso/products-service   1.0.0     <hash>   <tiempo>   <tamaño>
tu-usuario/products-service             1.0.0     <hash>   <tiempo>   <tamaño>
tu-usuario/products-service             latest    <hash>   <tiempo>   <tamaño>
```

Las tres etiquetas deben compartir el mismo IMAGE ID.

**Verificación:**

```bash
# Verificar que las etiquetas apuntan a la misma imagen
ID_LOCAL=$(docker inspect --format='{{.Id}}' microservicios-curso/products-service:1.0.0)
ID_HUB=$(docker inspect --format='{{.Id}}' ${DOCKERHUB_USER}/products-service:1.0.0)
if [ "$ID_LOCAL" = "$ID_HUB" ]; then
  echo "✓ Etiquetas apuntan a la misma imagen"
else
  echo "✗ Error: IDs no coinciden"
fi
```

---

### Paso 9: Autenticarse y publicar en Docker Hub

**Objetivo:** Iniciar sesión en Docker Hub y subir la imagen para que esté disponible públicamente.

**Instrucciones:**

1. Inicia sesión en Docker Hub:

```bash
docker login
```

Introduce tu nombre de usuario y contraseña (o token de acceso) cuando se solicite.

2. Publica la imagen con la etiqueta versionada:

```bash
docker push ${DOCKERHUB_USER}/products-service:1.0.0
```

3. Publica también la etiqueta `latest`:

```bash
docker push ${DOCKERHUB_USER}/products-service:latest
```

4. Observa la salida del push: Docker sube solo las capas que no existen ya en el registro.

**Resultado esperado:**

```
The push refers to repository [docker.io/tu-usuario/products-service]
<hash>: Pushed
<hash>: Pushed
<hash>: Mounted from library/python
...
1.0.0: digest: sha256:<digest> size: <size>
```

**Verificación:**

```bash
# Verificar que la imagen es accesible en Docker Hub
docker manifest inspect ${DOCKERHUB_USER}/products-service:1.0.0 > /dev/null 2>&1 && \
  echo "✓ Imagen publicada exitosamente en Docker Hub" || \
  echo "✗ Error: imagen no encontrada en Docker Hub"
```

---

### Paso 10: Registrar cambios en Git

**Objetivo:** Hacer commit de los archivos de contenedorización al repositorio del curso.

**Instrucciones:**

1. Navega al directorio raíz del curso:

```bash
cd ~/microservicios-curso/
```

2. Verifica los archivos nuevos:

```bash
git status
```

3. Añade los archivos de Docker al staging:

```bash
git add products-service/.dockerignore products-service/Dockerfile
```

4. Realiza el commit:

```bash
git commit -m "[lab03] Añadir Dockerfile multi-stage y .dockerignore para products-service"
```

**Resultado esperado:**

```
[main <hash>] [lab03] Añadir Dockerfile multi-stage y .dockerignore para products-service
 2 files changed, XX insertions(+)
 create mode 100644 products-service/.dockerignore
 create mode 100644 products-service/Dockerfile
```

**Verificación:**

```bash
git log --oneline -1
```

Debe mostrar el commit con el prefijo `[lab03]`.

---

## Validación y Pruebas

Ejecuta la siguiente secuencia completa de validación para confirmar que todos los objetivos se han cumplido:

```bash
#!/bin/bash
echo "========================================="
echo "  VALIDACIÓN COMPLETA - Lab 03-00-01"
echo "========================================="

PASS=0
FAIL=0

# Test 1: .dockerignore existe
if [ -f ~/microservicios-curso/products-service/.dockerignore ]; then
  echo "✓ [1/7] .dockerignore existe"
  ((PASS++))
else
  echo "✗ [1/7] .dockerignore NO encontrado"
  ((FAIL++))
fi

# Test 2: Dockerfile existe y tiene 2 stages
STAGES=$(grep -c "^FROM" ~/microservicios-curso/products-service/Dockerfile 2>/dev/null)
if [ "$STAGES" = "2" ]; then
  echo "✓ [2/7] Dockerfile multi-stage (2 stages)"
  ((PASS++))
else
  echo "✗ [2/7] Dockerfile no tiene 2 stages (encontrados: $STAGES)"
  ((FAIL++))
fi

# Test 3: Dockerfile tiene usuario no-root
if grep -q "USER" ~/microservicios-curso/products-service/Dockerfile; then
  echo "✓ [3/7] Usuario no-root configurado en Dockerfile"
  ((PASS++))
else
  echo "✗ [3/7] No se encontró instrucción USER"
  ((FAIL++))
fi

# Test 4: Imagen construida localmente
if docker image inspect microservicios-curso/products-service:1.0.0 > /dev/null 2>&1; then
  echo "✓ [4/7] Imagen local construida"
  ((PASS++))
else
  echo "✗ [4/7] Imagen local no encontrada"
  ((FAIL++))
fi

# Test 5: Imagen funciona correctamente
docker run -d --name validation-test -p 8000:8000 microservicios-curso/products-service:1.0.0 > /dev/null 2>&1
sleep 3
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/products 2>/dev/null)
docker stop validation-test > /dev/null 2>&1
docker rm validation-test > /dev/null 2>&1
if [ "$HTTP_CODE" = "200" ]; then
  echo "✓ [5/7] Contenedor responde HTTP 200"
  ((PASS++))
else
  echo "✗ [5/7] Contenedor no responde correctamente (HTTP $HTTP_CODE)"
  ((FAIL++))
fi

# Test 6: Imagen etiquetada para Docker Hub
if docker images | grep -q "${DOCKERHUB_USER}/products-service.*1.0.0"; then
  echo "✓ [6/7] Imagen etiquetada para Docker Hub"
  ((PASS++))
else
  echo "✗ [6/7] Etiqueta Docker Hub no encontrada"
  ((FAIL++))
fi

# Test 7: Commit en Git
LAST_COMMIT=$(cd ~/microservicios-curso && git log --oneline -1)
if echo "$LAST_COMMIT" | grep -q "\[lab03\]"; then
  echo "✓ [7/7] Commit registrado con prefijo [lab03]"
  ((PASS++))
else
  echo "✗ [7/7] Commit no encontrado con prefijo [lab03]"
  ((FAIL++))
fi

echo "========================================="
echo "  Resultado: $PASS/7 pruebas exitosas"
echo "========================================="
if [ "$FAIL" -eq 0 ]; then
  echo "  ✓ LABORATORIO COMPLETADO EXITOSAMENTE"
else
  echo "  ⚠ Revisar los puntos fallidos"
fi
```

---

## Resolución de Problemas

### Problema 1: Error "permission denied" al ejecutar el contenedor

**Síntomas:**

```
PermissionError: [Errno 13] Permission denied: '/app/...'
```

O el contenedor se detiene inmediatamente con código de salida 1.

**Causa:**

El usuario `appuser` (UID 1001) no tiene permisos de lectura sobre los archivos copiados al contenedor. Esto ocurre cuando la instrucción `COPY . .` se ejecuta antes del `chown` o cuando el `chown` no se aplica correctamente.

**Solución:**

1. Verifica que en el Dockerfile la instrucción `RUN chown -R appuser:appgroup /app` aparece **después** de todos los `COPY` y **antes** de `USER appuser`:

```dockerfile
COPY --from=builder /install /usr/local
COPY . .
RUN chown -R appuser:appgroup /app
USER appuser
```

2. Reconstruye la imagen:

```bash
docker build --no-cache -t microservicios-curso/products-service:1.0.0 .
```

---

### Problema 2: Error "port is already allocated" al ejecutar el contenedor

**Síntomas:**

```
docker: Error response from daemon: driver failed programming external connectivity 
on endpoint products-service-test: Bind for 0.0.0.0:8000 failed: port is already allocated.
```

**Causa:**

Otro proceso o contenedor ya está usando el puerto 8000 en el host. Puede ser una instancia previa del contenedor que no se detuvo correctamente, o Uvicorn ejecutándose localmente fuera de Docker.

**Solución:**

1. Identifica qué está usando el puerto:

```bash
# Buscar contenedores usando el puerto
docker ps --filter publish=8000

# Buscar procesos del sistema usando el puerto
sudo lsof -i :8000
```

2. Detén el proceso o contenedor conflictivo:

```bash
# Si es un contenedor Docker
docker stop $(docker ps -q --filter publish=8000)
docker rm $(docker ps -aq --filter publish=8000)

# Si es un proceso local (ejemplo: uvicorn)
kill $(sudo lsof -t -i :8000)
```

3. Vuelve a ejecutar el contenedor:

```bash
docker run -d --name products-service-test -p 8000:8000 \
  microservicios-curso/products-service:1.0.0
```

---

## Limpieza

Al finalizar la práctica, ejecuta los siguientes comandos para liberar recursos (manteniendo la imagen para prácticas posteriores):

```bash
# Detener y eliminar contenedores de prueba residuales
docker stop products-service-test 2>/dev/null
docker rm products-service-test 2>/dev/null

# Eliminar imágenes intermedias huérfanas (dangling)
docker image prune -f

# Verificar estado final
echo "=== Imágenes products-service conservadas ==="
docker images | grep products-service
```

> **Nota importante:** NO elimines la imagen `microservicios-curso/products-service:1.0.0` ni la imagen publicada en Docker Hub. Serán necesarias en la práctica 04-00-01 para el despliegue en Kubernetes.

---

## Resumen

En esta práctica has completado el ciclo completo de contenedorización de un microservicio Python:

| Artefacto creado | Ubicación |
|------------------|-----------|
| `.dockerignore` | `~/microservicios-curso/products-service/.dockerignore` |
| `Dockerfile` (multi-stage) | `~/microservicios-curso/products-service/Dockerfile` |
| Imagen local | `microservicios-curso/products-service:1.0.0` |
| Imagen en Docker Hub | `[tu-usuario]/products-service:1.0.0` |

**Conceptos clave aplicados:**

- **Multi-stage build**: Separar la instalación de dependencias (builder) de la imagen final (runtime) reduce el tamaño al no incluir herramientas de compilación
- **Usuario no-root**: Ejecutar con UID 1001 sigue el principio de mínimo privilegio, reduciendo la superficie de ataque
- **Orden de capas**: Copiar `requirements.txt` antes del código fuente permite aprovechar la caché de Docker cuando solo cambia el código
- **`.dockerignore`**: Evita enviar archivos innecesarios al daemon, acelerando el build y reduciendo el tamaño de la imagen

### Recursos adicionales

- [Dockerfile best practices](https://docs.docker.com/develop/develop-images/dockerfile_best-practices/)
- [Docker multi-stage builds](https://docs.docker.com/build/building/multi-stage/)
- [Docker Hub quickstart](https://docs.docker.com/docker-hub/)
- [Referencia de instrucciones Dockerfile](https://docs.docker.com/engine/reference/builder/)
