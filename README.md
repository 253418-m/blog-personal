# Miguel Dev Blog

Base de un blog estático y portafolio académico y profesional creado con Quarto.

## Requisito

Quarto instalado y disponible en la terminal. La base se verificó con Quarto 1.10.18. No requiere backend ni dependencias de Node.js, R o Python para renderizar estas páginas.

## Uso local

Desde la carpeta del proyecto:

```powershell
quarto --version
quarto render
quarto preview
```

`quarto render` genera el sitio en `_site/`. `quarto preview` inicia la vista previa local; se detiene con `Ctrl+C`.

## Estructura

- `_quarto.yml`: configuración global, navegación y tema.
- `index.qmd`: inicio.
- `posts/index.qmd`: listado automático de artículos.
- `blog.qmd`: acceso conservado al listado de artículos.
- `proyectos.qmd`: portafolio académico inicial.
- `about.qmd`: presentación.
- `posts/`: artículos y metadatos comunes en `_metadata.yml`.
- `posts/plantilla/index.qmd`: plantilla en borrador, excluida de la publicación normal.
- `styles.css`: estilos personalizados.
- `images/`: imágenes compartidas; añade texto alternativo al usarlas.
- `_site/`: salida generada, excluida del control de versiones.

## Crear un artículo

1. Copia `posts/plantilla/` a `posts/nombre-del-articulo/`.
2. Completa título, descripción, categorías y contenido en `index.qmd`.
3. Añade una fecha real con `date: AAAA-MM-DD` al encabezado YAML.
4. Cambia `draft: true` a `draft: false` cuando esté listo.
5. Ejecuta `quarto render` y revisa el artículo y su aparición en el listado.

Para revisar borradores localmente, usa `quarto preview --render all`; Quarto los muestra durante la vista previa.

## Próximas etapas

Completar al menos diez artículos, desarrollar el diseño y el portafolio, y ampliar el SEO técnico. Las descripciones y el idioma ya están definidos; la URL pública, los metadatos sociales y el sitemap se revisarán cuando se conozca el destino de publicación.

GitHub Pages y el dominio no están configurados en esta fase. Tampoco se ha inicializado Git ni creado un repositorio remoto.

## Documentación

- [Sitios web con Quarto](https://quarto.org/docs/websites/)
- [Blogs con Quarto](https://quarto.org/docs/websites/website-blog.html)
