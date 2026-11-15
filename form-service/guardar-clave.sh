#!/bin/sh
# Guarda en Secret Manager la clave de API de Brevo que haya en el portapapeles, sin mostrarla.
# Uso: copia la clave en Brevo y ejecuta  sh form-service/guardar-clave.sh
set -e
k=$(pbpaste)
case "$k" in
  xkeysib-*) ;;
  *) echo "El portapapeles no contiene una clave de API de Brevo (empiezan por xkeysib-). No se ha guardado nada."; exit 1 ;;
esac
printf %s "$k" | gcloud secrets versions add brevo-api-key --project elisavilchez-web --data-file=- >/dev/null
echo "Clave guardada en Secret Manager (brevo-api-key). Copia otro texto para vaciar el portapapeles."
