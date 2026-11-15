# elisavilchez.com

Web de Elisa Vílchez, traductora-intérprete jurada de inglés (MAEC n.º 6774). Sitio estático
con Jekyll, publicado en GitHub Pages, en cuatro idiomas (EN, ES, FR, CA).

Este documento describe **cómo está montado todo**: web, dominio, correo, formulario,
analítica y SEO técnico. El plan de trabajo y las decisiones de contenido se llevan fuera del
repositorio, que es público. Aquí no van claves ni datos de cuentas.

## Mapa

```
                       ┌───────────────────────── IONOS ─────────────────────────┐
visitante ──DNS──▶     │ elisavilchez.com (A → GitHub Pages)                     │
                       │ elisavilches.com → redirección a elisavilchez.com       │
                       │ correo: elisa@ y web@ son redirecciones al Gmail de Elisa│
                       └─────────────────────────────────────────────────────────┘
        │
        ▼
GitHub Pages (rama master) ── páginas estáticas, Jekyll 3.x
        │
        └─ formulario de presupuesto ──POST──▶ Cloud Run «quote-form» (Google Cloud, elisavilchez-web)
                                                  └─ API de Brevo ──▶ email a elisa@elisavilchez.com
```

| Pieza | Dónde | Detalle |
|---|---|---|
| Código | GitHub `elisavilches/elisavilches.github.io` | Publica `master`; el trabajo va en ramas `claude/*` |
| Hosting | GitHub Pages | `CNAME` → `elisavilchez.com` |
| Dominio y DNS | IONOS | También `elisavilches.com` (con s), que redirige a la web |
| Correo | IONOS (contrato de correo de Elisa) | `elisa@elisavilchez.com` y `web@elisavilchez.com` redirigen al Gmail de Elisa; no hay buzones |
| Formulario | Google Cloud `elisavilchez-web` + Brevo | Ver [`form-service/README.md`](form-service/README.md) |
| Analítica | Google Analytics 4 (`G-JNQ2TCMR0S`) | Solo se carga si el visitante acepta las cookies |
| Buscadores | Google Search Console | Propiedades de dominio y de prefijo de URL |

## Estructura del sitio

```
_config.yml            idiomas, url, quote_endpoint, exclusiones
_data/
  general.yml          datos de Elisa: nombre, MAEC, email, teléfono, NIF y domicilio legal, textos de portada
  i18n.yml             textos de la interfaz (menú, botones, pie, cookies) en los 4 idiomas
  faq.yml              preguntas frecuentes de la portada (también van a los datos estructurados)
  testimonials.yml     opiniones
  quote_form.yml       textos del formulario de presupuesto
_layouts/
  default.html         esqueleto: head, cabecera, contenido, pie
  mainpage.html        portada de cada idioma (/en/, /es/, /fr/, /ca/)
  content.html         páginas de contenido; las guías (kind) llevan columna lateral
  section.html         páginas antiguas (/services/, /contact/)
_includes/
  head.html            SEO (title, description, canonical, hreflang, Open Graph), CSS, GA4 con consentimiento
  header.html          menú, idiomas y botón de presupuesto
  footer.html          datos, MAEC, redes y enlaces legales
  structured-data.html JSON-LD (Person, ProfessionalService, FAQPage, AboutPage)
  cookie-banner.html   aviso de cookies (Aceptar / Rechazar)
  quote-form.html      formulario de presupuesto
  guide-cards.html     tarjetas del índice de guías
  icon.html            iconos SVG
css/site.css           hoja única (sin Bootstrap ni jQuery)
fonts/                 Source Serif 4 y Source Sans 3, alojadas aquí (licencia OFL incluida)
en/ es/ fr/ ca/        páginas por idioma
form-service/          servicio del formulario (no se publica en Pages)
```

### Páginas multilingües

Cada página existe una vez por idioma, en su carpeta y con su propia URL. Las versiones de una
misma página se enlazan entre sí con el campo `ref` del *front matter*:

```yaml
---
layout: content
lang: es
ref: about            # el mismo valor en /en/about/, /es/sobre-mi/, /fr/a-propos/, /ca/sobre-mi/
permalink: /es/sobre-mi/
title: "…"            # <title> (se le añade «| Elisa Vílchez»)
heading: "…"          # H1 de la banda
description: "…"      # meta description
last_updated: 2026-11-15
---
```

A partir de `ref` se generan solos el selector de idioma, los `hreflang`, los enlaces del menú
y el sitemap. Los `ref` en uso son `about`, `hub-visas`, `quote`, `legal` y `privacy`.

Las guías llevan además `kind: visa` o `kind: document` y `short:` (título corto para las
tarjetas del índice). Mientras no estén aprobadas van con `published: false`: se ven en local
con `--unpublished`, pero no se publican.

Las páginas legales llevan `robots: noindex, follow` y quedan fuera del sitemap.

## Desarrollo local

GitHub Pages usa **Jekyll 3.x**, así que no hay que usar filtros de Jekyll 4.

```sh
bundle exec jekyll serve --unpublished       # http://localhost:4000, con borradores
```

Sin Bundler (el Gemfile usa `gemspec`), con un directorio de gemas propio:

```sh
JEKYLL_NO_BUNDLER_REQUIRE=true GEM_HOME=… GEM_PATH=… jekyll serve --unpublished \
  --config _config.yml,local.yml             # local.yml: url: "http://localhost:4000"
```

Los cambios de `_config.yml` y de `local.yml` necesitan reiniciar el servidor.

## Publicar

Hacer push a `master`. GitHub Pages reconstruye la web en uno o dos minutos. Antes de publicar
un cambio de contenido visible, debe aprobarlo Elisa.

## Dominio, DNS y correo (IONOS)

Registros de `elisavilchez.com`:

| Tipo | Nombre | Valor | Para qué |
|---|---|---|---|
| A | `@`, `www` | `185.199.108.153` | GitHub Pages |
| MX | `@` | `mx00.ionos.es`, `mx01.ionos.es` | Correo entrante (IONOS) |
| TXT | `@` | `v=spf1 include:_spf-eu.ionos.com ~all` | SPF de IONOS |
| CNAME | `s1-ionos._domainkey`, `s2-ionos._domainkey`, `s42582890._domainkey` | `*.dkim.ionos.com` | DKIM de IONOS |
| TXT | `@` | `brevo-code:…` | Verificación del dominio en Brevo |
| CNAME | `brevo1._domainkey`, `brevo2._domainkey` | `b1/b2.elisavilchez-com.dkim.brevo.com` | DKIM de Brevo |
| TXT | `_dmarc` | `v=DMARC1; p=none; rua=mailto:rua@dmarc.brevo.com` | DMARC (sustituye al CNAME de IONOS desde el 15/11/2026) |
| TXT | `@` | `google-site-verification=…` | Search Console |

Correo: `elisa@elisavilchez.com` y `web@elisavilchez.com` son redirecciones al Gmail de Elisa.
`web@` es el remitente de los avisos del formulario.

## Formulario de presupuesto

Páginas `/en/quote/`, `/es/presupuesto/`, `/fr/devis/` y `/ca/pressupost/`. Los botones rojos de
presupuesto llevan aquí. El formulario envía a `quote_endpoint` (en `_config.yml`), un servicio
propio en Cloud Run que reenvía la solicitud y los adjuntos a Elisa con Brevo, sin guardar nada.
Todo el detalle está en [`form-service/README.md`](form-service/README.md).

## Analítica y cookies

- **GA4:** el script solo se carga cuando el visitante acepta en el aviso de cookies (Consent
  Mode con todo denegado por defecto). La elección se guarda en `localStorage`
  (`cookie-consent`); «Configurar cookies», en el pie, permite cambiarla.
- **Contactos (`generate_lead`)**, con el parámetro `method`: `email_click` (clic en un
  `mailto:`), `email_copy` o `phone_copy` (copiar el email o el teléfono) y `form` (envío del
  formulario).
- **Navegación** (sin datos personales):
  - grupo de contenido de cada página (`content_group`): `home`, `guides_index`, `guide_visa`,
    `guide_document`, `quote_form`, `about`, `legal`, `other`;
  - `quote_click` (`location`: header, hero, sidebar, page_end, services, footer), `guide_click`
    (`guide`), `faq_open` (`question`), `language_switch` (`to`) y `maec_lookup`;
  - formulario: `form_start`, `form_error` (`error`) y `generate_lead` con `method: form`, `visa`
    (código del visado elegido) y `files` (número de adjuntos).
  - Para filtrar por estos parámetros en los informes hay que registrarlos como dimensiones
    personalizadas en GA4 (Administrar → Definiciones personalizadas).
- **Tráfico interno:** abrir una vez `https://elisavilchez.com/?internal=1` en cada navegador propio (Alberto, Elisa, móviles) marca ese navegador como interno (`traffic_type=internal`), y el filtro de datos «Internal Traffic» de GA4 lo descarta. `?internal=0` lo desmarca.
- **Desde el 2026-11-15 (noche)** hay aviso de cookies: GA4 solo mide a quien acepta. Las cifras
  bajan sin que baje el tráfico real. Ver la tabla de fechas en `CLAUDE.md`.

## SEO técnico

- `sitemap.xml` generado con todas las páginas y sus `hreflang`. Las legales quedan fuera.
- `robots.txt` y `llms.txt` (resumen para asistentes de IA).
- Por página: `title`, `description`, `canonical`, `hreflang` (con `x-default` en inglés) y Open
  Graph, en `_includes/head.html`.
- Datos estructurados JSON-LD en `_includes/structured-data.html`: Person (con el nombre del
  registro del MAEC y `alternateName` «Elisa Vilches»), ProfessionalService, FAQPage y AboutPage.

## Datos legales

El aviso legal y la política de privacidad (4 idiomas) toman el titular, el NIF y el domicilio
de `_data/general.yml`. Si cambia algo, como el domicilio o un proveedor nuevo que trate datos,
hay que actualizar también la política de privacidad, que enumera los encargados de tratamiento.
