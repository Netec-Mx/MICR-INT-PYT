# Implementar Caching con Redis en Servicio Python

## Metadata

| Campo | Valor |
|-------|-------|
| **Duración** | 63 minutos |
| **Complejidad** | Media |
| **Nivel Bloom** | Aplicar |

## Descripción General

En esta práctica integrarás Redis 7.2.5 como capa de caché en el `catalog-service` construido en el Lab 08. Implementarás los patrones **cache-aside** (lazy loading) para lecturas y **write-through** para escrituras, aplicando TTL diferenciado y estrategias de invalidación por tags. Finalmente, medirás el impacto en rendimiento mediante benchmarking con Locust comparando latencia y throughput con y sin caché.

## Objetivos de Aprendizaje

- [ ] Implementar el patrón cache-aside con Redis asíncrono para cachear consultas frecuentes de productos
- [ ] Aplicar el patrón write-through para mantener consistencia entre Redis y las bases de datos en operaciones de escritura
- [ ] Configurar TTL diferenciado (300s para productos individuales, 60s para listados) y estrategias de invalidación por tags
- [ ] Crear decoradores Python reutilizables `@cache_response` e `@invalidate_cache` para abstraer la lógica de caché
- [ ] Medir y comparar latencia P95 y RPS con y sin caché usando Locust con 100 usuarios concurrentes

## Prerrequisitos

### Conocimientos Requeridos

- Familiaridad con FastAPI y programación asíncrona en Python (async/await)
- Comprensión de los patrones Cache-Aside y Write-Through (Lección 9.1)
- Experiencia básica con Docker Compose y redes Docker
- Lab 08-00-01 completado con `catalog-service`, PostgreSQL y MongoDB operativos

### Acceso y Recursos

- Red Docker `microservices-net` activa con contenedores del Lab 08 corriendo
- Imagen `redis:7.2.5-alpine` disponible localmente
- Python 3.12.3 con entorno virtual configurado
- Conexión a Internet para descargar dependencias Python

## Entorno del Laboratorio

### Software Requerido

| Componente | Versión | Propósito |
|------------|---------|-----------|
| Redis | 7.2.5 (alpine) | Motor de caché distribuida |
| redis-py | 5.0.6 | Cliente asíncrono Python para Redis |
| FastAPI | 0.111.0 | Framework del microservicio |
| Locust | 2.29.1 | Herramienta de benchmarking |
| Docker Compose | 2.27.1 | Orquestación de contenedores |

### Preparación del Entorno

```bash
# Crear directorio de trabajo
mkdir -p ~/microservicios-curso/lab09
cd ~/microservicios-curso/lab09

# Crear y activar entorno virtual
python3 -m venv venv
source venv/bin/activate

# Instalar dependencias
pip install "fastapi==0.111.0" "uvicorn[standard]==0.30.1" "redis[hiredis]==5.0.6" \
  "pydantic==2.7.1" "httpx==0.27.0" "locust==2.29.1" "motor==3.4.0" \
  "asyncpg==0.29.0" "sqlalchemy[asyncio]==2.0.30"
```

## Paso a Paso

### Paso 1: Levantar Redis con Docker Compose (8 min)

**Objetivo:** Añadir Redis 7.2.5 al stack existente del Lab 08 con configuración de memoria y política de evicción LRU.

**Instrucciones:**

1. Crea el archivo de configuración personalizada de Redis:

```bash
mkdir -p ~/microservicios-curso/lab09/redis
cat > ~/microservicios-curso/lab09/redis/redis.conf << 'EOF'
# Configuración de Redis para caché
maxmemory 256mb
maxmemory-policy allkeys-lru
save ""
appendonly no
tcp-keepalive 60
timeout 300
EOF
```

2. Crea el archivo `docker-compose.yml` extendiendo el stack del Lab 08:

```yaml
cat > ~/microservicios-curso/lab09/docker-compose.yml << 'EOF'
version: "3.9"

services:
  postgres:
    image: postgres:16.3-alpine
    container_name: postgres
    environment:
      POSTGRES_DB: catalog
      POSTGRES_USER: catalog_user
      POSTGRES_PASSWORD: catalog_pass_2024
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - microservices-net
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U catalog_user -d catalog"]
      interval: 5s
      timeout: 3s
      retries: 5

  mongo:
    image: mongo:7.0.11
    container_name: mongo
    environment:
      MONGO_INITDB_ROOT_USERNAME: mongo_user
      MONGO_INITDB_ROOT_PASSWORD: mongo_pass_2024
    ports:
      - "27017:27017"
    volumes:
      - mongo_data:/data/db
    networks:
      - microservices-net
    healthcheck:
      test: ["CMD", "mongosh", "--eval", "db.adminCommand('ping')"]
      interval: 5s
      timeout: 3s
      retries: 5

  redis:
    image: redis:7.2.5-alpine
    container_name: redis-cache
    ports:
      - "6379:6379"
    volumes:
      - ./redis/redis.conf:/usr/local/etc/redis/redis.conf:ro
    command: ["redis-server", "/usr/local/etc/redis/redis.conf"]
    networks:
      - microservices-net
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

volumes:
  postgres_data:
  mongo_data:

networks:
  microservices-net:
    name: microservices-net
    driver: bridge
EOF
```

3. Levanta el stack completo:

```bash
cd ~/microservicios-curso/lab09
docker compose up -d
```

4. Verifica que Redis está operativo:

```bash
docker exec redis-cache redis-cli ping
docker exec redis-cache redis-cli CONFIG GET maxmemory
docker exec redis-cache redis-cli CONFIG GET maxmemory-policy
```

**Salida esperada:**

```
PONG
1) "maxmemory"
2) "268435456"
1) "maxmemory-policy"
2) "allkeys-lru"
```

**Verificación:**

```bash
docker compose ps --format "table {{.Name}}\t{{.Status}}"
```

Los tres servicios deben mostrar estado `Up (healthy)`.

---

### Paso 2: Crear el módulo de conexión Redis asíncrono (7 min)

**Objetivo:** Implementar un cliente Redis asíncrono reutilizable con pool de conexiones para integrar con FastAPI sin bloquear el event loop.

**Instrucciones:**

1. Crea la estructura del proyecto:

```bash
mkdir -p ~/microservicios-curso/lab09/catalog_service/{routers,services,cache}
touch ~/microservicios-curso/lab09/catalog_service/__init__.py
touch ~/microservicios-curso/lab09/catalog_service/routers/__init__.py
touch ~/microservicios-curso/lab09/catalog_service/services/__init__.py
touch ~/microservicios-curso/lab09/catalog_service/cache/__init__.py
```

2. Crea el módulo de conexión Redis:

```python
cat > ~/microservicios-curso/lab09/catalog_service/cache/connection.py << 'EOF'
"""
Módulo de conexión asíncrona a Redis.
Gestiona el pool de conexiones y el ciclo de vida del cliente.
"""
import redis.asyncio as aioredis
from typing import Optional

# Instancia global del cliente Redis
_redis_client: Optional[aioredis.Redis] = None

REDIS_URL = "redis://localhost:6379/0"


async def get_redis() -> aioredis.Redis:
    """Retorna la instancia del cliente Redis."""
    global _redis_client
    if _redis_client is None:
        raise RuntimeError("Redis no está inicializado. Llama a init_redis() primero.")
    return _redis_client


async def init_redis(url: str = REDIS_URL) -> aioredis.Redis:
    """
    Inicializa el pool de conexiones Redis.
    Se invoca durante el startup de FastAPI.
    """
    global _redis_client
    _redis_client = aioredis.from_url(
        url,
        encoding="utf-8",
        decode_responses=True,
        max_connections=20,
        socket_connect_timeout=5,
        socket_timeout=5,
    )
    # Verificar conectividad
    await _redis_client.ping()
    return _redis_client


async def close_redis() -> None:
    """Cierra el pool de conexiones Redis."""
    global _redis_client
    if _redis_client:
        await _redis_client.close()
        _redis_client = None
EOF
```

3. Verifica la sintaxis:

```bash
cd ~/microservicios-curso/lab09
python -c "import catalog_service.cache.connection; print('OK: módulo de conexión válido')"
```

**Salida esperada:**

```
OK: módulo de conexión válido
```

**Verificación:**

El módulo se importa sin errores y define las tres funciones: `init_redis`, `get_redis`, `close_redis`.

---

### Paso 3: Implementar decoradores de caché reutilizables (12 min)

**Objetivo:** Crear los decoradores `@cache_response` e `@invalidate_cache` que encapsulan la lógica de los patrones cache-aside y write-through respectivamente.

**Instrucciones:**

1. Crea el módulo de decoradores:

```python
cat > ~/microservicios-curso/lab09/catalog_service/cache/decorators.py << 'EOF'
"""
Decoradores reutilizables para caching con Redis.
- @cache_response: implementa el patrón Cache-Aside (lazy loading)
- @invalidate_cache: invalida entradas de caché por tags tras escrituras
"""
import json
import hashlib
import functools
from typing import Callable, Optional, List

from catalog_service.cache.connection import get_redis

# TTL diferenciado por tipo de dato (en segundos)
TTL_PRODUCT_DETAIL = 300  # 5 minutos para producto individual
TTL_PRODUCT_LIST = 60     # 1 minuto para listados


def _generate_cache_key(prefix: str, *args, **kwargs) -> str:
    """Genera una clave de caché determinista basada en los argumentos."""
    key_data = f"{prefix}:{args}:{sorted(kwargs.items())}"
    key_hash = hashlib.md5(key_data.encode()).hexdigest()
    return f"cache:{prefix}:{key_hash}"


def cache_response(
    prefix: str,
    ttl: int = TTL_PRODUCT_DETAIL,
    tags: Optional[List[str]] = None
):
    """
    Decorador Cache-Aside (Lazy Loading).
    
    - Verifica si el resultado existe en Redis (hit).
    - Si no existe (miss), ejecuta la función, almacena en Redis con TTL.
    - Registra la clave en los tags proporcionados para invalidación futura.
    
    Args:
        prefix: Prefijo para la clave de caché (ej: 'product', 'product_list')
        ttl: Tiempo de vida en segundos
        tags: Lista de tags para agrupar claves relacionadas
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            redis = await get_redis()
            cache_key = _generate_cache_key(prefix, *args, **kwargs)

            # Intentar obtener de caché (Cache Hit)
            cached_data = await redis.get(cache_key)
            if cached_data is not None:
                return json.loads(cached_data)

            # Cache Miss: ejecutar función original
            result = await func(*args, **kwargs)

            if result is not None:
                # Almacenar en Redis con TTL
                await redis.setex(
                    cache_key,
                    ttl,
                    json.dumps(result, default=str)
                )

                # Registrar clave en tags para invalidación
                if tags:
                    for tag in tags:
                        tag_key = f"tag:{tag}"
                        await redis.sadd(tag_key, cache_key)
                        # El tag expira después del TTL más largo posible
                        await redis.expire(tag_key, ttl + 60)

            return result
        return wrapper
    return decorator


def invalidate_cache(tags: List[str]):
    """
    Decorador Write-Through: invalida entradas de caché por tags.
    
    Se aplica a funciones de escritura (crear, actualizar, eliminar).
    Tras ejecutar la escritura, elimina todas las claves asociadas a los tags.
    
    Args:
        tags: Lista de tags cuyas claves asociadas se invalidarán
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Ejecutar la escritura primero (write-through)
            result = await func(*args, **kwargs)

            # Invalidar caché por tags
            redis = await get_redis()
            for tag in tags:
                tag_key = f"tag:{tag}"
                # Obtener todas las claves asociadas al tag
                cached_keys = await redis.smembers(tag_key)
                if cached_keys:
                    # Eliminar todas las claves cacheadas
                    await redis.delete(*cached_keys)
                    # Eliminar el tag mismo
                    await redis.delete(tag_key)

            return result
        return wrapper
    return decorator
EOF
```

2. Crea el archivo `__init__.py` del módulo cache para exportar los decoradores:

```python
cat > ~/microservicios-curso/lab09/catalog_service/cache/__init__.py << 'EOF'
from catalog_service.cache.decorators import cache_response, invalidate_cache
from catalog_service.cache.connection import init_redis, close_redis, get_redis

__all__ = [
    "cache_response",
    "invalidate_cache",
    "init_redis",
    "close_redis",
    "get_redis",
]
EOF
```

3. Verifica la importación:

```bash
cd ~/microservicios-curso/lab09
python -c "from catalog_service.cache import cache_response, invalidate_cache; print('OK: decoradores importados')"
```

**Salida esperada:**

```
OK: decoradores importados
```

**Verificación:**

Los decoradores se importan correctamente y están listos para aplicarse en la capa de servicio.

---

### Paso 4: Implementar la capa de servicio con caché integrado (12 min)

**Objetivo:** Crear el servicio de productos que aplica los decoradores de caché sobre las operaciones CRUD, implementando cache-aside en lecturas y write-through en escrituras.

**Instrucciones:**

1. Crea el modelo de datos:

```python
cat > ~/microservicios-curso/lab09/catalog_service/models.py << 'EOF'
"""Modelos Pydantic para el catalog-service."""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ProductCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(default="", max_length=1000)
    price: float = Field(..., gt=0)
    category: str = Field(..., min_length=1, max_length=100)
    stock: int = Field(default=0, ge=0)


class ProductUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    price: Optional[float] = Field(None, gt=0)
    category: Optional[str] = Field(None, min_length=1, max_length=100)
    stock: Optional[int] = Field(None, ge=0)


class ProductResponse(BaseModel):
    id: str
    name: str
    description: str
    price: float
    category: str
    stock: int
    created_at: str
    updated_at: str
EOF
```

2. Crea el servicio de productos con caché integrado:

```python
cat > ~/microservicios-curso/lab09/catalog_service/services/product_service.py << 'EOF'
"""
Servicio de productos con caching Redis integrado.
- Lecturas: patrón Cache-Aside (lazy loading)
- Escrituras: patrón Write-Through con invalidación por tags
"""
import uuid
from datetime import datetime, timezone
from typing import Optional, List

from catalog_service.cache import cache_response, invalidate_cache
from catalog_service.cache.decorators import TTL_PRODUCT_DETAIL, TTL_PRODUCT_LIST

# Almacén en memoria simulando PostgreSQL/MongoDB del lab 08
# En producción se reemplaza por consultas reales a las bases de datos
_products_db: dict = {}


def _seed_products():
    """Genera datos de ejemplo para pruebas."""
    categories = ["electrónica", "hogar", "deportes", "libros", "ropa"]
    for i in range(1, 51):
        product_id = str(uuid.uuid4())
        _products_db[product_id] = {
            "id": product_id,
            "name": f"Producto {i:03d}",
            "description": f"Descripción del producto {i}",
            "price": round(10.0 + (i * 2.5), 2),
            "category": categories[i % len(categories)],
            "stock": i * 10,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }


# Inicializar datos de ejemplo
_seed_products()


@cache_response(prefix="product_list", ttl=TTL_PRODUCT_LIST, tags=["products"])
async def list_products(skip: int = 0, limit: int = 20) -> List[dict]:
    """
    Lista productos con paginación.
    Cache-Aside: primero busca en Redis, si no existe consulta la 'BD'.
    TTL: 60 segundos para listados.
    """
    products = list(_products_db.values())
    return products[skip:skip + limit]


@cache_response(prefix="product_detail", ttl=TTL_PRODUCT_DETAIL, tags=["products"])
async def get_product(product_id: str) -> Optional[dict]:
    """
    Obtiene un producto por ID.
    Cache-Aside: TTL de 300 segundos para detalles individuales.
    """
    return _products_db.get(product_id)


@invalidate_cache(tags=["products"])
async def create_product(product_data: dict) -> dict:
    """
    Crea un nuevo producto.
    Write-Through: escribe en BD e invalida caché de listados.
    """
    product_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    product = {
        "id": product_id,
        "name": product_data["name"],
        "description": product_data.get("description", ""),
        "price": product_data["price"],
        "category": product_data["category"],
        "stock": product_data.get("stock", 0),
        "created_at": now,
        "updated_at": now,
    }
    _products_db[product_id] = product
    return product


@invalidate_cache(tags=["products"])
async def update_product(product_id: str, update_data: dict) -> Optional[dict]:
    """
    Actualiza un producto existente.
    Write-Through: actualiza BD e invalida caché relacionada.
    """
    if product_id not in _products_db:
        return None

    product = _products_db[product_id]
    for key, value in update_data.items():
        if value is not None:
            product[key] = value
    product["updated_at"] = datetime.now(timezone.utc).isoformat()
    _products_db[product_id] = product
    return product


@invalidate_cache(tags=["products"])
async def delete_product(product_id: str) -> bool:
    """
    Elimina un producto.
    Write-Through: elimina de BD e invalida todo el caché de productos.
    """
    if product_id in _products_db:
        del _products_db[product_id]
        return True
    return False
EOF
```

3. Crea el router de la API:

```python
cat > ~/microservicios-curso/lab09/catalog_service/routers/products.py << 'EOF'
"""Router de productos con endpoints REST."""
from fastapi import APIRouter, HTTPException, Query
from typing import List

from catalog_service.models import ProductCreate, ProductUpdate, ProductResponse
from catalog_service.services import product_service

router = APIRouter(prefix="/api/v1/products", tags=["products"])


@router.get("/", response_model=List[ProductResponse])
async def list_products(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100)
):
    """Lista productos con paginación. Usa caché con TTL de 60s."""
    products = await product_service.list_products(skip=skip, limit=limit)
    return products


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(product_id: str):
    """Obtiene un producto por ID. Usa caché con TTL de 300s."""
    product = await product_service.get_product(product_id=product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return product


@router.post("/", response_model=ProductResponse, status_code=201)
async def create_product(product: ProductCreate):
    """Crea un producto. Invalida caché de listados (write-through)."""
    result = await product_service.create_product(product.model_dump())
    return result


@router.put("/{product_id}", response_model=ProductResponse)
async def update_product(product_id: str, product: ProductUpdate):
    """Actualiza un producto. Invalida caché relacionada (write-through)."""
    update_data = product.model_dump(exclude_unset=True)
    result = await product_service.update_product(product_id, update_data)
    if result is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return result


@router.delete("/{product_id}", status_code=204)
async def delete_product(product_id: str):
    """Elimina un producto. Invalida caché (write-through)."""
    deleted = await product_service.delete_product(product_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
EOF
```

4. Crea la aplicación principal con lifecycle de Redis:

```python
cat > ~/microservicios-curso/lab09/catalog_service/main.py << 'EOF'
"""
Aplicación principal del catalog-service con caching Redis.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI

from catalog_service.cache import init_redis, close_redis
from catalog_service.routers.products import router as products_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestión del ciclo de vida: inicializa y cierra Redis."""
    print("[STARTUP] Conectando a Redis...")
    await init_redis("redis://localhost:6379/0")
    print("[STARTUP] Redis conectado correctamente")
    yield
    print("[SHUTDOWN] Cerrando conexión Redis...")
    await close_redis()
    print("[SHUTDOWN] Redis desconectado")


app = FastAPI(
    title="Catalog Service con Redis Cache",
    version="2.0.0",
    lifespan=lifespan,
)

app.include_router(products_router)


@app.get("/health")
async def health_check():
    """Endpoint de salud."""
    return {"status": "healthy", "cache": "redis"}
EOF
```

5. Inicia el servicio y verifica:

```bash
cd ~/microservicios-curso/lab09
uvicorn catalog_service.main:app --host 0.0.0.0 --port 8000 &
sleep 2
curl -s http://localhost:8000/health | python -m json.tool
```

**Salida esperada:**

```json
{
    "status": "healthy",
    "cache": "redis"
}
```

**Verificación:**

```bash
# Primera llamada (cache miss)
curl -s http://localhost:8000/api/v1/products/?limit=3 | python -m json.tool

# Verificar que se almacenó en Redis
docker exec redis-cache redis-cli KEYS "cache:*"
```

Debes ver al menos una clave con prefijo `cache:product_list:` en Redis.

---

### Paso 5: Verificar patrones de caché con redis-cli (8 min)

**Objetivo:** Confirmar visualmente que los patrones cache-aside y write-through funcionan correctamente inspeccionando Redis directamente.

**Instrucciones:**

1. Realiza una consulta para generar un cache miss seguido de un hit:

```bash
# Primera petición - MISS (se almacena en Redis)
echo "=== Primera petición (MISS) ==="
curl -s -w "\nTiempo: %{time_total}s\n" http://localhost:8000/api/v1/products/?limit=5

# Segunda petición - HIT (se lee de Redis)
echo "=== Segunda petición (HIT) ==="
curl -s -w "\nTiempo: %{time_total}s\n" http://localhost:8000/api/v1/products/?limit=5
```

2. Inspecciona el estado de Redis:

```bash
# Ver todas las claves de caché
docker exec redis-cache redis-cli KEYS "cache:*"

# Ver las claves de tags
docker exec redis-cache redis-cli KEYS "tag:*"

# Ver el TTL de una clave de listado
CACHE_KEY=$(docker exec redis-cache redis-cli KEYS "cache:product_list:*" | head -1)
docker exec redis-cache redis-cli TTL "$CACHE_KEY"

# Ver los miembros del tag 'products'
docker exec redis-cache redis-cli SMEMBERS "tag:products"
```

3. Verifica la invalidación write-through creando un producto:

```bash
# Contar claves antes de la escritura
echo "Claves antes:"
docker exec redis-cache redis-cli DBSIZE

# Crear un producto (dispara invalidación)
curl -s -X POST http://localhost:8000/api/v1/products/ \
  -H "Content-Type: application/json" \
  -d '{"name":"Producto Test Cache","price":99.99,"category":"test"}' | python -m json.tool

# Contar claves después (deben haberse eliminado las de caché)
echo "Claves después de invalidación:"
docker exec redis-cache redis-cli DBSIZE
```

4. Verifica que la siguiente lectura genera un nuevo cache miss:

```bash
# Esta petición debe ser un MISS (caché fue invalidada)
curl -s http://localhost:8000/api/v1/products/?limit=5 > /dev/null

# Verificar que se regeneró la clave
docker exec redis-cache redis-cli KEYS "cache:product_list:*"
```

**Salida esperada:**

Tras la creación del producto, `DBSIZE` debe mostrar menos claves (las de caché fueron eliminadas). Tras la nueva lectura, la clave `cache:product_list:*` reaparece.

**Verificación:**

```bash
# Estadísticas de Redis
docker exec redis-cache redis-cli INFO stats | grep -E "keyspace_hits|keyspace_misses"
```

Debes ver valores crecientes en `keyspace_hits` y `keyspace_misses` confirmando que Redis está procesando solicitudes.

---

### Paso 6: Benchmarking con Locust — sin caché vs. con caché (16 min)

**Objetivo:** Medir cuantitativamente el impacto del caching en latencia P95 y throughput (RPS) usando Locust con 100 usuarios concurrentes.

**Instrucciones:**

1. Crea el archivo de prueba de Locust:

```python
cat > ~/microservicios-curso/lab09/locustfile.py << 'EOF'
"""
Prueba de carga para catalog-service.
Simula 100 usuarios concurrentes realizando lecturas frecuentes.
"""
from locust import HttpUser, task, between


class CatalogUser(HttpUser):
    wait_time = between(0.1, 0.5)
    host = "http://localhost:8000"

    @task(8)
    def list_products(self):
        """80% de las peticiones: listar productos."""
        self.client.get("/api/v1/products/?limit=20")

    @task(2)
    def get_product_detail(self):
        """20% de las peticiones: detalle de producto."""
        # Obtener lista y consultar el primer producto
        response = self.client.get("/api/v1/products/?limit=5")
        if response.status_code == 200:
            products = response.json()
            if products:
                product_id = products[0]["id"]
                self.client.get(f"/api/v1/products/{product_id}")
EOF
```

2. Primero, ejecuta el benchmark **CON caché** (estado actual):

```bash
cd ~/microservicios-curso/lab09

# Limpiar caché para empezar limpio
docker exec redis-cache redis-cli FLUSHDB

# Ejecutar Locust en modo headless: 100 usuarios, 10 usuarios/segundo de ramp-up, 30 segundos
locust --headless \
  --users 100 \
  --spawn-rate 10 \
  --run-time 30s \
  --csv results_with_cache \
  --locustfile locustfile.py \
  2>&1 | tail -20
```

3. Ahora, desactiva el caché temporalmente para comparar. Crea una versión del servicio sin caché:

```python
cat > ~/microservicios-curso/lab09/catalog_service/cache/decorators_bypass.py << 'EOF'
"""
Versión bypass de los decoradores para pruebas sin caché.
Los decoradores simplemente ejecutan la función sin interactuar con Redis.
"""
import functools
from typing import Callable, Optional, List

TTL_PRODUCT_DETAIL = 300
TTL_PRODUCT_LIST = 60


def cache_response(prefix: str, ttl: int = 300, tags: Optional[List[str]] = None):
    """Decorador bypass: no usa caché."""
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def invalidate_cache(tags: List[str]):
    """Decorador bypass: no invalida nada."""
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)
        return wrapper
    return decorator
EOF
```

4. Intercambia temporalmente los decoradores y reinicia el servicio:

```bash
# Detener el servicio actual
kill $(lsof -ti:8000) 2>/dev/null || true
sleep 1

# Hacer backup y reemplazar decoradores
cp ~/microservicios-curso/lab09/catalog_service/cache/decorators.py \
   ~/microservicios-curso/lab09/catalog_service/cache/decorators_real.py

cp ~/microservicios-curso/lab09/catalog_service/cache/decorators_bypass.py \
   ~/microservicios-curso/lab09/catalog_service/cache/decorators.py

# Reiniciar servicio sin caché
cd ~/microservicios-curso/lab09
uvicorn catalog_service.main:app --host 0.0.0.0 --port 8000 &
sleep 2
```

5. Ejecuta el benchmark **SIN caché**:

```bash
locust --headless \
  --users 100 \
  --spawn-rate 10 \
  --run-time 30s \
  --csv results_without_cache \
  --locustfile locustfile.py \
  2>&1 | tail -20
```

6. Restaura los decoradores con caché:

```bash
# Restaurar decoradores reales
cp ~/microservicios-curso/lab09/catalog_service/cache/decorators_real.py \
   ~/microservicios-curso/lab09/catalog_service/cache/decorators.py

# Reiniciar servicio con caché
kill $(lsof -ti:8000) 2>/dev/null || true
sleep 1
cd ~/microservicios-curso/lab09
uvicorn catalog_service.main:app --host 0.0.0.0 --port 8000 &
sleep 2
```

7. Compara los resultados:

```bash
echo "=== RESULTADOS CON CACHÉ ==="
cat results_with_cache_stats.csv | column -t -s','

echo ""
echo "=== RESULTADOS SIN CACHÉ ==="
cat results_without_cache_stats.csv | column -t -s','
```

**Salida esperada:**

Los resultados con caché deben mostrar:
- **Latencia P95** significativamente menor (típicamente 2-10x más rápida)
- **RPS (Requests Per Second)** mayor con caché habilitado
- **Tasa de fallos** cercana a 0% en ambos casos

Ejemplo de comparación típica:

| Métrica | Sin caché | Con caché | Mejora |
|---------|-----------|-----------|--------|
| P95 (ms) | ~15-25 | ~3-8 | 2-5x |
| RPS | ~800-1200 | ~2000-4000 | 2-3x |

**Verificación:**

```bash
# Verificar hits en Redis tras el benchmark con caché
docker exec redis-cache redis-cli INFO stats | grep -E "keyspace_hits|keyspace_misses"
```

El ratio `hits / (hits + misses)` debe ser superior al 80%.

---

## Validación y Pruebas

Ejecuta la siguiente secuencia completa para validar que todos los componentes funcionan correctamente:

```bash
cd ~/microservicios-curso/lab09

echo "=== 1. Verificar servicios activos ==="
docker compose ps
curl -s http://localhost:8000/health | python -m json.tool

echo ""
echo "=== 2. Verificar Cache-Aside (miss → hit) ==="
docker exec redis-cache redis-cli FLUSHDB
echo "Petición 1 (MISS):"
curl -s -o /dev/null -w "HTTP %{http_code} - %{time_total}s\n" \
  http://localhost:8000/api/v1/products/?limit=10
echo "Petición 2 (HIT):"
curl -s -o /dev/null -w "HTTP %{http_code} - %{time_total}s\n" \
  http://localhost:8000/api/v1/products/?limit=10

echo ""
echo "=== 3. Verificar Write-Through (invalidación) ==="
echo "Claves antes de crear:"
docker exec redis-cache redis-cli DBSIZE
curl -s -X POST http://localhost:8000/api/v1/products/ \
  -H "Content-Type: application/json" \
  -d '{"name":"Validación Final","price":50.0,"category":"test"}' > /dev/null
echo "Claves después de crear (invalidadas):"
docker exec redis-cache redis-cli DBSIZE

echo ""
echo "=== 4. Verificar TTL diferenciado ==="
# Generar entrada de listado (TTL 60s)
curl -s http://localhost:8000/api/v1/products/?limit=5 > /dev/null
LIST_KEY=$(docker exec redis-cache redis-cli KEYS "cache:product_list:*" | head -1)
echo "TTL listado: $(docker exec redis-cache redis-cli TTL $LIST_KEY)s (esperado: ~60)"

# Generar entrada de detalle (TTL 300s)
PRODUCT_ID=$(curl -s http://localhost:8000/api/v1/products/?limit=1 | python -c "import sys,json;print(json.load(sys.stdin)[0]['id'])")
curl -s http://localhost:8000/api/v1/products/$PRODUCT_ID > /dev/null
DETAIL_KEY=$(docker exec redis-cache redis-cli KEYS "cache:product_detail:*" | head -1)
echo "TTL detalle: $(docker exec redis-cache redis-cli TTL $DETAIL_KEY)s (esperado: ~300)"

echo ""
echo "=== 5. Verificar estadísticas Redis ==="
docker exec redis-cache redis-cli INFO stats | grep -E "keyspace_hits|keyspace_misses|total_commands"

echo ""
echo "=== VALIDACIÓN COMPLETA ==="
```

**Criterios de éxito:**
- ✅ Health check retorna `{"status": "healthy", "cache": "redis"}`
- ✅ Segunda petición idéntica es más rápida que la primera
- ✅ DBSIZE disminuye tras una operación de escritura
- ✅ TTL de listado ≈ 60s, TTL de detalle ≈ 300s
- ✅ `keyspace_hits` > 0 confirmando cache hits

---

## Resolución de Problemas

### Problema 1: Error de conexión a Redis al iniciar el servicio

**Síntomas:**

```
RuntimeError: Redis no está inicializado. Llama a init_redis() primero.
```
o
```
redis.exceptions.ConnectionError: Error 111 connecting to localhost:6379. Connection refused.
```

**Causa:** El contenedor Redis no está corriendo o no es accesible desde el host en el puerto 6379. Puede ocurrir si Docker Compose no levantó correctamente el servicio o si hay un conflicto de puertos.

**Solución:**

```bash
# Verificar que Redis está corriendo
docker compose ps redis

# Si no está corriendo, reiniciar
docker compose up -d redis

# Verificar conectividad directa
docker exec redis-cache redis-cli ping

# Si hay conflicto de puertos, verificar qué usa el 6379
lsof -i :6379

# Si se ejecuta dentro de Docker, usar el nombre del contenedor como host
# Cambiar REDIS_URL a "redis://redis-cache:6379/0" en connection.py
```

---

### Problema 2: Caché no se invalida tras operaciones de escritura

**Síntomas:** Después de crear o actualizar un producto, las peticiones GET siguen retornando datos antiguos. Las claves `cache:product_list:*` persisten en Redis tras un POST/PUT.

**Causa:** Los tags no se registraron correctamente durante la escritura en caché, o el decorador `@invalidate_cache` no se aplicó en el orden correcto. Esto sucede cuando la primera lectura no generó tags (por ejemplo, si `tags=None` fue pasado accidentalmente).

**Solución:**

```bash
# 1. Verificar que los tags existen en Redis
docker exec redis-cache redis-cli KEYS "tag:*"
docker exec redis-cache redis-cli SMEMBERS "tag:products"

# 2. Si los tags están vacíos, el problema está en cache_response
# Verificar que se pasa tags=["products"] en los decoradores de lectura

# 3. Solución inmediata: flush manual
docker exec redis-cache redis-cli FLUSHDB

# 4. Verificar el orden de decoradores en product_service.py
# @cache_response debe tener tags=["products"]
# @invalidate_cache debe tener tags=["products"]

# 5. Verificar en logs que la invalidación se ejecuta
# Añadir temporalmente un print en el decorador invalidate_cache:
# print(f"[INVALIDATE] Eliminando claves de tags: {tags}")
```

---

## Limpieza

```bash
# Detener el servicio FastAPI
kill $(lsof -ti:8000) 2>/dev/null || true

# Detener y eliminar contenedores
cd ~/microservicios-curso/lab09
docker compose down -v

# Desactivar entorno virtual
deactivate

# Opcional: eliminar archivos de resultados de benchmark
rm -f ~/microservicios-curso/lab09/results_*.csv
```

Para conservar el trabajo pero liberar recursos:

```bash
# Solo detener contenedores sin eliminar volúmenes
docker compose stop
```

---

## Resumen

En esta práctica implementaste exitosamente:

| Concepto | Implementación |
|----------|---------------|
| **Cache-Aside** | Decorador `@cache_response` que verifica Redis antes de consultar la BD |
| **Write-Through** | Decorador `@invalidate_cache` que elimina entradas tras escrituras |
| **TTL diferenciado** | 300s para detalles de producto, 60s para listados |
| **Invalidación por tags** | Sets de Redis agrupando claves para invalidación masiva |
| **Cliente asíncrono** | `redis.asyncio` con pool de 20 conexiones |
| **Benchmarking** | Locust con 100 usuarios midiendo P95 y RPS |

**Puntos clave aprendidos:**

- El patrón cache-aside ofrece control total sobre cuándo y qué se cachea
- La invalidación por tags permite eliminar grupos de claves relacionadas sin conocer sus nombres exactos
- Redis con `allkeys-lru` y `maxmemory 256mb` actúa como caché autogestionada que nunca agota la memoria
- El impacto medible del caching típicamente reduce la latencia P95 entre 2x y 5x

### Recursos Adicionales

- [Documentación redis-py asyncio](https://redis-py.readthedocs.io/en/stable/examples/asyncio_examples.html)
- [Redis — Patrones de caching](https://redis.io/docs/manual/patterns/)
- [Locust — Documentación oficial](https://docs.locust.io/en/stable/)
- [Microsoft — Patrón Cache-Aside](https://learn.microsoft.com/en-us/azure/architecture/patterns/cache-aside)

---

**Commit sugerido:**

```bash
cd ~/microservicios-curso
git add lab09/
git commit -m "[lab09] Implementar caching Redis con patrones cache-aside y write-through"
```
