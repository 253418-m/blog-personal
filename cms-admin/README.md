# CMS Admin

Interfaz privada de solo lectura para el CMS personal. Es una aplicación React + Vite separada de Quarto y de `docs/`. Usa las rutas Auth, Documents y Templates ya disponibles en `cms-api`; no crea ni edita contenido en esta fase.

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

Vite muestra la URL local, normalmente `http://localhost:5173`. El login está en `/login`; `/dashboard`, `/contenido` y `/plantillas` requieren una sesión validada. `VITE_API_BASE_URL` indica el origen del backend (ejemplo: `http://127.0.0.1:8000`). Es configuración pública del build, nunca un lugar para secretos. Las variables reales del entorno o un `.env` local del frontend pueden cambiarla. El backend permite por defecto los orígenes `http://localhost:5173` y `http://127.0.0.1:5173` mediante `CORS_ALLOWED_ORIGINS`.

## Sesión y seguridad

El formulario envía username y password por JSON a `POST /api/v1/auth/login`; guarda únicamente `access_token` en `sessionStorage` con la clave `cms_access_token`. No persiste la contraseña. Antes de mostrar rutas privadas, valida el JWT mediante `GET /api/v1/auth/me`. Cada petición protegida lleva `Authorization: Bearer`; un 401 limpia la sesión y redirige a Login. Cerrar sesión borra el token localmente: no existe endpoint de logout ni refresh token en el backend. El JWT vence aproximadamente a los 30 minutos.

`sessionStorage` permite recargar la pestaña, pero sigue siendo accesible a JavaScript. Una fase de despliegue con requisitos de seguridad mayores podría evaluar cookies HttpOnly. Las rutas del frontend no sustituyen la autorización JWT del backend. No hay registro público ni enlace al administrador en el sitio Quarto.

## Vistas disponibles

| Ruta | Datos |
| --- | --- |
| `/login` | Inicio de sesión administrativo |
| `/dashboard` | Conteos de BORRADOR, PUBLICADO, ARCHIVADO y Templates; hasta cinco Documents recientes |
| `/contenido` | Tabla de Documents y filtros locales de estado |
| `/plantillas` | Tabla de Templates y sus propiedades |

Documents y Templates son vistas de consulta. Sus formularios de creación y edición quedan pendientes.

## Verificación y build

```powershell
npm run lint
npm test -- --run
npm run build
```

El build se crea en `cms-admin/dist/`, ignorado por Git. No se copia a `docs/` ni se despliega en esta fase.
