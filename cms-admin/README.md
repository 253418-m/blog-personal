# CMS Admin

Interfaz privada para el CMS personal. Es una aplicación React + Vite separada de Quarto y de `docs/`. Usa las rutas Auth, Documents y Templates ya disponibles en `cms-api`. Permite administrar Documents y Templates.

## Desarrollo local

Primero inicia el backend desde otra terminal:

```powershell
cd C:\Users\migue\blog-personal\cms-api
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload
```

Después inicia el frontend:

```powershell
cd C:\Users\migue\blog-personal\cms-admin
Copy-Item .env.example .env
npm install
npm run dev
```

Vite muestra la URL local, normalmente `http://localhost:5173`. El login está en `/login`; `/dashboard`, las rutas de `/contenido` y las rutas de `/plantillas` requieren una sesión validada. `VITE_API_BASE_URL` indica el origen del backend (ejemplo: `http://127.0.0.1:8000`). Es configuración pública del build, nunca un lugar para secretos. Las variables reales del entorno o un `.env` local del frontend pueden cambiarla. El backend permite por defecto los orígenes `http://localhost:5173` y `http://127.0.0.1:5173` mediante `CORS_ALLOWED_ORIGINS`.

## Sesión y seguridad

El formulario envía username y password por JSON a `POST /api/v1/auth/login`; guarda únicamente `access_token` en `sessionStorage` con la clave `cms_access_token`. No persiste la contraseña. Antes de mostrar rutas privadas, valida el JWT mediante `GET /api/v1/auth/me`. Cada petición protegida lleva `Authorization: Bearer`; un 401 limpia la sesión y redirige a Login. Cerrar sesión borra el token localmente: no existe endpoint de logout ni refresh token en el backend. El JWT vence aproximadamente a los 30 minutos.

`sessionStorage` permite recargar la pestaña, pero sigue siendo accesible a JavaScript. Una fase de despliegue con requisitos de seguridad mayores podría evaluar cookies HttpOnly. Las rutas del frontend no sustituyen la autorización JWT del backend. No hay registro público ni enlace al administrador en el sitio Quarto.

## Vistas disponibles

| Ruta | Datos |
| --- | --- |
| `/login` | Inicio de sesión administrativo |
| `/dashboard` | Conteos de BORRADOR, PUBLICADO, ARCHIVADO y Templates; hasta cinco Documents recientes |
| `/contenido` | Lista de Documents, filtros de estado y tipo, acciones según el estado |
| `/contenido/nuevo` | Crear un POST en BORRADOR con plantilla POST y metadatos dinámicos |
| `/contenido/:documentId` | Ver contenido y metadatos; publicar, archivar o eliminar según el estado |
| `/contenido/:documentId/editar` | Editar únicamente BORRADOR |
| `/plantillas` | Lista y filtros de Templates POST/LANDING |
| `/plantillas/nueva` | Crear una Template y sus campos adicionales |
| `/plantillas/:templateId` | Ver detalle y eliminar tras confirmación |
| `/plantillas/:templateId/editar` | Editar nombre, predeterminada, campos y estructura |

El listado usa los filtros `status` y `content_type` del backend. Nuevo post carga únicamente Templates POST y preselecciona la marcada como default. El slug se sugiere desde el título hasta que se edita manualmente; debe cumplir `^[a-z0-9]+(?:-[a-z0-9]+)*$`. Los campos del contrato de metadatos se muestran como texto, entero, casilla o fecha. Se puede guardar un borrador con contenido o metadatos obligatorios pendientes; para publicar deben estar completos y el backend vuelve a validarlos. El contenido se edita en un textarea de Markdown/Quarto y se muestra como texto en la vista de detalle.

BORRADOR admite edición, publicación y eliminación; PUBLICADO se muestra en lectura y admite archivado; ARCHIVADO es terminal. Publicar exige confirmación porque un POST queda inmutable y el backend genera QMD y HTML. La interfaz muestra conflictos 409, datos inválidos 422 y fallos de render 500 sin exponer detalles internos. Tras un 500 al publicar, el borrador se conserva. Archivar un POST retira el QMD, actualiza el sitio generado localmente y lo quita del catálogo; si falla, el POST permanece PUBLICADO. LANDING conserva el archivado administrativo sin render Quarto. El despliegue en GitHub Pages sigue pendiente. El editor de páginas LANDING queda para una fase posterior.

## Gestión de plantillas

**Plantillas** muestra Artículos / Posts (`POST`) y Páginas del sitio (`LANDING`), con filtros y enlaces al detalle. Una plantilla de artículos alimenta **Contenido → Nuevo post**; una de páginas queda disponible para un futuro editor de Inicio y Sobre mí. La primera plantilla debe ser predeterminada. Activar otra como predeterminada desmarca la anterior en una operación del backend; la actual no puede desmarcarse sin elegir otra.

El formulario permite definir **Campos adicionales**. Cada fila guarda `field_key`, `expected_type` (`STRING`, `INTEGER`, `BOOLEAN` o `DATE`) e `is_required`; los nombres legibles son solo presentación y no se añaden al JSON. El identificador debe ser no vacío y único. **Estructura de contenido** admite un objeto JSON en un textarea; JSON inválido y arrays raíz se rechazan antes de enviar. La Template requiere al menos un campo. `target_type` y `allow_published_edit` se eligen al crear y luego se muestran como no modificables; PUT solo envía `name`, `is_default`, `metadata_contract` y `layout_structure`. Los posts publicados siguen siendo inmutables aunque una plantilla POST permita edición publicada.

Eliminar exige confirmación. El backend rechaza con 409 una plantilla utilizada por Documents o la última plantilla del catálogo; la UI explica ambos casos. Para probar manualmente, crea una plantilla POST ficticia llamada `Plantilla Post Prueba UI` con los campos `topic` (Texto, obligatorio), `difficulty` (Texto, opcional) y `published_date` (Fecha, opcional), y estructura `{"sections":["header","content"]}`. Comprueba su detalle, edítala y visita **Contenido → Nuevo post**: debe aparecer en el selector y mostrar Topic, Difficulty y Published date. Una plantilla LANDING creada del mismo modo aparece en Plantillas, pero no en Nuevo post. Puedes eliminar la plantilla ficticia si no la utiliza ningún Document. No se ejecutan estas pruebas manuales durante la suite.

Para una prueba manual, inicia sesión y entra en **Contenido → + Nuevo post**. Selecciona la plantilla POST existente y usa datos ficticios: título `Prueba desde CMS Admin`, slug `prueba-cms-admin`, `category` = `Pruebas`, `reading_time` = `2` si esos campos existen en la plantilla, y contenido `# Prueba desde CMS Admin` seguido de texto de prueba. Guarda el borrador, ábrelo, edítalo y guarda de nuevo. Pulsa **Publicar**, acepta la advertencia de inmutabilidad y espera a que termine el render. Comprueba `posts/prueba-cms-admin/index.qmd`, `docs/posts/prueba-cms-admin/index.html` y la página pública **Contenido**. Utiliza otro slug si ese directorio ya existe. Para probar **Archivar**, elige solo un POST ficticio publicado: tras confirmar, ambos archivos dejan de existir y Contenido ya no lo lista en el sitio generado local. El Document queda ARCHIVADO y no puede republicarse desde el CMS. GitHub Pages no se actualiza automáticamente.

## Verificación y build

```powershell
npm run lint
npm test -- --run
npm run build
```

El build se crea en `cms-admin/dist/`, ignorado por Git. No se copia a `docs/` ni se despliega en esta fase.
