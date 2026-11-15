#!/usr/bin/env bash
# Despliegue del formulario en Cloud Run (proyecto elisavilchez-web, europe-west1).
# SIMULACRO POR DEFECTO: imprime los comandos. Solo con --apply toca la nube.
#
# Uso:
#   ./deploy.sh [--apply] infra     cuenta de servicio y acceso al secreto (una vez)
#   ./deploy.sh [--apply] deploy    build con Cloud Build y despliegue del servicio
#   ./deploy.sh verify              /health y la URL del servicio (solo lectura)
#
# El secreto BREVO_API_KEY lo crea el dueño a mano, sin que el valor pase por argv ni por el historial:
#   gcloud secrets create brevo-api-key --project elisavilchez-web --replication-policy=user-managed --locations=europe-west1
#   pbpaste | gcloud secrets versions add brevo-api-key --project elisavilchez-web --data-file=-
set -euo pipefail
cd "$(dirname "$0")"

PROJECT=elisavilchez-web
REGION=europe-west1
SERVICE=quote-form
SA=quote-form-run@${PROJECT}.iam.gserviceaccount.com
ORIGINS="https://elisavilchez.com,https://www.elisavilchez.com"

APPLY=0
[[ "${1:-}" == "--apply" ]] && { APPLY=1; shift; }
run() { if (( APPLY )); then echo "+ $*"; "$@"; else echo "[simulacro] $*"; fi; }

case "${1:-}" in
  infra)
    run gcloud iam service-accounts create quote-form-run --project "$PROJECT" --display-name "Formulario de presupuesto (Cloud Run)"
    run gcloud secrets add-iam-policy-binding brevo-api-key --project "$PROJECT" \
      --member "serviceAccount:$SA" --role roles/secretmanager.secretAccessor
    ;;
  deploy)
    run gcloud run deploy "$SERVICE" --project "$PROJECT" --region "$REGION" --source . \
      --service-account "$SA" --allow-unauthenticated \
      --min-instances 0 --max-instances 1 --concurrency 10 --memory 512Mi --timeout 60 \
      --set-env-vars "^#^MAIL_BACKEND=brevo#MAIL_TO=elisa@elisavilchez.com#MAIL_FROM=info@elisavilchez.com#ALLOWED_ORIGINS=$ORIGINS" \
      --set-secrets "BREVO_API_KEY=brevo-api-key:latest"
    ;;
  verify)
    URL=$(gcloud run services describe "$SERVICE" --project "$PROJECT" --region "$REGION" --format 'value(status.url)')
    echo "URL: $URL"; curl -fsS "$URL/health"; echo
    ;;
  *) sed -n 2,12p "$0"; exit 1 ;;
esac
