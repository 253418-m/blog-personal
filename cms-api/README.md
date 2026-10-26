# CMS Core API

`cms-core-api` es la API interna para gestionar el contenido editorial del Blog Dev y del portafolio personal. Usa FastAPI, Pydantic v2 y Uvicorn, con contratos REST bajo `/api/v1`.

La persistencia usa PostgreSQL, SQLAlchemy 2.x, Alembic y psycopg. El entorno actual utiliza PostgreSQL 18.6 nativo en Windows; Docker Compose ofrece PostgreSQL 16 como alternativa. Incluye el esquema editorial, usuarios administrativos y autenticación HTTP con Argon2id y JWT. El desarrollo sigue API-First y los modelos ORM no se exponen como respuestas HTTP.

## Separación respecto a Quarto

Quarto genera el sitio público estático para GitHub Pages. La API no sirve sus páginas ni sustituye Quarto. `docs/` en la raíz es salida generada de Quarto; la documentación técnica del backend está en `cms-api/api-docs/`.

## Instalación local en Windows

Desde la raíz del repositorio:

```powershell
cd cms-api
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Además de FastAPI, Uvicorn y Pydantic v2, se declaran `pydantic-settings>=2.13,<3`, `SQLAlchemy>=2,<3`, `alembic>=1.13,<2`, `psycopg[binary]>=3.1,<4`, `pwdlib[argon2]>=0.3,<0.4`, `uuid6>=2025.0.1,<2026` y `PyJWT>=2.10,<3`. UUIDv7 está disponible mediante uuid6 en Python 3.13; la versión de PyJWT validada es 2.15.1.

Para desarrollar y ejecutar la suite, instala también sus dependencias:

```powershell
python -m pip install -r requirements-dev.txt
```

`requirements-dev.txt` incluye las dependencias normales y `httpx2>=2,<3`, usado por el TestClient de Starlette 1.10 para las pruebas HTTP.

## Ejecución de la API

Desde `cms-api/`, con el entorno virtual activo:

```powershell
python -m uvicorn app.main:app --reload
```

| Recurso | URL |
| --- | --- |
| Dirección base | http://127.0.0.1:8000 |
| Swagger UI | http://127.0.0.1:8000/docs |
| ReDoc | http://127.0.0.1:8000/redoc |
| OpenAPI generado | http://127.0.0.1:8000/openapi.json |

El OpenAPI publica `POST /api/v1/auth/login` y `GET /api/v1/auth/me`. Templates, Documents, Workflow, Preview y Metrics siguen como routers vacíos bajo `/api/v1`; `/` y las rutas editoriales responden `404`. Las operaciones de autenticación utilizan PostgreSQL mediante las sesiones de persistencia existentes.

## Configuración

`app/core/config.py` centraliza la configuración mediante `Settings`, basada en `pydantic-settings` y Pydantic v2. Carga automáticamente `cms-api/.env` en UTF-8 mediante una ruta derivada del propio módulo con `pathlib`, sin depender del directorio de trabajo. Las variables reales del entorno tienen precedencia sobre `.env`. FastAPI, SQLAlchemy, Alembic y la CLI usan esta misma fuente, sin exportar manualmente `DATABASE_URL` en PowerShell. La configuración inicial de la API es:

```dotenv
APP_ENV=development
APP_HOST=127.0.0.1
APP_PORT=8000
```

La autenticación requiere además estas opciones:

| Variable | Requisito o valor predeterminado |
| --- | --- |
| `JWT_SECRET_KEY` | Obligatoria, secreta y de al menos 32 bytes UTF-8; sin valor predeterminado |
| `JWT_ALGORITHM` | `HS256`; es el único algoritmo admitido |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `30`; configurable como entero positivo |

`JWT_SECRET_KEY` usa `SecretStr`, se excluye de repr y serialización y no aparece en errores de configuración. La instalación local ya dispone de una clave generada en `.env`; conserva su valor privado y no lo copies a ejemplos, logs ni respuestas HTTP. El entorno real tiene prioridad sobre `.env` también para estas variables.

Para cambiar host o puerto, pásalos también a Uvicorn:

```powershell
$env:APP_ENV = "development"
$env:APP_HOST = "127.0.0.1"
$env:APP_PORT = "8000"
python -m uvicorn app.main:app --reload --host $env:APP_HOST --port $env:APP_PORT
```

## Base de datos

Requisitos: el entorno Python instalado y PostgreSQL local, mediante una de las dos alternativas siguientes. El entorno utilizado actualmente es PostgreSQL nativo en Windows. Ejecuta los comandos desde `cms-api/`, exclusivamente sobre la base local de desarrollo creada para este backend.

### Variables de entorno

`.env.example` incluye estos valores de ejemplo:

```dotenv
POSTGRES_DB=cms_core
POSTGRES_USER=cms_user
POSTGRES_PASSWORD=change_me
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
DATABASE_URL=postgresql+psycopg://cms_user:change_me@localhost:5432/cms_core
```

Si `.env` todavía no existe, copia el ejemplo:

```powershell
if (-not (Test-Path -LiteralPath .env)) {
    Copy-Item -LiteralPath .env.example -Destination .env
}
```

`.env` permanece ignorado por Git y contiene la configuración local, incluida la URL con las credenciales del usuario de aplicación. Compose también lee ese archivo para configurar el contenedor y su puerto. `change_me` es un ejemplo, no un secreto real; configura las credenciales locales en `.env` y mantén su URL coherente con ellas.

`DATABASE_URL` se carga automáticamente desde `.env`; no es necesario asignarla manualmente antes de ejecutar FastAPI, Alembic o `create_admin`. En CI o producción puede suministrarse mediante el entorno real, que tiene prioridad y funciona sin archivo local. `python-dotenv` se instala como dependencia normal de `pydantic-settings`, sin una carga adicional en scripts o CLI.

`DATABASE_URL` es obligatoria al consumir la configuración. Si falta en ambas fuentes o es inválida, se produce un error claro, sin fallback de base de datos ni credenciales predeterminadas. Se protege mediante `SecretStr`, se excluye de repr y serialización de Settings y los mensajes de configuración no incluyen valores sensibles. `get_database_url()` conserva el contrato de devolver una cadena para SQLAlchemy; no debe imprimirse.

`get_settings()` mantiene una instancia inmutable en caché por proceso. Reinicia el proceso después de cambiar `.env` o variables del entorno; los tests pueden usar `get_settings.cache_clear()` para aislar sus casos. Crear el engine no abre una conexión; esta se establece cuando una operación de persistencia la solicita.

### A) PostgreSQL nativo en Windows — entorno actual

La instalación actual utiliza PostgreSQL 18.6 como servicio nativo `postgresql-x64-18`. La base `cms_core` y el usuario de aplicación `cms_user` ya fueron creados manualmente; las credenciales permanecen únicamente en `.env`.

| Parámetro | Valor |
| --- | --- |
| host | `localhost` |
| port | `5432` |
| database | `cms_core` |
| user | `cms_user` |

Comprueba que el servicio esté en ejecución antes de conectar o migrar:

```powershell
Get-Service -Name postgresql-x64-18
```

Con el servicio activo y `.env` configurado, continúa con las migraciones y pruebas de las secciones siguientes; Settings carga la URL automáticamente.

### B) Docker Compose — alternativa

Docker y Docker Compose se requieren únicamente para esta alternativa. Usa una sola instancia en el puerto configurado: el servicio nativo actual ya ocupa `5432`.

```powershell
docker compose up -d postgres
docker compose ps
```

Espera a que `postgres` figure como `healthy` antes de migrar. Compose usa la imagen oficial `postgres:16`, un volumen nombrado persistente y publica por defecto únicamente `127.0.0.1:5432`.

Para detener los contenedores conservando el volumen y sus datos:

```powershell
docker compose down
```

`docker compose down -v` elimina el volumen y todos sus datos. Úsalo únicamente cuando quieras descartar la base local.

### Migraciones

El esquema se administra con Alembic; no mediante `Base.metadata.create_all()`.

```powershell
alembic upgrade head
alembic current
```

La revisión `initial_cms_schema` define `templates`, `documents`, `canvas_blocks` y `review_reports`, con UUID, JSONB, timestamps con zona horaria, claves, restricciones e índices.

La cadena actual es `0001_initial_cms_schema → 0002_add_admin_users`. La revisión `0002` agrega únicamente `admin_users`; `0001` y las cuatro tablas editoriales permanecen sin cambios. `alembic heads` debe mostrar una sola HEAD: `0002_add_admin_users`.

Después de modificar modelos, genera una futura migración con:

```powershell
alembic revision --autogenerate -m "descripcion"
```

Revisa manualmente cada migración antes de aplicarla. Autogenerate requiere una conexión a PostgreSQL y no sustituye revisar tipos, relaciones y efectos sobre los datos.

Para comprobar la reversión incremental **solo en la base local de desarrollo**, partiendo de `0002_add_admin_users`:

```powershell
alembic downgrade -1
alembic upgrade head
alembic current
```

Desde `0002`, `downgrade -1` elimina `admin_users` y sus cuentas, dejando las cuatro tablas editoriales de `0001` intactas. El upgrade posterior restaura la tabla vacía. No ejecutes este ciclo sobre datos que quieras conservar ni contra bases externas o de producción.

Para inspeccionar solamente el SQL de `0002` sin conectar a PostgreSQL, con `DATABASE_URL` definida:

```powershell
alembic upgrade 0001_initial_cms_schema:0002_add_admin_users --sql
alembic downgrade 0002_add_admin_users:0001_initial_cms_schema --sql
```

### Modelo y transacciones

| Relación | Integridad |
| --- | --- |
| Template → Documents | `documents.template_id` con `ON DELETE RESTRICT` |
| Document → CanvasBlocks | `canvas_blocks.document_id` con `ON DELETE CASCADE` |
| Document → ReviewReports | `review_reports.document_id` con `ON DELETE CASCADE` |

`templates.name` y `documents.slug` son únicos. `(document_id, order_index)` es único en `canvas_blocks`. Las cascadas internas no autorizan borrar documentos: el futuro servicio deberá impedir eliminar físicamente `PUBLICADO` o `ARCHIVADO`.

JSONB almacena `metadata_contract`, `layout_structure`, `frozen_template`, `metadata_values`, `content_payload`, `style_config` y `findings`. `latest_review` se obtendrá de `review_reports` por `audited_at DESC`, sin columna duplicada. No hay tablas para MetricSnapshot ni PreviewSession.

Los identificadores se almacenan como UUID de PostgreSQL. El contrato exige UUIDv7, cuya generación corresponde a futuros casos de uso en la aplicación; no hay UUIDv4 ni defaults de UUID en la base. Las operaciones futuras deben suministrar timestamps explícitos con zona horaria.

`status` acepta mediante CHECK los cuatro valores confirmados: `BORRADOR`, `EN_REVISION`, `PUBLICADO`, `ARCHIVADO`. `target_type`, `content_type` y `block_type` usan texto porque sus catálogos siguen `CONTRACT_PENDING`; `expected_type` también sigue pendiente dentro del contrato JSON de metadatos. No se inventan enums cerrados.

La Session factory permite futuros límites transaccionales como `with SessionLocal.begin() as session:`. La dependency gestiona el cierre de la sesión; cada caso de uso deberá definir su transacción. Aún no se implementan creación, transferencia de default, reasignación, publicación ni archivado.

Las invariantes «al menos una Template» y «exactamente una default» requieren inicialización y coordinación transaccional en servicios, con bloqueo adecuado para concurrencia. No quedan garantizadas por un CHECK por fila. `bootstrap.py` registra `BOOTSTRAP_PENDING` / `CONTRACT_PENDING`; no inserta una plantilla arbitraria. La base recién migrada estará vacía hasta definir los valores oficiales de la plantilla inicial.

### Pruebas y validación

```powershell
python -m compileall app
python -c "from app.infrastructure.database.base import Base"
python -c "from app.infrastructure.database.session import engine"
python -m pip check
python -m unittest discover -s tests -v
```

Los tests de integración conservan la activación explícita mediante `TEST_DATABASE_URL` y requieren la base local `cms_core` ya migrada. Para ejecutar toda la suite con la configuración centralizada, sin imprimir ni copiar la URL, puedes preparar únicamente el proceso de tests:

```powershell
@'
import os
import subprocess
import sys
from app.core.config import get_database_url

os.environ["TEST_DATABASE_URL"] = get_database_url()
raise SystemExit(subprocess.call([
    sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"
]))
'@ | python -
```

Las pruebas de integración trabajan dentro de una transacción que se revierte al terminar; no usan `drop_all()` ni alteran el esquema persistente. Las 59 pruebas de integración administrativas usan una copia temporal privada de `admin_users` por conexión, con los tipos, constraints y defaults reales; no insertan, actualizan ni eliminan registros en `public.admin_users`. Comprueban persistencia, bootstrap, autenticación y respuestas HTTP con datos ficticios. Las pruebas editoriales verifican unicidad, claves foráneas, orden de bloques, JSONB, relaciones ORM y timestamps con zona horaria. Las pruebas estructurales verifican también el SQL offline de `0002` y su reversión aislada.

Validación del 2026-10-25 sobre PostgreSQL 18.6 nativo en Windows: `SELECT 1`, las migraciones online `0001` y `0002`, el ciclo `0002 → 0001 → 0002`, los tipos y operaciones JSONB, las claves foráneas y las restricciones UNIQUE se comprobaron contra la base real. La base quedó en `0002_add_admin_users` y los datos ficticios se revirtieron.

La validación de persistencia con `python -m unittest discover -s tests -v` finalizó con **45 passed, 0 failed, 0 skipped**; las 19 pruebas de integración se ejecutaron. El test de borrado de una Template referenciada espera correctamente SQLSTATE `23001` para `RESTRICT` en PostgreSQL 18; los casos de referencias inexistentes conservan `23503`.

La suite completa tras implementar autenticación HTTP finalizó con **163 passed, 0 failed, 0 skipped**, incluidas 72 pruebas de integración contra PostgreSQL. Cubre configuración, hashing, bootstrap, repositorio, AuthService, JWT, login, `/auth/me` y sus contratos OpenAPI. Durante esta validación no se inició sesión con el administrador real ni se modificó su registro.

## Autenticación administrativa

El CMS utiliza usuarios administrativos propios mediante `username + password`. El hashing y la verificación Argon2id están implementados con `PasswordHash.recommended()` de pwdlib, sin parámetros criptográficos manuales. El login HTTP emite un JWT de acceso y `/auth/me` exige un Bearer válido. La protección se aplica únicamente a `/auth/me`; los routers editoriales siguen sin CRUD ni protección global.

`admin_users` contiene exactamente `user_id`, `username`, `password_hash`, `is_active`, `created_at`, `updated_at` y `last_login_at`. El username es único y la base solo almacena `password_hash` como TEXT: las contraseñas originales nunca se persisten. `app/core/security.py` expone `PasswordHasher`, `hash_password()` y `verify_password()`; la verificación incorrecta o de un hash inválido devuelve `False`. No se retornan hashes mediante HTTP ni mediante el resultado del bootstrap.

`is_active` tiene default `true` en ORM y PostgreSQL, y `last_login_at` comienza como NULL. El bootstrap genera UUIDv7 mediante `uuid6.uuid7()` y suministra timestamps UTC explícitos. No se agregan roles, email, tablas de tokens o sesiones ni relaciones con contenido editorial.

### Login y consulta del administrador actual

`POST /api/v1/auth/login` recibe JSON con `username` y `password`. Un login válido de una cuenta activa devuelve `200` con exactamente `access_token`, `token_type: "bearer"` y `expires_in` en segundos: `1800` con la configuración predeterminada. AuthService verifica Argon2id y confirma `last_login_at` en UTC dentro de una transacción antes de emitir el token. El UPDATE exige nuevamente `is_active = true`, de modo que una desactivación durante la verificación impide completar el login. Para un username inexistente ejecuta una verificación con un hash ficticio; usuario inexistente, contraseña incorrecta y cuenta inactiva producen el mismo `401`, `{"detail":"Credenciales inválidas."}` y `WWW-Authenticate: Bearer`.

El JWT contiene únicamente `sub` con el UUID del administrador, `iat`, `exp` y `type: "access"`. Se firma y valida exclusivamente con HS256; el token no contiene contraseña ni hash. La validación exige los cuatro claims, un UUID válido y fechas coherentes, además de verificar firma y expiración.

`GET /api/v1/auth/me` recibe `Authorization: Bearer TU_ACCESS_TOKEN`, consulta el usuario actual en PostgreSQL y devuelve `200` con exactamente `user_id`, `username` e `is_active`. Un Bearer ausente, inválido o expirado, o un usuario que ya no existe, produce `401`, `{"detail":"No se pudieron validar las credenciales."}` y `WWW-Authenticate: Bearer`. Una cuenta inactiva con token válido produce `403` y `{"detail":"Cuenta inactiva."}`.

Las solicitudes de login que no cumplen el contrato JSON devuelven `422` con `{"detail":"Solicitud de autenticación inválida."}`, sin reflejar datos recibidos. Los errores de persistencia se presentan como `503` y `{"detail":"Servicio de autenticación no disponible."}`. No se implementan refresh tokens, logout, CRUD editorial ni frontend `cms-admin`.

### Bootstrap manual del primer administrador

Estado de la herramienta: `READY_FOR_MANUAL_EXECUTION`. El primer administrador real ya fue creado manualmente y se conserva intacto. No se crea ninguna cuenta al importar módulos o iniciar FastAPI. No se agregan credenciales administrativas a `.env.example` ni a migraciones.

Para una instalación nueva sin administradores, desde `cms-api/`, activa `.venv` y configura `.env`; su carga es automática. El comando explícito de bootstrap es:

```powershell
python -m app.cli.create_admin
```

La CLI solicita `Username:`, `Password:` y `Confirm password:`. Las dos entradas de contraseña usan `getpass` sin eco; si la terminal no permite entrada oculta, se cancela la operación. El comando no acepta argumentos de credenciales ni `--password`. No introduzcas contraseñas en comandos, historial o variables administrativas de entorno.

El username se guarda sin espacios exteriores y no puede estar vacío. Como decisión mínima de seguridad de esta implementación, la contraseña debe tener **al menos 12 caracteres** y no puede componerse solo de espacios. No se exigen símbolos ni combinaciones de mayúsculas; los espacios de una contraseña válida se conservan. La confirmación debe coincidir exactamente antes de escribir en la base.

`AdminBootstrapService` y el repositorio SQLAlchemy usan la Session existente y una transacción: crean únicamente el primer administrador activo, con `last_login_at = NULL`. Si existe el username o cualquier administrador, incluso inactivo, el bootstrap se rechaza sin modificarlo. Los intentos concurrentes se serializan mediante un bloqueo transaccional PostgreSQL; se requiere el aislamiento habitual `READ COMMITTED`. La CLI confirma el éxito sin mostrar contraseña ni hash, y SQLAlchemy oculta los parámetros de consultas en logs y errores.

La validación anterior de bootstrap y configuración finalizó con **89 passed, 0 failed, 0 skipped**; la suite completa actual es la de 163 pruebas descrita arriba. Los datos de bootstrap son exclusivamente ficticios, se aíslan en tablas temporales y se revierten; el administrador real permanece intacto. Se comprobó la carga local en procesos nuevos sin `DATABASE_URL` heredada, SQLAlchemy conectado a `cms_core` como `cms_user` y Alembic en `0002_add_admin_users (head)`. El esquema persistente y las migraciones permanecen intactos.

`cms-admin` será una aplicación privada separada del sitio público Quarto. Todavía no se crea su carpeta ni se añade a navegación, sitemap o `docs/`. Los futuros endpoints editoriales deberán incorporar su autorización explícita; el login y `/auth/me` ya están disponibles.

## Organización y contratos pendientes

| Carpeta | Responsabilidad |
| --- | --- |
| `app/api/v1/` | Agregador y routers REST |
| `app/core/` | Configuración, hashing Argon2id, JWT y excepciones |
| `app/domain/` | Modelos preliminares y estados del dominio |
| `app/schemas/` | Contratos de autenticación y schemas editoriales preliminares |
| `app/services/` | AuthService, bootstrap administrativo y futuros casos de uso |
| `app/repositories/` | Abstracciones para persistencia |
| `app/infrastructure/database/` | Base, sesiones, ORM, repositorio y entrada explícita al bootstrap |
| `app/cli/` | Bootstrap interactivo del primer administrador |
| `alembic/` | Migraciones y esquema inicial |
| `tests/` | Pruebas de estructura e integración PostgreSQL |
| `postman/` | Preparación de pruebas manuales |
| `api-docs/` | Plan técnico |

El contrato de persistencia ya define los campos de Template, Document, CanvasBlock y ReviewReport y exige UUIDv7. Los modelos de dominio y schemas HTTP editoriales continúan preliminares y no se conectan a endpoints en esta fase. Aún deben precisarse los cuerpos Create, Update y Response por operación, sus reglas y catálogos pendientes. Los contratos HTTP de autenticación ya están implementados.

## Postman y próximos contratos

Usa `base_url=http://127.0.0.1:8000`, con la API en ejecución y un administrador existente. Para comprobar la autenticación manualmente en Postman:

1. Crea una petición **POST** a `http://127.0.0.1:8000/api/v1/auth/login`. En **Authorization**, selecciona **No Auth**. En **Body → raw → JSON**, introduce tus credenciales únicamente al realizar la prueba:

   ```json
   {
     "username": "TU_USUARIO",
     "password": "TU_PASSWORD"
   }
   ```

2. Envía la petición y comprueba `200`, `token_type: "bearer"` y `expires_in: 1800` con el TTL predeterminado. Copia el `access_token` de esa respuesta para la petición siguiente.
3. Crea una petición **GET** a `http://127.0.0.1:8000/api/v1/auth/me`. En **Authorization → Bearer Token**, pega el token recibido; Postman enviará `Authorization: Bearer TU_ACCESS_TOKEN`. No necesita body.
4. Comprueba `200` y que la respuesta contiene únicamente `user_id`, `username` e `is_active`. Para comprobar errores, usa un password ficticio incorrecto en login (`401`) o elimina el Bearer de `/auth/me` (`401`).

Los valores `TU_USUARIO`, `TU_PASSWORD` y `TU_ACCESS_TOKEN` son marcadores, no credenciales. No guardes contraseñas ni tokens reales en colecciones exportadas, ejemplos o archivos del repositorio. Esta fase no incorpora una colección Postman. Las operaciones editoriales GET, POST, PUT y DELETE siguen pendientes.

PATCH permanece `CONTRACT_PENDING`. Live Preview requiere WebSocket y no se implementa todavía. Tampoco se integran un servicio analítico ni un agente de revisión.

Consulta [el plan de implementación](api-docs/implementation-plan.md) y [las convenciones de Postman](postman/README.md).
