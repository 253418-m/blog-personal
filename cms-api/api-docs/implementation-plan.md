# Plan de implementación de cms-core-api

La API implementa el login JSON y la consulta del administrador autenticado mediante JWT Bearer. Los routers editoriales siguen sin operaciones activas. Esta fase reutiliza PostgreSQL sin modificar el esquema ni contenido Quarto. La documentación técnica permanece en `cms-api/api-docs/`; `docs/` en la raíz es salida generada de Quarto para GitHub Pages.

## Estado actual

| Entrega | Estado | Alcance |
| --- | --- | --- |
| Persistencia PostgreSQL | `IMPLEMENTED` | PostgreSQL 18.6 nativo en Windows, SQLAlchemy 2.x, psycopg, Base, engine, Session factory, cuatro modelos editoriales y AdminUser; Compose PostgreSQL 16 como alternativa |
| Migración inicial | `IMPLEMENTED` | Alembic y revisión `initial_cms_schema` para cuatro tablas |
| Migración administrativa | `IMPLEMENTED` | `0002_add_admin_users`, dependiente de `0001`, sin alterar el esquema editorial |
| PostgreSQL native Windows | `IMPLEMENTED` | Servicio nativo Windows validado en localhost:5432, base cms_core y usuario cms_user |
| PostgreSQL runtime validation | `IMPLEMENTED` | Conexión real SQLAlchemy/psycopg, SELECT 1, identidad de conexión y esquema físico verificados |
| Migration 0001 online validation | `IMPLEMENTED` | Aplicación online y cuatro tablas editoriales verificadas antes de crear admin_users |
| Migration 0002 online validation | `IMPLEMENTED` | Creación exclusiva de admin_users y ciclo 0002 → 0001 → 0002 validados; base en HEAD |
| Integration tests | `IMPLEMENTED` | Suite actual: 163 passed, 0 failed, 0 skipped; incluye 72 pruebas de integración PostgreSQL y 18 de configuración |
| Environment configuration | `IMPLEMENTED` | pydantic-settings, variables reales con precedencia y errores seguros sin fallback de base de datos |
| Automatic local .env loading | `IMPLEMENTED` | Ruta portable relativa al módulo; carga automática sin depender del cwd ni exportar DATABASE_URL manualmente |
| Centralized Settings | `IMPLEMENTED` | BaseSettings inmutable y en caché; get_settings/get_database_url compartidos por persistencia, Alembic y CLI |
| Persistence layer | `IMPLEMENTED` | UUID, JSONB, UNIQUE, FK, RESTRICT, CASCADE y timestamps validados contra PostgreSQL real |
| Bootstrap Template default | `CONTRACT_PENDING` | Mecanismo `BOOTSTRAP_PENDING`; faltan valores oficiales, sin seed ficticio |
| Endpoints CRUD | `PENDING` | Sin operaciones nuevas; schemas HTTP y casos de uso pendientes |
| Templates CRUD | `PENDING` | Contratos y casos de uso pendientes |
| Documents CRUD | `PENDING` | Contratos y casos de uso pendientes |
| PATCH contract | `CONTRACT_PENDING` | Sin ruta, cuerpo ni implementación |

La persistencia y las migraciones están aplicadas y validadas contra PostgreSQL real de desarrollo. El hashing Argon2id, el bootstrap administrativo, la configuración centralizada y la primera fase de autenticación HTTP están implementados. La primera cuenta real ya fue creada manualmente y se conserva sin cambios, incluido `last_login_at`; las pruebas de autenticación utilizan cuentas ficticias aisladas. Los endpoints de negocio permanecen pendientes. El procedimiento local está en [README.md](../README.md#base-de-datos).

## Persistencia implementada

Las tablas editoriales son `templates`, `documents`, `canvas_blocks` y `review_reports`; la tabla administrativa independiente es `admin_users`. Se almacenan identificadores como UUID, objetos contractuales como JSONB y fechas como timestamps con zona horaria. El bootstrap administrativo genera UUIDv7 con `uuid6` y timestamps UTC explícitos; los casos de uso editoriales futuros deberán seguir ese contrato. No hay UUIDv4 ni generación de identificadores en la base.

Restricciones estructurales:

- `UNIQUE templates.name`.
- `UNIQUE documents.slug`.
- `UNIQUE canvas_blocks(document_id, order_index)`.
- `documents.template_id → templates.template_id`, con `ON DELETE RESTRICT`.
- `canvas_blocks.document_id → documents.document_id`, con `ON DELETE CASCADE`.
- `review_reports.document_id → documents.document_id`, con `ON DELETE CASCADE`.
- NOT NULL según el diseño y estados `BORRADOR`, `EN_REVISION`, `PUBLICADO`, `ARCHIVADO` mediante CHECK.

JSONB se utiliza en `templates.metadata_contract`, `templates.layout_structure`, `documents.frozen_template`, `documents.metadata_values`, `canvas_blocks.content_payload`, `canvas_blocks.style_config` y `review_reports.findings`.

`latest_review` se obtendrá del reporte más reciente por `audited_at DESC`; no se duplica como columna. No se persisten MetricSnapshot ni PreviewSession.

Los catálogos de `target_type`, `content_type`, `block_type` y `expected_type` siguen `CONTRACT_PENDING`. Las columnas de los tres primeros usan texto; `expected_type` pertenece al contrato JSON de metadatos. No se crean enums cerrados incompletos.

Los tests de integración requieren `TEST_DATABASE_URL` apuntando a la base local `cms_core` previamente migrada. Se omiten cuando esa variable está ausente y revierten sus cambios mediante transacciones, sin borrar el esquema. El 2026-10-25, la validación inicial de persistencia ejecutó correctamente 45 pruebas, incluidas las 19 de integración: 45 passed, 0 failed, 0 skipped; entonces las tablas quedaron vacías. Actualmente existe un administrador real. Las 59 pruebas administrativas y HTTP con persistencia usan una tabla temporal privada por conexión, revertida al terminar, y no escriben en `public.admin_users`. La comparación de todos los campos del registro real antes y después confirma su conservación. El ciclo online `0002 → downgrade -1 → 0001 → upgrade head → 0002` ya fue validado anteriormente; no se repite sobre la cuenta real. La base continúa en `0002_add_admin_users (head)` y el esquema persistente no cambió.

## AUTENTICACIÓN ADMINISTRATIVA

| Entrega | Estado |
| --- | --- |
| AdminUser persistence | `IMPLEMENTED` |
| PostgreSQL persistence | `IMPLEMENTED` |
| username unique | `IMPLEMENTED` |
| password_hash storage | `IMPLEMENTED` |
| is_active | `IMPLEMENTED` |
| Argon2 password hashing | `IMPLEMENTED` |
| Argon2 | `IMPLEMENTED` |
| Admin bootstrap tooling | `IMPLEMENTED` |
| Admin bootstrap | `IMPLEMENTED` |
| Bootstrap status | `READY_FOR_MANUAL_EXECUTION` |
| First real admin | `IMPLEMENTED` |
| POST /api/v1/auth/login | `IMPLEMENTED` |
| GET /api/v1/auth/me | `IMPLEMENTED` |
| JWT access token | `IMPLEMENTED` |
| get_current_admin | `IMPLEMENTED` |
| Global endpoint protection | `PENDING` |
| cms-admin frontend | `PENDING` |
| cms-admin | `PENDING` |

La entidad contiene exactamente `user_id` (UUID), `username` (VARCHAR UNIQUE), `password_hash` (TEXT), `is_active` (BOOLEAN default true), `created_at`, `updated_at` y `last_login_at` (timestamps con zona horaria). Solo `last_login_at` admite NULL y comienza sin fecha. No hay roles, email, contraseñas en texto plano, tokens, sesiones ni relaciones nuevas con tablas editoriales.

La cadena es `0001_initial_cms_schema → 0002_add_admin_users`, con una sola HEAD. `0001` permanece intacta. Upgrade de `0002` crea exclusivamente `admin_users`; downgrade elimina exclusivamente esa tabla. El SQL de ambos rangos se valida offline contra los metadatos; no se insertan cuentas en migraciones. La aplicación y reversión también se validaron contra PostgreSQL real, sin crear cuentas permanentes.

El estado anterior `ADMIN_BOOTSTRAP_PENDING` pasa a `READY_FOR_MANUAL_EXECUTION`. `python -m app.cli.create_admin` solicita username y contraseña confirmada con `getpass`; no acepta `--password`, no imprime credenciales ni hashes y nunca se ejecuta desde FastAPI. El primer administrador real ya fue creado manualmente. Esta tarea no vuelve a ejecutar el bootstrap real ni modifica su registro; tampoco agrega credenciales al ejemplo de entorno. La CLI obtiene Settings mediante la Session existente, sin carga manual de .env adicional.

`AdminBootstrapService` valida username sin espacios exteriores y contraseña no vacía de al menos 12 caracteres, sin reglas de composición. Esta longitud es una decisión mínima de seguridad de implementación; la contraseña válida no se recorta. `PasswordHash.recommended()` produce Argon2id con salt aleatorio. El repositorio ofrece `get_by_username`, `exists_by_username`, `create`, `get_by_id` y `update_last_login`, sin confirmar transacciones por su cuenta.

La transacción del servicio usa un bloqueo PostgreSQL para serializar bootstraps bajo `READ COMMITTED`. Cualquier administrador existente, incluso inactivo, impide crear otro; un username duplicado no se modifica. Se generan UUIDv7, timestamps UTC y `is_active = true`, con `last_login_at = NULL`. Los errores hacen rollback y la CLI presenta mensajes seguros; el engine oculta parámetros SQL.

Validación actual: 163 passed, 0 failed, 0 skipped. Incluye 18 pruebas de configuración, 18 de JWT, 9 de AuthService, 17 de login HTTP, 14 de `/auth/me`, 4 de las nuevas operaciones del repositorio y 5 de contratos/OpenAPI, además de las pruebas anteriores de persistencia, hashing, bootstrap y CLI. Se usan exclusivamente datos ficticios aislados y transacciones revertidas. Se verificaron precedencia del entorno sobre .env, protección de secretos, caché y errores explícitos si faltan DATABASE_URL o JWT_SECRET_KEY. `pip check` y `compileall app` pasan. El administrador real y el esquema persistente permanecen intactos; Alembic continúa en `0002_add_admin_users (head)`.

`POST /api/v1/auth/login` es público y acepta JSON con username/password. AuthService normaliza espacios exteriores del username, verifica Argon2 y el estado activo, actualiza únicamente `last_login_at` con UTC y confirma la transacción antes de emitir un token. La actualización exige que la cuenta siga activa, por si se desactiva durante la verificación. Usuario inexistente ejecuta igualmente una verificación contra un hash Argon2id ficticio. Usuario ausente, contraseña incorrecta y cuenta inactiva reciben el mismo 401 y `WWW-Authenticate: Bearer`. Los errores de persistencia no emiten tokens; los errores de validación HTTP no devuelven el cuerpo de login.

PyJWT firma access tokens exclusivamente con HS256. Los claims son `sub` (UUID del administrador), `iat`, `exp` y `type="access"`. Se exige firma válida, los cuatro claims, expiración y un subject UUID. Settings requiere JWT_SECRET_KEY protegido con SecretStr, sin fallback; el TTL positivo es configurable y vale 30 minutos por defecto. La clave local fue generada con entropía de 32 bytes y permanece únicamente en el .env ignorado. No se guardan JWT en PostgreSQL.

`get_current_admin` valida Bearer y consulta el administrador en PostgreSQL. Token ausente o inválido, o usuario inexistente, producen 401; una cuenta inactiva con token válido produce 403. `GET /api/v1/auth/me` devuelve exclusivamente user_id, username e is_active y es el único endpoint protegido. OpenAPI declara ambos endpoints y el esquema HTTP Bearer. La protección global, el frontend privado y los casos de uso editoriales siguen pendientes. El procedimiento manual de Postman está documentado en README; no se realizó login con la cuenta real.

## Bootstrap y límites transaccionales

Estado del mecanismo: `BOOTSTRAP_PENDING`. Estado del contrato de la plantilla inicial: `CONTRACT_PENDING`.

La migración no inserta plantillas arbitrarias. Antes del bootstrap deben definirse los valores oficiales de la Template inicial, incluidos su contrato de metadatos y estructura.

Las invariantes «al menos una Template» y «exactamente una default» deberán coordinarse en services dentro de transacciones, con bloqueo adecuado para concurrencia. Un CHECK por fila no garantiza estas invariantes. La Session factory permite preparar operaciones con `SessionLocal.begin()`; todavía no se implementa esa lógica de negocio.

La BD protege integridad estructural. Inmutabilidad, transiciones, eliminación de documentos publicados y validación completa de metadatos deberán resolverse en dominio/services. Las cascadas internas no sustituyen esas reglas.

## FASE 1 — Templates

Estado de endpoints: `PENDING`.

- `POST /api/v1/templates`
- `GET /api/v1/templates`
- `PUT /api/v1/templates/{template_id}`
- `DELETE /api/v1/templates/{template_id}`

El contrato de persistencia define `template_id`, `name`, `target_type`, `is_default`, `allow_published_edit`, `metadata_contract`, `layout_structure` y `created_at`. Los identificadores son UUIDv7 generados por la aplicación. Antes de implementar rutas, completar los cuerpos Create, Update y Response y el catálogo de `target_type`. Los modelos de dominio y schemas Pydantic iniciales continúan preliminares y no están conectados a endpoints.

Reglas pendientes de servicios y pruebas:

- Mantener al menos una Template y exactamente una default dentro de una transacción.
- Mantener `target_type` y `allow_published_edit` inmutables tras la creación.
- Validar que `metadata_contract` no esté vacío y cumpla su estructura contractual.
- Reasignar documentos según contrato antes de eliminar una Template referenciada.

## FASE 2 — Documents

Estado de endpoints: `PENDING`.

- `POST /api/v1/documents`
- `GET /api/v1/documents/{document_id}`
- `PUT /api/v1/documents/{document_id}`
- `DELETE /api/v1/documents/{document_id}`

El contrato define `document_id`, `slug`, `title`, `content_type`, `status`, `template_id`, `frozen_template`, `metadata_values`, `canvas_blocks`, `latest_review`, `updated_at` y `published_at`. `canvas_blocks` corresponde a la relación ordenada y `latest_review` se deriva de reportes. Los identificadores son UUIDv7. Completar los cuerpos por operación, catálogos y validación de objetos JSON antes de activar rutas. No inferir campos desde Quarto.

Reglas pendientes de servicios y pruebas:

- Un Document debe contener uno o más CanvasBlock ordenados.
- `ARCHIVADO` es terminal.
- `PUBLICADO` no vuelve a `BORRADOR` ni a `EN_REVISION`.
- `PUBLICADO` y `ARCHIVADO` no pueden eliminarse físicamente.
- Un documento `DEV_BLOG` publicado es inmutable.
- Un borrador del Blog Dev puede editarse; un post ya alcanzó `PUBLICADO` y nunca vuelve a ser borrador.

La BD prepara la unicidad de `slug`, las referencias y el orden único de bloques por Document. Estas restricciones no garantizan al menos un bloque ni las transiciones.

## FASE 3 — Workflow

Estado: `PENDING`.

- `POST /api/v1/documents/{document_id}/submit-review`
- `POST /api/v1/documents/{document_id}/review-report`
- `POST /api/v1/documents/{document_id}/publish`
- `POST /api/v1/documents/{document_id}/archive`

Transiciones permitidas:

| Desde | Hacia |
| --- | --- |
| `BORRADOR` | `EN_REVISION` |
| `EN_REVISION` | `BORRADOR` |
| `EN_REVISION` | `PUBLICADO` |
| `BORRADOR` | `PUBLICADO` |
| `PUBLICADO` | `ARCHIVADO` |

`PUBLICADO → BORRADOR`, `PUBLICADO → EN_REVISION` y cualquier salida de `ARCHIVADO` están prohibidas. Estas reglas corresponden al futuro servicio, no al CHECK de estados.

ReviewReport tiene definidos `report_id`, `findings` y `audited_at`, con pertenencia a un Document en persistencia. Queda pendiente detallar `findings`, cuerpos y respuestas por operación, relación con transiciones, errores e idempotencia. No se implementa un agente de revisión.

## FASE 4 — Live Preview

Estado: `PENDING`.

Referencia: `GET /api/v1/documents/{document_id}/live-preview` con upgrade a WebSocket.

Definir PreviewSession, handshake, mensajes, ciclo de vida y errores antes de implementar. No hay tabla para sesiones temporales ni endpoint HTTP de relleno.

## FASE 5 — Metrics

Estado: `PENDING`.

- `GET /api/v1/documents/{document_id}/metrics`

Definir MetricSnapshot, parámetros, respuesta, errores y comportamiento ante indisponibilidad del servicio analítico. Ese servicio será la fuente de verdad; las métricas no se almacenan en esta base.

## FASE 6 — PATCH

Estado: `CONTRACT_PENDING`.

Antes de implementarlo definir:

- Recurso.
- Campos modificables.
- Estados permitidos.
- Request.
- Response.
- Errores.
- Idempotencia, si aplica.

No se define una ruta PATCH, cuerpo ni estados editables hasta cerrar su contrato.

## Criterios transversales pendientes

Mantener rutas y semántica HTTP. Usar path parameters para identidad, query parameters para filtros contractuales y JSON cuando corresponda. Las respuestas serán JSON salvo las explícitamente sin contenido.

Precisar por operación los códigos aplicables entre `200`, `201`, `202`, `204`, `404`, `409`, `422`, `500` y `504`. Separar invariantes del dominio de fallos operativos. La traducción HTTP de ResourceNotFound, DomainConflict, InvalidTransition y BusinessRuleViolation sigue pendiente.

Siguen pendientes CRUD, publicación, archivado, borrado, revisión, idempotencia e integración analítica. La autenticación implementada se limita a login JSON, access token JWT y `/auth/me`. El siguiente paso es verificar manualmente este flujo y cerrar el contrato del bootstrap oficial de Templates antes de implementar sus operaciones y protección.
