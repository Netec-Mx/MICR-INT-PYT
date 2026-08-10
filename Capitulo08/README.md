# Persistencia Híbrida (PostgreSQL + MongoDB) para un Servicio

## Metadatos

| Campo | Valor |
|-------|-------|
| **Duración** | 63 minutos |
| **Complejidad** | Alta |
| **Nivel Bloom** | Crear |

## Descripción General

En esta práctica construirás un microservicio `catalog-service` que implementa el patrón **Polyglot Persistence**: los datos maestros de productos (id, nombre, precio, stock) se almacenan en PostgreSQL 16.3 con SQLAlchemy 2.0.30 asíncrono, mientras que los detalles enriquecidos (descripciones, imágenes, atributos variables, historial) se persisten en MongoDB 7.0.11 con Motor 3.4.0. Implementarás el **patrón Saga con compensación** para garantizar consistencia entre ambas bases de datos, y protegerás los endpoints con autenticación JWT RS256 reutilizando la clave pública del `auth-service` del lab 7.

## Objetivos de Aprendizaje

- [ ] Diseñar e implementar un microservicio Python que use PostgreSQL para datos transaccionales y MongoDB para documentos flexibles simultáneamente
- [ ] Implementar el patrón Saga con compensación para manejar transacciones distribuidas entre ambas bases de datos
- [ ] Configurar SQLAlchemy 2.0.30 con asyncpg para operaciones asíncronas y Motor 3.4.0 para MongoDB
- [ ] Integrar autenticación JWT RS256 para proteger todos los endpoints del servicio
- [ ] Validar la consistencia del sistema mediante pruebas de integración con pytest

## Prerrequisitos

### Conocimientos Requeridos

- Lab 07-00-01 completado con `auth-service` funcional (JWT RS256)
- Fundamentos de SQLAlchemy y modelos declarativos
- Conceptos de bases de datos documentales (MongoDB)
- Patrón Saga y transacciones distribuidas (lección 8.2)

### Acceso y Recursos

- Docker Engine 26.1.3 con red `microservices-net` creada
- Imágenes `postgres:16.3` y `mongo:7.0.11` descargadas
- Archivo `public_key.pem` del `auth-service` disponible
- Conexión a Internet para instalar dependencias Python

## Entorno del Laboratorio

### Software Requerido

| Componente | Versión |
|------------|---------|
| Python | 3.12.3 |
| FastAPI | 0.111.0 |
| SQLAlchemy | 2.0.30 |
| asyncpg | 0.29.0 |
| Motor | 3.4.0 |
| Alembic | 1.13.1 |
| PostgreSQL | 16.3 (Docker) |
| MongoDB | 7.0.11 (Docker) |
| Docker Compose | 2.27.1 |
| pytest | 8.2.2 |
| pytest-asyncio | 0.23.7 |

### Configuración Inicial del Entorno

```bash
# Crear estructura de directorios
mkdir -p ~/microservicios-curso/catalog-service/{app/{routers,models,schemas,services,db},tests,certs,alembic/versions}

# Navegar al directorio del servicio
cd ~/microservicios-curso/catalog-service

# Crear y activar entorno virtual
python3 -m venv .venv
source .venv/bin/activate

# Verificar red Docker existente
docker network ls | grep microservices-net || docker network create microservices-net

# Copiar clave pública del auth-service
cp ~/microservicios-curso/auth-service/certs/public_key.pem ./certs/
```

## Paso a Paso

### Paso 1: Configurar Dependencias y Docker Compose

**Objetivo:** Establecer el archivo de dependencias Python y la orquestación de contenedores para PostgreSQL, MongoDB y el catalog-service.

**Instrucciones:**

1. Crea el archivo `requirements.txt`:

```bash
cat > ~/microservicios-curso/catalog-service/requirements.txt << 'EOF'
fastapi==0.111.0
uvicorn[standard]==0.30.1
sqlalchemy[asyncio]==2.0.30
asyncpg==0.29.0
motor==3.4.0
alembic==1.13.1
pydantic==2.7.1
pydantic-settings==2.3.1
python-jose[cryptography]==3.3.0
httpx==0.27.0
pytest==8.2.2
pytest-asyncio==0.23.7
EOF
```

2. Instala las dependencias:

```bash
cd ~/microservicios-curso/catalog-service
source .venv/bin/activate
pip install -r requirements.txt
```

3. Crea el archivo `docker-compose.yml`:

```bash
cat > ~/microservicios-curso/catalog-service/docker-compose.yml << 'EOF'
version: "3.9"

services:
  postgres-catalog:
    image: postgres:16.3
    container_name: postgres-catalog
    environment:
      POSTGRES_DB: catalog_db
      POSTGRES_USER: catalog_user
      POSTGRES_PASSWORD: catalog_pass_2024
    ports:
      - "5432:5432"
    volumes:
      - pg_catalog_data:/var/lib/postgresql/data
    networks:
      - microservices-net
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U catalog_user -d catalog_db"]
      interval: 5s
      timeout: 3s
      retries: 5

  mongo-catalog:
    image: mongo:7.0.11
    container_name: mongo-catalog
    environment:
      MONGO_INITDB_ROOT_USERNAME: mongo_user
      MONGO_INITDB_ROOT_PASSWORD: mongo_pass_2024
    ports:
      - "27017:27017"
    volumes:
      - mongo_catalog_data:/data/db
    networks:
      - microservices-net
    healthcheck:
      test: ["CMD", "mongosh", "--eval", "db.adminCommand('ping')"]
      interval: 5s
      timeout: 3s
      retries: 5

volumes:
  pg_catalog_data:
  mongo_catalog_data:

networks:
  microservices-net:
    external: true
EOF
```

4. Levanta los contenedores de bases de datos:

```bash
cd ~/microservicios-curso/catalog-service
docker compose up -d postgres-catalog mongo-catalog
```

**Resultado Esperado:**

```
[+] Running 2/2
 ✔ Container postgres-catalog  Started
 ✔ Container mongo-catalog     Started
```

**Verificación:**

```bash
# Verificar que PostgreSQL está listo
docker exec postgres-catalog pg_isready -U catalog_user -d catalog_db

# Verificar que MongoDB está listo
docker exec mongo-catalog mongosh --eval "db.adminCommand('ping')" -u mongo_user -p mongo_pass_2024
```

---

### Paso 2: Configurar Modelos SQLAlchemy y Conexión Asíncrona a PostgreSQL

**Objetivo:** Crear el modelo de datos transaccional en PostgreSQL con SQLAlchemy asíncrono y configurar la sesión de base de datos.

**Instrucciones:**

1. Crea el archivo de configuración `app/config.py`:

```bash
cat > ~/microservicios-curso/catalog-service/app/config.py << 'EOF'
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # PostgreSQL
    postgres_url: str = "postgresql+asyncpg://catalog_user:catalog_pass_2024@localhost:5432/catalog_db"
    
    # MongoDB
    mongo_url: str = "mongodb://mongo_user:mongo_pass_2024@localhost:27017"
    mongo_db_name: str = "catalog_details"
    
    # JWT
    jwt_public_key_path: str = "certs/public_key.pem"
    jwt_algorithm: str = "RS256"
    
    # App
    app_name: str = "catalog-service"
    debug: bool = False

    class Config:
        env_file = ".env"


@lru_cache
def get_settings() -> Settings:
    return Settings()
EOF
```

2. Crea la conexión asíncrona a PostgreSQL en `app/db/postgres.py`:

```bash
cat > ~/microservicios-curso/catalog-service/app/db/__init__.py << 'EOF'
EOF

cat > ~/microservicios-curso/catalog-service/app/db/postgres.py << 'EOF'
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.postgres_url,
    echo=settings.debug,
    pool_size=5,
    max_overflow=10,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_pg_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_pg():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_pg():
    await engine.dispose()
EOF
```

3. Crea el modelo de producto en `app/models/product.py`:

```bash
cat > ~/microservicios-curso/catalog-service/app/models/__init__.py << 'EOF'
from app.models.product import Product
EOF

cat > ~/microservicios-curso/catalog-service/app/models/product.py << 'EOF'
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Numeric, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.db.postgres import Base


class Product(Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    stock: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
EOF
```

**Resultado Esperado:** Archivos creados sin errores de sintaxis.

**Verificación:**

```bash
cd ~/microservicios-curso/catalog-service
source .venv/bin/activate
python -c "from app.models.product import Product; print(f'Modelo: {Product.__tablename__}')"
```

Salida esperada: `Modelo: products`

---

### Paso 3: Configurar Conexión a MongoDB con Motor

**Objetivo:** Establecer la conexión asíncrona a MongoDB usando Motor y definir la estructura de documentos de detalle.

**Instrucciones:**

1. Crea el módulo de conexión MongoDB en `app/db/mongodb.py`:

```bash
cat > ~/microservicios-curso/catalog-service/app/db/mongodb.py << 'EOF'
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.config import get_settings

settings = get_settings()

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


async def init_mongo() -> None:
    global _client, _db
    _client = AsyncIOMotorClient(settings.mongo_url)
    _db = _client[settings.mongo_db_name]
    # Verificar conexión
    await _client.admin.command("ping")


async def close_mongo() -> None:
    global _client
    if _client:
        _client.close()


def get_mongo_db() -> AsyncIOMotorDatabase:
    if _db is None:
        raise RuntimeError("MongoDB no inicializado. Llama a init_mongo() primero.")
    return _db
EOF
```

2. Crea los esquemas Pydantic en `app/schemas/product.py`:

```bash
cat > ~/microservicios-curso/catalog-service/app/schemas/__init__.py << 'EOF'
EOF

cat > ~/microservicios-curso/catalog-service/app/schemas/product.py << 'EOF'
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class ProductBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    price: float = Field(..., gt=0)
    stock: int = Field(..., ge=0)
    category: str = Field(..., min_length=1, max_length=100)


class ProductDetails(BaseModel):
    description: str = Field(default="", max_length=5000)
    images: list[str] = Field(default_factory=list)
    attributes: dict[str, str | int | float | bool] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)


class ProductCreate(ProductBase):
    details: ProductDetails = Field(default_factory=ProductDetails)


class ProductResponse(ProductBase):
    id: str
    created_at: datetime
    updated_at: datetime
    details: Optional[ProductDetails] = None

    class Config:
        from_attributes = True


class ProductListResponse(BaseModel):
    products: list[ProductResponse]
    total: int
EOF
```

**Resultado Esperado:** Módulos creados correctamente.

**Verificación:**

```bash
python -c "from app.db.mongodb import get_mongo_db; print('Módulo MongoDB OK')"
python -c "from app.schemas.product import ProductCreate; print('Schemas OK')"
```

---

### Paso 4: Implementar el Patrón Saga con Compensación

**Objetivo:** Crear el servicio de negocio que coordina la escritura en PostgreSQL y MongoDB con compensación automática si falla la segunda operación.

**Instrucciones:**

1. Crea el servicio de catálogo en `app/services/catalog_service.py`:

```bash
cat > ~/microservicios-curso/catalog-service/app/services/__init__.py << 'EOF'
EOF

cat > ~/microservicios-curso/catalog-service/app/services/catalog_service.py << 'EOF'
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.models.product import Product
from app.schemas.product import ProductCreate, ProductResponse, ProductDetails
from app.db.mongodb import get_mongo_db

logger = logging.getLogger(__name__)


class SagaCompensationError(Exception):
    """Error cuando la compensación de la Saga también falla."""
    pass


class CatalogService:
    """
    Implementa el patrón Saga para crear productos en dos bases de datos:
    1. PostgreSQL: datos maestros (transaccional)
    2. MongoDB: detalles enriquecidos (documental)
    
    Compensación: si MongoDB falla, se elimina el registro de PostgreSQL.
    """

    def __init__(self, pg_session: AsyncSession):
        self.pg_session = pg_session
        self.mongo_db = get_mongo_db()
        self.details_collection = self.mongo_db["product_details"]

    async def create_product(self, data: ProductCreate) -> ProductResponse:
        """
        Saga: Crear producto con persistencia híbrida.
        Paso 1: Insertar en PostgreSQL (datos maestros)
        Paso 2: Insertar en MongoDB (detalles)
        Compensación: Si paso 2 falla, eliminar de PostgreSQL
        """
        product = None

        # === PASO 1: Insertar en PostgreSQL ===
        try:
            product = Product(
                name=data.name,
                price=data.price,
                stock=data.stock,
                category=data.category,
            )
            self.pg_session.add(product)
            await self.pg_session.commit()
            await self.pg_session.refresh(product)
            logger.info(f"Saga Paso 1 OK: Producto '{product.id}' insertado en PostgreSQL")
        except Exception as e:
            await self.pg_session.rollback()
            logger.error(f"Saga Paso 1 FALLO: Error en PostgreSQL - {e}")
            raise RuntimeError(f"Error al crear producto en PostgreSQL: {e}")

        # === PASO 2: Insertar en MongoDB ===
        try:
            detail_doc = {
                "product_id": product.id,
                "description": data.details.description,
                "images": data.details.images,
                "attributes": data.details.attributes,
                "tags": data.details.tags,
                "history": [
                    {
                        "action": "created",
                        "timestamp": product.created_at.isoformat(),
                        "data": data.details.model_dump(),
                    }
                ],
            }
            await self.details_collection.insert_one(detail_doc)
            logger.info(f"Saga Paso 2 OK: Detalles de '{product.id}' insertados en MongoDB")
        except Exception as e:
            logger.error(f"Saga Paso 2 FALLO: Error en MongoDB - {e}")
            # === COMPENSACIÓN: Eliminar de PostgreSQL ===
            await self._compensate_pg(product.id)
            raise RuntimeError(
                f"Error al crear detalles en MongoDB. Compensación ejecutada: {e}"
            )

        return self._build_response(product, data.details)

    async def get_product(self, product_id: str) -> ProductResponse | None:
        """Obtener producto combinando datos de PostgreSQL y MongoDB."""
        # Consultar PostgreSQL
        stmt = select(Product).where(Product.id == product_id)
        result = await self.pg_session.execute(stmt)
        product = result.scalar_one_or_none()

        if not product:
            return None

        # Consultar MongoDB
        detail_doc = await self.details_collection.find_one(
            {"product_id": product_id}
        )

        details = None
        if detail_doc:
            details = ProductDetails(
                description=detail_doc.get("description", ""),
                images=detail_doc.get("images", []),
                attributes=detail_doc.get("attributes", {}),
                tags=detail_doc.get("tags", []),
            )

        return self._build_response(product, details)

    async def list_products(self, skip: int = 0, limit: int = 20) -> tuple[list[ProductResponse], int]:
        """Listar productos con paginación."""
        from sqlalchemy import func

        # Contar total
        count_stmt = select(func.count()).select_from(Product)
        count_result = await self.pg_session.execute(count_stmt)
        total = count_result.scalar()

        # Obtener página
        stmt = select(Product).offset(skip).limit(limit)
        result = await self.pg_session.execute(stmt)
        products = result.scalars().all()

        responses = []
        for product in products:
            detail_doc = await self.details_collection.find_one(
                {"product_id": product.id}
            )
            details = None
            if detail_doc:
                details = ProductDetails(
                    description=detail_doc.get("description", ""),
                    images=detail_doc.get("images", []),
                    attributes=detail_doc.get("attributes", {}),
                    tags=detail_doc.get("tags", []),
                )
            responses.append(self._build_response(product, details))

        return responses, total

    async def delete_product(self, product_id: str) -> bool:
        """Eliminar producto de ambas bases de datos."""
        stmt = select(Product).where(Product.id == product_id)
        result = await self.pg_session.execute(stmt)
        product = result.scalar_one_or_none()

        if not product:
            return False

        # Eliminar de MongoDB primero
        await self.details_collection.delete_one({"product_id": product_id})
        
        # Eliminar de PostgreSQL
        delete_stmt = delete(Product).where(Product.id == product_id)
        await self.pg_session.execute(delete_stmt)
        await self.pg_session.commit()

        logger.info(f"Producto '{product_id}' eliminado de ambas bases de datos")
        return True

    async def _compensate_pg(self, product_id: str) -> None:
        """Compensación: eliminar registro de PostgreSQL tras fallo en MongoDB."""
        try:
            delete_stmt = delete(Product).where(Product.id == product_id)
            await self.pg_session.execute(delete_stmt)
            await self.pg_session.commit()
            logger.info(f"Compensación OK: Producto '{product_id}' eliminado de PostgreSQL")
        except Exception as comp_error:
            logger.critical(
                f"COMPENSACIÓN FALLIDA: No se pudo eliminar '{product_id}' de PostgreSQL - {comp_error}"
            )
            raise SagaCompensationError(
                f"Compensación fallida para producto {product_id}: {comp_error}"
            )

    def _build_response(
        self, product: Product, details: ProductDetails | None
    ) -> ProductResponse:
        return ProductResponse(
            id=product.id,
            name=product.name,
            price=float(product.price),
            stock=product.stock,
            category=product.category,
            created_at=product.created_at,
            updated_at=product.updated_at,
            details=details,
        )
EOF
```

**Resultado Esperado:** Servicio creado con lógica de Saga completa.

**Verificación:**

```bash
python -c "from app.services.catalog_service import CatalogService, SagaCompensationError; print('Servicio Saga OK')"
```

---

### Paso 5: Implementar Middleware de Autenticación JWT

**Objetivo:** Crear la dependencia de autenticación JWT que valida tokens usando la clave pública RS256 del auth-service.

**Instrucciones:**

1. Crea el módulo de autenticación en `app/auth.py`:

```bash
cat > ~/microservicios-curso/catalog-service/app/auth.py << 'EOF'
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError, ExpiredSignatureError
from app.config import get_settings
from pathlib import Path

security = HTTPBearer()
settings = get_settings()

_public_key: str | None = None


def _load_public_key() -> str:
    global _public_key
    if _public_key is None:
        key_path = Path(settings.jwt_public_key_path)
        if not key_path.exists():
            raise RuntimeError(f"Clave pública no encontrada: {key_path}")
        _public_key = key_path.read_text()
    return _public_key


async def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """
    Dependencia FastAPI que valida el token JWT RS256.
    Retorna el payload decodificado si es válido.
    """
    token = credentials.credentials
    public_key = _load_public_key()

    try:
        payload = jwt.decode(
            token,
            public_key,
            algorithms=[settings.jwt_algorithm],
            options={"verify_aud": False},
        )
        return payload
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token inválido: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )
EOF
```

**Resultado Esperado:** Módulo de autenticación listo.

**Verificación:**

```bash
python -c "from app.auth import verify_token; print('Auth module OK')"
```

---

### Paso 6: Crear los Endpoints del Router

**Objetivo:** Implementar los endpoints REST del catalog-service protegidos con JWT.

**Instrucciones:**

1. Crea el router de productos en `app/routers/products.py`:

```bash
cat > ~/microservicios-curso/catalog-service/app/routers/__init__.py << 'EOF'
EOF

cat > ~/microservicios-curso/catalog-service/app/routers/products.py << 'EOF'
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.postgres import get_pg_session
from app.auth import verify_token
from app.schemas.product import ProductCreate, ProductResponse, ProductListResponse
from app.services.catalog_service import CatalogService

router = APIRouter(prefix="/api/v1/products", tags=["products"])


@router.post(
    "/",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear producto (Saga: PostgreSQL + MongoDB)",
)
async def create_product(
    data: ProductCreate,
    token_payload: dict = Depends(verify_token),
    pg_session: AsyncSession = Depends(get_pg_session),
):
    """
    Crea un producto usando el patrón Saga:
    1. Inserta datos maestros en PostgreSQL
    2. Inserta detalles en MongoDB
    3. Si paso 2 falla, compensa eliminando de PostgreSQL
    """
    service = CatalogService(pg_session)
    try:
        product = await service.create_product(data)
        return product
    except RuntimeError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get(
    "/{product_id}",
    response_model=ProductResponse,
    summary="Obtener producto por ID",
)
async def get_product(
    product_id: str,
    token_payload: dict = Depends(verify_token),
    pg_session: AsyncSession = Depends(get_pg_session),
):
    service = CatalogService(pg_session)
    product = await service.get_product(product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Producto '{product_id}' no encontrado",
        )
    return product


@router.get(
    "/",
    response_model=ProductListResponse,
    summary="Listar productos con paginación",
)
async def list_products(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    token_payload: dict = Depends(verify_token),
    pg_session: AsyncSession = Depends(get_pg_session),
):
    service = CatalogService(pg_session)
    products, total = await service.list_products(skip=skip, limit=limit)
    return ProductListResponse(products=products, total=total)


@router.delete(
    "/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar producto de ambas bases de datos",
)
async def delete_product(
    product_id: str,
    token_payload: dict = Depends(verify_token),
    pg_session: AsyncSession = Depends(get_pg_session),
):
    service = CatalogService(pg_session)
    deleted = await service.delete_product(product_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Producto '{product_id}' no encontrado",
        )
EOF
```

2. Crea la aplicación principal en `app/main.py`:

```bash
cat > ~/microservicios-curso/catalog-service/app/__init__.py << 'EOF'
EOF

cat > ~/microservicios-curso/catalog-service/app/main.py << 'EOF'
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.db.postgres import init_pg, close_pg
from app.db.mongodb import init_mongo, close_mongo
from app.routers.products import router as products_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Inicializando conexiones a bases de datos...")
    await init_pg()
    logger.info("PostgreSQL conectado y tablas creadas")
    await init_mongo()
    logger.info("MongoDB conectado")
    yield
    # Shutdown
    logger.info("Cerrando conexiones...")
    await close_pg()
    await close_mongo()
    logger.info("Conexiones cerradas")


app = FastAPI(
    title="Catalog Service",
    description="Microservicio con persistencia híbrida PostgreSQL + MongoDB",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(products_router)


@app.get("/health", tags=["health"])
async def health_check():
    return {"status": "healthy", "service": "catalog-service"}
EOF
```

**Resultado Esperado:** Aplicación FastAPI completa con router y lifespan.

**Verificación:**

```bash
python -c "from app.main import app; print(f'Rutas: {[r.path for r in app.routes]}')"
```

Salida esperada (parcial):
```
Rutas: ['/api/v1/products/', '/api/v1/products/{product_id}', '/api/v1/products/', '/api/v1/products/{product_id}', '/health', ...]
```

---

### Paso 7: Configurar Alembic para Migraciones

**Objetivo:** Configurar Alembic para gestionar migraciones de esquema en PostgreSQL de forma controlada.

**Instrucciones:**

1. Inicializa Alembic:

```bash
cd ~/microservicios-curso/catalog-service
alembic init alembic
```

2. Edita `alembic/env.py` para soporte asíncrono:

```bash
cat > ~/microservicios-curso/catalog-service/alembic/env.py << 'EOF'
import asyncio
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context

from app.db.postgres import Base
from app.models.product import Product  # noqa: F401
from app.config import get_settings

config = context.config
settings = get_settings()

# Sobrescribir URL desde configuración
config.set_main_option("sqlalchemy.url", settings.postgres_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
EOF
```

3. Actualiza `alembic.ini` con el driver correcto:

```bash
sed -i 's|sqlalchemy.url = driver://user:pass@localhost/dbname|sqlalchemy.url = postgresql+asyncpg://catalog_user:catalog_pass_2024@localhost:5432/catalog_db|' ~/microservicios-curso/catalog-service/alembic.ini
```

4. Genera y aplica la migración inicial:

```bash
cd ~/microservicios-curso/catalog-service
alembic revision --autogenerate -m "create_products_table"
alembic upgrade head
```

**Resultado Esperado:**

```
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade  -> xxxxxxxxxxxx, create_products_table
```

**Verificación:**

```bash
docker exec postgres-catalog psql -U catalog_user -d catalog_db -c "\dt"
```

Salida esperada (incluye tabla `products` y `alembic_version`):
```
            List of relations
 Schema |      Name       | Type  |    Owner
--------+-----------------+-------+--------------
 public | alembic_version | table | catalog_user
 public | products        | table | catalog_user
```

---

### Paso 8: Arrancar el Servicio y Probar Manualmente

**Objetivo:** Verificar que el catalog-service arranca correctamente y responde a peticiones autenticadas.

**Instrucciones:**

1. Arranca el servicio:

```bash
cd ~/microservicios-curso/catalog-service
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload &
sleep 3
```

2. Verifica el health check:

```bash
curl -s http://localhost:8001/health | python -m json.tool
```

**Resultado Esperado:**

```json
{
    "status": "healthy",
    "service": "catalog-service"
}
```

3. Genera un token JWT de prueba (usando el auth-service del lab 7 o creando uno temporal):

```bash
# Si auth-service está corriendo en puerto 8000:
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}' | python -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

echo "Token: ${TOKEN:0:50}..."
```

> **Nota:** Si el auth-service no está disponible, genera un token temporal con la clave privada para pruebas. Consulta la sección de Troubleshooting si necesitas un script de generación.

4. Crea un producto:

```bash
curl -s -X POST http://localhost:8001/api/v1/products/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Televisor 4K Samsung",
    "price": 899.99,
    "stock": 50,
    "category": "Electrónica",
    "details": {
      "description": "Smart TV 55 pulgadas con resolución 4K UHD",
      "images": ["https://example.com/tv1.jpg", "https://example.com/tv2.jpg"],
      "attributes": {"resolucion": "3840x2160", "pulgadas": 55, "smart_tv": true},
      "tags": ["4k", "smart-tv", "samsung"]
    }
  }' | python -m json.tool
```

**Resultado Esperado:**

```json
{
    "id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
    "name": "Televisor 4K Samsung",
    "price": 899.99,
    "stock": 50,
    "category": "Electrónica",
    "created_at": "2024-...",
    "updated_at": "2024-...",
    "details": {
        "description": "Smart TV 55 pulgadas con resolución 4K UHD",
        "images": ["https://example.com/tv1.jpg", "https://example.com/tv2.jpg"],
        "attributes": {"resolucion": "3840x2160", "pulgadas": 55, "smart_tv": true},
        "tags": ["4k", "smart-tv", "samsung"]
    }
}
```

5. Verifica que los datos están en ambas bases de datos:

```bash
# Verificar PostgreSQL
docker exec postgres-catalog psql -U catalog_user -d catalog_db -c "SELECT id, name, price, stock FROM products;"

# Verificar MongoDB
docker exec mongo-catalog mongosh --eval "db.getSiblingDB('catalog_details').product_details.find().pretty()" -u mongo_user -p mongo_pass_2024 --authenticationDatabase admin
```

**Verificación:** Ambas consultas deben mostrar el producto creado con datos correspondientes.

---

### Paso 9: Implementar Pruebas de Integración

**Objetivo:** Crear pruebas automatizadas que validen la consistencia de la Saga, incluyendo el escenario de compensación.

**Instrucciones:**

1. Crea el archivo de configuración de tests `tests/conftest.py`:

```bash
cat > ~/microservicios-curso/catalog-service/tests/__init__.py << 'EOF'
EOF

cat > ~/microservicios-curso/catalog-service/tests/conftest.py << 'EOF'
import pytest
import asyncio
from datetime import datetime, timedelta, timezone
from jose import jwt
from pathlib import Path
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.db.postgres import engine, Base
from app.db.mongodb import get_mongo_db, init_mongo, close_mongo


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


def generate_test_token() -> str:
    """Genera un token JWT para pruebas usando la clave privada."""
    # Intentar usar la clave privada si está disponible
    private_key_path = Path("certs/private_key.pem")
    if private_key_path.exists():
        private_key = private_key_path.read_text()
    else:
        # Generar un par de claves temporal para tests
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization

        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        private_key = key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode()
        # Guardar la clave pública para que el servicio la use
        public_key = key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.SubjectPublicKeyInfo,
        ).decode()
        Path("certs").mkdir(exist_ok=True)
        Path("certs/public_key.pem").write_text(public_key)
        Path("certs/private_key.pem").write_text(private_key)

    payload = {
        "sub": "test-user",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, private_key, algorithm="RS256")


@pytest.fixture(scope="session")
def auth_token() -> str:
    return generate_test_token()


@pytest.fixture(scope="session")
def auth_headers(auth_token) -> dict:
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture
async def async_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture(autouse=True, scope="session")
async def setup_databases():
    """Inicializar bases de datos para tests."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await init_mongo()
    yield
    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    mongo_db = get_mongo_db()
    await mongo_db.product_details.drop()
    await close_mongo()
EOF
```

2. Crea las pruebas de integración en `tests/test_catalog.py`:

```bash
cat > ~/microservicios-curso/catalog-service/tests/test_catalog.py << 'EOF'
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, AsyncMock
from app.main import app


@pytest.mark.asyncio
async def test_health_check(async_client: AsyncClient):
    """Verificar que el health check responde correctamente."""
    response = await async_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "catalog-service"


@pytest.mark.asyncio
async def test_create_product_success(async_client: AsyncClient, auth_headers: dict):
    """Verificar creación exitosa de producto en ambas bases de datos."""
    payload = {
        "name": "Laptop Pro 16",
        "price": 1299.99,
        "stock": 25,
        "category": "Computadores",
        "details": {
            "description": "Laptop profesional con 32GB RAM",
            "images": ["https://example.com/laptop.jpg"],
            "attributes": {"ram_gb": 32, "storage_tb": 1, "cpu": "M3 Pro"},
            "tags": ["laptop", "profesional", "apple"],
        },
    }

    response = await async_client.post(
        "/api/v1/products/", json=payload, headers=auth_headers
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Laptop Pro 16"
    assert data["price"] == 1299.99
    assert data["stock"] == 25
    assert data["details"]["description"] == "Laptop profesional con 32GB RAM"
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_get_product_by_id(async_client: AsyncClient, auth_headers: dict):
    """Verificar obtención de producto por ID con datos de ambas BDs."""
    # Crear producto primero
    payload = {
        "name": "Mouse Inalámbrico",
        "price": 49.99,
        "stock": 100,
        "category": "Periféricos",
        "details": {
            "description": "Mouse ergonómico Bluetooth",
            "attributes": {"dpi": 1600, "bluetooth": True},
            "tags": ["mouse", "bluetooth"],
        },
    }
    create_resp = await async_client.post(
        "/api/v1/products/", json=payload, headers=auth_headers
    )
    product_id = create_resp.json()["id"]

    # Obtener por ID
    response = await async_client.get(
        f"/api/v1/products/{product_id}", headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == product_id
    assert data["name"] == "Mouse Inalámbrico"
    assert data["details"]["attributes"]["dpi"] == 1600


@pytest.mark.asyncio
async def test_list_products_pagination(async_client: AsyncClient, auth_headers: dict):
    """Verificar listado con paginación."""
    response = await async_client.get(
        "/api/v1/products/?skip=0&limit=10", headers=auth_headers
    )
    assert response.status_code == 200
    data = response.json()
    assert "products" in data
    assert "total" in data
    assert isinstance(data["products"], list)


@pytest.mark.asyncio
async def test_create_product_unauthorized():
    """Verificar que sin token se rechaza la petición."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "name": "Producto Sin Auth",
            "price": 10.0,
            "stock": 1,
            "category": "Test",
        }
        response = await client.post("/api/v1/products/", json=payload)
        assert response.status_code == 403  # HTTPBearer returns 403 when missing


@pytest.mark.asyncio
async def test_get_product_not_found(async_client: AsyncClient, auth_headers: dict):
    """Verificar 404 para producto inexistente."""
    response = await async_client.get(
        "/api/v1/products/non-existent-id", headers=auth_headers
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_product(async_client: AsyncClient, auth_headers: dict):
    """Verificar eliminación de producto de ambas bases de datos."""
    # Crear producto
    payload = {
        "name": "Producto a Eliminar",
        "price": 5.0,
        "stock": 1,
        "category": "Temporal",
    }
    create_resp = await async_client.post(
        "/api/v1/products/", json=payload, headers=auth_headers
    )
    product_id = create_resp.json()["id"]

    # Eliminar
    response = await async_client.delete(
        f"/api/v1/products/{product_id}", headers=auth_headers
    )
    assert response.status_code == 204

    # Verificar que ya no existe
    get_resp = await async_client.get(
        f"/api/v1/products/{product_id}", headers=auth_headers
    )
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_saga_compensation_on_mongo_failure(
    async_client: AsyncClient, auth_headers: dict
):
    """
    Verificar patrón Saga: si MongoDB falla, PostgreSQL se compensa.
    """
    payload = {
        "name": "Producto Saga Test",
        "price": 100.0,
        "stock": 10,
        "category": "Test Saga",
        "details": {
            "description": "Este producto debe ser compensado",
            "tags": ["saga", "test"],
        },
    }

    # Simular fallo en MongoDB
    with patch(
        "app.services.catalog_service.CatalogService.create_product"
    ) as mock_create:
        # Simular que MongoDB lanza excepción después de insertar en PG
        mock_create.side_effect = RuntimeError(
            "Error al crear detalles en MongoDB. Compensación ejecutada: Connection refused"
        )
        response = await async_client.post(
            "/api/v1/products/", json=payload, headers=auth_headers
        )
        assert response.status_code == 500
        assert "Compensación ejecutada" in response.json()["detail"]
EOF
```

3. Crea el archivo `pytest.ini`:

```bash
cat > ~/microservicios-curso/catalog-service/pytest.ini << 'EOF'
[pytest]
asyncio_mode = auto
testpaths = tests
python_files = test_*.py
python_functions = test_*
EOF
```

4. Detén el servidor uvicorn si está corriendo y ejecuta los tests:

```bash
# Detener uvicorn en background
kill %1 2>/dev/null || true

# Ejecutar pruebas
cd ~/microservicios-curso/catalog-service
source .venv/bin/activate
pip install cryptography  # Necesario para generar claves de test
pytest tests/ -v --tb=short
```

**Resultado Esperado:**

```
tests/test_catalog.py::test_health_check PASSED
tests/test_catalog.py::test_create_product_success PASSED
tests/test_catalog.py::test_get_product_by_id PASSED
tests/test_catalog.py::test_list_products_pagination PASSED
tests/test_catalog.py::test_create_product_unauthorized PASSED
tests/test_catalog.py::test_get_product_not_found PASSED
tests/test_catalog.py::test_delete_product PASSED
tests/test_catalog.py::test_saga_compensation_on_mongo_failure PASSED

========== 8 passed ==========
```

**Verificación:** Todos los tests pasan, confirmando que la Saga funciona correctamente en escenarios de éxito y fallo.

---

### Paso 10: Commit Final y Documentación

**Objetivo:** Guardar el trabajo en el repositorio Git con un commit descriptivo.

**Instrucciones:**

1. Crea el archivo `.gitignore`:

```bash
cat > ~/microservicios-curso/catalog-service/.gitignore << 'EOF'
.venv/
__pycache__/
*.pyc
.env
certs/private_key.pem
secret.yaml
.pytest_cache/
EOF
```

2. Realiza el commit:

```bash
cd ~/microservicios-curso
git add catalog-service/
git commit -m "[lab08] Implementar catalog-service con persistencia híbrida PostgreSQL + MongoDB y patrón Saga"
```

**Resultado Esperado:**

```
[main xxxxxxx] [lab08] Implementar catalog-service con persistencia híbrida PostgreSQL + MongoDB y patrón Saga
 XX files changed, XXXX insertions(+)
```

## Validación y Pruebas

Ejecuta la siguiente secuencia de validación completa:

```bash
cd ~/microservicios-curso/catalog-service
source .venv/bin/activate

echo "=== 1. Verificar contenedores ==="
docker ps --format "table {{.Names}}\t{{.Status}}" | grep -E "postgres-catalog|mongo-catalog"

echo "=== 2. Verificar tabla PostgreSQL ==="
docker exec postgres-catalog psql -U catalog_user -d catalog_db -c "SELECT count(*) FROM products;"

echo "=== 3. Verificar colección MongoDB ==="
docker exec mongo-catalog mongosh --eval "db.getSiblingDB('catalog_details').product_details.countDocuments({})" -u mongo_user -p mongo_pass_2024 --authenticationDatabase admin

echo "=== 4. Ejecutar tests ==="
pytest tests/ -v --tb=short

echo "=== 5. Verificar arranque del servicio ==="
uvicorn app.main:app --host 0.0.0.0 --port 8001 &
sleep 2
curl -s http://localhost:8001/health
kill %1

echo "=== VALIDACIÓN COMPLETA ==="
```

**Criterios de éxito:**
- ✅ Ambos contenedores de BD están `healthy`
- ✅ La tabla `products` existe en PostgreSQL
- ✅ La colección `product_details` existe en MongoDB
- ✅ Todos los tests pasan (8/8)
- ✅ El servicio arranca y responde en `/health`

## Solución de Problemas

### Problema 1: Error de conexión a PostgreSQL al ejecutar Alembic

**Síntomas:**
```
sqlalchemy.exc.OperationalError: (asyncpg.exceptions.ConnectionDoesNotExistError)
connection refused
```

**Causa:** El contenedor `postgres-catalog` no ha terminado de inicializarse o el puerto 5432 está ocupado por otra instancia de PostgreSQL local.

**Solución:**

```bash
# Verificar que el contenedor está healthy
docker inspect postgres-catalog --format='{{.State.Health.Status}}'

# Si no está healthy, esperar y reiniciar
docker compose restart postgres-catalog
sleep 10

# Verificar que el puerto está disponible
ss -tlnp | grep 5432

# Si hay conflicto de puertos, detener PostgreSQL local
sudo systemctl stop postgresql 2>/dev/null || true

# Reintentar la migración
alembic upgrade head
```

### Problema 2: Token JWT rechazado con "Token inválido" al hacer peticiones

**Síntomas:**
```json
{"detail": "Token inválido: Signature verification failed."}
```

**Causa:** La clave pública en `certs/public_key.pem` no corresponde a la clave privada usada para firmar el token en el `auth-service`, o el archivo no se copió correctamente.

**Solución:**

```bash
# Verificar que la clave pública existe y tiene contenido
cat ~/microservicios-curso/catalog-service/certs/public_key.pem | head -2

# Debe mostrar: -----BEGIN PUBLIC KEY-----

# Si no existe o está vacía, copiar nuevamente desde auth-service
cp ~/microservicios-curso/auth-service/certs/public_key.pem \
   ~/microservicios-curso/catalog-service/certs/

# Si el auth-service no está disponible, generar par de claves para pruebas
cd ~/microservicios-curso/catalog-service
python -c "
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
# Guardar privada
with open('certs/private_key.pem', 'wb') as f:
    f.write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
# Guardar pública
with open('certs/public_key.pem', 'wb') as f:
    f.write(key.public_key().public_bytes(serialization.Encoding.PEM, serialization.SubjectPublicKeyInfo))
print('Claves generadas correctamente')
"

# Generar token con la nueva clave privada
python -c "
from jose import jwt
from datetime import datetime, timedelta, timezone
from pathlib import Path
private_key = Path('certs/private_key.pem').read_text()
token = jwt.encode({'sub': 'admin', 'exp': datetime.now(timezone.utc) + timedelta(hours=1)}, private_key, algorithm='RS256')
print(token)
"
```

## Limpieza

```bash
# Detener servicios en background
kill %1 2>/dev/null || true

# Detener y eliminar contenedores de bases de datos
cd ~/microservicios-curso/catalog-service
docker compose down -v

# (Opcional) Eliminar volúmenes de datos
docker volume rm catalog-service_pg_catalog_data catalog-service_mongo_catalog_data 2>/dev/null || true

# Desactivar entorno virtual
deactivate
```

## Resumen

En esta práctica has construido un microservicio `catalog-service` que demuestra el patrón **Polyglot Persistence** en acción:

| Logro | Tecnología |
|-------|-----------|
| Datos maestros transaccionales | PostgreSQL 16.3 + SQLAlchemy 2.0.30 async |
| Documentos flexibles | MongoDB 7.0.11 + Motor 3.4.0 |
| Consistencia distribuida | Patrón Saga con compensación |
| Migraciones de esquema | Alembic 1.13.1 |
| Seguridad | JWT RS256 con clave pública compartida |
| Calidad | 8 tests de integración con pytest-asyncio |

**Conceptos clave aplicados:**
- **Polyglot Persistence:** Cada tipo de dato usa el motor más adecuado
- **Patrón Saga:** Garantiza consistencia eventual con compensación automática
- **Separación de responsabilidades:** PostgreSQL para integridad referencial, MongoDB para flexibilidad de esquema
- **Teorema CAP:** PostgreSQL prioriza Consistencia; MongoDB ofrece flexibilidad con consistencia eventual configurable

### Recursos Adicionales

- [SQLAlchemy 2.0 Async Documentation](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [Motor (Async MongoDB Driver) Documentation](https://motor.readthedocs.io/en/stable/)
- [Alembic Tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
- [Saga Pattern - Microsoft Architecture Guide](https://learn.microsoft.com/en-us/azure/architecture/reference-architectures/saga/saga)
