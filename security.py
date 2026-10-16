import secrets
from urllib.parse import urlsplit

from flask import request, g, abort
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

# CSRF validado con el patron "double-submit cookie":
#   - El servidor emite una cookie firmada csrftoken (HttpOnly, SameSite=Lax).
#   - El cliente debe devolver el mismo token en un campo de formulario
#     (csrf_token) o en una cabecera (X-CSRFToken).
#   - Es independiente de la sesion de Flask, por lo que los registros offline
#     del PWA que se repliegan mas tarde siguen funcionando mientras la cookie
#     del dispositivo este vigente.
_CSRF_COOKIE = "csrftoken"
_CSRF_FIELD = "csrf_token"
_CSRF_HEADERS = ("X-CSRFToken", "X-CSRF-Token", "X-CSRF-TOKEN")
_CSRF_MAX_AGE = 7 * 24 * 3600

# Endpoints GET que mutan estado. Se validan por mismo-origen (Origin/Referer)
# ya que este tipo de peticiones no puede portar token sin romper los enlaces.
_GET_MUTATING_ENDPOINTS = {
    "toggle_usuario",
    "reset_usuario_contrasena",
    "clear_import_result",
    "admin_vehiculo_toggle",
    "admin_vehiculo_eliminar",
    "admin_categoria_toggle",
    "admin_categoria_eliminar",
    "admin_checklist_mover",
    "admin_checklist_toggle_vencimiento",
    "admin_checklist_toggle",
    "admin_checklist_eliminar",
    "admin_pas_opcion_toggle",
    "admin_pas_opcion_eliminar",
    "admin_aseguradora_toggle",
    "admin_aseguradora_eliminar",
    "admin_aseguradora_soat_toggle",
    "admin_aseguradora_soat_eliminar",
}


def _serializer():
    from flask import current_app
    return URLSafeTimedSerializer(current_app.secret_key, salt="csrf-token")


def _read_row_token():
    raw = request.cookies.get(_CSRF_COOKIE)
    if not raw:
        return None
    try:
        return _serializer().loads(raw, max_age=_CSRF_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None


def ensure_csrf_token():
    token = _read_row_token()
    if token:
        g.csrf_token = token
        g.csrf_signed = None
    else:
        token = secrets.token_urlsafe(32)
        g.csrf_token = token
        g.csrf_signed = _serializer().dumps(token)


def set_csrf_cookie_if_needed(response):
    signed = getattr(g, "csrf_signed", None)
    if signed:
        response.set_cookie(
            _CSRF_COOKIE,
            signed,
            max_age=_CSRF_MAX_AGE,
            httponly=True,
            samesite="Lax",
            secure=request.is_secure,
        )
    return response


def csrf_token():
    if not hasattr(g, "csrf_token"):
        ensure_csrf_token()
    return g.csrf_token


def _same_origin():
    origin = request.headers.get("Origin")
    referer = request.headers.get("Referer")
    if not origin and not referer:
        return None
    for value in (origin, referer):
        if not value:
            continue
        try:
            parsed = urlsplit(value)
        except ValueError:
            return False
        if parsed.netloc and parsed.netloc.lower() != request.host.lower():
            return False
    return True


def validate_csrf():
    method = request.method

    if method in ("POST", "PUT", "PATCH", "DELETE"):
        expected = _read_row_token()
        if not expected:
            abort(400, description="Falta token CSRF.")
        submitted = request.form.get(_CSRF_FIELD)
        if not submitted:
            for header_name in _CSRF_HEADERS:
                submitted = request.headers.get(header_name)
                if submitted:
                    break
        if not submitted or not secrets.compare_digest(submitted, expected):
            abort(400, description="Token CSRF inválido.")
        return

    if method == "GET" and request.endpoint in _GET_MUTATING_ENDPOINTS:
        if _same_origin() is False:
            abort(403, description="Origen no permitido.")