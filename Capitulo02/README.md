# Práctica 2 — Crear una API REST simple en FastAPI

| Campo | Valor |
|-------|-------|
| **Duración** | 56 minutos |
| **Complejidad** | Media |
| **Nivel Bloom** | Crear |

## Descripción General

En esta práctica implementarás desde cero el microservicio `products-service` identificado en la propuesta de descomposición (PROPUESTA.md) de la práctica anterior. Construirás una API REST completa con operaciones CRUD sobre productos, almacenamiento en memoria, validación con Pydantic, manejo de errores HTTP y pruebas de integración automatizadas. El resultado será un servicio listo para ser contenedorizado en la práctica 03-00-01.

## Objetivos de Aprendizaje

- [ ] Implementar un microservicio RESTful completo con FastAPI 0.111.0 que exponga cinco endpoints CRUD para productos
- [ ] Definir modelos de datos con Pydantic 2.7.1 incluyendo validación automática de tipos y restricciones
- [ ] Estructurar el proyecto con separación clara de responsabilidades: routers, modelos, esquemas y capa de datos
- [ ] Escribir y ejecutar pruebas de integración con pytest 8.2.1 y httpx 0.27.0 que cubran todos los endpoints y casos de error

## Prerrequisitos

### Conocimientos

- Práctica 01-00-01 completada con `PROPUESTA.md` disponible en `~/microservicios-curso/lab01/`
- Comprensión básica de HTTP/REST: verbos GET, POST, PUT, DELETE y códigos de estado (200, 201, 404, 422)
- Familiaridad con clases Python, tipado con type hints y decoradores

### Acceso y herramientas

- Python 3.12.3 instalado y accesible como `python3`
- pip 24.0 disponible
- Terminal con acceso al directorio `~/microservicios-curso/`
- Conexión a Internet para instalar dependencias desde PyPI

## Entorno del Laboratorio

### Software requerido

| Herramienta | Versión | Verificación |
|-------------|---------|--------------|
| Python | 3.12.3 | `python3 --version` |
| pip | 24.0+ | `pip --version` |
| Git | 2.45+ | `git --version` |

### Preparación inicial

```bash
# Verificar versiones
python3 --version
pip --version

# Posicionarse en el directorio raíz del curso
cd ~/microservicios-curso/
```

---

## Paso 1: Crear la estructura del proyecto

**Objetivo:** Establecer la arquitectura de directorios del microservicio con separación modular de responsabilidades.

### Instrucciones

1. Crea el directorio del servicio y los subdirectorios necesarios:

```bash
cd ~/microservicios-curso/
mkdir -p products-service/{routers,models,schemas,tests}
```

2. Crea los archivos `__init__.py` para que Python reconozca los paquetes:

```bash
touch products-service/routers/__init__.py
touch products-service/models/__init__.py
touch products-service/schemas/__init__.py
touch products-service/tests/__init__.py
```

3. Verifica la estructura resultante:

```bash
find products-service -type f | sort
```

### Salida esperada

```
products-service/models/__init__.py
products-service/routers/__init__.py
products-service/schemas/__init__.py
products-service/tests/__init__.py
```

### Verificación

```bash
# Confirmar que existen los 4 directorios con __init__.py
test -f products-service/routers/__init__.py && \
test -f products-service/models/__init__.py && \
test -f products-service/schemas/__init__.py && \
test -f products-service/tests/__init__.py && \
echo "✅ Estructura correcta" || echo "❌ Faltan archivos"
```

---

## Paso 2: Definir dependencias en requirements.txt

**Objetivo:** Declarar todas las dependencias del proyecto con versiones fijadas para garantizar reproducibilidad.

### Instrucciones

1. Crea el archivo `requirements.txt` en la raíz del servicio:

```bash
cat > products-service/requirements.txt << 'EOF'
fastapi==0.111.0
uvicorn[standard]==0.30.1
pydantic==2.7.1
httpx==0.27.0
pytest==8.2.1
pytest-asyncio==0.23.7
EOF
```

2. Crea un entorno virtual e instala las dependencias:

```bash
cd ~/microservicios-curso/products-service/
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Salida esperada

La instalación finaliza con mensajes como:

```
Successfully installed fastapi-0.111.0 uvicorn-0.30.1 pydantic-2.7.1 ...
```

### Verificación

```bash
# Confirmar que FastAPI se importa correctamente
python3 -c "import fastapi; print(f'✅ FastAPI {fastapi.__version__} instalado')"
python3 -c "import pydantic; print(f'✅ Pydantic {pydantic.__version__} instalado')"
```

---

## Paso 3: Definir los esquemas Pydantic

**Objetivo:** Crear los modelos de validación de entrada/salida que definen el contrato de la API.

### Instrucciones

1. Crea el archivo de esquemas `schemas/product.py`:

```bash
cat > schemas/product.py << 'EOF'
"""Esquemas Pydantic para validación de datos de productos."""

from pydantic import BaseModel, Field
from typing import Optional


class ProductBase(BaseModel):
    """Campos compartidos entre creación y respuesta."""
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Nombre del producto",
        examples=["Laptop HP Pavilion"]
    )
    description: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Descripción detallada del producto",
        examples=["Laptop con procesador Intel i7, 16GB RAM"]
    )
    price: float = Field(
        ...,
        gt=0,
        description="Precio del producto en USD",
        examples=[999.99]
    )
    category: Optional[str] = Field(
        default=None,
        max_length=50,
        description="Categoría del producto",
        examples=["Electrónica"]
    )


class ProductCreate(ProductBase):
    """Esquema para crear un producto (entrada del POST)."""
    pass


class ProductUpdate(BaseModel):
    """Esquema para actualizar un producto (entrada del PUT). Todos los campos opcionales."""
    name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=100,
        examples=["Laptop HP Pavilion 15"]
    )
    description: Optional[str] = Field(
        default=None,
        max_length=500,
        examples=["Laptop actualizada con 32GB RAM"]
    )
    price: Optional[float] = Field(
        default=None,
        gt=0,
        examples=[1099.99]
    )
    category: Optional[str] = Field(
        default=None,
        max_length=50,
        examples=["Electrónica"]
    )


class ProductResponse(ProductBase):
    """Esquema de respuesta que incluye el ID generado."""
    id: int = Field(..., description="Identificador único del producto", examples=[1])

    model_config = {"from_attributes": True}
EOF
```

### Salida esperada

Archivo creado sin errores.

### Verificación

```bash
python3 -c "
from schemas.product import ProductCreate, ProductResponse, ProductUpdate
p = ProductCreate(name='Test', price=10.0)
print(f'✅ ProductCreate válido: {p.model_dump()}')
"
```

Debe imprimir:
```
✅ ProductCreate válido: {'name': 'Test', 'description': None, 'price': 10.0, 'category': None}
```

---

## Paso 4: Implementar la capa de datos en memoria

**Objetivo:** Crear un almacén de datos en memoria (diccionario) con una interfaz preparada para ser reemplazada por una base de datos real.

### Instrucciones

1. Crea el archivo `database.py`:

```bash
cat > database.py << 'EOF'
"""Capa de datos en memoria para el microservicio de productos.

Este módulo simula una base de datos usando un diccionario Python.
La interfaz está diseñada para ser reemplazable por una conexión
real a PostgreSQL, MongoDB u otro motor en prácticas posteriores.
"""

from typing import Optional


class ProductDatabase:
    """Almacén de productos en memoria con operaciones CRUD."""

    def __init__(self):
        self._products: dict[int, dict] = {}
        self._counter: int = 0

    def _next_id(self) -> int:
        """Genera el siguiente ID autoincremental."""
        self._counter += 1
        return self._counter

    def get_all(self) -> list[dict]:
        """Retorna todos los productos."""
        return list(self._products.values())

    def get_by_id(self, product_id: int) -> Optional[dict]:
        """Retorna un producto por ID o None si no existe."""
        return self._products.get(product_id)

    def create(self, product_data: dict) -> dict:
        """Crea un nuevo producto y retorna el producto con ID asignado."""
        product_id = self._next_id()
        product = {"id": product_id, **product_data}
        self._products[product_id] = product
        return product

    def update(self, product_id: int, product_data: dict) -> Optional[dict]:
        """Actualiza un producto existente. Retorna None si no existe."""
        if product_id not in self._products:
            return None
        existing = self._products[product_id]
        # Solo actualizar campos que no sean None
        for key, value in product_data.items():
            if value is not None:
                existing[key] = value
        self._products[product_id] = existing
        return existing

    def delete(self, product_id: int) -> bool:
        """Elimina un producto. Retorna True si existía, False si no."""
        if product_id in self._products:
            del self._products[product_id]
            return True
        return False


# Instancia singleton utilizada por los routers
db = ProductDatabase()
EOF
```

### Verificación

```bash
python3 -c "
from database import ProductDatabase
db = ProductDatabase()
p = db.create({'name': 'Test', 'price': 9.99, 'description': None, 'category': None})
assert p['id'] == 1
assert db.get_by_id(1) == p
assert db.delete(1) is True
assert db.get_by_id(1) is None
print('✅ ProductDatabase funciona correctamente')
"
```

---

## Paso 5: Implementar el router de productos

**Objetivo:** Crear los cinco endpoints CRUD con manejo de errores HTTP apropiado.

### Instrucciones

1. Crea el archivo `routers/products.py`:

```bash
cat > routers/products.py << 'EOF'
"""Router de endpoints para gestión de productos."""

from fastapi import APIRouter, HTTPException, status
from schemas.product import ProductCreate, ProductUpdate, ProductResponse
from database import db

router = APIRouter(
    prefix="/products",
    tags=["products"],
    responses={404: {"description": "Producto no encontrado"}},
)


@router.get(
    "/",
    response_model=list[ProductResponse],
    summary="Listar todos los productos",
    description="Retorna la lista completa de productos registrados.",
)
def list_products():
    """Obtiene todos los productos del catálogo."""
    return db.get_all()


@router.get(
    "/{product_id}",
    response_model=ProductResponse,
    summary="Obtener un producto por ID",
    description="Retorna los detalles de un producto específico.",
)
def get_product(product_id: int):
    """Obtiene un producto por su identificador único."""
    product = db.get_by_id(product_id)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Producto con id {product_id} no encontrado",
        )
    return product


@router.post(
    "/",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear un nuevo producto",
    description="Registra un nuevo producto en el catálogo.",
)
def create_product(product: ProductCreate):
    """Crea un producto con los datos proporcionados."""
    product_data = product.model_dump()
    created = db.create(product_data)
    return created


@router.put(
    "/{product_id}",
    response_model=ProductResponse,
    summary="Actualizar un producto",
    description="Actualiza los campos proporcionados de un producto existente.",
)
def update_product(product_id: int, product: ProductUpdate):
    """Actualiza parcialmente un producto existente."""
    product_data = product.model_dump(exclude_unset=True)
    updated = db.update(product_id, product_data)
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Producto con id {product_id} no encontrado",
        )
    return updated


@router.delete(
    "/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar un producto",
    description="Elimina un producto del catálogo por su ID.",
)
def delete_product(product_id: int):
    """Elimina un producto existente."""
    deleted = db.delete(product_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Producto con id {product_id} no encontrado",
        )
    return None
EOF
```

### Verificación

```bash
python3 -c "
from routers.products import router
routes = [r.path for r in router.routes]
assert '/products/' in routes or '/' in routes
print(f'✅ Router cargado con {len(router.routes)} rutas')
"
```

---

## Paso 6: Crear la aplicación principal

**Objetivo:** Configurar la aplicación FastAPI principal que integra el router y expone metadatos de la API.

### Instrucciones

1. Crea el archivo `main.py`:

```bash
cat > main.py << 'EOF'
"""Punto de entrada del microservicio products-service.

Ejecutar con:
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload
"""

from fastapi import FastAPI
from routers.products import router as products_router

app = FastAPI(
    title="Products Service",
    description="Microservicio de gestión de productos - API REST CRUD",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Registrar el router de productos
app.include_router(products_router)


@app.get("/health", tags=["health"])
def health_check():
    """Endpoint de verificación de salud del servicio."""
    return {"status": "healthy", "service": "products-service"}
EOF
```

### Verificación

```bash
python3 -c "
from main import app
routes = [r.path for r in app.routes]
print(f'Rutas registradas: {routes}')
assert '/products/' in routes
assert '/products/{product_id}' in routes
assert '/health' in routes
print('✅ Aplicación FastAPI configurada correctamente')
"
```

---

## Paso 7: Iniciar el servidor y probar manualmente

**Objetivo:** Verificar que el servicio arranca correctamente y responde a peticiones HTTP.

### Instrucciones

1. Inicia el servidor en segundo plano:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 &
SERVER_PID=$!
echo "Servidor iniciado con PID: $SERVER_PID"
sleep 2
```

2. Prueba el endpoint de salud:

```bash
curl -s http://localhost:8000/health | python3 -m json.tool
```

### Salida esperada

```json
{
    "status": "healthy",
    "service": "products-service"
}
```

3. Crea un producto:

```bash
curl -s -X POST http://localhost:8000/products/ \
  -H "Content-Type: application/json" \
  -d '{"name": "Laptop HP Pavilion", "price": 999.99, "category": "Electrónica"}' \
  | python3 -m json.tool
```

### Salida esperada

```json
{
    "name": "Laptop HP Pavilion",
    "description": null,
    "price": 999.99,
    "category": "Electrónica",
    "id": 1
}
```

4. Lista todos los productos:

```bash
curl -s http://localhost:8000/products/ | python3 -m json.tool
```

5. Obtén un producto por ID:

```bash
curl -s http://localhost:8000/products/1 | python3 -m json.tool
```

6. Actualiza el producto:

```bash
curl -s -X PUT http://localhost:8000/products/1 \
  -H "Content-Type: application/json" \
  -d '{"price": 899.99}' \
  | python3 -m json.tool
```

7. Prueba un 404:

```bash
curl -s -w "\nHTTP Status: %{http_code}\n" http://localhost:8000/products/999
```

### Salida esperada

```json
{"detail":"Producto con id 999 no encontrado"}
HTTP Status: 404
```

8. Elimina el producto:

```bash
curl -s -w "HTTP Status: %{http_code}\n" -X DELETE http://localhost:8000/products/1
```

### Salida esperada

```
HTTP Status: 204
```

9. Detén el servidor:

```bash
kill $SERVER_PID 2>/dev/null
echo "✅ Servidor detenido"
```

### Verificación

```bash
# Verificar que el puerto 8000 está libre
! lsof -i :8000 > /dev/null 2>&1 && echo "✅ Puerto 8000 libre" || echo "⚠️ Puerto 8000 aún en uso"
```

---

## Paso 8: Escribir pruebas de integración

**Objetivo:** Crear una suite de pruebas automatizadas que validen todos los endpoints y casos de error.

### Instrucciones

1. Crea el archivo de configuración de pytest:

```bash
cat > pytest.ini << 'EOF'
[pytest]
testpaths = tests
asyncio_mode = auto
EOF
```

2. Crea el archivo de pruebas `tests/test_products.py`:

```bash
cat > tests/test_products.py << 'EOF'
"""Pruebas de integración para el microservicio de productos."""

import pytest
from fastapi.testclient import TestClient
from main import app
from database import db


@pytest.fixture(autouse=True)
def reset_database():
    """Reinicia la base de datos antes de cada prueba."""
    db._products.clear()
    db._counter = 0
    yield
    db._products.clear()
    db._counter = 0


@pytest.fixture
def client():
    """Cliente de pruebas de FastAPI."""
    return TestClient(app)


@pytest.fixture
def sample_product():
    """Datos de ejemplo para crear un producto."""
    return {
        "name": "Laptop HP Pavilion",
        "description": "Laptop con Intel i7, 16GB RAM",
        "price": 999.99,
        "category": "Electrónica",
    }


class TestHealthEndpoint:
    """Pruebas del endpoint de salud."""

    def test_health_returns_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_returns_correct_body(self, client):
        response = client.get("/health")
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "products-service"


class TestCreateProduct:
    """Pruebas del endpoint POST /products/."""

    def test_create_product_returns_201(self, client, sample_product):
        response = client.post("/products/", json=sample_product)
        assert response.status_code == 201

    def test_create_product_returns_id(self, client, sample_product):
        response = client.post("/products/", json=sample_product)
        data = response.json()
        assert "id" in data
        assert data["id"] == 1

    def test_create_product_returns_all_fields(self, client, sample_product):
        response = client.post("/products/", json=sample_product)
        data = response.json()
        assert data["name"] == sample_product["name"]
        assert data["description"] == sample_product["description"]
        assert data["price"] == sample_product["price"]
        assert data["category"] == sample_product["category"]

    def test_create_product_minimal_fields(self, client):
        minimal = {"name": "Simple Product", "price": 5.0}
        response = client.post("/products/", json=minimal)
        assert response.status_code == 201
        data = response.json()
        assert data["description"] is None
        assert data["category"] is None

    def test_create_product_invalid_price_returns_422(self, client):
        invalid = {"name": "Bad Product", "price": -10.0}
        response = client.post("/products/", json=invalid)
        assert response.status_code == 422

    def test_create_product_missing_name_returns_422(self, client):
        invalid = {"price": 10.0}
        response = client.post("/products/", json=invalid)
        assert response.status_code == 422

    def test_create_product_empty_name_returns_422(self, client):
        invalid = {"name": "", "price": 10.0}
        response = client.post("/products/", json=invalid)
        assert response.status_code == 422

    def test_create_multiple_products_increments_id(self, client, sample_product):
        r1 = client.post("/products/", json=sample_product)
        r2 = client.post("/products/", json=sample_product)
        assert r1.json()["id"] == 1
        assert r2.json()["id"] == 2


class TestListProducts:
    """Pruebas del endpoint GET /products/."""

    def test_list_empty_returns_empty_list(self, client):
        response = client.get("/products/")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_returns_created_products(self, client, sample_product):
        client.post("/products/", json=sample_product)
        client.post("/products/", json=sample_product)
        response = client.get("/products/")
        assert response.status_code == 200
        assert len(response.json()) == 2


class TestGetProduct:
    """Pruebas del endpoint GET /products/{product_id}."""

    def test_get_existing_product_returns_200(self, client, sample_product):
        client.post("/products/", json=sample_product)
        response = client.get("/products/1")
        assert response.status_code == 200

    def test_get_existing_product_returns_correct_data(self, client, sample_product):
        client.post("/products/", json=sample_product)
        response = client.get("/products/1")
        data = response.json()
        assert data["name"] == sample_product["name"]
        assert data["id"] == 1

    def test_get_nonexistent_product_returns_404(self, client):
        response = client.get("/products/999")
        assert response.status_code == 404

    def test_get_nonexistent_product_returns_detail_message(self, client):
        response = client.get("/products/999")
        data = response.json()
        assert "detail" in data
        assert "999" in data["detail"]


class TestUpdateProduct:
    """Pruebas del endpoint PUT /products/{product_id}."""

    def test_update_product_returns_200(self, client, sample_product):
        client.post("/products/", json=sample_product)
        response = client.put("/products/1", json={"price": 799.99})
        assert response.status_code == 200

    def test_update_product_changes_field(self, client, sample_product):
        client.post("/products/", json=sample_product)
        client.put("/products/1", json={"price": 799.99})
        response = client.get("/products/1")
        assert response.json()["price"] == 799.99

    def test_update_product_preserves_other_fields(self, client, sample_product):
        client.post("/products/", json=sample_product)
        client.put("/products/1", json={"price": 799.99})
        response = client.get("/products/1")
        data = response.json()
        assert data["name"] == sample_product["name"]
        assert data["category"] == sample_product["category"]

    def test_update_nonexistent_product_returns_404(self, client):
        response = client.put("/products/999", json={"price": 100.0})
        assert response.status_code == 404


class TestDeleteProduct:
    """Pruebas del endpoint DELETE /products/{product_id}."""

    def test_delete_product_returns_204(self, client, sample_product):
        client.post("/products/", json=sample_product)
        response = client.delete("/products/1")
        assert response.status_code == 204

    def test_delete_product_removes_from_list(self, client, sample_product):
        client.post("/products/", json=sample_product)
        client.delete("/products/1")
        response = client.get("/products/")
        assert len(response.json()) == 0

    def test_delete_product_makes_get_return_404(self, client, sample_product):
        client.post("/products/", json=sample_product)
        client.delete("/products/1")
        response = client.get("/products/1")
        assert response.status_code == 404

    def test_delete_nonexistent_product_returns_404(self, client):
        response = client.delete("/products/999")
        assert response.status_code == 404
EOF
```

### Verificación

```bash
# Verificar que el archivo de pruebas es sintácticamente correcto
python3 -c "import ast; ast.parse(open('tests/test_products.py').read()); print('✅ Archivo de pruebas válido')"
```

---

## Paso 9: Ejecutar las pruebas

**Objetivo:** Ejecutar la suite completa de pruebas y verificar que todas pasan.

### Instrucciones

1. Ejecuta pytest con salida detallada:

```bash
cd ~/microservicios-curso/products-service/
python3 -m pytest tests/ -v --tb=short
```

### Salida esperada

```
tests/test_products.py::TestHealthEndpoint::test_health_returns_200 PASSED
tests/test_products.py::TestHealthEndpoint::test_health_returns_correct_body PASSED
tests/test_products.py::TestCreateProduct::test_create_product_returns_201 PASSED
tests/test_products.py::TestCreateProduct::test_create_product_returns_id PASSED
tests/test_products.py::TestCreateProduct::test_create_product_returns_all_fields PASSED
tests/test_products.py::TestCreateProduct::test_create_product_minimal_fields PASSED
tests/test_products.py::TestCreateProduct::test_create_product_invalid_price_returns_422 PASSED
tests/test_products.py::TestCreateProduct::test_create_product_missing_name_returns_422 PASSED
tests/test_products.py::TestCreateProduct::test_create_product_empty_name_returns_422 PASSED
tests/test_products.py::TestCreateProduct::test_create_multiple_products_increments_id PASSED
tests/test_products.py::TestListProducts::test_list_empty_returns_empty_list PASSED
tests/test_products.py::TestListProducts::test_list_returns_created_products PASSED
tests/test_products.py::TestGetProduct::test_get_existing_product_returns_200 PASSED
tests/test_products.py::TestGetProduct::test_get_existing_product_returns_correct_data PASSED
tests/test_products.py::TestGetProduct::test_get_nonexistent_product_returns_404 PASSED
tests/test_products.py::TestGetProduct::test_get_nonexistent_product_returns_detail_message PASSED
tests/test_products.py::TestUpdateProduct::test_update_product_returns_200 PASSED
tests/test_products.py::TestUpdateProduct::test_update_product_changes_field PASSED
tests/test_products.py::TestUpdateProduct::test_update_product_preserves_other_fields PASSED
tests/test_products.py::TestUpdateProduct::test_update_nonexistent_product_returns_404 PASSED
tests/test_products.py::TestDeleteProduct::test_delete_product_returns_204 PASSED
tests/test_products.py::TestDeleteProduct::test_delete_product_removes_from_list PASSED
tests/test_products.py::TestDeleteProduct::test_delete_product_makes_get_return_404 PASSED
tests/test_products.py::TestDeleteProduct::test_delete_nonexistent_product_returns_404 PASSED

========================= 24 passed in 0.45s =========================
```

### Verificación

```bash
# Ejecutar pytest y verificar que el código de salida es 0 (éxito)
python3 -m pytest tests/ -q && echo "✅ Todas las pruebas pasaron" || echo "❌ Hay pruebas fallidas"
```

---

## Paso 10: Verificar la documentación automática de la API

**Objetivo:** Confirmar que FastAPI genera correctamente la documentación OpenAPI interactiva.

### Instrucciones

1. Inicia el servidor temporalmente:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 &
SERVER_PID=$!
sleep 2
```

2. Descarga el esquema OpenAPI y verifica su estructura:

```bash
curl -s http://localhost:8000/openapi.json | python3 -c "
import json, sys
schema = json.load(sys.stdin)
print(f'Título: {schema[\"info\"][\"title\"]}')
print(f'Versión: {schema[\"info\"][\"version\"]}')
paths = list(schema['paths'].keys())
print(f'Endpoints: {paths}')
assert '/products/' in paths
assert '/products/{product_id}' in paths
assert '/health' in paths
print('✅ Documentación OpenAPI generada correctamente')
"
```

### Salida esperada

```
Título: Products Service
Versión: 1.0.0
Endpoints: ['/products/', '/products/{product_id}', '/health']
✅ Documentación OpenAPI generada correctamente
```

3. Detén el servidor:

```bash
kill $SERVER_PID 2>/dev/null
echo "✅ Servidor detenido"
```

> **Nota:** Cuando el servidor está en ejecución, puedes acceder a la documentación interactiva en `http://localhost:8000/docs` (Swagger UI) o `http://localhost:8000/redoc` (ReDoc).

---

## Paso 11: Verificar la estructura final del proyecto

**Objetivo:** Confirmar que todos los archivos están en su lugar y el proyecto está completo.

### Instrucciones

1. Lista la estructura completa del proyecto:

```bash
cd ~/microservicios-curso/products-service/
find . -type f -not -path './.venv/*' -not -name '*.pyc' -not -path './__pycache__/*' -not -path './.pytest_cache/*' | sort
```

### Salida esperada

```
./database.py
./main.py
./models/__init__.py
./pytest.ini
./requirements.txt
./routers/__init__.py
./routers/products.py
./schemas/__init__.py
./schemas/product.py
./tests/__init__.py
./tests/test_products.py
```

### Verificación

```bash
# Verificación final completa
cd ~/microservicios-curso/products-service/
echo "=== Verificación Final del Lab 02-00-01 ==="
echo ""

# 1. Estructura de archivos
echo "1. Verificando estructura de archivos..."
FILES=(
    "main.py"
    "database.py"
    "requirements.txt"
    "pytest.ini"
    "routers/__init__.py"
    "routers/products.py"
    "models/__init__.py"
    "schemas/__init__.py"
    "schemas/product.py"
    "tests/__init__.py"
    "tests/test_products.py"
)
ALL_FILES_OK=true
for f in "${FILES[@]}"; do
    if [ ! -f "$f" ]; then
        echo "   ❌ Falta: $f"
        ALL_FILES_OK=false
    fi
done
$ALL_FILES_OK && echo "   ✅ Todos los archivos presentes"

# 2. Importaciones
echo ""
echo "2. Verificando importaciones..."
python3 -c "from main import app; print('   ✅ main.py importa correctamente')"
python3 -c "from database import db; print('   ✅ database.py importa correctamente')"
python3 -c "from schemas.product import ProductCreate, ProductResponse; print('   ✅ schemas importan correctamente')"
python3 -c "from routers.products import router; print('   ✅ router importa correctamente')"

# 3. Pruebas
echo ""
echo "3. Ejecutando pruebas..."
python3 -m pytest tests/ -q --no-header 2>&1 | tail -1

echo ""
echo "=== Verificación completada ==="
```

---

## Resumen

En esta práctica has implementado un microservicio REST completo con FastAPI que incluye:

| Componente | Archivo | Responsabilidad |
|------------|---------|-----------------|
| Aplicación | `main.py` | Configuración de FastAPI y registro de routers |
| Router | `routers/products.py` | 5 endpoints CRUD con manejo de errores |
| Esquemas | `schemas/product.py` | Validación de entrada/salida con Pydantic |
| Base de datos | `database.py` | Almacenamiento en memoria con interfaz CRUD |
| Pruebas | `tests/test_products.py` | 24 pruebas de integración automatizadas |

### Endpoints implementados

| Método | Ruta | Código Éxito | Descripción |
|--------|------|--------------|-------------|
| GET | `/health` | 200 | Verificación de salud |
| GET | `/products/` | 200 | Listar todos los productos |
| GET | `/products/{id}` | 200 | Obtener producto por ID |
| POST | `/products/` | 201 | Crear nuevo producto |
| PUT | `/products/{id}` | 200 | Actualizar producto |
| DELETE | `/products/{id}` | 204 | Eliminar producto |

### Próximos pasos

En la **Práctica 03-00-01** contenedorizarás este servicio con Docker, creando un `Dockerfile` optimizado y configurando `docker-compose.yml` para orquestar el despliegue.

---

## Solución de Problemas

| Problema | Causa probable | Solución |
|----------|---------------|----------|
| `ModuleNotFoundError: No module named 'fastapi'` | Entorno virtual no activado | Ejecutar `source .venv/bin/activate` |
| `Address already in use` al iniciar uvicorn | Proceso previo en puerto 8000 | Ejecutar `lsof -ti :8000 | xargs kill -9` para liberar el puerto |
| Pruebas fallan con `ImportError` | Directorio de trabajo incorrecto | Ejecutar `cd ~/microservicios-curso/products-service/` |
| `422 Unprocessable Entity` en POST | JSON de entrada no cumple validación | Verificar que `name` no esté vacío y `price` sea mayor a 0 |
| pytest no encuentra pruebas | Falta `pytest.ini` o `__init__.py` en tests | Verificar que ambos archivos existen |
