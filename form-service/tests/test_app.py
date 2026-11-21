import base64
import json
import time

import httpx
import pytest
from fastapi.testclient import TestClient

import app as svc

ORIGIN = "https://elisavilchez.com"


def fields(**over):
    base = {
        "name": "Jane Doe",
        "email": "jane@example.com",
        "visa": "Non-lucrative",
        "consulate": "Los Angeles",
        "documents": "FBI check + apostille",
        "deadline": "2026-12-20",
        "delivery": "Digital",
        "message": "Hi <b>Elisa</b>",
        "lang": "en",
        "website": "",
        "t": str(int((time.time() - 30) * 1000)),
    }
    base.update(over)
    return base


def make_client(tmp_path, backend="file", transport=None, api_key=""):
    settings = svc.Settings(backend=backend, api_key=api_key, mail_dir=str(tmp_path), origins=[ORIGIN])
    http = httpx.AsyncClient(transport=transport) if transport else None
    return TestClient(svc.create_app(settings, http)), tmp_path


def post(client, data, files=None, origin=ORIGIN, ip="1.1.1.1"):
    return client.post("/quote", data=data, files=files, headers={"origin": origin, "x-forwarded-for": ip})


def written(tmp_path):
    return [json.loads(p.read_text()) for p in sorted(tmp_path.glob("*.json"))]


def to_elisa(tmp_path):
    return [m for m in written(tmp_path) if m["to"] == [{"email": "elisa@elisavilchez.com"}]]


def confirmations(tmp_path):
    return [m for m in written(tmp_path) if m["to"][0]["email"] != "elisa@elisavilchez.com"]


def test_envia_formulario_con_adjuntos(tmp_path):
    c, d = make_client(tmp_path)
    r = post(c, fields(), files=[("files", ("fbi.pdf", b"%PDF-1.4 fake", "application/pdf"))])
    assert r.status_code == 200 and r.json() == {"ok": True}
    [mail] = to_elisa(d)
    assert mail["to"] == [{"email": "elisa@elisavilchez.com"}]
    assert mail["replyTo"]["email"] == "jane@example.com"
    assert mail["sender"]["email"] == "web@elisavilchez.com"
    assert mail["subject"] == "Presupuesto: Jane Doe – Non-lucrative"
    assert base64.b64decode(mail["attachment"][0]["content"]) == b"%PDF-1.4 fake"
    assert "&lt;b&gt;Elisa&lt;/b&gt;" in mail["htmlContent"]  # el HTML del cliente se escapa


def test_sin_adjuntos_no_lleva_campo_attachment(tmp_path):
    c, d = make_client(tmp_path)
    assert post(c, fields()).status_code == 200
    assert "attachment" not in to_elisa(d)[0]


@pytest.mark.parametrize(
    "over,code",
    [({"email": "no-es-email"}, "email_invalid"), ({"name": ""}, "name_required"), ({"t": str(int(time.time() * 1000))}, "too_fast"), ({"t": ""}, "too_fast")],
)
def test_validaciones(tmp_path, over, code):
    c, d = make_client(tmp_path)
    r = post(c, fields(**over))
    assert r.status_code == 400 and r.json()["error"] == code
    assert written(d) == []


def test_campo_trampa_finge_exito_y_no_envia(tmp_path):
    c, d = make_client(tmp_path)
    r = post(c, fields(website="http://spam"))
    assert r.json() == {"ok": True}
    assert written(d) == []


def test_origen_no_permitido(tmp_path):
    c, d = make_client(tmp_path)
    r = post(c, fields(), origin="https://evil.example")
    assert r.status_code == 403 and written(d) == []


def test_tipo_de_archivo_no_permitido(tmp_path):
    c, d = make_client(tmp_path)
    r = post(c, fields(), files=[("files", ("virus.exe", b"MZ", "application/octet-stream"))])
    assert r.status_code == 400 and r.json()["error"] == "file_type"


def test_demasiado_grande(tmp_path, monkeypatch):
    monkeypatch.setattr(svc, "MAX_TOTAL_BYTES", 1000)
    c, d = make_client(tmp_path)
    big = [("files", ("a.pdf", b"x" * 600, "application/pdf")), ("files", ("b.pdf", b"x" * 600, "application/pdf"))]
    r = post(c, fields(), files=big)
    assert r.status_code == 413 and written(d) == []


def test_demasiados_archivos(tmp_path):
    c, d = make_client(tmp_path)
    many = [("files", (f"{i}.pdf", b"x", "application/pdf")) for i in range(svc.MAX_FILES + 1)]
    r = post(c, fields(), files=many)
    assert r.status_code == 400 and written(d) == []


def test_limite_por_ip(tmp_path):
    c, d = make_client(tmp_path)
    codes = [post(c, fields(), ip="9.9.9.9").status_code for _ in range(svc.RATE_LIMIT + 1)]
    assert codes[:-1] == [200] * svc.RATE_LIMIT and codes[-1] == 429
    assert post(c, fields(), ip="8.8.8.8").status_code == 200  # otra IP no se ve afectada


def test_brevo_recibe_clave_y_payload(tmp_path):
    seen = []

    def handler(request: httpx.Request):
        seen.append((str(request.url), request.headers["api-key"], json.loads(request.content)))
        return httpx.Response(201, json={"messageId": "x"})

    c, d = make_client(tmp_path, backend="brevo", transport=httpx.MockTransport(handler), api_key="k-123")
    assert post(c, fields()).status_code == 200
    assert len(seen) == 2  # a Elisa y la confirmación al cliente
    for url, key, _ in seen:
        assert url == "https://api.brevo.com/v3/smtp/email" and key == "k-123"
    assert seen[0][2]["replyTo"]["email"] == "jane@example.com"
    assert seen[1][2]["to"][0]["email"] == "jane@example.com"


def test_si_falla_la_confirmacion_el_cliente_ve_exito(tmp_path):
    calls = []

    def handler(request: httpx.Request):
        calls.append(1)
        return httpx.Response(201 if len(calls) == 1 else 500)

    c, _ = make_client(tmp_path, backend="brevo", transport=httpx.MockTransport(handler), api_key="k")
    r = post(c, fields())
    assert r.status_code == 200 and r.json() == {"ok": True} and len(calls) == 2


@pytest.mark.parametrize(
    "lang,subject,snippet",
    [
        ("es", "Solicitud de presupuesto recibida", "a la mayor brevedad"),
        ("en", "Quote request received", "as soon as possible"),
        ("fr", "Demande de devis bien reçue", "dans les meilleurs délais"),
        ("ca", "Sol·licitud de pressupost rebuda", "el més aviat possible"),
        ("", "Quote request received", "as soon as possible"),  # sin idioma: inglés
    ],
)
def test_confirmacion_en_el_idioma_de_la_pagina(tmp_path, lang, subject, snippet):
    c, d = make_client(tmp_path)
    post(c, fields(lang=lang), files=[("files", ("fbi.pdf", b"x", "application/pdf"))])
    [conf] = confirmations(d)
    assert conf["subject"] == subject and snippet in conf["textContent"]
    assert conf["to"] == [{"email": "jane@example.com", "name": "Jane Doe"}]
    assert conf["replyTo"]["email"] == "elisa@elisavilchez.com"
    assert "attachment" not in conf
    assert "fbi.pdf" in conf["textContent"] and "20/12/2026" in conf["textContent"]


def test_confirmacion_no_repite_texto_libre(tmp_path):
    c, d = make_client(tmp_path)
    spam = "Compre ya en http://spam.example " * 10
    post(c, fields(name="Jane " + spam, message=spam, documents=spam, consulate=spam, visa=spam))
    [conf] = confirmations(d)
    # Solo puede colarse lo que quepa en los 60 caracteres del nombre; el resto no se repite.
    assert conf["textContent"].count("spam.example") <= 1 and conf["htmlContent"].count("spam.example") <= 1
    assert len(conf["to"][0]["name"]) <= 60


def test_brevo_falla_devuelve_502(tmp_path):
    c, d = make_client(tmp_path, backend="brevo", transport=httpx.MockTransport(lambda r: httpx.Response(500)), api_key="k")
    r = post(c, fields())
    assert r.status_code == 502 and r.json()["error"] == "send_failed"


def test_brevo_sin_clave_devuelve_503(tmp_path):
    c, d = make_client(tmp_path, backend="brevo")
    assert post(c, fields()).status_code == 503


def test_cors_preflight(tmp_path):
    c, _ = make_client(tmp_path)
    r = c.options("/quote", headers={"origin": ORIGIN, "access-control-request-method": "POST"})
    assert r.headers["access-control-allow-origin"] == ORIGIN
    r = c.options("/quote", headers={"origin": "https://evil.example", "access-control-request-method": "POST"})
    assert "access-control-allow-origin" not in r.headers


def test_health(tmp_path):
    c, _ = make_client(tmp_path)
    assert c.get("/health").json() == {"ok": True}


@pytest.mark.parametrize("code,shown", [("forum", "Un foro o grupo (Reddit, Facebook…)"), ("", None), ("<b>spam</b>", None)])
def test_como_me_ha_conocido(tmp_path, code, shown, caplog):
    c, d = make_client(tmp_path)
    with caplog.at_level("INFO", logger="form-service"):
        assert post(c, fields(source=code)).status_code == 200
    [mail] = to_elisa(d)
    if shown:
        assert f"Cómo me ha conocido: {shown}" in mail["textContent"]
        assert "origen=forum" in caplog.text
    else:
        assert "Cómo me ha conocido" not in mail["textContent"] and "spam" not in mail["htmlContent"]
        assert "origen=none" in caplog.text
