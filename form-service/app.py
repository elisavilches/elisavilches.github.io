"""Servicio del formulario de presupuesto de elisavilchez.com.

Recibe el formulario de la web (con los documentos adjuntos) y lo reenvía por email a Elisa
con la API de Brevo. Después manda al cliente un email de confirmación en el idioma de la página. No guarda nada: ni base de datos ni disco. Los adjuntos solo pasan por
memoria y los registros no llevan datos personales.

Variables de entorno:
  MAIL_BACKEND      "brevo" (producción) o "file" (desarrollo: escribe el email en MAIL_DIR)
  BREVO_API_KEY     clave de la API de Brevo (Secret Manager en producción)
  MAIL_TO           destinatario (por defecto elisa@elisavilchez.com)
  MAIL_FROM         remitente verificado en Brevo (por defecto web@elisavilchez.com)
  MAIL_DIR          carpeta para MAIL_BACKEND=file
  ALLOWED_ORIGINS   orígenes permitidos, separados por comas
"""

from __future__ import annotations

import base64
import html
import itertools
import json
import logging
import os
import re
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from fastapi import FastAPI, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

log = logging.getLogger("form-service")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

# ---------------------------------------------------------------- configuración

MAX_FILES = 20
# Brevo admite 25 MB por email y el base64 de los adjuntos ocupa un 37 % más: 15 MB reales caben con margen.
MAX_TOTAL_BYTES = 15 * 1024 * 1024
MAX_FIELD_CHARS = 4000
MIN_FILL_SECONDS = 4  # un humano tarda más que esto en rellenar el formulario
RATE_LIMIT = 5  # envíos por IP...
RATE_WINDOW = 3600  # ...por hora
ALLOWED_EXT = {".pdf", ".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp", ".doc", ".docx", ".tif", ".tiff"}
EMAIL_RE = re.compile(r"^[^@\s<>]+@[^@\s<>]+\.[^@\s<>]+$")

TEXT_FIELDS = ("name", "email", "visa", "consulate", "documents", "deadline", "delivery", "message", "source", "lang")
LABELS = {
    "name": "Nombre",
    "email": "Email",
    "visa": "Visado o trámite",
    "consulate": "Consulado / organismo",
    "documents": "Documentos",
    "deadline": "Fecha límite",
    "delivery": "Formato de entrega",
    "message": "Comentarios",
    "source": "Cómo me ha conocido",
    "lang": "Idioma de la web",
}


# Email de confirmación al cliente, en el idioma de la página. Solo repite datos cortos y de
# opciones (trámite, plazo, entrega, nombres de archivo): nada del texto libre del cliente, para que
# nadie pueda usar el formulario para mandar su propio texto a otra dirección.
CONFIRM = {
    "es": {
        "subject": "Solicitud de presupuesto recibida",
        "hello": "Hola, {name}:",
        "body": "Gracias por escribirme. He recibido su solicitud de presupuesto y le responderé a la mayor brevedad.",
        "summary": "Resumen de su solicitud:",
        "visa": "Trámite", "deadline": "Fecha límite", "delivery": "Entrega", "files": "Documentos adjuntos", "none": "ninguno",
        "role": "Traductora jurada de inglés n.º 6774 (Ministerio de Asuntos Exteriores)",
        "auto": "Este es un mensaje automático de confirmación.",
    },
    "en": {
        "subject": "Quote request received",
        "hello": "Hello {name},",
        "body": "Thank you for getting in touch. I have received your quote request and will reply as soon as possible.",
        "summary": "Summary of your request:",
        "visa": "Purpose", "deadline": "Needed by", "delivery": "Delivery", "files": "Attached documents", "none": "none",
        "role": "Sworn translator English–Spanish no. 6774 (Spanish Ministry of Foreign Affairs)",
        "auto": "This is an automatic confirmation.",
    },
    "fr": {
        "subject": "Demande de devis bien reçue",
        "hello": "Bonjour {name},",
        "body": "Merci de votre message. J’ai bien reçu votre demande de devis et je vous répondrai dans les meilleurs délais.",
        "summary": "Récapitulatif de votre demande :",
        "visa": "Démarche", "deadline": "Pour le", "delivery": "Livraison", "files": "Documents joints", "none": "aucun", "sep": "\u00a0: ",
        "role": "Traductrice assermentée d’anglais n° 6774 (ministère espagnol des Affaires étrangères)",
        "auto": "Ceci est une confirmation automatique.",
    },
    "ca": {
        "subject": "Sol·licitud de pressupost rebuda",
        "hello": "Hola, {name}:",
        "body": "Gràcies per escriure’m. He rebut la vostra sol·licitud de pressupost i us respondré el més aviat possible.",
        "summary": "Resum de la vostra sol·licitud:",
        "visa": "Tràmit", "deadline": "Data límit", "delivery": "Lliurament", "files": "Documents adjunts", "none": "cap",
        "role": "Traductora jurada d’anglès núm. 6774 (Ministeri d’Afers Estrangers)",
        "auto": "Aquest és un missatge automàtic de confirmació.",
    },
}
SHORT_FIELD = 100  # los campos de opciones nunca pasan de esto; si pasan, no se repiten
DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")


# «¿Cómo me ha conocido?»: la web envía un código; Elisa lo lee en español y el registro guarda solo el código.
SOURCES = {
    "google": "Google",
    "referral": "Recomendación de un conocido",
    "forum": "Un foro o grupo (Reddit, Facebook…)",
    "professional": "Un consulado, una agencia o un abogado",
    "client": "Ya era cliente",
    "other": "Otro",
}


@dataclass
class Settings:
    backend: str = field(default_factory=lambda: os.environ.get("MAIL_BACKEND", "file"))
    api_key: str = field(default_factory=lambda: os.environ.get("BREVO_API_KEY", ""))
    mail_to: str = field(default_factory=lambda: os.environ.get("MAIL_TO", "elisa@elisavilchez.com"))
    mail_from: str = field(default_factory=lambda: os.environ.get("MAIL_FROM", "web@elisavilchez.com"))
    mail_dir: str = field(default_factory=lambda: os.environ.get("MAIL_DIR", "/tmp/form-service-mail"))
    origins: list[str] = field(
        default_factory=lambda: [
            o.strip()
            for o in os.environ.get(
                "ALLOWED_ORIGINS", "https://elisavilchez.com,https://www.elisavilchez.com,http://localhost:4000"
            ).split(",")
            if o.strip()
        ]
    )


class FormError(Exception):
    def __init__(self, code: str, status: int = 400):
        super().__init__(code)
        self.code = code
        self.status = status


# ---------------------------------------------------------------- límite por IP (en memoria)


class RateLimiter:
    """Ventana deslizante por IP. En memoria: con una instancia de Cloud Run basta para frenar abusos."""

    def __init__(self, limit: int, window: int):
        self.limit, self.window = limit, window
        self.hits: dict[str, deque] = defaultdict(deque)

    def allow(self, key: str, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        q = self.hits[key]
        while q and now - q[0] > self.window:
            q.popleft()
        if len(q) >= self.limit:
            return False
        q.append(now)
        return True


# ---------------------------------------------------------------- envío

_seq = itertools.count()


def build_email(fields: dict[str, str], files: list[tuple[str, bytes]], settings: Settings) -> dict:
    """Payload de la API de Brevo (POST /v3/smtp/email)."""
    who = fields.get("name") or fields["email"]
    subject = f"Presupuesto: {who}" + (f" – {fields['visa']}" if fields.get("visa") else "")
    rows = "".join(
        f"<tr><th align='left' style='padding:4px 12px 4px 0;vertical-align:top'>{LABELS[k]}</th>"
        f"<td style='padding:4px 0;white-space:pre-wrap'>{html.escape(fields[k])}</td></tr>"
        for k in TEXT_FIELDS
        if fields.get(k)
    )
    names = "".join(f"<li>{html.escape(n)} ({len(b) // 1024} KB)</li>" for n, b in files) or "<li>Ninguno</li>"
    body = (
        "<p>Nueva solicitud de presupuesto desde elisavilchez.com.</p>"
        f"<table>{rows}</table><p><b>Adjuntos</b></p><ul>{names}</ul>"
        "<p style='color:#666'>Responda a este email para contestar directamente al cliente.</p>"
    )
    text = "\n".join(f"{LABELS[k]}: {fields[k]}" for k in TEXT_FIELDS if fields.get(k))
    payload = {
        "sender": {"name": "Elisa Vílchez – Formulario web", "email": settings.mail_from},
        "to": [{"email": settings.mail_to}],
        "replyTo": {"email": fields["email"], "name": fields.get("name") or fields["email"]},
        "subject": subject,
        "htmlContent": body,
        "textContent": text + f"\nAdjuntos: {len(files)}",
    }
    if files:
        payload["attachment"] = [{"name": n, "content": base64.b64encode(b).decode()} for n, b in files]
    return payload


def build_confirmation(fields: dict[str, str], files: list[tuple[str, bytes]], settings: Settings) -> dict:
    """Email de confirmación al cliente (sin adjuntos). Si responde, la respuesta le llega a Elisa."""
    t = CONFIRM.get(fields.get("lang") or "", CONFIRM["en"])
    name = fields["name"][:60]
    rows = []
    if fields.get("visa") and len(fields["visa"]) <= SHORT_FIELD:
        rows.append((t["visa"], fields["visa"]))
    m = DATE_RE.match(fields.get("deadline") or "")
    if m:
        rows.append((t["deadline"], f"{m[3]}/{m[2]}/{m[1]}"))
    if fields.get("delivery") and len(fields["delivery"]) <= SHORT_FIELD:
        rows.append((t["delivery"], fields["delivery"]))
    names = [n for n, _ in files]
    rows.append((t["files"], ", ".join(names) if names else t["none"]))
    e = html.escape
    body = (
        f"<p>{e(t['hello'].format(name=name))}</p><p>{e(t['body'])}</p>"
        f"<p><b>{e(t['summary'])}</b></p><ul>"
        + "".join(f"<li>{e(k)}{t.get('sep', ': ')}{e(v)}</li>" for k, v in rows)
        + "</ul>"
        f"<p>Elisa Vílchez<br>{e(t['role'])}<br><a href='https://elisavilchez.com'>elisavilchez.com</a></p>"
        f"<p style='color:#888;font-size:12px'>{e(t['auto'])}</p>"
    )
    text = "\n".join(
        [t["hello"].format(name=name), "", t["body"], "", t["summary"]]
        + [f"- {k}{t.get('sep', ': ')}{v}" for k, v in rows]
        + ["", "Elisa Vílchez", t["role"], "https://elisavilchez.com", "", t["auto"]]
    )
    return {
        "sender": {"name": "Elisa Vílchez", "email": settings.mail_from},
        "to": [{"email": fields["email"], "name": name}],
        "replyTo": {"email": settings.mail_to, "name": "Elisa Vílchez"},
        "subject": t["subject"],
        "htmlContent": body,
        "textContent": text,
    }


async def send(payload: dict, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
    if settings.backend == "file":
        out = Path(settings.mail_dir)
        out.mkdir(parents=True, exist_ok=True)
        path = out / f"{time.time_ns()}-{next(_seq):04d}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
        log.info("email escrito en %s", path)
        return
    if not settings.api_key:
        raise FormError("not_configured", 503)
    own = client is None
    client = client or httpx.AsyncClient(timeout=30)
    try:
        r = await client.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={"api-key": settings.api_key, "accept": "application/json"},
            json=payload,
        )
    finally:
        if own:
            await client.aclose()
    if r.status_code >= 300:
        # Sin el cuerpo: podría repetir datos del formulario.
        log.error("Brevo respondió %s", r.status_code)
        raise FormError("send_failed", 502)


# ---------------------------------------------------------------- validación


def _clean(value: object) -> str:
    return str(value or "").strip()[:MAX_FIELD_CHARS]


def validate_fields(form) -> dict[str, str]:
    if _clean(form.get("website")):  # campo trampa: los humanos no lo ven
        raise FormError("spam")
    try:
        started = float(form.get("t") or 0) / 1000
    except ValueError:
        started = 0
    if not started or time.time() - started < MIN_FILL_SECONDS:
        raise FormError("too_fast")
    fields = {k: _clean(form.get(k)) for k in TEXT_FIELDS}
    if not fields["name"]:
        raise FormError("name_required")
    if not EMAIL_RE.match(fields["email"]):
        raise FormError("email_invalid")
    fields["source"] = SOURCES.get(fields["source"], "")  # código desconocido: se descarta
    return fields


async def read_files(uploads: list[UploadFile]) -> list[tuple[str, bytes]]:
    uploads = [u for u in uploads if u is not None and u.filename]
    if len(uploads) > MAX_FILES:
        raise FormError("too_many_files")
    files, total = [], 0
    for u in uploads:
        name = Path(u.filename).name[:150]
        if Path(name).suffix.lower() not in ALLOWED_EXT:
            raise FormError("file_type")
        data = await u.read(MAX_TOTAL_BYTES + 1 - total)
        total += len(data)
        if total > MAX_TOTAL_BYTES:
            raise FormError("too_large", 413)
        files.append((name, data))
    return files


# ---------------------------------------------------------------- app


def create_app(settings: Settings | None = None, client: httpx.AsyncClient | None = None) -> FastAPI:
    settings = settings or Settings()
    limiter = RateLimiter(RATE_LIMIT, RATE_WINDOW)
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(
        CORSMiddleware, allow_origins=settings.origins, allow_methods=["POST"], allow_headers=["*"], max_age=3600
    )

    @app.get("/health")
    async def health():
        return {"ok": True}

    @app.post("/quote")
    async def quote(request: Request):
        try:
            origin = request.headers.get("origin", "")
            if origin not in settings.origins:
                raise FormError("origin", 403)
            ip = (request.headers.get("x-forwarded-for") or (request.client.host if request.client else "")).split(",")[0]
            if not limiter.allow(ip.strip()):
                raise FormError("rate_limited", 429)
            try:
                form = await request.form(max_files=MAX_FILES + 1, max_part_size=MAX_TOTAL_BYTES + 1)
            except Exception:  # multipart mal formado o fuera de límites
                raise FormError("bad_form")
            fields = validate_fields(form)
            files = await read_files(form.getlist("files"))
            await send(build_email(fields, files, settings), settings, client)
            source = next((k for k, v in SOURCES.items() if v == fields["source"]), "none")
            log.info(
                "presupuesto enviado: %d adjuntos, %d KB, origen=%s",
                len(files), sum(len(b) for _, b in files) // 1024, source,
            )
            try:  # la solicitud ya ha llegado a Elisa: si falla la confirmación, no se avisa de error al cliente
                await send(build_confirmation(fields, files, settings), settings, client)
            except Exception as e:  # noqa: BLE001
                log.error("confirmación no enviada: %s", getattr(e, "code", type(e).__name__))
            return {"ok": True}
        except FormError as e:
            if e.code != "spam":
                log.info("rechazado: %s", e.code)
            # Al bot del campo trampa se le dice que todo fue bien.
            if e.code == "spam":
                return {"ok": True}
            return JSONResponse({"ok": False, "error": e.code}, status_code=e.status)

    return app


app = create_app()
