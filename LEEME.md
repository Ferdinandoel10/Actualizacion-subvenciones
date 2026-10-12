# Qué me corresponde: actualización automática

La página se mantiene al día sola de dos formas:

1. **Lo que caduca desaparece solo.** Cada oferta, ayuda o beca tiene su fecha de fin. Al abrir la página se compara con la fecha de ese día: lo vencido deja de mostrarse y las convocatorias que se repiten cada año pasan a «Próximas convocatorias».
2. **Lo nuevo aparece solo.** Cada día, el programa `actualizar.py` descarga de la Base de Datos Nacional de Subvenciones todas las convocatorias para particulares del Estado, de las comunidades, de las diputaciones y de los ayuntamientos que siguen en plazo. Las guarda en `convocatorias.json`, y la página las muestra en la sección «Otras convocatorias abiertas para particulares».

## Puesta en marcha (una sola vez, gratis)

1. Crea una cuenta en github.com si no la tienes.
2. Crea un repositorio nuevo (por ejemplo `que-me-corresponde`) y sube estos archivos, respetando la carpeta `.github/workflows`:
   - `ofertas.html`, renombrado como `index.html` para que sea la portada de la web
   - `actualizar.py`
   - `.github/workflows/actualizar.yml`
3. En el repositorio, ve a **Settings → Pages**, elige **Deploy from a branch**, la rama `main` y la carpeta `/ (root)`. En un par de minutos la web estará en `https://TU-USUARIO.github.io/que-me-corresponde/`.
4. Ve a la pestaña **Actions**, abre «Actualizar convocatorias» y pulsa **Run workflow** para la primera descarga. La primera vez tarda bastante (puede llegar a una hora) porque descarga el detalle de cada convocatoria; después solo baja las nuevas y tarda pocos minutos.
5. A partir de ahí se ejecuta solo cada madrugada. Si un día falla, GitHub te avisa por correo y al día siguiente lo vuelve a intentar.

## Cosas a tener en cuenta

- La página tiene que estar publicada en una web, como GitHub Pages. Si abres el archivo directamente desde tu ordenador, el navegador no deja leer `convocatorias.json` y esa sección no aparece; el resto funciona igual.
- En la sección automática la página **no comprueba requisitos**, porque la base de datos no los publica en un formato que se pueda leer. Solo muestra lo que está en plazo en tu zona, con enlace a la ficha oficial y a las bases.
- Para no duplicar, si una convocatoria ya tiene ficha revisada (con «Fuente: BDNS número» en su nota), no se repite en la sección automática.
- El filtro que descarta premios, convenios y ayudas a sectores concretos está en la variable `EXCLUIR` de `actualizar.py`. Si se cuela algo que no interesa, se añade ahí una palabra.
- La Base de Datos Nacional de Subvenciones avisa de que puede limitar el acceso automatizado. El programa va despacio a propósito (una petición cada 0,3 segundos) y reintenta si falla.
