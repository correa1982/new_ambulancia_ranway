"""Los formularios guardan datos, tanto en el envío normal como en la sincronización offline.

En la sincronización offline el celular espera una respuesta JSON con
status = "success". Si no la recibe, vuelve a enviar el registro (duplicados)
o lo deja pendiente para siempre.
"""
from datetime import date

import pytest

from conftest import enviar, sin_error_de_servidor

HOY = date.today().isoformat()
TIPOS_CHECKLIST = ["tam", "tab", "avanzada", "pasb", "pasm", "equipos", "calif_atencion", "segur_paciente"]
TABLA_CHECKLIST = {
    "tam": "checklist_tam", "tab": "checklist_tab", "avanzada": "checklist_avanzada",
    "pasb": "checklist_pasb", "pasm": "checklist_pasm", "equipos": "checklist_equipos",
    "calif_atencion": "calif_atencion", "segur_paciente": "segur_paciente",
}


def _paciente(identificacion, **extra):
    datos = {
        "accion": "borrador", "tipo_documento": "CC", "identificacion_paciente": identificacion,
        "primer_nombre": "Paciente", "primer_apellido": "Prueba",
        "fecha_inicio_atencion": f"{HOY} 08:00", "atencion_colectiva_id": "",
    }
    datos.update(extra)
    return datos


def _sync_offline(datos, dedupe_key=""):
    datos = dict(datos)
    datos.update({"_offline_sync": "1", "_offline_id": "1", "_offline_dedupe_key": dedupe_key})
    return datos


def _es_exito_json(respuesta):
    return respuesta.status_code == 200 and (respuesta.get_json(silent=True) or {}).get("status") == "success"


# ── Historia clínica ─────────────────────────────────────────────────────
def test_historia_clinica_borrador(cliente_operativo, bd):
    antes = bd.contar("pacientes")
    respuesta = enviar(cliente_operativo, "/formulario", _paciente("1000000001"))
    assert respuesta.status_code == 302
    assert bd.contar("pacientes") == antes + 1


def test_historia_clinica_finalizar_sin_campos_obligatorios_no_se_guarda(cliente_operativo, bd):
    antes = bd.contar("pacientes")
    respuesta = enviar(cliente_operativo, "/formulario", _paciente("1000000002", accion="finalizar"))
    assert sin_error_de_servidor(respuesta)
    assert bd.contar("pacientes") == antes


def test_historia_clinica_finalizar_completa(cliente_operativo, bd):
    antes = bd.contar("pacientes", "finalizado = 1")
    datos = _paciente(
        "1000000003", accion="finalizar", fecha_nacimiento="1990-05-10", sexo_biologico="Hombre",
        tipo_afiliacion="Contributivo", aseguradora="Nueva EPS", motivo_consulta="Dolor",
        enfermedad_actual="Dolor de prueba", diagnostico_cie10="R52 - Dolor",
    )
    respuesta = enviar(cliente_operativo, "/formulario", datos)
    assert respuesta.status_code == 302
    assert bd.contar("pacientes", "finalizado = 1") == antes + 1


def test_historia_clinica_offline_y_sin_duplicados(cliente_operativo, bd):
    datos = _paciente("1000000004")
    clave = f"CC|1000000004|{HOY} 08:00|Paciente|Prueba|"
    antes = bd.contar("pacientes")

    primera = enviar(cliente_operativo, "/formulario", _sync_offline(datos, clave))
    assert _es_exito_json(primera), primera.get_data(as_text=True)[:300]
    assert bd.contar("pacientes") == antes + 1

    # El celular puede reenviar el mismo registro (por ejemplo, si se cortó la conexión
    # antes de recibir la respuesta). El servidor no debe duplicarlo.
    segunda = enviar(cliente_operativo, "/formulario", _sync_offline(datos, clave))
    assert _es_exito_json(segunda)
    assert bd.contar("pacientes") == antes + 1


def test_historia_clinica_offline_finalizar_incompleta_responde_error_json(cliente_operativo):
    respuesta = enviar(cliente_operativo, "/formulario",
                       _sync_offline(_paciente("1000000005", accion="finalizar")))
    assert respuesta.status_code == 400
    assert respuesta.get_json()["status"] == "error"


# ── Eventos, atención colectiva y atención vehículo ──────────────────────
FORMULARIOS_SIMPLES = {
    "eventos": ("/formularios/eventos", "eventos",
                {"fecha_inicio": HOY, "hora_inicio": "08:00", "tipo_evento": "Prueba",
                 "direccion": "Calle 1", "municipio": "Medellín"}),
    "atencion_colectiva": ("/formularios/atencion-colectiva", "atencion_colectiva",
                           {"fecha_inicio": HOY, "hora_inicio": "08:00", "lugar": "Lugar de prueba",
                            "tipo_incidente": "Prueba"}),
    "atencion_vehiculo": ("/formularios/atencion_vehiculo", "atencion_vehiculo",
                          {"accion": "borrador", "consecutivo": "AV-1", "municipio": "Medellín",
                           "direccion": "Calle 1", "tipo": "Prueba", "descripcion": "Prueba"}),
}


@pytest.mark.parametrize("nombre", sorted(FORMULARIOS_SIMPLES))
def test_formulario_envio_normal(nombre, cliente_operativo, bd):
    url, tabla, datos = FORMULARIOS_SIMPLES[nombre]
    antes = bd.contar(tabla)
    respuesta = enviar(cliente_operativo, url, datos)
    assert respuesta.status_code == 302, f"{nombre}: respuesta {respuesta.status_code}"
    assert bd.contar(tabla) == antes + 1, f"{nombre}: no se guardó el registro"


@pytest.mark.parametrize("nombre", sorted(FORMULARIOS_SIMPLES))
def test_formulario_sincronizacion_offline(nombre, cliente_operativo, bd):
    url, tabla, datos = FORMULARIOS_SIMPLES[nombre]
    antes = bd.contar(tabla)
    respuesta = enviar(cliente_operativo, url, _sync_offline(datos))
    assert _es_exito_json(respuesta), f"{nombre}: el celular no recibió la confirmación JSON"
    assert bd.contar(tabla) == antes + 1, f"{nombre}: respondió éxito pero no guardó"


# ── Checklists ───────────────────────────────────────────────────────────
@pytest.mark.parametrize("tipo", TIPOS_CHECKLIST)
def test_checklist_pagina_carga(tipo, cliente_admin):
    respuesta = cliente_admin.get(f"/checklist/{tipo}")
    assert respuesta.status_code == 200, f"{tipo}: {respuesta.status_code}"


@pytest.mark.parametrize("tipo", TIPOS_CHECKLIST)
def test_checklist_borrador(tipo, cliente_admin, bd):
    tabla = TABLA_CHECKLIST[tipo]
    antes = bd.contar(tabla)
    respuesta = enviar(cliente_admin, f"/checklist/{tipo}",
                       {"accion": "borrador", "fecha": HOY, "hora": "08:00", "placa": "PRU123"})
    assert respuesta.status_code == 302
    assert bd.contar(tabla) == antes + 1, f"{tipo}: el borrador no se guardó"


@pytest.mark.parametrize("tipo", TIPOS_CHECKLIST)
def test_checklist_sincronizacion_offline(tipo, cliente_admin, bd):
    tabla = TABLA_CHECKLIST[tipo]
    antes = bd.contar(tabla)
    respuesta = enviar(cliente_admin, f"/checklist/{tipo}",
                       _sync_offline({"accion": "borrador", "fecha": HOY, "hora": "08:00", "placa": "PRU123"}))
    assert _es_exito_json(respuesta), f"{tipo}: el celular no recibió la confirmación JSON"
    assert bd.contar(tabla) == antes + 1


def test_checklist_tipo_invalido_no_falla(cliente_admin):
    respuesta = cliente_admin.get("/checklist/no_existe")
    assert respuesta.status_code == 302


# ── Reporte de gasto ─────────────────────────────────────────────────────
def test_reporte_gasto_borrador_offline(cliente_operativo, bd):
    respuesta = enviar(cliente_operativo, "/reporte_gasto/nuevo",
                       _sync_offline({"accion": "borrador", "fecha": HOY, "nombre_evento": "Evento prueba"}))
    assert _es_exito_json(respuesta), "El celular no recibió la confirmación JSON (causaba duplicados)"
    assert bd.contar("reporte_gasto", "finalizado = 0") >= 1


def test_reporte_gasto_finalizar_incompleto_offline_responde_error_json(cliente_operativo):
    respuesta = enviar(cliente_operativo, "/reporte_gasto/nuevo",
                       _sync_offline({"accion": "finalizar", "fecha": HOY}))
    assert respuesta.status_code == 400
    assert respuesta.get_json()["status"] == "error"


# ── Otros formularios con página propia ──────────────────────────────────
@pytest.mark.parametrize("url", [
    "/preoperacional", "/formularios/reporte_actividades/nuevo", "/voluntariado",
    "/formulario_mci", "/programacion_operativa", "/archivador/nuevo",
])
def test_formularios_cargan(url, cliente_admin):
    respuesta = cliente_admin.get(url)
    assert sin_error_de_servidor(respuesta), f"{url}: {respuesta.status_code}"
