# Fundamentos de Microservicios

Repositorio de laboratorios del curso **Fundamentos de Microservicios** (`MICR_INT_PYT`). Las prácticas recorren diseño, APIs, contenedores, Kubernetes, persistencia, seguridad, caché y observabilidad con Python.

## Información del curso

| Campo | Valor |
|---|---|
| Duración total del curso | 25 horas / 1500 minutos |
| Capítulos | 10 |
| Laboratorios | 10 |
| Duración total de laboratorios | 393 minutos |
| Lenguaje principal | Python |

Los tiempos de esta tabla provienen del temario contractual. La instalación inicial de herramientas y la descarga de imágenes deben completarse antes de iniciar el cronómetro de cada práctica.

## Laboratorios

| Capítulo | Práctica | Duración | Resultado principal | Enlace |
|---:|---|---:|---|---|
| 1 | Análisis de un monolito y propuesta de servicios | 24 min | `PROPUESTA.md` con límites, datos, contratos y trade-offs | [Abrir laboratorio](Capitulo01/README.md) |
| 2 | Crear una API REST simple en FastAPI | 40 min | API CRUD validada con pruebas y OpenAPI | [Abrir laboratorio](Capitulo02/README.md) |
| 3 | Construir y publicar una imagen Docker | 41 min | Imagen versionada, optimizada y sin ejecución como root | [Abrir laboratorio](Capitulo03/README.md) |
| 4 | Desplegar un servicio Python en un clúster local | 41 min | Deployment, Service, configuración y reconciliación en minikube | [Abrir laboratorio](Capitulo04/README.md) |
| 5 | Montar un volumen persistente para un servicio Python | 41 min | Datos conservados tras reemplazar el Pod mediante PV/PVC | [Abrir laboratorio](Capitulo05/README.md) |
| 6 | Crear un chart de Helm y escalar un Deployment | 41 min | Chart validado, release, Service y HPA | [Abrir laboratorio](Capitulo06/README.md) |
| 7 | Implementar autenticación JWT y TLS entre servicios | 41 min | JWT RS256, autorización por rol y comunicación mTLS | [Abrir laboratorio](Capitulo07/README.md) |
| 8 | Persistencia híbrida PostgreSQL + MongoDB | 41 min | Escritura híbrida y Saga con compensación | [Abrir laboratorio](Capitulo08/README.md) |
| 9 | Implementar caching con Redis en un servicio Python | 41 min | Cache-aside, TTL, invalidación y fallback | [Abrir laboratorio](Capitulo09/README.md) |
| 10 | Instrumentar un servicio con Prometheus, Grafana y Jaeger | 42 min | Métricas RED, dashboard y trazas correlacionadas | [Abrir laboratorio](Capitulo10/README.md) |
| | **TOTAL** | **393 min** | | |

## Continuidad entre prácticas

```text
Diseño (1) → API (2) → imagen (3) → Kubernetes (4)
                                  ├→ persistencia en volumen (5)
                                  └→ Helm y HPA (6)

Seguridad (7)         práctica autocontenida
Persistencia híbrida (8) → extensión opcional en caché (9)
Observabilidad (10)   servicio instrumentado autocontenido
```

- El laboratorio 3 reutiliza la solución validada del laboratorio 2.
- Los laboratorios 4–6 reutilizan conceptualmente `products-service` y el clúster minikube.
- El laboratorio 7 no depende del release Helm del laboratorio 6.
- Los laboratorios 8–10 incluyen proyectos iniciales para no reconstruir capítulos anteriores dentro del tiempo contractual.

## Requisitos por bloque

| Laboratorios | Requisitos principales |
|---|---|
| 1 | Editor de Markdown |
| 2 | Python 3.12 y `pip` |
| 3 | Docker y cuenta de registro para el push |
| 4–5 | Docker, minikube y `kubectl` |
| 6 | minikube, `kubectl`, Helm y metrics-server |
| 7 | Python 3.12 y OpenSSL; Bash o PowerShell para certificados |
| 8 | Python, Docker Compose, PostgreSQL y MongoDB mediante contenedores |
| 9 | Python, Docker Compose y Redis mediante contenedor |
| 10 | Python, Docker Compose, Prometheus, Grafana y Jaeger mediante contenedores |

Consulte los prerrequisitos concretos y los puertos utilizados dentro de cada guía. No use etiquetas `latest` como baseline reproducible.

## Estado de validación

- Cobertura curricular: **PASS**.
- Tiempo contractual de laboratorios: **PASS**, 393/393 minutos.
- Integridad de los originales: **PASS**, diez respaldos disponibles.
- Pruebas y validación estática: **PASS** según la evidencia de cada capítulo.
- Ejecución Kubernetes: **WARNING**, requiere un clúster local activo.
- Stacks Docker de datos y observabilidad: **WARNING**, la validación integral quedó pendiente porque el registro interrumpió las descargas de imágenes durante la revisión.
- Portabilidad: **WARNING**, algunas comprobaciones auxiliares usan sintaxis Bash; las rutas críticas incluyen indicaciones para PowerShell cuando aplica.

La evidencia consolidada está disponible en [la auditoría transversal de laboratorios](revision_labs/FINAL_LABS_AUDIT.md).

## Estructura

```text
CapituloNN/
  README.md        guía contractual
  app/             código cuando aplica
  tests/           pruebas cuando aplica
  manifests/       recursos Kubernetes cuando aplica
  chart/           chart Helm cuando aplica

revision_labs/
  backups/         copias de las guías originales
  chapterNN/       auditoría y QA por laboratorio
```

## Flujo de colaboración

Trabaje en una rama propia, revise `git status` antes de modificar y abra un Pull Request hacia la rama indicada por los responsables del repositorio. No se fija aquí un nombre de rama permanente porque puede variar entre entregas.
