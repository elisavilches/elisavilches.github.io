# CLAUDE.md — elisavilchez.com

Instrucciones para trabajar en este repositorio. La descripción técnica completa está en
[`README.md`](README.md) y la del formulario en [`form-service/README.md`](form-service/README.md).

## Fechas que hay que tener en cuenta al leer datos

| Fecha | Qué cambió | Efecto en los datos |
|---|---|---|
| 2026-11-15 (mañana) | Publicados los cambios de SEO: títulos y meta por idioma, hreflang, sitemap, «sworn» en vez de «certified», evento `generate_lead` | Punto de partida para comparar Search Console (ticket de revisión el 2026-12-15) |
| **2026-11-15 (noche)** | **Publicado el rediseño**: aviso de cookies (GA4 solo se carga si el visitante acepta), formulario de presupuesto, 7 guías en inglés, páginas legales | **GA4 mide menos visitas y menos `generate_lead` desde esta fecha sin que baje el tráfico real**: solo cuenta a quien acepta las cookies (suele ser entre la mitad y dos tercios). No confundirlo con una caída. Comparar periodos antes y después con cuidado; Search Console no se ve afectado |
| **2026-11-17 (tarde)** | **Corregido el orden consentimiento → `config` de GA4.** Hasta entonces la `page_view` de cada página se enviaba antes de aplicar el consentimiento (`gcs=G100`, identificador nuevo) y GA4 la descartaba | Entre el 15/11 (noche) y el 17/11 faltan vistas de página y visitas cortas (solo constan las visitas con otros eventos: scroll, clics, `user_engagement`). Desde el 17/11 las vistas y los usuarios suben sin que cambie el tráfico real |
| 2026-11-15 (noche) | Eventos de navegación nuevos: `quote_click`, `guide_click`, `faq_open`, `language_switch`, `maec_lookup`, `form_start`, `form_error` y el grupo de contenido | Antes de esta fecha no existen; no hay histórico con el que comparar |

## Normas del proyecto

- **Idioma:** responder al usuario en español, con ortografía correcta.
- **Repositorio público:** no subir documentos internos (estrategia, competencia, auditorías,
  pendientes) ni claves. `AUDITORIA-SEO.md` y `PENDIENTES.md` están en `.gitignore`. El plan de
  trabajo vive en un artefacto privado de Claude.
- **Textos visibles:** los cambios de contenido los valida Elisa. Desde el 2026-11-15 se publica y
  ella revisa en vivo; lo pendiente de su revisión está apuntado en el plan.
- **Nombre:** «Elisa Vílchez» (con z y tilde) en toda la web. «Vilches» solo como `alternateName`
  en los datos estructurados y en `llms.txt`, nunca visible. Nombre del registro del MAEC:
  «Elisa María Vílchez Sánchez», n.º 6774.
- **Precios:** no se publican. Se habla de presupuesto cerrado y plazos.
- **Tono:** nada de sospecha («compruébalo si no te fías»). El número del MAEC y el enlace al
  buscador oficial bastan.
- **Español de la web:** de usted.
- **Jekyll 3.x** (GitHub Pages): no usar filtros de Jekyll 4.
- **Commits:** terminar los mensajes con las líneas de atribución que indique la sesión. No crear PR
  salvo que se pida.

## Ramas y publicación

- `master` es lo publicado (GitHub Pages). Desde el 2026-11-15 `master` = `claude/rediseno`.
- Para publicar: hacer el trabajo en una rama, comprobar en local (`jekyll serve --unpublished`) y
  llevarlo a `master` con un *fast-forward*.
- El servicio del formulario se despliega aparte (`form-service/deploy.sh`, modo simulacro por
  defecto). Solo acepta envíos desde `https://elisavilchez.com`.

## Seguimiento pendiente (resumen)

- Dominio autenticado en Brevo el 2026-11-16 (DKIM `brevo1`/`brevo2`, código `brevo-code` y DMARC `p=none` con informes a Brevo). Más adelante se puede endurecer el DMARC a `p=quarantine`.
- GA4 configurado el 2026-11-15: `generate_lead` es evento clave, anotación del cambio de medición,
  9 dimensiones personalizadas (location, guide, visa, error, question, method, page_type, to,
  files), conservación de datos a 14 meses, medición mejorada (scroll, clics de salida,
  descargas), referencias de spam excluidas, filtro de tráfico interno activo (`?internal=1`) y
  Search Console vinculado. El canal «AI Assistant» ya viene en el grupo predeterminado de GA4.
- Revisar cada mes el registro de envíos de Brevo (Transaccional → Logs).
