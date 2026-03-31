# TFG - Inventory Backend

Idioma: Español | [English](README.md)

Backend del Trabajo de Fin de Grado para una aplicación de gestión de inventario multiempresa con control por sedes, roles, operaciones de stock y exportación de histórico.

La API está implementada con FastAPI y SQLAlchemy, con autenticación JWT y reglas de negocio por rol.

## Stack tecnológico

- Python 3.9+
- FastAPI
- SQLAlchemy 2
- Alembic
- MySQL (runtime)
- Uvicorn
- Pydantic v2 + pydantic-settings
- python-jose + passlib (JWT y hashing)
- WeasyPrint (export PDF)
- Pillow + pillow-heif (imágenes y conversión HEIC/HEIF/AVIF a WebP)
- Pytest + HTTPX

## Funcionalidad principal

- Registro de empresa con creación automática de usuario ADMIN
- Login con JWT y endpoint de perfil autenticado
- Gestión de usuarios con roles ADMIN, MANAGER y EMPLOYEE
- Gestión de sedes con estados activo/inactivo
- Gestión de categorías
- Gestión de artículos con:
  - filtros, búsqueda, ordenación y paginación
  - stock por sede
  - asociación de categorías
  - subida, consulta y borrado de imagen
- Gestión de operaciones de inventario:
  - tipos: IN, OUT, TRANSFER, ADJUSTMENT
  - estados: PENDING, TRANSIT, COMPLETED, CANCELLED
  - eventos históricos por operación (CREATED, EDITED, SENT, COMPLETED, CANCELLED)
  - adjuntos de documentos (PDF, Office, CSV, TXT, imágenes)
- Exportación de operaciones a CSV y PDF (con filtros)

## Arquitectura

Arquitectura por capas:

- app/api/v1/routes: endpoints REST
- app/services: lógica de negocio
- app/repositories: consultas/persistencia
- app/db/models: modelo de datos SQLAlchemy
- app/schemas: contratos de entrada/salida
- app/core: seguridad, configuración, manejo de ficheros y excepciones

## Modelo de dominio (resumen)

- Company
  - tiene Users, Branches, Items y Categories
- User
  - role: ADMIN | MANAGER | EMPLOYEE
  - is_active
  - puede estar asignado a una Branch
- Branch
  - is_active
  - agrupa usuarios y operaciones
- Item
  - unidad de medida, datos comerciales y estado
  - relación N:N con Category
  - imagen opcional
- Transaction
  - tipo de operación y estado
  - líneas de operación
  - eventos de auditoría
  - documento opcional
- StockMovement
  - movimientos derivados de completar operaciones

## API y prefijo

- Prefijo global: /api/v1
- Swagger UI: http://localhost:8000/docs
- OpenAPI JSON: http://localhost:8000/openapi.json

### Endpoints por módulo

- Auth
  - POST /auth/login
  - GET /auth/me
- Company
  - POST /company/register
  - GET /company
  - PUT /company
- Users
  - POST /users
  - GET /users
  - GET /users/{user_id}
  - PUT /users/{user_id}
  - PUT /users/{user_id}/admin
  - DELETE /users/{user_id}
- Branches
  - POST /branches
  - GET /branches
  - GET /branches/{branch_id}
  - PUT /branches/{branch_id}
  - DELETE /branches/{branch_id}
- Categories
  - POST /categories
  - GET /categories
  - GET /categories/{category_id}
  - PUT /categories/{category_id}
  - DELETE /categories/{category_id}
- Items
  - GET /items
  - POST /items
  - GET /items/{item_id}
  - PUT /items/{item_id}
  - DELETE /items/{item_id}
  - POST /items/{item_id}/categories
  - GET /items/{item_id}/categories
  - GET /items/{item_id}/image
  - POST /items/{item_id}/image
  - DELETE /items/{item_id}/image
- Transactions
  - GET /transactions
  - GET /transactions/export?format=csv|pdf
  - POST /transactions
  - GET /transactions/{transaction_id}
  - PUT /transactions/{transaction_id}
  - POST /transactions/{transaction_id}/cancel
  - POST /transactions/{transaction_id}/complete
  - POST /transactions/{transaction_id}/document
  - GET /transactions/{transaction_id}/document
  - DELETE /transactions/{transaction_id}/document
- Health/debug
  - GET /health
  - GET /db-check
  - POST /test-user (debug)
  - GET /debug/settings (debug)

## Seguridad y autorización

- Autenticación Bearer JWT (OAuth2PasswordBearer)
- Login bloqueado para usuarios inactivos
- Control de acceso por rol:
  - ADMIN: control total de empresa/sedes/usuarios
  - MANAGER: gestión operativa (items, categorías, operaciones)
  - EMPLOYEE: acceso operativo con restricciones
- Reglas de visibilidad por sede:
  - usuarios con sede asignada trabajan con alcance de su sede (según endpoint)
- Reglas de actividad:
  - endpoints protegidos validan user.is_active

## Ficheros y media

- Carpeta base: media
- Imágenes de artículos: media/items/{company_id}
  - formatos: jpg, png, webp, heic, heif, avif
  - límite: 5 MB
- Documentos de operaciones: media/transactions/{company_id}
  - formatos: PDF, Word, Excel, CSV, TXT, imágenes
  - límite: 10 MB
- HEIC/HEIF/AVIF se convierten a WebP al guardar

## Exportaciones

- CSV y PDF en GET /transactions/export
- Solo ADMIN y MANAGER pueden exportar
- Se aplican los mismos filtros de listado
- Límites internos de exportación para evitar cargas excesivas
- PDF usa WeasyPrint y mantiene una ruta fallback para entornos sin dependencias nativas

## Requisitos previos

- Python 3.9+
- MySQL en ejecución

## Configuración de entorno

Crear archivo .env en la raíz del proyecto.

Variables consumidas por la aplicación (app/core/config.py):

- app_name
- env
- db_user
- db_password
- db_host
- db_port
- db_name
- secret_key
- access_token_expire_minutes

Variables utilizadas por Alembic (alembic/env.py):

- DB_USER
- DB_PASSWORD
- DB_HOST
- DB_PORT
- DB_NAME

Ejemplo mínimo de .env compatible con ambos:

```env
app_name=TFG Inventory Backend
env=dev

db_user=root
db_password=your_password
db_host=127.0.0.1
db_port=3306
db_name=inventory_db

DB_USER=root
DB_PASSWORD=your_password
DB_HOST=127.0.0.1
DB_PORT=3306
DB_NAME=inventory_db

secret_key=change_this_secret
access_token_expire_minutes=60
```

## Puesta en marcha local

1. Crear entorno virtual

```bash
python -m venv .venv
source .venv/bin/activate
```

2. Instalar dependencias

```bash
pip install -r requirements.txt
```

3. Aplicar migraciones

```bash
alembic upgrade head
```

4. Ejecutar servidor

```bash
uvicorn app.main:app --reload
```

5. Abrir documentación

- http://localhost:8000/docs

## Tests

La suite usa SQLite en memoria para aislamiento y rapidez (tests/conftest.py), creando esquema desde Base.metadata.

Ejecutar todos los tests:

```bash
pytest
```

Ejecutar módulos concretos (ejemplos):

```bash
pytest tests/api/test_auth_login.py
pytest tests/api/test_transaction_export_contract.py
pytest tests/services/test_transaction_export_pdf_html.py
```

Cobertura funcional destacada en tests:

- login y usuario actual
- CRUD de empresa, usuarios, sedes
- estados activos/inactivos (usuarios y sedes)
- protección de endpoints para usuarios inactivos
- listado avanzado de ítems
- CRUD y flujo de operaciones
- contrato de exportación CSV/PDF

## Notas de desarrollo

- CORS permitido para frontend local en http://localhost:5173
- El servicio expone endpoints de debug que no deberían habilitarse en producción
- Los códigos de error de negocio se devuelven como detail (por ejemplo: INSUFFICIENT_ROLE, USER_INACTIVE, ITEM_NOT_FOUND)

## Autor

Mateo Sarria Franco de Sarabia

Trabajo de Fin de Grado - Grado en Ingeniería de Tecnologías y Servicios de Telecomunicación