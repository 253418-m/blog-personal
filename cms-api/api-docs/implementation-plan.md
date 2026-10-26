# Plan de implementación de cms-core-api

La API implementa login, Templates y Documents con JWT Bearer. Publicar un POST exporta QMD, renderiza el sitio Quarto completo a staging, actualiza `docs/` y después confirma PostgreSQL. LANDING continúa publicándose solo en la base. La migración 0003 permanece vigente y esta fase no añade migraciones.

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
| Integration tests | `IMPLEMENTED` | Suite actual: 326 passed, 0 failed, 0 skipped; baseline de esta fase 324/0/0 |
| Environment configuration | `IMPLEMENTED` | pydantic-settings, variables reales con precedencia y errores seguros sin fallback de base de datos |
| Automatic local .env loading | `IMPLEMENTED` | Ruta portable relativa al módulo; carga automática sin depender del cwd ni exportar DATABASE_URL manualmente |
| Centralized Settings | `IMPLEMENTED` | BaseSettings inmutable y en caché; get_settings/get_database_url compartidos por persistencia, Alembic y CLI |
| Persistence layer | `IMPLEMENTED` | UUID, JSONB, UNIQUE, FK, RESTRICT, CASCADE y timestamps validados contra PostgreSQL real |
| Primera Template real | `IMPLEMENTED` | Una Template creada manualmente por el usuario; conservada íntegramente |
| Template enums | `IMPLEMENTED` | POST/LANDING y STRING/INTEGER/BOOLEAN/DATE |
| Template schemas | `IMPLEMENTED` | Requests estrictos, metadatos no vacíos y claves únicas |
| Template repository | `IMPLEMENTED` | Protocolo y SQLAlchemy usando la Session existente |
| Template service | `IMPLEMENTED` | Invariantes y transacciones completas, sin HTTPException |
| Template CRUD | `IMPLEMENTED` | POST/GET/PUT/DELETE, sin paginación ni idempotencia |
| Template authorization | `IMPLEMENTED` | Las cuatro operaciones usan get_current_admin |
| Documents CRUD | `IMPLEMENTED` | POST, GET colección/detalle, PUT y DELETE de borradores |
| Workflow | `IMPLEMENTED` | BORRADOR → PUBLICADO → ARCHIVADO; exportación QMD únicamente al publicar POST |
| Document enums | `IMPLEMENTED` | POST/LANDING; BORRADOR/PUBLICADO/ARCHIVADO |
| Document schemas | `IMPLEMENTED` | Requests estrictos y respuesta de once campos |
| Document repository | `IMPLEMENTED` | SQLAlchemy, filtros y orden estable |
| Document service | `IMPLEMENTED` | Transacciones, reglas y traducción de errores |
| POST immutability | `IMPLEMENTED` | PUBLICADO nunca editable, incluso con allow_published_edit=true |
| LANDING published editing | `IMPLEMENTED` | Solo con permiso de la Template; conserva published_at |
| Metadata validation | `IMPLEMENTED` | Tipos exactos, campos conocidos y requeridos al publicar |
| Migration 0003 online validation | `IMPLEMENTED` | Ciclo 0002 → 0003 → 0002 → 0003 y datos reales intactos |
| Quarto POST exporter | `IMPLEMENTED` | Archivo nuevo `posts/<slug>/index.qmd` |
| POST publish → QMD | `IMPLEMENTED` | Exportar antes del commit, compensar fallo posterior |
| Quarto collision protection | `IMPLEMENTED` | Nunca sobrescribir directorios existentes |
| Quarto CLI renderer | `IMPLEMENTED` | Render completo a staging mediante subprocess, timeout configurable |
| POST publish → Quarto render | `IMPLEMENTED` | Verificar HTML antes de PUBLICADO |
| Render compensation | `IMPLEMENTED` | Backup y restauración de docs/ ante fallo |
| Local static output generation | `IMPLEMENTED` | Sustitución completa de docs/ tras render correcto |
| Quarto backend isolation | `IMPLEMENTED` | `project.render` limita las páginas a raíz, posts y proyectos públicos; `project.resources` limita los recursos |
| Internal CMS content exclusion | `IMPLEMENTED` | `cms-api/` y staging quedan fuera de HTML, recursos, búsqueda y output; verificado en copias temporales |
| Automatic Content catalog | `IMPLEMENTED` | Listing grid nativo de Quarto, ordenado por `date desc`; PuraVida conserva su tarjeta manual |
| Quarto post discovery | `IMPLEMENTED` | `posts/*/index.qmd` incluye posts históricos y CMS; el scaffold `draft: true` queda fuera |
| GitHub Pages deployment integration | `PENDING` | Sin commit, push ni deploy |
| LANDING → Quarto | `PENDING` | Inicio y Sobre mí continúan intactos |
| Archive → Quarto sync | `PENDING` | ARCHIVE_QUARTO_SYNC pendiente |
| Legacy QMD import | `PENDING` | LEGACY_POST_IMPORT pendiente |
| Public content API | `PENDING` | Sin rutas públicas nuevas |
| PATCH contract | `CONTRACT_PENDING` | Sin ruta, cuerpo ni implementación |

La persistencia está validada contra PostgreSQL local. Al cierre de esta validación la base contiene un administrador, dos Templates y cinco Documents; las pruebas usan datos ficticios temporales y no crean seeds. HEAD actual: `0003_simplify_documents`.

## Persistencia implementada

Las tablas editoriales son `templates`, `documents`, `canvas_blocks` y `review_reports`; la tabla administrativa independiente es `admin_users`. Se almacenan identificadores como UUID, objetos contractuales como JSONB y fechas como timestamps con zona horaria. El bootstrap administrativo y TemplateService generan UUIDv7 con `uuid6` y timestamps UTC explícitos; los casos de uso editoriales futuros deberán seguir ese contrato. No hay UUIDv4 ni generación de identificadores en la base.

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

El contrato activo fija TemplateTargetType y DocumentContentType POST/LANDING, MetadataExpectedType STRING/INTEGER/BOOLEAN/DATE y DocumentStatus BORRADOR/PUBLICADO/ARCHIVADO. El CHECK físico histórico mantiene EN_REVISION por compatibilidad; no se expone en el flujo activo. No se implementan bloques.

Los tests de integración requieren TEST_DATABASE_URL local y la base migrada. Sin esa activación se omiten; en esta validación se ejecutaron todos. Las pruebas HTTP y administrativas usan tablas pg_temp y rollback. El ciclo histórico 0002 → 0001 → 0002 no se repite sobre cuentas reales. Se validó 0002 → 0003 → 0002 → 0003, conservando todos los datos reales.

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

La cadena es `0001_initial_cms_schema → 0002_add_admin_users → 0003_simplify_documents`, con una sola HEAD. Las migraciones 0001 y 0002 no se modificaron. 0003 agrega content y created_at; su downgrade rechaza cualquier Document existente para impedir pérdida de datos.

El estado anterior `ADMIN_BOOTSTRAP_PENDING` pasa a `READY_FOR_MANUAL_EXECUTION`. `python -m app.cli.create_admin` solicita username y contraseña confirmada con `getpass`; no acepta `--password`, no imprime credenciales ni hashes y nunca se ejecuta desde FastAPI. El primer administrador real ya fue creado manualmente. Esta tarea no vuelve a ejecutar el bootstrap real ni modifica su registro; tampoco agrega credenciales al ejemplo de entorno. La CLI obtiene Settings mediante la Session existente, sin carga manual de .env adicional.

`AdminBootstrapService` valida username sin espacios exteriores y contraseña no vacía de al menos 12 caracteres, sin reglas de composición. Esta longitud es una decisión mínima de seguridad de implementación; la contraseña válida no se recorta. `PasswordHash.recommended()` produce Argon2id con salt aleatorio. El repositorio ofrece `get_by_username`, `exists_by_username`, `create`, `get_by_id` y `update_last_login`, sin confirmar transacciones por su cuenta.

La transacción del servicio usa un bloqueo PostgreSQL para serializar bootstraps bajo `READ COMMITTED`. Cualquier administrador existente, incluso inactivo, impide crear otro; un username duplicado no se modifica. Se generan UUIDv7, timestamps UTC y `is_active = true`, con `last_login_at = NULL`. Los errores hacen rollback y la CLI presenta mensajes seguros; el engine oculta parámetros SQL.

Baselines de autenticación 163/0/0, Templates 218/0/0, Documents 289/0/0 y exportación QMD 306/0/0. Todas las regresiones pasan dentro de la suite actual 326/0/0. Alembic está en `0003_simplify_documents (head)`.

`POST /api/v1/auth/login` es público y acepta JSON con username/password. AuthService normaliza espacios exteriores del username, verifica Argon2 y el estado activo, actualiza únicamente `last_login_at` con UTC y confirma la transacción antes de emitir un token. La actualización exige que la cuenta siga activa, por si se desactiva durante la verificación. Usuario inexistente ejecuta igualmente una verificación contra un hash Argon2id ficticio. Usuario ausente, contraseña incorrecta y cuenta inactiva reciben el mismo 401 y `WWW-Authenticate: Bearer`. Los errores de persistencia no emiten tokens; los errores de validación HTTP no devuelven el cuerpo de login.

PyJWT firma access tokens exclusivamente con HS256. Los claims son `sub` (UUID del administrador), `iat`, `exp` y `type="access"`. Se exige firma válida, los cuatro claims, expiración y un subject UUID. Settings requiere JWT_SECRET_KEY protegido con SecretStr, sin fallback; el TTL positivo es configurable y vale 30 minutos por defecto. La clave local fue generada con entropía de 32 bytes y permanece únicamente en el .env ignorado. No se guardan JWT en PostgreSQL.

`get_current_admin` valida Bearer y consulta el administrador en PostgreSQL. Token ausente o inválido, o usuario inexistente, producen 401; una cuenta inactiva con token válido produce 403. `GET /api/v1/auth/me` devuelve exclusivamente user_id, username e is_active. También se protegen explícitamente las cuatro operaciones de Templates; login sigue público y no se agrega protección global. OpenAPI mantiene HTTP Bearer. JWT y Argon2 no cambiaron. El procedimiento manual está en README; no se realizó login con la cuenta real durante los tests.

## Bootstrap y límites transaccionales

El catálogo comienza vacío y se inicializa mediante POST manual con `is_default=true`. La solicitud con `false` recibe 422; no se altera silenciosamente el input. No se ejecuta el marcador histórico `bootstrap.py`, no se insertan seeds y no se crea contenido al iniciar FastAPI.

TemplateService garantiza exactamente una default después de inicializar el catálogo y prohíbe borrar su última fila. Todas las escrituras toman `LOCK TABLE templates IN SHARE ROW EXCLUSIVE MODE` antes de consultar el catálogo y usan `session.begin()`. El bloqueo serializa escrituras incluso con cero filas y permite lecturas normales. Cada cambio de default se confirma junto con la operación completa; errores de persistencia revierten todo. Las restricciones UNIQUE y FK físicas siguen siendo la defensa final y sus conflictos conocidos se traducen a 409. No se requiere migración 0003.

La BD protege integridad estructural. Inmutabilidad, transiciones, eliminación de documentos publicados y validación completa de metadatos deberán resolverse en dominio/services. Las cascadas internas no sustituyen esas reglas.

## FASE 1 — Templates

Estado de endpoints: `IMPLEMENTED` (contrato simplificado del Blog Personal).

- `POST /api/v1/templates`
- `GET /api/v1/templates`
- `PUT /api/v1/templates/{template_id}`
- `DELETE /api/v1/templates/{template_id}`

Se exponen ocho campos: `template_id`, `name`, `target_type`, `is_default`, `allow_published_edit`, `metadata_contract`, `layout_structure`, `created_at`. Los identificadores son UUIDv7; timestamps y respuestas usan UTC. POST devuelve 201, GET una colección `items` sin paginación, PUT la Template completa y DELETE únicamente `deleted_template_id`, con 200.

Reglas implementadas y verificadas:

- `name` no vacío y único; se recortan espacios exteriores, manteniendo sensibilidad a mayúsculas.
- `target_type` acepta POST/LANDING; `allow_published_edit` acepta el booleano enviado, sin imponer la recomendación por tipo.
- PUT reemplaza únicamente name/is_default/metadata_contract/layout_structure. `extra="forbid"` rechaza con 422 los atributos inmutables, identidad, fechas y campos desconocidos.
- Metadatos: lista no vacía, field_key no vacío ni repetido tras recortar espacios, expected_type STRING/INTEGER/BOOLEAN/DATE e is_required booleano JSON.
- Layout: objeto JSON sin motor visual ni validaciones estructurales complejas.
- GET acepta solo el filtro contractual opcional target_type y ordena por created_at ASC, UUID ASC en empates.
- Primera Template obligatoriamente default; transferencias atómicas; no se permite dejar cero defaults ni eliminar la última Template.
- DELETE rechaza con 409 cualquier referencia de Documents, sin reasignación ni cambios a esos documentos. Si elimina la default, elige la restante más antigua y desempata por UUID ASC.
- Inexistentes PUT/DELETE: 404; nombre duplicado: 409; schema e invariantes de default: 422; errores operativos: 503 genérico.

Simplificaciones intencionales del ejemplo docente: sin Idempotency-Key, cursor, limit, timeout HTTP explícito, fallback_template_id, reasignación ni autenticación de Preview Server. ReviewReport, MetricSnapshot, PreviewSession, WebSockets, agentes y métricas no se amplían ni se implementan; las secciones históricas siguientes no son requisitos de esta entrega académica.

Validación histórica de Templates: 55 pruebas nuevas y suite 218/0/0. Todas siguen pasando. Los cambios actuales agregan 71 pruebas de Documents, metadatos, OpenAPI y migración, con suite total 289/0/0.

## FASE 2 — Documents

Estado: `IMPLEMENTED`, contrato simplificado del Blog Personal.

- `POST /api/v1/documents`
- `GET /api/v1/documents`
- `GET /api/v1/documents/{document_id}`
- `PUT /api/v1/documents/{document_id}`
- `DELETE /api/v1/documents/{document_id}`

La respuesta expone exactamente document_id, title, slug, content_type, status, template_id, metadata_values, content, created_at, updated_at, published_at. UUIDv7 y timestamps UTC explícitos. POST crea BORRADOR con published_at=NULL; content puede estar vacío. Slug único global con patrón `^[a-z0-9]+(?:-[a-z0-9]+)*$`. GET devuelve items y admite content_type/status, sin paginación; orden created_at ASC y document_id ASC.

PUT reemplaza title, slug, template_id, metadata_values y content; otros campos producen 422. Template inexistente: 404; tipo incompatible: 422; slug duplicado: 409. Se validan claves conocidas y tipos STRING/INTEGER/BOOLEAN/DATE; bool no es INTEGER y DATE requiere YYYY-MM-DD válido. BORRADOR puede omitir campos requeridos, pero los presentes siempre se validan.

POST PUBLICADO es inmutable, cualquiera que sea allow_published_edit. LANDING PUBLICADO permite PUT solo si la Template lo permite; si se cambia Template, tanto la actual como la nueva deben permitirlo, evitando eludir la restricción. Las ediciones publicadas conservan required metadata, contenido no vacío y published_at. ARCHIVADO es terminal y no editable. Solo BORRADOR puede eliminarse físicamente.

0003 agrega content TEXT y created_at TIMESTAMPTZ, ambos NOT NULL sin defaults. Backfill: texto vacío y created_at=updated_at. No elimina frozen_template, CanvasBlock ni ReviewReport. El downgrade comprueba que no existan Documents antes de quitar columnas. No se modificaron 0001/0002 ni datos reales.

## FASE 3 — Workflow

Estado: `IMPLEMENTED`, publicación y archivado locales.

- `POST /api/v1/documents/{document_id}/publish`
- `POST /api/v1/documents/{document_id}/archive`

Ambos endpoints requieren Bearer y no necesitan body. Devuelven el Document actualizado con 200. Transiciones permitidas:

| Desde | Hacia |
| --- | --- |
| `BORRADOR` | `PUBLICADO` |
| `PUBLICADO` | `ARCHIVADO` |

Publicar requiere título y contenido no vacíos y todos los metadatos requeridos válidos. Establece published_at y updated_at. Archivar conserva published_at y actualiza updated_at. Estado incompatible o transición repetida: 409. Inexistente: 404. Se bloquea la fila durante la operación y cualquier fallo revierte los cambios.

Publicar POST valida contenido/Template/metadatos, reserva un directorio nuevo y escribe QMD. Quarto 1.10.18 renderiza el proyecto completo en staging con `--output-dir`; se verifican `index.html` y el HTML del POST antes de sustituir `docs/`. El backup anterior permanece hasta confirmar PostgreSQL. Errores de CLI, timeout, output incompleto o filesystem devuelven 500 seguro y mantienen BORRADOR. La compensación restaura `docs/` y elimina solo el QMD nuevo; cualquier fallo excepcional se registra y se informa. Publicaciones POST concurrentes se serializan mediante advisory lock transaccional. LANDING no genera archivos ni ejecuta Quarto. Archivar no toca QMD ni docs (`ARCHIVE_QUARTO_SYNC = PENDING`). Los artículos históricos no se modifican ni importan. El listing nativo de `posts/index.qmd` descubre automáticamente los QMD en `posts/*/index.qmd` y los ordena por fecha; `plantilla/` queda fuera por `draft: true`. PuraVida conserva una tarjeta manual. No hay deploy.

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

Templates y Documents traducen errores de dominio a 404/409/422 y fallos de persistencia a 503 seguro. Documents devuelve 201 al crear, 200 al consultar/editar/publicar/archivar y 204 vacío al eliminar un borrador.

Siguen pendientes PATCH (`CONTRACT_PENDING`), cms-admin, despliegue GitHub Pages, exportación LANDING, sincronización al archivar e importación histórica. La prueba manual recomendada usa `cms-prueba-render` y se documenta en README; `cms-prueba-quarto` ya existe y permanece intacto. Los tests no renderizaron el sitio real.
