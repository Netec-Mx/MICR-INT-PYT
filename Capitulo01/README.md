# Análisis de un Monolito y Propuesta de Servicios

## Metadata

| Campo | Valor |
|-------|-------|
| **Duración** | 39 minutos |
| **Complejidad** | Fácil |
| **Nivel Bloom** | Crear |

## Descripción General

En esta práctica inicial analizarás una aplicación monolítica Python (Flask + SQLite) que gestiona una tienda en línea con módulos de usuarios, productos, pedidos e inventario. A partir de ese análisis, aplicarás principios de descomposición (bounded contexts, cohesión alta, acoplamiento bajo) para proponer una arquitectura de microservicios documentada en un archivo `PROPUESTA.md`. Este documento será la referencia de diseño para todas las prácticas siguientes del curso.

## Objetivos de Aprendizaje

- [ ] Identificar las características estructurales y los problemas de escalabilidad de una aplicación monolítica Python
- [ ] Aplicar los principios de bounded contexts y separación de responsabilidades para proponer una descomposición en al menos 4 microservicios
- [ ] Documentar los contratos de comunicación entre los servicios propuestos mediante especificaciones escritas en Markdown
- [ ] Evaluar las ventajas y compromisos (trade-offs) de la arquitectura de microservicios frente al monolito analizado

## Prerrequisitos

### Conocimientos Requeridos

| Conocimiento | Nivel |
|---|---|
| Python 3.x y programación orientada a objetos | Básico |
| HTTP/REST: verbos, recursos, códigos de estado | Básico |
| Bases de datos relacionales y SQL | Básico |
| Git: init, add, commit, branch | Básico |
| Markdown: sintaxis básica | Básico |

### Acceso y Herramientas

| Herramienta | Versión |
|---|---|
| Python | 3.12.3 |
| Git | 2.45.1 |
| Editor de texto/código | VS Code, Vim o similar |
| Terminal | Bash/Zsh |

## Entorno del Laboratorio

### Estructura de Directorios Objetivo

```
~/microservicios-curso/
├── lab01/
│   ├── monolito/
│   │   ├── app.py
│   │   ├── models.py
│   │   ├── database.py
│   │   ├── requirements.txt
│   │   └── tienda.db
│   ├── PROPUESTA.md
│   └── diagrama-componentes.md
└── .gitignore
```

### Configuración Inicial del Entorno

Ejecuta los siguientes comandos para preparar el directorio de trabajo:

```bash
mkdir -p ~/microservicios-curso/lab01/monolito
cd ~/microservicios-curso
```

---

## Paso 1: Inicializar el Repositorio Git del Curso

**Objetivo:** Crear el repositorio Git que se usará durante todo el curso, con la rama principal `main` y un `.gitignore` adecuado.

### Instrucciones

1. Navega al directorio raíz del curso:

```bash
cd ~/microservicios-curso
```

2. Inicializa el repositorio Git con rama `main`:

```bash
git init -b main
```

3. Crea el archivo `.gitignore` con exclusiones relevantes:

```bash
cat > .gitignore << 'EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
*.egg-info/
dist/
venv/
.env

# Base de datos
*.db

# Secretos Kubernetes
secret.yaml
*-secret.yaml

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db
EOF
```

4. Realiza el commit inicial:

```bash
git add .gitignore
git commit -m "[lab01] Inicializar repositorio del curso con .gitignore"
```

### Salida Esperada

```
Initialized empty Git repository in /home/<usuario>/microservicios-curso/.git/
[main (root-commit) <hash>] [lab01] Inicializar repositorio del curso con .gitignore
 1 file changed, 20 insertions(+)
 create mode 100644 .gitignore
```

### Verificación

```bash
git log --oneline
git branch
```

Debes ver un commit en la rama `main`.

---

## Paso 2: Crear el Código Fuente del Monolito

**Objetivo:** Escribir la aplicación monolítica Flask que simula una tienda en línea con cuatro módulos acoplados (usuarios, productos, pedidos, inventario) para su posterior análisis.

### Instrucciones

1. Crea el archivo de dependencias:

```bash
cat > ~/microservicios-curso/lab01/monolito/requirements.txt << 'EOF'
Flask==3.0.3
EOF
```

2. Crea el módulo de base de datos (`database.py`):

```bash
cat > ~/microservicios-curso/lab01/monolito/database.py << 'EOF'
# database.py - Módulo de acceso a datos (compartido por TODOS los módulos)
# PROBLEMA: Una sola conexión y esquema compartido genera acoplamiento fuerte

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "tienda.db")

def get_connection():
    """Conexión compartida por todos los módulos del monolito."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    """Inicializa TODAS las tablas en una sola base de datos."""
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            rol TEXT DEFAULT 'cliente',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            descripcion TEXT,
            precio REAL NOT NULL,
            categoria TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS inventario (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            producto_id INTEGER NOT NULL,
            cantidad INTEGER NOT NULL DEFAULT 0,
            ubicacion_almacen TEXT DEFAULT 'principal',
            ultima_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (producto_id) REFERENCES productos(id)
        );

        CREATE TABLE IF NOT EXISTS pedidos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER NOT NULL,
            estado TEXT DEFAULT 'pendiente',
            total REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
        );

        CREATE TABLE IF NOT EXISTS detalle_pedidos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pedido_id INTEGER NOT NULL,
            producto_id INTEGER NOT NULL,
            cantidad INTEGER NOT NULL,
            precio_unitario REAL NOT NULL,
            FOREIGN KEY (pedido_id) REFERENCES pedidos(id),
            FOREIGN KEY (producto_id) REFERENCES productos(id)
        );
    """)
    conn.close()
EOF
```

3. Crea el módulo de modelos (`models.py`):

```bash
cat > ~/microservicios-curso/lab01/monolito/models.py << 'EOF'
# models.py - Lógica de negocio de TODOS los dominios mezclada en un solo archivo
# PROBLEMA: Alta cohesión interna inexistente; responsabilidades cruzadas

from database import get_connection

# ============================================================
# MÓDULO DE USUARIOS
# ============================================================
def crear_usuario(nombre, email, password_hash, rol="cliente"):
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO usuarios (nombre, email, password_hash, rol) VALUES (?, ?, ?, ?)",
        (nombre, email, password_hash, rol)
    )
    conn.commit()
    usuario_id = cursor.lastrowid
    conn.close()
    return usuario_id

def obtener_usuario(usuario_id):
    conn = get_connection()
    usuario = conn.execute(
        "SELECT * FROM usuarios WHERE id = ?", (usuario_id,)
    ).fetchone()
    conn.close()
    return dict(usuario) if usuario else None

def listar_usuarios():
    conn = get_connection()
    usuarios = conn.execute("SELECT id, nombre, email, rol FROM usuarios").fetchall()
    conn.close()
    return [dict(u) for u in usuarios]

# ============================================================
# MÓDULO DE PRODUCTOS
# ============================================================
def crear_producto(nombre, descripcion, precio, categoria):
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO productos (nombre, descripcion, precio, categoria) VALUES (?, ?, ?, ?)",
        (nombre, descripcion, precio, categoria)
    )
    conn.commit()
    producto_id = cursor.lastrowid
    # PROBLEMA: Lógica de inventario acoplada directamente al crear producto
    conn.execute(
        "INSERT INTO inventario (producto_id, cantidad) VALUES (?, 0)",
        (producto_id,)
    )
    conn.commit()
    conn.close()
    return producto_id

def obtener_producto(producto_id):
    conn = get_connection()
    producto = conn.execute(
        "SELECT * FROM productos WHERE id = ?", (producto_id,)
    ).fetchone()
    conn.close()
    return dict(producto) if producto else None

def listar_productos():
    conn = get_connection()
    productos = conn.execute("SELECT * FROM productos").fetchall()
    conn.close()
    return [dict(p) for p in productos]

# ============================================================
# MÓDULO DE INVENTARIO
# ============================================================
def actualizar_stock(producto_id, cantidad):
    conn = get_connection()
    conn.execute(
        "UPDATE inventario SET cantidad = cantidad + ?, ultima_actualizacion = CURRENT_TIMESTAMP WHERE producto_id = ?",
        (cantidad, producto_id)
    )
    conn.commit()
    conn.close()

def obtener_stock(producto_id):
    conn = get_connection()
    inv = conn.execute(
        "SELECT cantidad, ubicacion_almacen FROM inventario WHERE producto_id = ?",
        (producto_id,)
    ).fetchone()
    conn.close()
    return dict(inv) if inv else None

def verificar_disponibilidad(producto_id, cantidad_requerida):
    stock = obtener_stock(producto_id)
    if stock is None:
        return False
    return stock["cantidad"] >= cantidad_requerida

# ============================================================
# MÓDULO DE PEDIDOS (depende de usuarios, productos e inventario)
# ============================================================
def crear_pedido(usuario_id, items):
    """
    items: lista de dicts con {producto_id, cantidad}
    PROBLEMA: Esta función mezcla validación de usuario, verificación de
    inventario, cálculo de precios y creación de pedido en una sola transacción.
    """
    # Verificar que el usuario existe
    usuario = obtener_usuario(usuario_id)
    if not usuario:
        raise ValueError(f"Usuario {usuario_id} no encontrado")

    conn = get_connection()
    total = 0

    # Verificar stock y calcular total (acoplamiento con inventario y productos)
    for item in items:
        producto = obtener_producto(item["producto_id"])
        if not producto:
            conn.close()
            raise ValueError(f"Producto {item['producto_id']} no encontrado")

        if not verificar_disponibilidad(item["producto_id"], item["cantidad"]):
            conn.close()
            raise ValueError(
                f"Stock insuficiente para producto {item['producto_id']}"
            )
        total += producto["precio"] * item["cantidad"]

    # Crear pedido
    cursor = conn.execute(
        "INSERT INTO pedidos (usuario_id, total, estado) VALUES (?, ?, 'confirmado')",
        (usuario_id, total)
    )
    pedido_id = cursor.lastrowid

    # Crear detalle y descontar inventario
    for item in items:
        producto = obtener_producto(item["producto_id"])
        conn.execute(
            "INSERT INTO detalle_pedidos (pedido_id, producto_id, cantidad, precio_unitario) VALUES (?, ?, ?, ?)",
            (pedido_id, item["producto_id"], item["cantidad"], producto["precio"])
        )
        # Descuento directo de inventario (acoplamiento fuerte)
        actualizar_stock(item["producto_id"], -item["cantidad"])

    conn.commit()
    conn.close()
    return {"pedido_id": pedido_id, "total": total, "estado": "confirmado"}

def obtener_pedido(pedido_id):
    conn = get_connection()
    pedido = conn.execute(
        "SELECT * FROM pedidos WHERE id = ?", (pedido_id,)
    ).fetchone()
    if not pedido:
        conn.close()
        return None
    detalles = conn.execute(
        "SELECT * FROM detalle_pedidos WHERE pedido_id = ?", (pedido_id,)
    ).fetchall()
    conn.close()
    resultado = dict(pedido)
    resultado["items"] = [dict(d) for d in detalles]
    return resultado
EOF
```

4. Crea la aplicación principal (`app.py`):

```bash
cat > ~/microservicios-curso/lab01/monolito/app.py << 'EOF'
# app.py - Punto de entrada del monolito
# PROBLEMA: Un solo proceso sirve TODOS los dominios de negocio.
# Si el módulo de pedidos tiene alta carga, no se puede escalar
# independientemente del módulo de usuarios.

from flask import Flask, request, jsonify
from database import init_db
import models

app = Flask(__name__)

# ============================================================
# RUTAS DE USUARIOS
# ============================================================
@app.route("/usuarios", methods=["POST"])
def api_crear_usuario():
    data = request.get_json()
    try:
        usuario_id = models.crear_usuario(
            data["nombre"], data["email"], data.get("password_hash", "hash123"), data.get("rol", "cliente")
        )
        return jsonify({"id": usuario_id, "mensaje": "Usuario creado"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/usuarios", methods=["GET"])
def api_listar_usuarios():
    return jsonify(models.listar_usuarios()), 200

@app.route("/usuarios/<int:usuario_id>", methods=["GET"])
def api_obtener_usuario(usuario_id):
    usuario = models.obtener_usuario(usuario_id)
    if not usuario:
        return jsonify({"error": "Usuario no encontrado"}), 404
    return jsonify(usuario), 200

# ============================================================
# RUTAS DE PRODUCTOS
# ============================================================
@app.route("/productos", methods=["POST"])
def api_crear_producto():
    data = request.get_json()
    try:
        producto_id = models.crear_producto(
            data["nombre"], data.get("descripcion", ""), data["precio"], data.get("categoria", "general")
        )
        return jsonify({"id": producto_id, "mensaje": "Producto creado"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/productos", methods=["GET"])
def api_listar_productos():
    return jsonify(models.listar_productos()), 200

@app.route("/productos/<int:producto_id>", methods=["GET"])
def api_obtener_producto(producto_id):
    producto = models.obtener_producto(producto_id)
    if not producto:
        return jsonify({"error": "Producto no encontrado"}), 404
    return jsonify(producto), 200

# ============================================================
# RUTAS DE INVENTARIO
# ============================================================
@app.route("/inventario/<int:producto_id>", methods=["GET"])
def api_obtener_stock(producto_id):
    stock = models.obtener_stock(producto_id)
    if not stock:
        return jsonify({"error": "Producto sin inventario"}), 404
    return jsonify(stock), 200

@app.route("/inventario/<int:producto_id>", methods=["PUT"])
def api_actualizar_stock(producto_id):
    data = request.get_json()
    models.actualizar_stock(producto_id, data["cantidad"])
    return jsonify({"mensaje": "Stock actualizado"}), 200

# ============================================================
# RUTAS DE PEDIDOS
# ============================================================
@app.route("/pedidos", methods=["POST"])
def api_crear_pedido():
    data = request.get_json()
    try:
        resultado = models.crear_pedido(data["usuario_id"], data["items"])
        return jsonify(resultado), 201
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

@app.route("/pedidos/<int:pedido_id>", methods=["GET"])
def api_obtener_pedido(pedido_id):
    pedido = models.obtener_pedido(pedido_id)
    if not pedido:
        return jsonify({"error": "Pedido no encontrado"}), 404
    return jsonify(pedido), 200

# ============================================================
# INICIALIZACIÓN
# ============================================================
if __name__ == "__main__":
    init_db()
    # PROBLEMA: Un solo puerto, un solo proceso para todo
    app.run(host="0.0.0.0", port=5000, debug=True)
EOF
```

### Salida Esperada

Tras ejecutar `ls ~/microservicios-curso/lab01/monolito/`:

```
app.py  database.py  models.py  requirements.txt
```

### Verificación

```bash
cd ~/microservicios-curso/lab01/monolito
python3 -c "import ast; ast.parse(open('app.py').read()); print('app.py: sintaxis válida')"
python3 -c "import ast; ast.parse(open('models.py').read()); print('models.py: sintaxis válida')"
python3 -c "import ast; ast.parse(open('database.py').read()); print('database.py: sintaxis válida')"
```

Cada comando debe imprimir "sintaxis válida" sin errores.

---

## Paso 3: Analizar el Monolito e Identificar Problemas

**Objetivo:** Leer el código fuente del monolito, identificar puntos de acoplamiento, responsabilidades mezcladas y cuellos de botella, y documentar los hallazgos.

### Instrucciones

1. Revisa el código de cada archivo prestando atención a los comentarios `# PROBLEMA:` que señalan antipatrones. Ejecuta el siguiente comando para listarlos rápidamente:

```bash
cd ~/microservicios-curso/lab01/monolito
grep -n "PROBLEMA" *.py
```

2. Identifica los siguientes problemas estructurales (mínimo):

| # | Problema | Archivo | Línea/Zona |
|---|----------|---------|------------|
| 1 | Base de datos única compartida por todos los dominios | `database.py` | `init_db()` |
| 2 | Lógica de inventario acoplada a la creación de productos | `models.py` | `crear_producto()` |
| 3 | Función `crear_pedido()` depende de usuarios, productos e inventario | `models.py` | `crear_pedido()` |
| 4 | Un solo proceso/puerto sirve todos los dominios | `app.py` | `app.run()` |
| 5 | No es posible escalar un módulo sin escalar todo el monolito | `app.py` | Arquitectura general |

3. Documenta el diagrama de componentes actual del monolito. Crea el archivo:

```bash
cat > ~/microservicios-curso/lab01/diagrama-componentes.md << 'EOF'
# Diagrama de Componentes - Monolito Tienda en Línea

## Arquitectura Actual (Monolito)

```
┌─────────────────────────────────────────────────────────┐
│                    app.py (Flask)                        │
│                    Puerto: 5000                          │
│                                                         │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐  │
│  │ Rutas    │ │ Rutas    │ │ Rutas    │ │ Rutas     │  │
│  │ Usuarios │ │ Productos│ │ Inventario│ │ Pedidos   │  │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └─────┬─────┘  │
│       │             │            │              │        │
│  ┌────▼─────────────▼────────────▼──────────────▼─────┐  │
│  │              models.py                             │  │
│  │  (Toda la lógica de negocio en un solo archivo)    │  │
│  └────────────────────────┬───────────────────────────┘  │
│                           │                              │
│  ┌────────────────────────▼───────────────────────────┐  │
│  │            database.py (SQLite)                    │  │
│  │  Conexión compartida - Una sola BD: tienda.db      │  │
│  └────────────────────────────────────────────────────┘  │
│                                                         │
└─────────────────────────────────────────────────────────┘
                           │
                    ┌──────▼──────┐
                    │  tienda.db  │
                    │  (SQLite)   │
                    │             │
                    │ - usuarios  │
                    │ - productos │
                    │ - inventario│
                    │ - pedidos   │
                    │ - detalle   │
                    └─────────────┘
```

## Problemas Identificados

1. **Acoplamiento de datos**: Todas las tablas en una sola BD con foreign keys cruzadas
2. **Acoplamiento funcional**: `crear_pedido()` invoca lógica de usuarios, productos e inventario
3. **Despliegue monolítico**: Cualquier cambio requiere redesplegar toda la aplicación
4. **Escalado uniforme**: No se puede escalar solo el módulo con mayor carga
5. **Punto único de fallo**: Si el proceso cae, toda la tienda queda inoperativa
EOF
```

### Salida Esperada

El comando `grep -n "PROBLEMA" *.py` debe mostrar al menos 5 líneas con comentarios de problema.

### Verificación

```bash
test -f ~/microservicios-curso/lab01/diagrama-componentes.md && echo "✓ Diagrama creado"
wc -l ~/microservicios-curso/lab01/diagrama-componentes.md
```

El archivo debe existir y tener más de 30 líneas.

---

## Paso 4: Proponer la Descomposición en Microservicios

**Objetivo:** Aplicar criterios de bounded contexts, cohesión alta y acoplamiento bajo para identificar al menos 4 microservicios candidatos y documentar la propuesta completa.

### Instrucciones

1. Crea el documento de propuesta `PROPUESTA.md`:

```bash
cat > ~/microservicios-curso/lab01/PROPUESTA.md << 'EOF'
# Propuesta de Descomposición en Microservicios

## 1. Resumen Ejecutivo

Se propone descomponer el monolito de la tienda en línea en **4 microservicios independientes**, cada uno con su propia base de datos y API REST bien definida. La descomposición sigue los principios de bounded contexts (DDD), responsabilidad única y autonomía de despliegue.

## 2. Criterios de Descomposición Aplicados

| Criterio | Descripción | Aplicación |
|----------|-------------|------------|
| **Bounded Context** | Cada servicio encapsula un dominio de negocio completo | Usuarios, Productos, Inventario y Pedidos son dominios independientes |
| **Cohesión alta** | Las funciones dentro de un servicio están fuertemente relacionadas | Toda la lógica de stock pertenece al servicio de inventario |
| **Acoplamiento bajo** | Los servicios se comunican solo por APIs, sin compartir BD | Cada servicio tiene su propia base de datos |
| **Autonomía de despliegue** | Un servicio puede desplegarse sin afectar a los demás | Contratos de API versionados y estables |
| **Escalado independiente** | Cada servicio escala según su propia demanda | Pedidos puede tener más réplicas que Usuarios |

## 3. Microservicios Propuestos

### 3.1 Servicio de Usuarios (`users-service`)

- **Responsabilidad**: Gestión de cuentas de usuario, autenticación y perfiles
- **Base de datos propia**: PostgreSQL (tabla `usuarios`)
- **Puerto asignado**: 8001

#### API Propuesta

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/api/v1/users` | Crear usuario |
| GET | `/api/v1/users` | Listar usuarios |
| GET | `/api/v1/users/{id}` | Obtener usuario por ID |
| PUT | `/api/v1/users/{id}` | Actualizar usuario |
| DELETE | `/api/v1/users/{id}` | Eliminar usuario |
| POST | `/api/v1/users/login` | Autenticar usuario |

#### Ejemplo de contrato (respuesta)

```json
{
  "id": 1,
  "nombre": "Juan Pérez",
  "email": "juan@ejemplo.com",
  "rol": "cliente",
  "created_at": "2024-01-15T10:30:00Z"
}
```

---

### 3.2 Servicio de Productos (`products-service`)

- **Responsabilidad**: Catálogo de productos, categorías y búsqueda
- **Base de datos propia**: PostgreSQL (tabla `productos`)
- **Puerto asignado**: 8000 (puerto principal del curso)

#### API Propuesta

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/api/v1/products` | Crear producto |
| GET | `/api/v1/products` | Listar productos |
| GET | `/api/v1/products/{id}` | Obtener producto por ID |
| PUT | `/api/v1/products/{id}` | Actualizar producto |
| DELETE | `/api/v1/products/{id}` | Eliminar producto |

#### Ejemplo de contrato (respuesta)

```json
{
  "id": 1,
  "nombre": "Laptop Pro 15",
  "descripcion": "Laptop de alto rendimiento",
  "precio": 1299.99,
  "categoria": "electrónica",
  "created_at": "2024-01-15T10:30:00Z"
}
```

---

### 3.3 Servicio de Inventario (`inventory-service`)

- **Responsabilidad**: Control de stock, ubicaciones de almacén y alertas de reposición
- **Base de datos propia**: PostgreSQL (tabla `inventario`)
- **Puerto asignado**: 8002

#### API Propuesta

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| GET | `/api/v1/inventory/{product_id}` | Consultar stock de un producto |
| PUT | `/api/v1/inventory/{product_id}` | Actualizar stock |
| POST | `/api/v1/inventory/{product_id}/reserve` | Reservar unidades |
| POST | `/api/v1/inventory/{product_id}/release` | Liberar reserva |

#### Ejemplo de contrato (respuesta)

```json
{
  "product_id": 1,
  "cantidad": 50,
  "ubicacion_almacen": "principal",
  "ultima_actualizacion": "2024-01-15T14:00:00Z"
}
```

---

### 3.4 Servicio de Pedidos (`orders-service`)

- **Responsabilidad**: Creación, seguimiento y gestión del ciclo de vida de pedidos
- **Base de datos propia**: PostgreSQL (tablas `pedidos`, `detalle_pedidos`)
- **Puerto asignado**: 8003

#### API Propuesta

| Método | Endpoint | Descripción |
|--------|----------|-------------|
| POST | `/api/v1/orders` | Crear pedido |
| GET | `/api/v1/orders/{id}` | Obtener pedido |
| GET | `/api/v1/orders?user_id={id}` | Listar pedidos de un usuario |
| PUT | `/api/v1/orders/{id}/status` | Actualizar estado del pedido |

#### Ejemplo de contrato (solicitud de creación)

```json
{
  "user_id": 1,
  "items": [
    {"product_id": 1, "cantidad": 2},
    {"product_id": 3, "cantidad": 1}
  ]
}
```

---

## 4. Diagrama de Arquitectura Propuesta

```
                    ┌─────────────┐
                    │   Cliente   │
                    │  (Frontend) │
                    └──────┬──────┘
                           │ HTTP
                    ┌──────▼──────┐
                    │ API Gateway │  (futuro)
                    └──┬───┬───┬──┘
            ┌──────────┘   │   └──────────┐
            │              │              │
    ┌───────▼───────┐ ┌───▼────────┐ ┌───▼──────────┐
    │ users-service │ │  products- │ │   orders-    │
    │   :8001       │ │  service   │ │   service    │
    │               │ │  :8000     │ │   :8003      │
    └───────┬───────┘ └───┬────────┘ └───┬───┬──────┘
            │             │              │   │
    ┌───────▼───┐  ┌──────▼───┐         │   │
    │ Users DB  │  │Products  │         │   │
    │(PostgreSQL)│  │DB        │         │   │
    └───────────┘  └──────────┘         │   │
                                        │   │
                              ┌─────────▼───▼────────┐
                              │  inventory-service   │
                              │       :8002          │
                              └──────────┬───────────┘
                                         │
                              ┌───────────▼──────────┐
                              │   Inventory DB       │
                              │   (PostgreSQL)       │
                              └──────────────────────┘

    Comunicación entre servicios: HTTP REST síncrono
    Patrón futuro: eventos asíncronos para notificaciones
```

## 5. Comunicación Entre Servicios

| Origen | Destino | Tipo | Propósito |
|--------|---------|------|-----------|
| orders-service | users-service | HTTP GET | Validar existencia del usuario |
| orders-service | products-service | HTTP GET | Obtener precio actual del producto |
| orders-service | inventory-service | HTTP POST | Reservar stock al crear pedido |
| inventory-service | products-service | HTTP GET | Validar que el producto existe |

## 6. Ventajas de la Arquitectura Propuesta

1. **Escalado independiente**: El servicio de pedidos (mayor carga en Black Friday) puede escalar sin afectar al catálogo
2. **Despliegue autónomo**: El equipo de inventario puede actualizar su lógica sin coordinar con otros equipos
3. **Aislamiento de fallos**: Si el servicio de usuarios cae, el catálogo de productos sigue disponible
4. **Flexibilidad tecnológica**: Cada servicio puede elegir la tecnología más adecuada (FastAPI para todos inicialmente)
5. **Equipos independientes**: Cada servicio puede ser mantenido por un equipo pequeño y autónomo (Ley de Conway)

## 7. Trade-offs y Compromisos

| Aspecto | Ventaja | Compromiso |
|---------|---------|------------|
| Complejidad operativa | Servicios simples individualmente | Necesidad de orquestación (Kubernetes), observabilidad y service mesh |
| Consistencia de datos | Cada servicio controla su BD | Consistencia eventual entre servicios; no hay transacciones ACID distribuidas simples |
| Latencia | Escalado preciso | Llamadas de red entre servicios añaden latencia |
| Depuración | Código más pequeño y enfocado | Trazabilidad distribuida requiere herramientas (Jaeger) |
| Infraestructura | Despliegue granular | Más contenedores, más configuración, más monitorización |

## 8. Plan de Migración (Referencia para el Curso)

1. **Práctica 02**: Implementar `products-service` con FastAPI (primer microservicio)
2. **Práctica 03**: Contenerizar con Docker
3. **Práctica 04**: Añadir caching con Redis
4. **Práctica 05**: Desplegar en Kubernetes con almacenamiento persistente
5. **Práctica 06**: Instrumentar con Prometheus, Grafana y Jaeger
EOF
```

### Salida Esperada

```bash
wc -l ~/microservicios-curso/lab01/PROPUESTA.md
```

Debe mostrar aproximadamente 180-200 líneas.

### Verificación

```bash
# Verificar que contiene al menos 4 servicios propuestos
grep -c "### 3\." ~/microservicios-curso/lab01/PROPUESTA.md
```

El resultado debe ser `4` o mayor.

---

## Paso 5: Confirmar los Artefactos y Realizar el Commit Final

**Objetivo:** Agregar todos los archivos generados al repositorio Git y crear un commit descriptivo que cierre la práctica.

### Instrucciones

1. Navega al directorio raíz del curso:

```bash
cd ~/microservicios-curso
```

2. Verifica el estado del repositorio:

```bash
git status
```

3. Agrega todos los archivos del laboratorio (nota: `tienda.db` está en `.gitignore`):

```bash
git add lab01/
```

4. Verifica qué archivos se van a incluir en el commit:

```bash
git status
```

5. Realiza el commit final de la práctica:

```bash
git commit -m "[lab01] Añadir análisis del monolito y propuesta de descomposición en microservicios"
```

### Salida Esperada

```
[main <hash>] [lab01] Añadir análisis del monolito y propuesta de descomposición en microservicios
 6 files changed, XXX insertions(+)
 create mode 100644 lab01/PROPUESTA.md
 create mode 100644 lab01/diagrama-componentes.md
 create mode 100644 lab01/monolito/app.py
 create mode 100644 lab01/monolito/database.py
 create mode 100644 lab01/monolito/models.py
 create mode 100644 lab01/monolito/requirements.txt
```

### Verificación

```bash
git log --oneline
```

Debe mostrar 2 commits en la rama `main`:

```
<hash2> [lab01] Añadir análisis del monolito y propuesta de descomposición en microservicios
<hash1> [lab01] Inicializar repositorio del curso con .gitignore
```

---

## Validación y Pruebas

Ejecuta las siguientes verificaciones para confirmar que la práctica se completó correctamente:

```bash
echo "=== Verificación Final de la Práctica 01 ==="
echo ""

# 1. Estructura de directorios
echo "1. Verificando estructura de directorios..."
test -d ~/microservicios-curso/lab01/monolito && echo "   ✓ Directorio monolito existe" || echo "   ✗ FALTA directorio monolito"
test -f ~/microservicios-curso/lab01/monolito/app.py && echo "   ✓ app.py existe" || echo "   ✗ FALTA app.py"
test -f ~/microservicios-curso/lab01/monolito/models.py && echo "   ✓ models.py existe" || echo "   ✗ FALTA models.py"
test -f ~/microservicios-curso/lab01/monolito/database.py && echo "   ✓ database.py existe" || echo "   ✗ FALTA database.py"
echo ""

# 2. Documentos de propuesta
echo "2. Verificando documentos de propuesta..."
test -f ~/microservicios-curso/lab01/PROPUESTA.md && echo "   ✓ PROPUESTA.md existe" || echo "   ✗ FALTA PROPUESTA.md"
test -f ~/microservicios-curso/lab01/diagrama-componentes.md && echo "   ✓ diagrama-componentes.md existe" || echo "   ✗ FALTA diagrama-componentes.md"
echo ""

# 3. Contenido mínimo de la propuesta
echo "3. Verificando contenido de PROPUESTA.md..."
SERVICIOS=$(grep -c "### 3\." ~/microservicios-curso/lab01/PROPUESTA.md 2>/dev/null)
test "$SERVICIOS" -ge 4 && echo "   ✓ Al menos 4 servicios propuestos ($SERVICIOS encontrados)" || echo "   ✗ Menos de 4 servicios propuestos"
grep -q "Trade-offs" ~/microservicios-curso/lab01/PROPUESTA.md && echo "   ✓ Sección de trade-offs incluida" || echo "   ✗ FALTA sección de trade-offs"
grep -q "Comunicación Entre Servicios" ~/microservicios-curso/lab01/PROPUESTA.md && echo "   ✓ Contratos de comunicación documentados" || echo "   ✗ FALTA documentación de comunicación"
echo ""

# 4. Repositorio Git
echo "4. Verificando repositorio Git..."
cd ~/microservicios-curso
BRANCH=$(git branch --show-current)
test "$BRANCH" = "main" && echo "   ✓ Rama actual: main" || echo "   ✗ Rama incorrecta: $BRANCH"
COMMITS=$(git log --oneline | wc -l)
test "$COMMITS" -ge 2 && echo "   ✓ Al menos 2 commits ($COMMITS encontrados)" || echo "   ✗ Menos de 2 commits"
echo ""

# 5. Sintaxis Python válida
echo "5. Verificando sintaxis Python..."
cd ~/microservicios-curso/lab01/monolito
python3 -c "import ast; ast.parse(open('app.py').read())" 2>/dev/null && echo "   ✓ app.py: sintaxis válida" || echo "   ✗ app.py: error de sintaxis"
python3 -c "import ast; ast.parse(open('models.py').read())" 2>/dev/null && echo "   ✓ models.py: sintaxis válida" || echo "   ✗ models.py: error de sintaxis"
python3 -c "import ast; ast.parse(open('database.py').read())" 2>/dev/null && echo "   ✓ database.py: sintaxis válida" || echo "   ✗ database.py: error de sintaxis"
echo ""

echo "=== Verificación completada ==="
```

Todos los ítems deben mostrar `✓`.

---

## Solución de Problemas

### Problema 1: Error "not a git repository" al hacer commit

**Síntomas:**

```
fatal: not a git repository (or any of the parent directories): .git
```

**Causa:** El comando `git init` no se ejecutó en el directorio correcto, o el terminal está posicionado fuera de `~/microservicios-curso/`.

**Solución:**

```bash
cd ~/microservicios-curso
# Verificar si existe el directorio .git
ls -la .git

# Si no existe, inicializar:
git init -b main

# Si ya existe pero estabas en otro directorio, simplemente navega:
cd ~/microservicios-curso
git status
```

---

### Problema 2: Python no puede parsear los archivos (error de sintaxis por comillas)

**Síntomas:**

```
SyntaxError: unterminated string literal
```

o errores al copiar/pegar los bloques `cat > archivo << 'EOF'`.

**Causa:** Al copiar los bloques heredoc (`<< 'EOF'`), el terminal puede interpretar caracteres especiales o las comillas se corrompen si se usa un terminal con codificación diferente a UTF-8.

**Solución:**

```bash
# Verificar la codificación del terminal
echo $LANG
# Debe mostrar algo como: en_US.UTF-8 o es_ES.UTF-8

# Si el archivo está corrupto, verificar caracteres extraños:
file ~/microservicios-curso/lab01/monolito/app.py
# Debe mostrar: Python script, UTF-8 Unicode text

# Solución: recrear el archivo manualmente con un editor
nano ~/microservicios-curso/lab01/monolito/app.py
# O usar VS Code:
code ~/microservicios-curso/lab01/monolito/app.py
```

Si persiste el problema, asegúrate de que el heredoc usa `'EOF'` (con comillas simples) para evitar la expansión de variables del shell:

```bash
cat > archivo.py << 'EOF'
# contenido aquí (sin expansión de $variables)
EOF
```

---

## Limpieza

Esta práctica no requiere limpieza ya que los artefactos generados (`PROPUESTA.md`, código del monolito, diagrama) son la base para las prácticas siguientes del curso. **No elimines ningún archivo.**

Si por alguna razón necesitas reiniciar la práctica desde cero:

```bash
cd ~/microservicios-curso
git log --oneline  # Anotar el hash del commit inicial
git reset --hard <hash-commit-inicial>
rm -rf lab01/
```

---

## Resumen

En esta práctica has completado los siguientes logros:

| Logro | Descripción |
|-------|-------------|
| ✅ Repositorio inicializado | Git configurado con rama `main` y `.gitignore` adecuado |
| ✅ Monolito analizado | Identificados 5+ problemas de acoplamiento y escalabilidad |
| ✅ Diagrama de componentes | Documentada la arquitectura actual del monolito |
| ✅ Propuesta de microservicios | 4 servicios identificados con APIs, contratos y justificación |
| ✅ Trade-offs documentados | Ventajas y compromisos evaluados objetivamente |

### Conceptos Clave Aplicados

- **Bounded Context**: Cada servicio propuesto encapsula un dominio de negocio completo (usuarios, productos, inventario, pedidos)
- **Cohesión alta**: Las funciones dentro de cada servicio están fuertemente relacionadas entre sí
- **Acoplamiento bajo**: Los servicios se comunican solo mediante APIs REST, sin compartir base de datos
- **Autonomía de despliegue**: Cada servicio puede evolucionar y desplegarse independientemente
- **Diseño orientado al fallo**: La separación permite que un servicio falle sin afectar al resto

### Recursos Adicionales

- [Building Microservices, 2nd Edition — Sam Newman](https://www.oreilly.com/library/view/building-microservices-2nd/9781492034018/) — Capítulos 1-3 sobre descomposición
- [Microservices — Martin Fowler](https://martinfowler.com/articles/microservices.html) — Artículo fundacional
- [Domain-Driven Design — Eric Evans](https://www.domainlanguage.com/ddd/) — Concepto de Bounded Contexts
- [Microservices Patterns — Chris Richardson](https://microservices.io/patterns/decomposition/decompose-by-business-capability.html) — Patrones de descomposición

### Próxima Práctica

En la **Práctica 02** implementarás el primer microservicio (`products-service`) usando FastAPI, aplicando directamente el contrato de API definido en esta propuesta.
