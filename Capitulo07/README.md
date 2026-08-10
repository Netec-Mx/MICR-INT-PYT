# Implementar Autenticación JWT y TLS entre Servicios

## Metadatos

| Campo | Valor |
|-------|-------|
| **Duración** | 63 minutos |
| **Complejidad** | Alta |
| **Nivel Bloom** | Crear |

## Descripción General

En esta práctica construirás una capa de seguridad completa para una arquitectura de microservicios. Crearás un servicio de autenticación (`auth-service`) que emite tokens JWT firmados con RS256 usando claves asimétricas RSA-2048, configurarás TLS mutuo (mTLS) entre servicios usando certificados autofirmados, y protegerás los endpoints del `inventory-service` con middleware de validación JWT. Finalmente, extenderás el Helm chart del lab 6 para desplegar ambos servicios en Kubernetes con los certificados almacenados en Secrets.

## Objetivos de Aprendizaje

- [ ] Implementar un servicio de autenticación FastAPI que genere y valide tokens JWT con firma RS256 usando claves asimétricas RSA-2048
- [ ] Configurar TLS mutuo (mTLS) entre `auth-service` e `inventory-service` usando certificados autofirmados generados con OpenSSL
- [ ] Proteger endpoints del `inventory-service` con middleware de validación JWT que verifique claims `sub`, `exp` y `roles`
- [ ] Extender el Helm chart existente para incluir Kubernetes Secrets con certificados TLS y configuración de autenticación

## Prerrequisitos

### Conocimientos Requeridos

- Conceptos de PKI: Autoridad Certificadora (CA), certificados X.509, firma digital
- Flujo de autenticación JWT (header, payload, signature)
- Control de acceso basado en roles (RBAC)
- Uso básico de Helm charts y Kubernetes Secrets
- FastAPI: middleware y dependency injection

### Acceso y Recursos

- Lab 06-00-01 completado: Helm chart `inventory-chart` desplegado en namespace `microservices`
- Minikube 1.33.1 ejecutándose con el deployment del lab 6 activo
- OpenSSL 3.3.1 disponible en CLI
- Acceso a Docker Hub para push de imágenes (opcional)

## Entorno del Laboratorio

### Software Requerido

| Herramienta | Versión | Propósito |
|-------------|---------|-----------|
| Python | 3.12.3 | Runtime para microservicios |
| FastAPI | 0.111.0 | Framework web |
| python-jose | 3.3.0 | Generación/validación JWT |
| cryptography | 42.0.8 | Soporte RSA para python-jose |
| passlib | 1.7.4 | Hashing bcrypt de contraseñas |
| httpx | 0.27.0 | Cliente HTTP para pruebas |
| OpenSSL | 3.3.1 | Generación de certificados |
| Helm | 3.15.2 | Despliegue en Kubernetes |
| Minikube | 1.33.1 | Clúster Kubernetes local |
| Docker Engine | 26.1.3 | Construcción de imágenes |

### Configuración Inicial

```bash
# Crear directorio de trabajo
mkdir -p ~/labs/lab07/{auth-service,inventory-service,certs,k8s}
cd ~/labs/lab07

# Crear y activar entorno virtual
python3 -m venv venv
source venv/bin/activate

# Instalar dependencias
pip install fastapi==0.111.0 uvicorn==0.30.1 "python-jose[cryptography]==3.3.0" \
  "passlib[bcrypt]==1.7.4" httpx==0.27.0 pydantic==2.7.1 pytest==8.2.1 \
  pytest-asyncio==0.23.7 cryptography==42.0.8
```

---

## Paso 1: Generar Par de Claves RSA-2048 para Firma JWT

**Objetivo:** Crear el par de claves asimétricas que el `auth-service` usará para firmar tokens JWT con algoritmo RS256.

### Instrucciones

1. Navega al directorio de certificados:

```bash
cd ~/labs/lab07/certs
```

2. Genera la clave privada RSA de 2048 bits:

```bash
openssl genrsa -out jwt_private.pem 2048
```

3. Extrae la clave pública correspondiente:

```bash
openssl rsa -in jwt_private.pem -pubout -out jwt_public.pem
```

4. Verifica las claves generadas:

```bash
openssl rsa -in jwt_private.pem -check -noout
openssl rsa -pubin -in jwt_public.pem -text -noout | head -5
```

5. Establece permisos restrictivos en la clave privada:

```bash
chmod 600 jwt_private.pem
chmod 644 jwt_public.pem
```

### Salida Esperada

```
RSA key ok
Public-Key: (2048 bit)
Modulus:
    00:b7:...
```

### Verificación

```bash
# La clave privada debe tener exactamente 2048 bits
openssl rsa -in jwt_private.pem -text -noout | grep "Private-Key"
# Salida: Private-Key: (2048 bit, 2 primes)
```

---

## Paso 2: Generar CA Autofirmada y Certificados TLS para mTLS

**Objetivo:** Crear una Autoridad Certificadora local y emitir certificados TLS individuales para cada microservicio, habilitando comunicación mTLS.

### Instrucciones

1. Genera la clave privada y certificado de la CA:

```bash
cd ~/labs/lab07/certs

# Clave privada de la CA
openssl genrsa -out ca.key 4096

# Certificado autofirmado de la CA (válido 365 días)
openssl req -new -x509 -days 365 -key ca.key -out ca.crt \
  -subj "/C=ES/ST=Madrid/L=Madrid/O=MicroserviciosCurso/CN=Lab07-CA"
```

2. Genera clave y certificado para `auth-service`:

```bash
# Clave privada del auth-service
openssl genrsa -out auth-service.key 2048

# Solicitud de firma (CSR)
openssl req -new -key auth-service.key -out auth-service.csr \
  -subj "/C=ES/ST=Madrid/L=Madrid/O=MicroserviciosCurso/CN=auth-service"

# Crear archivo de extensiones para SAN
cat > auth-service-ext.cnf << 'EOF'
authorityKeyIdentifier=keyid,issuer
basicConstraints=CA:FALSE
keyUsage = digitalSignature, nonRepudiation, keyEncipherment, dataEncipherment
subjectAltName = @alt_names

[alt_names]
DNS.1 = auth-service
DNS.2 = auth-service.microservices.svc.cluster.local
DNS.3 = localhost
IP.1 = 127.0.0.1
EOF

# Firmar con la CA
openssl x509 -req -in auth-service.csr -CA ca.crt -CAkey ca.key \
  -CAcreateserial -out auth-service.crt -days 365 \
  -extfile auth-service-ext.cnf
```

3. Genera clave y certificado para `inventory-service`:

```bash
openssl genrsa -out inventory-service.key 2048

openssl req -new -key inventory-service.key -out inventory-service.csr \
  -subj "/C=ES/ST=Madrid/L=Madrid/O=MicroserviciosCurso/CN=inventory-service"

cat > inventory-service-ext.cnf << 'EOF'
authorityKeyIdentifier=keyid,issuer
basicConstraints=CA:FALSE
keyUsage = digitalSignature, nonRepudiation, keyEncipherment, dataEncipherment
subjectAltName = @alt_names

[alt_names]
DNS.1 = inventory-service
DNS.2 = inventory-service.microservices.svc.cluster.local
DNS.3 = localhost
IP.1 = 127.0.0.1
EOF

openssl x509 -req -in inventory-service.csr -CA ca.crt -CAkey ca.key \
  -CAcreateserial -out inventory-service.crt -days 365 \
  -extfile inventory-service-ext.cnf
```

4. Verifica la cadena de confianza:

```bash
openssl verify -CAfile ca.crt auth-service.crt
openssl verify -CAfile ca.crt inventory-service.crt
```

### Salida Esperada

```
auth-service.crt: OK
inventory-service.crt: OK
```

### Verificación

```bash
# Listar todos los archivos generados
ls -la ~/labs/lab07/certs/
# Deben existir: ca.key, ca.crt, auth-service.{key,crt}, inventory-service.{key,crt}, jwt_private.pem, jwt_public.pem
```

---

## Paso 3: Implementar el Auth-Service con JWT RS256

**Objetivo:** Crear un microservicio FastAPI completo que autentique usuarios y emita tokens JWT firmados con RS256.

### Instrucciones

1. Crea la estructura del proyecto:

```bash
mkdir -p ~/labs/lab07/auth-service
cd ~/labs/lab07/auth-service
```

2. Crea el archivo `main.py`:

```python
# ~/labs/lab07/auth-service/main.py
from datetime import datetime, timedelta, timezone
from typing import Optional
from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

# --- Configuración ---
ALGORITHM = "RS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
CERTS_DIR = Path(__file__).parent.parent / "certs"

# Cargar claves RSA
PRIVATE_KEY = (CERTS_DIR / "jwt_private.pem").read_text()
PUBLIC_KEY = (CERTS_DIR / "jwt_public.pem").read_text()

# --- Modelos ---
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenValidation(BaseModel):
    valid: bool
    sub: Optional[str] = None
    roles: list[str] = []
    exp: Optional[int] = None

class UserCreate(BaseModel):
    username: str
    password: str
    roles: list[str] = ["reader"]

# --- Hashing de contraseñas ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

# --- Base de datos simulada ---
users_db: dict = {
    "admin": {
        "username": "admin",
        "hashed_password": pwd_context.hash("admin-secret-2024"),
        "roles": ["admin", "reader"],
    },
    "viewer": {
        "username": "viewer",
        "hashed_password": pwd_context.hash("viewer-secret-2024"),
        "roles": ["reader"],
    },
}

# --- Aplicación FastAPI ---
app = FastAPI(title="Auth Service", version="1.0.0")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Genera un JWT firmado con RS256 usando la clave privada."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    encoded_jwt = jwt.encode(to_encode, PRIVATE_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_token(token: str) -> dict:
    """Decodifica y valida un JWT usando la clave pública."""
    return jwt.decode(token, PUBLIC_KEY, algorithms=[ALGORITHM])

@app.post("/token", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    """Autentica al usuario y devuelve un JWT firmado con RS256."""
    user = users_db.get(form_data.username)
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(
        data={"sub": user["username"], "roles": user["roles"]},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return Token(access_token=access_token, token_type="bearer")

@app.get("/validate", response_model=TokenValidation)
def validate_token(token: str = Depends(oauth2_scheme)):
    """Valida un JWT y devuelve los claims si es válido."""
    try:
        payload = decode_token(token)
        return TokenValidation(
            valid=True,
            sub=payload.get("sub"),
            roles=payload.get("roles", []),
            exp=payload.get("exp"),
        )
    except JWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token inválido: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

@app.get("/health")
def health():
    return {"status": "healthy", "service": "auth-service"}

@app.get("/.well-known/jwks.json")
def get_public_key():
    """Expone la clave pública para que otros servicios validen tokens."""
    return {"public_key": PUBLIC_KEY, "algorithm": ALGORITHM}
```

3. Crea el archivo de arranque con TLS (`run_tls.py`):

```python
# ~/labs/lab07/auth-service/run_tls.py
import uvicorn
from pathlib import Path

CERTS_DIR = Path(__file__).parent.parent / "certs"

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8001,
        ssl_keyfile=str(CERTS_DIR / "auth-service.key"),
        ssl_certfile=str(CERTS_DIR / "auth-service.crt"),
        ssl_ca_certs=str(CERTS_DIR / "ca.crt"),
    )
```

4. Prueba el servicio en modo local (sin TLS primero):

```bash
cd ~/labs/lab07/auth-service
uvicorn main:app --host 0.0.0.0 --port 8001 &
AUTH_PID=$!
sleep 2

# Obtener token
curl -s -X POST http://localhost:8001/token \
  -d "username=admin&password=admin-secret-2024" \
  -H "Content-Type: application/x-www-form-urlencoded" | python3 -m json.tool

# Detener el servicio
kill $AUTH_PID
```

### Salida Esperada

```json
{
    "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer"
}
```

### Verificación

```bash
# Decodificar el header del token para confirmar RS256
TOKEN=$(curl -s -X POST http://localhost:8001/token \
  -d "username=admin&password=admin-secret-2024" \
  -H "Content-Type: application/x-www-form-urlencoded" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

echo $TOKEN | cut -d'.' -f1 | base64 -d 2>/dev/null
# Debe mostrar: {"alg":"RS256","typ":"JWT"}
```

---

## Paso 4: Implementar Middleware JWT en Inventory-Service

**Objetivo:** Modificar el `inventory-service` para proteger sus endpoints con validación JWT, verificando firma RS256, expiración y claims de rol.

### Instrucciones

1. Crea la estructura del inventory-service:

```bash
mkdir -p ~/labs/lab07/inventory-service
cd ~/labs/lab07/inventory-service
```

2. Crea el archivo `auth_middleware.py`:

```python
# ~/labs/lab07/inventory-service/auth_middleware.py
from typing import Optional
from pathlib import Path

from fastapi import Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt, ExpiredSignatureError

CERTS_DIR = Path(__file__).parent.parent / "certs"
PUBLIC_KEY = (CERTS_DIR / "jwt_public.pem").read_text()
ALGORITHM = "RS256"

security = HTTPBearer()

class JWTValidator:
    """Middleware de validación JWT con verificación de claims."""

    def __init__(self, required_roles: Optional[list[str]] = None):
        self.required_roles = required_roles or []

    async def __call__(self, request: Request) -> dict:
        # Extraer token del header Authorization
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Header Authorization con Bearer token requerido",
                headers={"WWW-Authenticate": "Bearer"},
            )

        token = auth_header.split(" ")[1]

        try:
            # Verificar firma y decodificar
            payload = jwt.decode(token, PUBLIC_KEY, algorithms=[ALGORITHM])
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

        # Verificar claims obligatorios
        sub = payload.get("sub")
        exp = payload.get("exp")
        roles = payload.get("roles", [])

        if not sub:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Claim 'sub' ausente en el token",
            )

        if not exp:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Claim 'exp' ausente en el token",
            )

        # Verificar roles requeridos
        if self.required_roles:
            if not any(role in roles for role in self.required_roles):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Acceso denegado. Roles requeridos: {self.required_roles}. Roles del usuario: {roles}",
                )

        return {"sub": sub, "roles": roles, "exp": exp}
```

3. Crea el archivo principal `main.py`:

```python
# ~/labs/lab07/inventory-service/main.py
from typing import Optional
from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException, status, Request
from pydantic import BaseModel

from auth_middleware import JWTValidator

app = FastAPI(title="Inventory Service", version="2.0.0")

# --- Modelos ---
class InventoryItem(BaseModel):
    id: Optional[int] = None
    name: str
    quantity: int
    category: str

class InventoryResponse(BaseModel):
    items: list[InventoryItem]
    total: int

# --- Base de datos simulada ---
inventory_db: list[dict] = [
    {"id": 1, "name": "Widget A", "quantity": 100, "category": "electronics"},
    {"id": 2, "name": "Gadget B", "quantity": 50, "category": "electronics"},
    {"id": 3, "name": "Tool C", "quantity": 200, "category": "hardware"},
]

# --- Instancias del validador JWT ---
require_auth = JWTValidator()
require_admin = JWTValidator(required_roles=["admin"])

# --- Endpoints públicos ---
@app.get("/health")
def health():
    return {"status": "healthy", "service": "inventory-service"}

# --- Endpoints protegidos (cualquier usuario autenticado) ---
@app.get("/inventory", response_model=InventoryResponse)
async def list_inventory(request: Request):
    """Lista el inventario. Requiere autenticación."""
    claims = await require_auth(request)
    return InventoryResponse(items=inventory_db, total=len(inventory_db))

@app.get("/inventory/{item_id}")
async def get_item(item_id: int, request: Request):
    """Obtiene un item por ID. Requiere autenticación."""
    claims = await require_auth(request)
    item = next((i for i in inventory_db if i["id"] == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Item no encontrado")
    return item

# --- Endpoints protegidos (solo admin) ---
@app.post("/inventory", status_code=201)
async def create_item(item: InventoryItem, request: Request):
    """Crea un nuevo item. Requiere rol 'admin'."""
    claims = await require_admin(request)
    new_id = max(i["id"] for i in inventory_db) + 1 if inventory_db else 1
    new_item = item.model_dump()
    new_item["id"] = new_id
    inventory_db.append(new_item)
    return {"message": "Item creado", "item": new_item, "created_by": claims["sub"]}

@app.delete("/inventory/{item_id}")
async def delete_item(item_id: int, request: Request):
    """Elimina un item. Requiere rol 'admin'."""
    claims = await require_admin(request)
    global inventory_db
    original_len = len(inventory_db)
    inventory_db = [i for i in inventory_db if i["id"] != item_id]
    if len(inventory_db) == original_len:
        raise HTTPException(status_code=404, detail="Item no encontrado")
    return {"message": "Item eliminado", "deleted_by": claims["sub"]}
```

4. Crea el archivo de arranque con TLS (`run_tls.py`):

```python
# ~/labs/lab07/inventory-service/run_tls.py
import uvicorn
from pathlib import Path

CERTS_DIR = Path(__file__).parent.parent / "certs"

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8002,
        ssl_keyfile=str(CERTS_DIR / "inventory-service.key"),
        ssl_certfile=str(CERTS_DIR / "inventory-service.crt"),
        ssl_ca_certs=str(CERTS_DIR / "ca.crt"),
    )
```

### Salida Esperada

Al iniciar el servicio, uvicorn reportará:

```
INFO:     Started server process
INFO:     Uvicorn running on https://0.0.0.0:8002 (Press CTRL+C to quit)
```

### Verificación

```bash
# Arrancar ambos servicios para prueba local
cd ~/labs/lab07/auth-service && uvicorn main:app --port 8001 &
cd ~/labs/lab07/inventory-service && uvicorn main:app --port 8002 &
sleep 2

# Obtener token
TOKEN=$(curl -s -X POST http://localhost:8001/token \
  -d "username=admin&password=admin-secret-2024" \
  -H "Content-Type: application/x-www-form-urlencoded" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Acceder a endpoint protegido con token válido
curl -s http://localhost:8002/inventory \
  -H "Authorization: Bearer $TOKEN" | python3 -m json.tool

# Intentar sin token (debe dar 401)
curl -s -w "\n%{http_code}\n" http://localhost:8002/inventory

# Limpiar procesos
kill %1 %2 2>/dev/null
```

---

## Paso 5: Probar mTLS entre Servicios

**Objetivo:** Verificar que la comunicación TLS mutua funciona correctamente entre los dos servicios usando los certificados generados.

### Instrucciones

1. Arranca ambos servicios con TLS:

```bash
cd ~/labs/lab07/auth-service
python3 run_tls.py &
AUTH_TLS_PID=$!
sleep 2

cd ~/labs/lab07/inventory-service
python3 run_tls.py &
INV_TLS_PID=$!
sleep 2
```

2. Prueba la conexión TLS con curl verificando el certificado de la CA:

```bash
# Verificar auth-service con TLS
curl -s --cacert ~/labs/lab07/certs/ca.crt \
  https://localhost:8001/health | python3 -m json.tool

# Verificar inventory-service con TLS
curl -s --cacert ~/labs/lab07/certs/ca.crt \
  https://localhost:8002/health | python3 -m json.tool
```

3. Prueba mTLS completo (cliente presenta su certificado):

```bash
# Obtener token vía TLS
TOKEN=$(curl -s --cacert ~/labs/lab07/certs/ca.crt \
  --cert ~/labs/lab07/certs/auth-service.crt \
  --key ~/labs/lab07/certs/auth-service.key \
  -X POST https://localhost:8001/token \
  -d "username=admin&password=admin-secret-2024" \
  -H "Content-Type: application/x-www-form-urlencoded" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

echo "Token obtenido: ${TOKEN:0:50}..."

# Acceder a inventory-service con mTLS + JWT
curl -s --cacert ~/labs/lab07/certs/ca.crt \
  --cert ~/labs/lab07/certs/inventory-service.crt \
  --key ~/labs/lab07/certs/inventory-service.key \
  -H "Authorization: Bearer $TOKEN" \
  https://localhost:8002/inventory | python3 -m json.tool
```

4. Detén los servicios:

```bash
kill $AUTH_TLS_PID $INV_TLS_PID 2>/dev/null
```

### Salida Esperada

```json
{
    "items": [
        {"id": 1, "name": "Widget A", "quantity": 100, "category": "electronics"},
        {"id": 2, "name": "Gadget B", "quantity": 50, "category": "electronics"},
        {"id": 3, "name": "Tool C", "quantity": 200, "category": "hardware"}
    ],
    "total": 3
}
```

### Verificación

```bash
# Sin el certificado de la CA, la conexión debe fallar
curl -s https://localhost:8002/health 2>&1 | grep -i "certificate"
# Debe mostrar un error de verificación de certificado
```

---

## Paso 6: Crear Dockerfiles para Ambos Servicios

**Objetivo:** Construir imágenes Docker optimizadas para ambos servicios, preparándolos para el despliegue en Kubernetes.

### Instrucciones

1. Crea el Dockerfile del `auth-service`:

```dockerfile
# ~/labs/lab07/auth-service/Dockerfile
FROM python:3.12-slim AS builder

WORKDIR /app

RUN pip install --no-cache-dir fastapi==0.111.0 uvicorn==0.30.1 \
    "python-jose[cryptography]==3.3.0" "passlib[bcrypt]==1.7.4"

COPY main.py .

FROM python:3.12-slim

WORKDIR /app

RUN adduser --disabled-password --gecos '' appuser

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/uvicorn /usr/local/bin/uvicorn
COPY main.py .

USER appuser

EXPOSE 8001

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
```

2. Crea el Dockerfile del `inventory-service`:

```dockerfile
# ~/labs/lab07/inventory-service/Dockerfile
FROM python:3.12-slim AS builder

WORKDIR /app

RUN pip install --no-cache-dir fastapi==0.111.0 uvicorn==0.30.1 \
    "python-jose[cryptography]==3.3.0"

COPY main.py auth_middleware.py ./

FROM python:3.12-slim

WORKDIR /app

RUN adduser --disabled-password --gecos '' appuser

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/uvicorn /usr/local/bin/uvicorn
COPY main.py auth_middleware.py ./

USER appuser

EXPOSE 8002

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]
```

3. Construye las imágenes usando el contexto de Minikube:

```bash
eval $(minikube docker-env)

cd ~/labs/lab07/auth-service
docker build -t microservicios-curso/auth-service:1.0.0 .

cd ~/labs/lab07/inventory-service
docker build -t microservicios-curso/inventory-service:2.0.0 .
```

4. Verifica las imágenes:

```bash
docker images | grep microservicios-curso
```

### Salida Esperada

```
microservicios-curso/auth-service        1.0.0   abc123def456   10 seconds ago   185MB
microservicios-curso/inventory-service   2.0.0   789ghi012jkl   5 seconds ago    175MB
```

### Verificación

```bash
# Verificar que las imágenes se ejecutan correctamente
docker run --rm -d --name test-auth -p 18001:8001 microservicios-curso/auth-service:1.0.0
sleep 3
curl -s http://localhost:18001/health
docker stop test-auth
```

---

## Paso 7: Extender el Helm Chart con Secrets y Despliegue

**Objetivo:** Extender el Helm chart del lab 6 para incluir Kubernetes Secrets con certificados TLS, claves JWT y desplegar ambos servicios.

### Instrucciones

1. Crea la estructura del chart extendido:

```bash
mkdir -p ~/labs/lab07/k8s/inventory-chart/templates
cd ~/labs/lab07/k8s/inventory-chart
```

2. Crea el archivo `Chart.yaml`:

```yaml
# ~/labs/lab07/k8s/inventory-chart/Chart.yaml
apiVersion: v2
name: inventory-chart
description: Helm chart para auth-service e inventory-service con JWT y mTLS
type: application
version: 2.0.0
appVersion: "2.0.0"
```

3. Crea el archivo `values.yaml`:

```yaml
# ~/labs/lab07/k8s/inventory-chart/values.yaml
namespace: microservices

authService:
  name: auth-service
  replicas: 1
  image: microservicios-curso/auth-service:1.0.0
  imagePullPolicy: Never
  port: 8001
  resources:
    requests:
      memory: "128Mi"
      cpu: "100m"
    limits:
      memory: "256Mi"
      cpu: "250m"

inventoryService:
  name: inventory-service
  replicas: 1
  image: microservicios-curso/inventory-service:2.0.0
  imagePullPolicy: Never
  port: 8002
  resources:
    requests:
      memory: "128Mi"
      cpu: "100m"
    limits:
      memory: "256Mi"
      cpu: "250m"

jwt:
  algorithm: RS256
  expirationMinutes: 30
```

4. Crea el Secret para las claves JWT (`templates/jwt-secret.yaml`):

```yaml
# ~/labs/lab07/k8s/inventory-chart/templates/jwt-secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: jwt-keys
  namespace: {{ .Values.namespace }}
type: Opaque
data:
  jwt_private.pem: {{ .Files.Get "certs/jwt_private.pem" | b64enc }}
  jwt_public.pem: {{ .Files.Get "certs/jwt_public.pem" | b64enc }}
```

5. Crea el Secret TLS para auth-service (`templates/auth-tls-secret.yaml`):

```yaml
# ~/labs/lab07/k8s/inventory-chart/templates/auth-tls-secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: auth-service-tls
  namespace: {{ .Values.namespace }}
type: kubernetes.io/tls
data:
  tls.crt: {{ .Files.Get "certs/auth-service.crt" | b64enc }}
  tls.key: {{ .Files.Get "certs/auth-service.key" | b64enc }}
  ca.crt: {{ .Files.Get "certs/ca.crt" | b64enc }}
```

6. Crea el Secret TLS para inventory-service (`templates/inventory-tls-secret.yaml`):

```yaml
# ~/labs/lab07/k8s/inventory-chart/templates/inventory-tls-secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: inventory-service-tls
  namespace: {{ .Values.namespace }}
type: kubernetes.io/tls
data:
  tls.crt: {{ .Files.Get "certs/inventory-service.crt" | b64enc }}
  tls.key: {{ .Files.Get "certs/inventory-service.key" | b64enc }}
  ca.crt: {{ .Files.Get "certs/ca.crt" | b64enc }}
```

7. Crea el Deployment del auth-service (`templates/auth-deployment.yaml`):

```yaml
# ~/labs/lab07/k8s/inventory-chart/templates/auth-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ .Values.authService.name }}
  namespace: {{ .Values.namespace }}
  labels:
    app: {{ .Values.authService.name }}
spec:
  replicas: {{ .Values.authService.replicas }}
  selector:
    matchLabels:
      app: {{ .Values.authService.name }}
  template:
    metadata:
      labels:
        app: {{ .Values.authService.name }}
    spec:
      containers:
        - name: {{ .Values.authService.name }}
          image: {{ .Values.authService.image }}
          imagePullPolicy: {{ .Values.authService.imagePullPolicy }}
          ports:
            - containerPort: {{ .Values.authService.port }}
          env:
            - name: JWT_ALGORITHM
              value: {{ .Values.jwt.algorithm }}
            - name: JWT_EXPIRATION_MINUTES
              value: "{{ .Values.jwt.expirationMinutes }}"
          volumeMounts:
            - name: jwt-keys
              mountPath: /app/certs
              readOnly: true
            - name: tls-certs
              mountPath: /app/tls
              readOnly: true
          resources:
            requests:
              memory: {{ .Values.authService.resources.requests.memory }}
              cpu: {{ .Values.authService.resources.requests.cpu }}
            limits:
              memory: {{ .Values.authService.resources.limits.memory }}
              cpu: {{ .Values.authService.resources.limits.cpu }}
          livenessProbe:
            httpGet:
              path: /health
              port: {{ .Values.authService.port }}
            initialDelaySeconds: 10
            periodSeconds: 30
          readinessProbe:
            httpGet:
              path: /health
              port: {{ .Values.authService.port }}
            initialDelaySeconds: 5
            periodSeconds: 10
      volumes:
        - name: jwt-keys
          secret:
            secretName: jwt-keys
        - name: tls-certs
          secret:
            secretName: auth-service-tls
```

8. Crea el Deployment del inventory-service (`templates/inventory-deployment.yaml`):

```yaml
# ~/labs/lab07/k8s/inventory-chart/templates/inventory-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ .Values.inventoryService.name }}
  namespace: {{ .Values.namespace }}
  labels:
    app: {{ .Values.inventoryService.name }}
spec:
  replicas: {{ .Values.inventoryService.replicas }}
  selector:
    matchLabels:
      app: {{ .Values.inventoryService.name }}
  template:
    metadata:
      labels:
        app: {{ .Values.inventoryService.name }}
    spec:
      containers:
        - name: {{ .Values.inventoryService.name }}
          image: {{ .Values.inventoryService.image }}
          imagePullPolicy: {{ .Values.inventoryService.imagePullPolicy }}
          ports:
            - containerPort: {{ .Values.inventoryService.port }}
          volumeMounts:
            - name: jwt-public-key
              mountPath: /app/certs
              readOnly: true
            - name: tls-certs
              mountPath: /app/tls
              readOnly: true
          resources:
            requests:
              memory: {{ .Values.inventoryService.resources.requests.memory }}
              cpu: {{ .Values.inventoryService.resources.requests.cpu }}
            limits:
              memory: {{ .Values.inventoryService.resources.limits.memory }}
              cpu: {{ .Values.inventoryService.resources.limits.cpu }}
          livenessProbe:
            httpGet:
              path: /health
              port: {{ .Values.inventoryService.port }}
            initialDelaySeconds: 10
            periodSeconds: 30
          readinessProbe:
            httpGet:
              path: /health
              port: {{ .Values.inventoryService.port }}
            initialDelaySeconds: 5
            periodSeconds: 10
      volumes:
        - name: jwt-public-key
          secret:
            secretName: jwt-keys
            items:
              - key: jwt_public.pem
                path: jwt_public.pem
        - name: tls-certs
          secret:
            secretName: inventory-service-tls
```

9. Crea los Services (`templates/services.yaml`):

```yaml
# ~/labs/lab07/k8s/inventory-chart/templates/services.yaml
apiVersion: v1
kind: Service
metadata:
  name: {{ .Values.authService.name }}
  namespace: {{ .Values.namespace }}
spec:
  selector:
    app: {{ .Values.authService.name }}
  ports:
    - protocol: TCP
      port: {{ .Values.authService.port }}
      targetPort: {{ .Values.authService.port }}
  type: ClusterIP
---
apiVersion: v1
kind: Service
metadata:
  name: {{ .Values.inventoryService.name }}
  namespace: {{ .Values.namespace }}
spec:
  selector:
    app: {{ .Values.inventoryService.name }}
  ports:
    - protocol: TCP
      port: {{ .Values.inventoryService.port }}
      targetPort: {{ .Values.inventoryService.port }}
      nodePort: 30082
  type: NodePort
```

10. Copia los certificados al chart y despliega:

```bash
# Copiar certificados al chart para que Helm pueda acceder a ellos
cp -r ~/labs/lab07/certs ~/labs/lab07/k8s/inventory-chart/

# Crear namespace si no existe
kubectl create namespace microservices --dry-run=client -o yaml | kubectl apply -f -

# Desplegar con Helm
cd ~/labs/lab07/k8s
helm upgrade --install inventory-secure ./inventory-chart \
  --namespace microservices
```

### Salida Esperada

```
Release "inventory-secure" does not exist. Installing it now.
NAME: inventory-secure
LAST DEPLOYED: ...
NAMESPACE: microservices
STATUS: deployed
REVISION: 1
```

### Verificación

```bash
# Verificar que los pods están corriendo
kubectl get pods -n microservices
# Ambos pods deben estar en estado Running

# Verificar los secrets creados
kubectl get secrets -n microservices
# Deben aparecer: jwt-keys, auth-service-tls, inventory-service-tls

# Verificar los services
kubectl get svc -n microservices
```

---

## Paso 8: Pruebas de Integración End-to-End en Kubernetes

**Objetivo:** Validar el flujo completo de autenticación y autorización dentro del clúster Kubernetes.

### Instrucciones

1. Espera a que los pods estén listos:

```bash
kubectl wait --for=condition=ready pod -l app=auth-service \
  -n microservices --timeout=60s
kubectl wait --for=condition=ready pod -l app=inventory-service \
  -n microservices --timeout=60s
```

2. Configura port-forward para acceder a los servicios:

```bash
# Port-forward al auth-service
kubectl port-forward svc/auth-service 8001:8001 -n microservices &
PF_AUTH=$!
sleep 2

# Port-forward al inventory-service
kubectl port-forward svc/inventory-service 8002:8002 -n microservices &
PF_INV=$!
sleep 2
```

3. Ejecuta las pruebas de integración. Crea el archivo de pruebas:

```python
# ~/labs/lab07/test_integration.py
import httpx
import pytest
import time

AUTH_URL = "http://localhost:8001"
INV_URL = "http://localhost:8002"

class TestAuthService:
    """Pruebas del servicio de autenticación."""

    def test_health(self):
        r = httpx.get(f"{AUTH_URL}/health")
        assert r.status_code == 200
        assert r.json()["service"] == "auth-service"

    def test_login_valid_credentials(self):
        r = httpx.post(
            f"{AUTH_URL}/token",
            data={"username": "admin", "password": "admin-secret-2024"},
        )
        assert r.status_code == 200
        body = r.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"

    def test_login_invalid_credentials(self):
        r = httpx.post(
            f"{AUTH_URL}/token",
            data={"username": "admin", "password": "wrong"},
        )
        assert r.status_code == 401

    def test_validate_valid_token(self):
        # Obtener token
        r = httpx.post(
            f"{AUTH_URL}/token",
            data={"username": "admin", "password": "admin-secret-2024"},
        )
        token = r.json()["access_token"]

        # Validar token
        r = httpx.get(
            f"{AUTH_URL}/validate",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["valid"] is True
        assert body["sub"] == "admin"
        assert "admin" in body["roles"]


class TestInventoryServiceAuth:
    """Pruebas de autenticación en el inventory-service."""

    def _get_token(self, username: str, password: str) -> str:
        r = httpx.post(
            f"{AUTH_URL}/token",
            data={"username": username, "password": password},
        )
        return r.json()["access_token"]

    def test_health_no_auth_required(self):
        r = httpx.get(f"{INV_URL}/health")
        assert r.status_code == 200

    def test_inventory_without_token_returns_401(self):
        r = httpx.get(f"{INV_URL}/inventory")
        assert r.status_code == 401

    def test_inventory_with_valid_token(self):
        token = self._get_token("admin", "admin-secret-2024")
        r = httpx.get(
            f"{INV_URL}/inventory",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        assert "items" in r.json()

    def test_inventory_reader_can_list(self):
        token = self._get_token("viewer", "viewer-secret-2024")
        r = httpx.get(
            f"{INV_URL}/inventory",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200

    def test_create_item_requires_admin(self):
        # viewer no debe poder crear
        token = self._get_token("viewer", "viewer-secret-2024")
        r = httpx.post(
            f"{INV_URL}/inventory",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": "Test", "quantity": 1, "category": "test"},
        )
        assert r.status_code == 403

    def test_create_item_admin_succeeds(self):
        token = self._get_token("admin", "admin-secret-2024")
        r = httpx.post(
            f"{INV_URL}/inventory",
            headers={"Authorization": f"Bearer {token}"},
            json={"name": "New Item", "quantity": 10, "category": "test"},
        )
        assert r.status_code == 201
        assert r.json()["created_by"] == "admin"

    def test_expired_token_returns_401(self):
        # Usar un token manualmente expirado (simulado con jose)
        from jose import jwt
        from datetime import datetime, timedelta, timezone
        from pathlib import Path

        private_key = (Path.home() / "labs/lab07/certs/jwt_private.pem").read_text()
        expired_token = jwt.encode(
            {
                "sub": "admin",
                "roles": ["admin"],
                "exp": datetime.now(timezone.utc) - timedelta(hours=1),
            },
            private_key,
            algorithm="RS256",
        )
        r = httpx.get(
            f"{INV_URL}/inventory",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert r.status_code == 401
        assert "expirado" in r.json()["detail"].lower() or "expired" in r.json()["detail"].lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

4. Ejecuta las pruebas:

```bash
cd ~/labs/lab07
source venv/bin/activate
pytest test_integration.py -v
```

5. Limpia los port-forwards:

```bash
kill $PF_AUTH $PF_INV 2>/dev/null
```

### Salida Esperada

```
test_integration.py::TestAuthService::test_health PASSED
test_integration.py::TestAuthService::test_login_valid_credentials PASSED
test_integration.py::TestAuthService::test_login_invalid_credentials PASSED
test_integration.py::TestAuthService::test_validate_valid_token PASSED
test_integration.py::TestInventoryServiceAuth::test_health_no_auth_required PASSED
test_integration.py::TestInventoryServiceAuth::test_inventory_without_token_returns_401 PASSED
test_integration.py::TestInventoryServiceAuth::test_inventory_with_valid_token PASSED
test_integration.py::TestInventoryServiceAuth::test_inventory_reader_can_list PASSED
test_integration.py::TestInventoryServiceAuth::test_create_item_requires_admin PASSED
test_integration.py::TestInventoryServiceAuth::test_create_item_admin_succeeds PASSED
test_integration.py::TestInventoryServiceAuth::test_expired_token_returns_401 PASSED

========================= 11 passed in 4.52s =========================
```

### Verificación

```bash
# Verificar que todas las pruebas pasan
pytest test_integration.py -v --tb=short 2>&1 | tail -3
# Debe mostrar "11 passed"
```

---

## Validación y Pruebas

Ejecuta la siguiente secuencia de validación completa para confirmar que todo el laboratorio funciona correctamente:

```bash
cd ~/labs/lab07

echo "=== 1. Verificando certificados ==="
openssl verify -CAfile certs/ca.crt certs/auth-service.crt
openssl verify -CAfile certs/ca.crt certs/inventory-service.crt

echo "=== 2. Verificando claves JWT ==="
openssl rsa -in certs/jwt_private.pem -check -noout

echo "=== 3. Verificando pods en Kubernetes ==="
kubectl get pods -n microservices -o wide

echo "=== 4. Verificando secrets ==="
kubectl get secrets -n microservices | grep -E "(jwt-keys|tls)"

echo "=== 5. Verificando Helm release ==="
helm list -n microservices

echo "=== 6. Ejecutando pruebas de integración ==="
kubectl port-forward svc/auth-service 8001:8001 -n microservices &
kubectl port-forward svc/inventory-service 8002:8002 -n microservices &
sleep 3

# Test rápido del flujo completo
TOKEN=$(curl -s -X POST http://localhost:8001/token \
  -d "username=admin&password=admin-secret-2024" \
  -H "Content-Type: application/x-www-form-urlencoded" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

echo "Token (primeros 50 chars): ${TOKEN:0:50}..."

RESPONSE=$(curl -s -w "\n%{http_code}" http://localhost:8002/inventory \
  -H "Authorization: Bearer $TOKEN")
HTTP_CODE=$(echo "$RESPONSE" | tail -1)
echo "Inventory response code: $HTTP_CODE"

if [ "$HTTP_CODE" = "200" ]; then
  echo "✅ VALIDACIÓN COMPLETA: El flujo JWT + autorización funciona correctamente"
else
  echo "❌ ERROR: Respuesta inesperada ($HTTP_CODE)"
fi

# Limpiar port-forwards
kill %1 %2 2>/dev/null
```

**Criterios de éxito:**
- Los certificados verifican correctamente contra la CA
- Ambos pods están en estado `Running`
- Los 3 secrets existen en el namespace `microservices`
- El Helm release está en estado `deployed`
- El flujo completo (login → token → acceso protegido) retorna HTTP 200

---

## Resolución de Problemas

### Problema 1: Pod del auth-service en CrashLoopBackOff por ruta de claves

**Síntomas:** El pod `auth-service` reinicia continuamente. Los logs muestran:

```
FileNotFoundError: [Errno 2] No such file or directory: '/app/certs/jwt_private.pem'
```

**Causa:** El código del `auth-service` dentro del contenedor intenta leer las claves JWT desde una ruta relativa (`../certs/`) que no coincide con el `mountPath` definido en el Deployment (`/app/certs`).

**Solución:** Modifica el `main.py` del `auth-service` para leer las claves desde la ruta del volumen montado en Kubernetes. Usa una variable de entorno para hacer la ruta configurable:

```python
import os
from pathlib import Path

# Usar variable de entorno o ruta por defecto
CERTS_DIR = Path(os.getenv("CERTS_PATH", "/app/certs"))
PRIVATE_KEY = (CERTS_DIR / "jwt_private.pem").read_text()
PUBLIC_KEY = (CERTS_DIR / "jwt_public.pem").read_text()
```

Añade la variable de entorno en el Deployment:

```yaml
env:
  - name: CERTS_PATH
    value: "/app/certs"
```

Reconstruye la imagen y actualiza el Helm release:

```bash
docker build -t microservicios-curso/auth-service:1.0.0 .
helm upgrade inventory-secure ./inventory-chart -n microservices
```

---

### Problema 2: Error 401 al validar token entre servicios por desincronización de claves

**Síntomas:** El `auth-service` emite tokens correctamente, pero el `inventory-service` rechaza todos los tokens con el error:

```json
{"detail": "Token inválido: Signature verification failed."}
```

**Causa:** El Secret `jwt-keys` fue actualizado (por ejemplo, se regeneraron las claves) pero solo se actualizó el pod del `auth-service`. El `inventory-service` todavía tiene montada la clave pública anterior en su volumen.

**Solución:** Reinicia ambos deployments para que monten los secrets actualizados:

```bash
# Verificar que el secret contiene la clave correcta
kubectl get secret jwt-keys -n microservices -o jsonpath='{.data.jwt_public\.pem}' | base64 -d | head -2

# Reiniciar ambos pods para recargar los volúmenes
kubectl rollout restart deployment auth-service -n microservices
kubectl rollout restart deployment inventory-service -n microservices

# Esperar a que los pods estén listos
kubectl rollout status deployment auth-service -n microservices
kubectl rollout status deployment inventory-service -n microservices
```

Si el problema persiste, regenera el secret desde los archivos actuales:

```bash
kubectl delete secret jwt-keys -n microservices
helm upgrade inventory-secure ./inventory-chart -n microservices
```

---

## Limpieza

```bash
# Desinstalar el Helm release
helm uninstall inventory-secure -n microservices

# Verificar que los recursos fueron eliminados
kubectl get all -n microservices

# Eliminar secrets residuales
kubectl delete secret jwt-keys auth-service-tls inventory-service-tls \
  -n microservices --ignore-not-found

# Eliminar imágenes Docker del contexto de Minikube
eval $(minikube docker-env)
docker rmi microservicios-curso/auth-service:1.0.0 2>/dev/null
docker rmi microservicios-curso/inventory-service:2.0.0 2>/dev/null

# Restaurar contexto Docker local
eval $(minikube docker-env -u)

# Desactivar entorno virtual
deactivate

# (Opcional) Eliminar directorio del lab
# rm -rf ~/labs/lab07
```

---

## Resumen

En esta práctica has implementado una capa de seguridad completa para microservicios:

| Componente | Logro |
|------------|-------|
| **Claves RSA-2048** | Par asimétrico generado con OpenSSL para firma JWT |
| **CA + Certificados TLS** | Infraestructura PKI completa con CA autofirmada y certificados por servicio |
| **Auth-Service** | Microservicio FastAPI que autentica con bcrypt y emite JWT RS256 |
| **Middleware JWT** | Validación de firma, expiración y roles en el inventory-service |
| **mTLS** | Comunicación cifrada y autenticada mutuamente entre servicios |
| **Helm Chart** | Despliegue automatizado con Secrets TLS y Opaque en Kubernetes |
| **Pruebas E2E** | 11 pruebas de integración cubriendo flujos válidos e inválidos |

### Conceptos Clave Reforzados

- **RS256 vs HS256:** RS256 permite que cualquier servicio valide tokens con solo la clave pública, sin compartir secretos.
- **Claims JWT:** `sub`, `exp` y `roles` son verificados en cada petición para garantizar identidad, vigencia y autorización.
- **Kubernetes Secrets:** Tipo `kubernetes.io/tls` para certificados y tipo `Opaque` para claves JWT, montados como volúmenes de solo lectura.
- **Principio de mínimo privilegio:** El `inventory-service` solo tiene acceso a la clave pública (no puede emitir tokens).

### Recursos Adicionales

- [RFC 7519 — JSON Web Token](https://datatracker.ietf.org/doc/html/rfc7519)
- [python-jose documentación](https://python-jose.readthedocs.io/en/latest/)
- [FastAPI Security — OAuth2 con JWT](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/)
- [Kubernetes TLS Secrets](https://kubernetes.io/docs/concepts/configuration/secret/#tls-secrets)
- [OpenSSL Cookbook — generación de certificados](https://www.feistyduck.com/library/openssl-cookbook/)

### Commit Final

```bash
cd ~/microservicios-curso
cp -r ~/labs/lab07 ./lab07
git add lab07/
git commit -m "[lab07] Implementar autenticación JWT RS256 y mTLS entre servicios"
```
