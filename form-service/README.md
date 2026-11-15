# Formulario de presupuesto (form-service)

Servicio mínimo que recibe el formulario de presupuesto de elisavilchez.com
(`/en/quote/`, `/es/presupuesto/`, `/fr/devis/`, `/ca/pressupost/`) y lo reenvía por email
a Elisa, con los documentos adjuntos.

GitHub Pages solo sirve ficheros estáticos y no puede recibir un formulario. Además, la clave
de la API de envío no puede estar en la web, porque cualquiera la vería en el código fuente.
Por eso existe este servicio: guarda la clave, valida y filtra el spam y siempre envía al mismo
destinatario.

No guarda nada: no hay base de datos ni escribe en disco. Los adjuntos solo pasan por memoria,
y los registros no contienen datos personales.

## Recorrido

```
navegador ──POST /quote──▶ Cloud Run «quote-form» ──API──▶ Brevo ──email──▶ elisa@elisavilchez.com ──▶ Gmail de Elisa
                               │                                  de: web@elisavilchez.com
                               └─ lee BREVO_API_KEY de Secret Manager       responder a: el cliente
```

## Dónde vive cada cosa

| Pieza | Dónde | Notas |
|---|---|---|
| Código | este directorio (`app.py`, `tests/`) | FastAPI, Python 3.12 |
| Servicio | Google Cloud, proyecto `elisavilchez-web`, Cloud Run `quote-form`, región `europe-west1` | De 0 a 1 instancias; se apaga sin tráfico. **No comparte nada con las apps Mister**, solo la cuenta de facturación |
| Clave de Brevo | Secret Manager `brevo-api-key` (europe-west1) | La lee solo la cuenta de servicio `quote-form-run@elisavilchez-web.iam.gserviceaccount.com` |
| Envío | Brevo, plan gratuito (300 emails/día) | Clave `formulario-web`, restringida a «Emails transaccionales». Caduca tras 90 días sin uso |
| Remitente | `web@elisavilchez.com` | Verificado en Brevo. En IONOS es una redirección (sin buzón) al Gmail de Elisa |
| DNS (IONOS) | `brevo-code` (TXT @), `brevo1._domainkey` y `brevo2._domainkey` (CNAME), `_dmarc` (TXT con `rua` de Brevo) | Conviven con los registros de correo de IONOS (MX, SPF, DKIM) |
| Endpoint en la web | `_config.yml` → `quote_endpoint` | |

## Variables de entorno

| Variable | Producción | Para qué |
|---|---|---|
| `MAIL_BACKEND` | `brevo` | `file` en desarrollo: escribe el email en `MAIL_DIR` en vez de enviarlo |
| `BREVO_API_KEY` | secreto `brevo-api-key` | |
| `MAIL_TO` | `elisa@elisavilchez.com` | Destinatario fijo |
| `MAIL_FROM` | `web@elisavilchez.com` | Remitente verificado en Brevo |
| `ALLOWED_ORIGINS` | `https://elisavilchez.com,https://www.elisavilchez.com` | Solo acepta envíos desde la web |

## Protecciones

- Origen: solo los dominios de `ALLOWED_ORIGINS` (CORS y comprobación del `Origin`).
- Campo trampa invisible (`website`): si viene relleno, se responde «ok» y no se envía nada.
- Tiempo mínimo de rellenado: 4 segundos.
- Límite por IP: 5 envíos por hora.
- Adjuntos: hasta 10 archivos y 15 MB en total; solo PDF, imágenes y Word.

## Desarrollo

```sh
cd form-service
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r requirements.txt pytest
.venv/bin/python -m pytest -q                      # tests
MAIL_BACKEND=file MAIL_DIR=/tmp/mail .venv/bin/uvicorn app:app --port 8006
```

Para probar la web en local contra este servicio, pon `quote_endpoint: "http://localhost:8006/quote"`
en la configuración local de Jekyll.

## Despliegue

`deploy.sh` está en **modo simulacro** por defecto: imprime los comandos sin ejecutarlos.

```sh
./deploy.sh infra              # ver qué haría
./deploy.sh --apply infra      # cuenta de servicio y acceso al secreto (una sola vez)
./deploy.sh --apply deploy     # build con Cloud Build y nueva revisión de Cloud Run
./deploy.sh verify             # URL del servicio y /health
```

Las dependencias van fijadas con hashes en `requirements.txt` (`uv pip compile --generate-hashes`).

## Cambiar la clave de Brevo

1. En Brevo: Configuración → SMTP y API → Claves API → Generar (acceso restringido, solo
   «Emails transaccionales: Todos») y copiarla.
2. `sh form-service/guardar-clave.sh` (lee el portapapeles, comprueba que empieza por `xkeysib-`
   y la guarda como nueva versión del secreto sin mostrarla).
3. `./deploy.sh --apply deploy` para que el servicio coja la versión nueva.

## Si no llega un presupuesto

1. **Brevo → Transaccional → Logs:** cada envío aparece como «Enviado», «Entregado» o «Error»,
   con el motivo.
2. Si no aparece nada en Brevo: **Google Cloud → elisavilchez-web → Cloud Run → quote-form →
   Registros**. Los rechazos se registran como `rechazado: <motivo>`.
3. Ojo: si Brevo acepta el envío y lo rechaza después, el cliente ve «Solicitud recibida»
   aunque el email no llegue. Por eso conviene mirar los registros de Brevo de vez en cuando.
