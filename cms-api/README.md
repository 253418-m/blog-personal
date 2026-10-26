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

El OpenAPI publica login y `/auth/me`, las cuatro operaciones de Templates y las siete de Documents (CRUD, publish, archive). Templates y Documents requieren JWT Bearer mediante `get_current_admin`. Preview y Metrics siguen sin operaciones; `/` responde `404`.

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

La cadena actual es `0001_initial_cms_schema → 0002_add_admin_users → 0003_simplify_documents`, con una sola HEAD: `0003_simplify_documents`. `0001` y `0002` permanecen intactas. `0003` agrega únicamente `documents.content` (TEXT NOT NULL) y `documents.created_at` (TIMESTAMPTZ NOT NULL). Para filas históricas usa contenido vacío y copia `updated_at` a `created_at`; no inventa contenido ni fechas.

Después de modificar modelos, genera una futura migración con:

```powershell
alembic revision --autogenerate -m "descripcion"
```

Revisa manualmente cada migración antes de aplicarla. Autogenerate requiere una conexión a PostgreSQL y no sustituye revisar tipos, relaciones y efectos sobre los datos.

El ciclo `0002 → 0003 → 0002 → 0003` fue validado en PostgreSQL local, con Documents vacíos y conservando el administrador y la Template reales. Para una base de desarrollo en `0003` y sin Documents:

```powershell
alembic downgrade -1
alembic upgrade head
alembic current
```

Desde `0003`, `downgrade -1` elimina únicamente las dos columnas nuevas; se niega a ejecutarse si hay Documents para evitar pérdida de contenido. No bajar de `0002`: su reversión eliminaría `admin_users`. El ciclo mostrado solo debe ejecutarse en una base local de desarrollo sin Documents.

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

`templates.name` y `documents.slug` son únicos. `(document_id, order_index)` es único en `canvas_blocks`. DocumentService permite eliminar físicamente solo BORRADOR, nunca PUBLICADO ni ARCHIVADO.

JSONB almacena `metadata_contract`, `layout_structure`, `frozen_template`, `metadata_values`, `content_payload`, `style_config` y `findings`. `latest_review` se obtendrá de `review_reports` por `audited_at DESC`, sin columna duplicada. No hay tablas para MetricSnapshot ni PreviewSession.

Los identificadores se almacenan como UUID de PostgreSQL. El contrato exige UUIDv7, generado en la aplicación por bootstrap administrativo y TemplateService; no hay UUIDv4 ni defaults de UUID en la base. Las operaciones futuras deben suministrar timestamps explícitos con zona horaria.

El CHECK histórico conserva BORRADOR/EN_REVISION/PUBLICADO/ARCHIVADO para compatibilidad con `0001`. El contrato activo solo admite BORRADOR/PUBLICADO/ARCHIVADO y content_type POST/LANDING. No hay flujo EN_REVISION ni operaciones de bloques. Los tipos de metadatos son STRING/INTEGER/BOOLEAN/DATE.

La Session factory permite `session.begin()`. TemplateService y DocumentService administran transacciones completas; los repositorios solo hacen flush. Las mutaciones de Documents bloquean su fila para serializar edición/publicación/archivado; la validación mantiene estable la Template asociada con un bloqueo de lectura. Autenticación conserva su propia sesión.

El catálogo puede comenzar vacío. La primera Template se crea manualmente por POST y debe enviar `is_default=true`; de lo contrario recibe `422`. TemplateService conserva exactamente una default cuando existe contenido y bloquea el borrado de la última Template. Serializa las escrituras mediante `LOCK TABLE templates IN SHARE ROW EXCLUSIVE MODE`, incluso con catálogo vacío, y usa una sola transacción para cada transferencia. Las lecturas normales siguen permitidas; las escrituras administrativas esperan su turno. No se generan seeds ni una primera Template automáticamente.

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

Las pruebas de integración revierten sus transacciones; las pruebas HTTP y administrativas usan copias pg_temp, sin modificar registros reales. Las pruebas de 0003 ejecutan backfill, rechazo de downgrade con filas y ciclo vacío exclusivamente sobre Documents temporales. Se verifican constraints, FK, JSONB, timestamps, HTTP y rollback.

Validación del 2026-10-25 sobre PostgreSQL 18.6 nativo en Windows: `SELECT 1`, las migraciones online `0001` y `0002`, el ciclo `0002 → 0001 → 0002`, los tipos y operaciones JSONB, las claves foráneas y las restricciones UNIQUE se comprobaron contra la base real. La base quedó en `0002_add_admin_users` y los datos ficticios se revirtieron.

La validación de persistencia con `python -m unittest discover -s tests -v` finalizó con **45 passed, 0 failed, 0 skipped**; las 19 pruebas de integración se ejecutaron. El test de borrado de una Template referenciada espera correctamente SQLSTATE `23001` para `RESTRICT` en PostgreSQL 18; los casos de referencias inexistentes conservan `23503`.

Baselines anteriores: autenticación 163/0/0 y Templates 218/0/0. La suite completa actual finaliza con **289 passed, 0 failed, 0 skipped**. Las 71 pruebas nuevas de Documents cubren 60 casos HTTP (CREATE 15, LIST/GET 8, UPDATE 8, PUBLISH 7, edición publicada 6, ARCHIVE 5, DELETE 5, autorización 2, rollback 4), 5 de metadatos, 3 de OpenAPI y 3 de migración. El administrador real y la Template real mantienen todos sus campos; Documents termina con cero filas.

## Autenticación administrativa

El CMS utiliza usuarios administrativos propios mediante `username + password`. El hashing y la verificación Argon2id están implementados con `PasswordHash.recommended()` de pwdlib, sin parámetros criptográficos manuales. El login HTTP emite un JWT de acceso. `/auth/me` y las cuatro operaciones de Templates requieren Bearer mediante `get_current_admin`; no se modifica el contrato JWT ni se agrega protección global.

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

La validación histórica de bootstrap y configuración finalizó con 89/0/0. Sigue pasando dentro de las 289 pruebas actuales. Settings funciona sin DATABASE_URL heredada, conectado a cms_core como cms_user. HEAD actual: `0003_simplify_documents`; no se modificó el administrador real.

`cms-admin` será una aplicación privada separada del sitio público Quarto. Todavía no se crea su carpeta ni se añade a navegación, sitemap o `docs/`. Los futuros endpoints editoriales deberán incorporar su autorización explícita; el login y `/auth/me` ya están disponibles.

## Organización y contratos pendientes

| Carpeta | Responsabilidad |
| --- | --- |
| `app/api/v1/` | Agregador y routers REST |
| `app/core/` | Configuración, hashing Argon2id, JWT y excepciones |
| `app/domain/` | Modelos preliminares y estados del dominio |
| `app/schemas/` | Contratos de autenticación y schemas editoriales preliminares |
| `app/services/` | AuthService, TemplateService, bootstrap y futuros casos de uso |
| `app/repositories/` | Abstracciones para persistencia |
| `app/infrastructure/database/` | Base, sesiones, ORM, repositorio y entrada explícita al bootstrap |
| `app/cli/` | Bootstrap interactivo del primer administrador |
| `alembic/` | Migraciones y esquema inicial |
| `tests/` | Pruebas de estructura e integración PostgreSQL |
| `postman/` | Preparación de pruebas manuales |
| `api-docs/` | Plan técnico |

Templates y Documents tienen schemas, repositorios, servicios y rutas protegidas. Document usa contenido Markdown como string; frozen_template, CanvasBlock y ReviewReport se conservan físicamente por compatibilidad, sin exponerlos en este contrato ni ampliar sus operaciones. No se modifican los contratos HTTP de autenticación.

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

Los valores `TU_USUARIO`, `TU_PASSWORD` y `TU_ACCESS_TOKEN` son marcadores, no credenciales. No guardes contraseñas ni tokens reales en colecciones exportadas, ejemplos o archivos del repositorio. Esta fase documenta la configuración manual de Postman; no incorpora una colección exportada.

### Templates simplificadas del Blog Personal

Una Template define metadatos y un objeto JSON de estructura reutilizable. `POST` corresponde a publicaciones del blog y `LANDING` a la página profesional. Los tipos de metadatos admitidos son exclusivamente `STRING`, `INTEGER`, `BOOLEAN`, `DATE`. `metadata_contract` necesita al menos un elemento, claves no vacías y sin duplicados; cada elemento contiene solo `field_key`, `expected_type`, `is_required`. Se recortan espacios exteriores de `name` y `field_key`; los nombres son únicos y distinguen mayúsculas. Los booleanos deben ser booleanos JSON. `layout_structure` admite cualquier objeto JSON, incluso vacío: no hay motor de layouts.

Es una adaptación académica del ejemplo docente: no incluye Idempotency-Key, timeout HTTP explícito de 10 segundos, cursor, limit, fallback, reasignación de Documents ni autenticación de servicios Preview. No se agregan ReviewReport, métricas, WebSockets ni pipelines. El esquema ya existente se conserva.

| Operación | Resultado | Reglas principales |
| --- | --- | --- |
| POST `/api/v1/templates` | `201`, Template completa | Primera default obligatoria; name duplicado `409`; validación `422` |
| GET `/api/v1/templates` | `200`, `{"items": [...]}` | Todas, filtro opcional target_type; orden created_at ASC y UUID ASC para empates |
| PUT `/api/v1/templates/{template_id}` | `200`, Template completa | Reemplaza los cuatro campos editables; inexistente `404`, name duplicado `409`, dejar cero defaults `422` |
| DELETE `/api/v1/templates/{template_id}` | `200`, `{"deleted_template_id": "UUID"}` | Inexistente `404`; última o referenciada por cualquier Document `409` |

Las cuatro rutas requieren Bearer: ausente/inválido `401`, administrador inactivo `403`. Los errores operativos de persistencia devuelven un `503` genérico. Las respuestas de Template contienen los ocho campos públicos, con UUIDv7 y `created_at` UTC. PUT admite exclusivamente `name`, `is_default`, `metadata_contract`, `layout_structure`: enviar identidad, fecha, target_type, allow_published_edit u otros campos produce `422` por `extra="forbid"`.

Crear o actualizar otra Template con `is_default=true` transfiere el default atómicamente. Eliminar la default selecciona la restante más antigua; los empates se resuelven por UUID ASC. Si hay Documents asociados, se rechaza sin cambiar ninguna fila, sin importar su estado; `ON DELETE RESTRICT` sigue siendo la protección final. Se recomienda `allow_published_edit=false` para POST y `true` para LANDING, pero la API acepta el booleano enviado y lo conserva inmutable.

### Postman: carpeta 02 - Templates

Crea una colección `Blog-personal` con carpetas `01 - Auth` (POST Login, GET Current Admin) y `02 - Templates`. Configura estas variables localmente:

| Variable | Valor |
| --- | --- |
| `base_url` | `http://127.0.0.1:8000` |
| `access_token` | Token que obtengas manualmente mediante login; no exportarlo |
| `template_id` | UUID devuelto por POST o GET |

En `02 - Templates`, selecciona **Authorization → Bearer Token → `{{access_token}}`**. En las cuatro peticiones selecciona **Inherit auth from parent**. No configures Idempotency-Key. Los ejemplos siguientes son ficticios; no se ejecutan automáticamente.

**POST Create Template:** `{{base_url}}/api/v1/templates`, **Body → raw → JSON**. Para inicializar un catálogo vacío:

```json
{
  "name": "Plantilla Post",
  "target_type": "POST",
  "is_default": true,
  "allow_published_edit": false,
  "metadata_contract": [
    {"field_key": "category", "expected_type": "STRING", "is_required": true},
    {"field_key": "reading_time", "expected_type": "INTEGER", "is_required": false}
  ],
  "layout_structure": {"sections": ["header", "content"]}
}
```

Espera `201`. Para crear una segunda Template LANDING sin cambiar el default, usa:

```json
{
  "name": "Plantilla Landing",
  "target_type": "LANDING",
  "is_default": false,
  "allow_published_edit": true,
  "metadata_contract": [
    {"field_key": "title", "expected_type": "STRING", "is_required": true}
  ],
  "layout_structure": {"sections": ["hero", "about", "projects", "certifications"]}
}
```

Guarda el UUID de esa segunda respuesta como `template_id` para practicar PUT y DELETE conservando la primera.

**GET List Templates:** `{{base_url}}/api/v1/templates`, sin body. Espera `200` con `items`; prueba también `?target_type=POST` o `?target_type=LANDING`. No envíes cursor ni limit.

**PUT Update Template:** `{{base_url}}/api/v1/templates/{{template_id}}`, **Body → raw → JSON**:

```json
{
  "name": "Plantilla Landing Principal",
  "is_default": true,
  "metadata_contract": [
    {"field_key": "title", "expected_type": "STRING", "is_required": true},
    {"field_key": "updated_on", "expected_type": "DATE", "is_required": false},
    {"field_key": "show_projects", "expected_type": "BOOLEAN", "is_required": false}
  ],
  "layout_structure": {"sections": ["hero", "about", "projects"]}
}
```

Espera `200`; GET debe mostrar exactamente una default, ahora la LANDING. Los cuatro campos editables son obligatorios en PUT.

**DELETE Template:** `{{base_url}}/api/v1/templates/{{template_id}}`, sin body. Si quedan al menos dos Templates y la seleccionada no tiene Documents, espera `200` con `deleted_template_id`; si es la última o está utilizada, espera `409`. Ya existe una Template creada manualmente por el usuario y se conserva intacta.

PATCH permanece `CONTRACT_PENDING`. Live Preview requiere WebSocket y no se implementa todavía. Tampoco se integran un servicio analítico ni un agente de revisión.

### Documents y publicación local

Document contiene once campos públicos: `document_id`, `title`, `slug`, `content_type`, `status`, `template_id`, `metadata_values`, `content`, `created_at`, `updated_at`, `published_at`. Los UUID son v7 y las fechas UTC. `content` guarda Markdown como string; no genera HTML ni QMD. Los estados activos son BORRADOR/PUBLICADO/ARCHIVADO y los tipos POST/LANDING.

Al crear, el título no puede estar vacío, el slug es único global y debe cumplir `^[a-z0-9]+(?:-[a-z0-9]+)*$`. La Template debe existir y coincidir con content_type. El borrador puede tener contenido vacío y omitir metadatos requeridos; cada metadato presente debe existir en el contrato y cumplir su tipo. INTEGER no acepta bool ni números decimales; BOOLEAN requiere booleanos JSON; DATE requiere una fecha válida YYYY-MM-DD. Publicar exige contenido no vacío y todos los campos requeridos.

POST PUBLICADO es **inmutable incluso con allow_published_edit=true**. LANDING PUBLICADO admite PUT cuando su Template permite edición; si cambia de Template, tanto la actual como la nueva deben permitirla. Esta decisión evita eludir la restricción mediante un cambio de Template. La edición publicada debe conservar contenido y metadatos válidos, y mantiene published_at. ARCHIVADO es terminal, no editable. Solo BORRADOR admite DELETE físico.

Errores: sin Bearer/inválido 401, cuenta inactiva 403, Document/Template inexistente 404, slug duplicado o estado incompatible 409, datos inválidos 422 y persistencia indisponible 503 genérico. Cada mutación es transaccional. Publicar establece published_at/updated_at; archivar solo cambia status/updated_at.

### Postman: carpeta 03 - Documents

Dentro de `Blog-personal`, crea **03 - Documents**. Configura **Authorization → Bearer Token → `{{access_token}}`** en la carpeta y **Inherit auth from parent** en las siete peticiones. Variables locales: `base_url=http://127.0.0.1:8000`, `access_token`, `document_id`, `post_template_id`, `landing_template_id`. Obtén los UUID de Templates mediante GET `/api/v1/templates`; deben corresponder al tipo indicado. La LANDING de prueba debe tener allow_published_edit=true. Los ejemplos siguientes presuponen los contratos category/reading_time y title de la sección Templates; adapta sus metadatos si tus contratos difieren.

| Petición | URL | Body | Resultado |
| --- | --- | --- | --- |
| POST Create Document | `{{base_url}}/api/v1/documents` | JSON POST o LANDING de abajo | 201 |
| GET List Documents | `{{base_url}}/api/v1/documents` | Ninguno | 200, items |
| GET Get Document | `{{base_url}}/api/v1/documents/{{document_id}}` | Ninguno | 200 |
| PUT Update Document | `{{base_url}}/api/v1/documents/{{document_id}}` | Los cinco campos editables | 200 |
| POST Publish Document | `{{base_url}}/api/v1/documents/{{document_id}}/publish` | Ninguno | 200 |
| POST Archive Document | `{{base_url}}/api/v1/documents/{{document_id}}/archive` | Ninguno | 200 |
| DELETE Document | `{{base_url}}/api/v1/documents/{{document_id}}` | Ninguno | 204 vacío, solo borrador |

GET List acepta `?content_type=POST&status=PUBLICADO` o cualquiera de los filtros por separado; sin paginación. Orden: created_at ASC y document_id ASC para empates.

En **Scripts → Post-response** de POST Create Document:

```javascript
if (pm.response.code === 201) {
  pm.collectionVariables.set("document_id", pm.response.json().document_id);
}
```

**Body → raw → JSON**, ejemplo POST ficticio:

```json
{
  "title": "Post de prueba manual",
  "slug": "post-prueba-manual",
  "content_type": "POST",
  "template_id": "{{post_template_id}}",
  "metadata_values": {"category": "Pruebas", "reading_time": 3},
  "content": "# Post de prueba\n\nContenido ficticio de validación."
}
```

Ejemplo LANDING ficticio:

```json
{
  "title": "Landing de prueba manual",
  "slug": "landing-prueba-manual",
  "content_type": "LANDING",
  "template_id": "{{landing_template_id}}",
  "metadata_values": {"title": "Página de prueba"},
  "content": "# Página de prueba\n\nContenido ficticio editable."
}
```

Para PUT envía el mismo JSON del Document elegido **sin content_type**, conservando los otros cinco campos: title, slug, template_id, metadata_values, content. Cambia title/content para comprobar la edición. No envíes status, fechas ni document_id: producen 422. No uses el ejemplo completo de POST como body de PUT.

Flujo manual: crea POST → PUT de borrador (200) → publish (200) → PUT (409) → archive (200) → PUT/publish/DELETE (409). Crea LANDING → publish → PUT (200 si allow_published_edit=true, conservando published_at) → archive → PUT (409). Para probar DELETE 204, crea otro borrador con slug diferente y elimínalo antes de publicar. Las pruebas manuales de publicación dejan registros deliberadamente persistidos, que luego solo pueden archivarse por esta API.

**Publicar todavía no modifica Quarto.** No se importan artículos históricos, no se escriben QMD, no se ejecuta `quarto render` ni se despliega. La futura integración podrá mapear LANDING inicio a `/` y sobre-mi a `/sobre-mi`; Contenido será el listado de POST PUBLICADO, no otro Document. QUARTO_SYNC, LEGACY_POST_IMPORT, Public content API y cms-admin siguen pendientes. PATCH continúa CONTRACT_PENDING.

Consulta [el plan de implementación](api-docs/implementation-plan.md) y [las convenciones de Postman](postman/README.md).
