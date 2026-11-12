"""La base de datos se crea completa con init_db() y cumple las reglas principales de la política.

Las pruebas marcadas con xfail son incumplimientos conocidos de la política
(ver docs/auditoria/solicitud-cambios.md). Aparecen como "xfail" mientras estén
pendientes; cuando se corrijan aparecerán como "XPASS" y se debe quitar la marca.
"""
import pytest

from conftest import BASE

TABLAS_ESPERADAS = [
    "usuarios", "archivador", "archivador_categorias", "archivador_formularios",
    "nomina", "nomina_empleados", "nomina_pagos", "items_nomina_empleados", "items_pagos_varios",
    "registro_pagos_nomina_empleados", "registro_pagos_varios",
    "pacientes", "configuracion", "imagenes", "eventos", "atencion_vehiculo", "atencion_colectiva",
    "preoperacional", "checklist_tam", "checklist_tab", "checklist_avanzada", "checklist_pasb",
    "checklist_pasm", "checklist_equipos", "calif_atencion", "segur_paciente", "checklist_items",
    "checklist_pasb_traslados", "checklist_categorias", "checklist_pas_opciones", "reporte_gasto",
    "vehiculos", "aseguradoras", "aseguradoras_soat",
    "ths_sga_records", "ths_trip_records", "ths_soc_records",
    "ths_licencias_conduccion", "ths_vacunas", "ths_contratos", "ths_certificados_adicionales",
    "inventarios", "inventarios_catalogo", "inventarios_historial",
    "programacion_operativa", "programacion_operativa_integrantes", "personal_operativo",
    "registro_voluntariado", "reporte_actividades",
]


def _tablas(bd):
    filas = bd.todos("SELECT table_name AS t FROM information_schema.tables WHERE table_schema = ?", (BASE,))
    return {fila["t"] for fila in filas}


def test_init_db_crea_todas_las_tablas(bd):
    faltantes = sorted(set(TABLAS_ESPERADAS) - _tablas(bd))
    assert not faltantes, f"init_db() no creó estas tablas: {faltantes}"


def test_todas_las_tablas_son_innodb(bd):
    filas = bd.todos(
        "SELECT table_name AS t, engine AS e FROM information_schema.tables WHERE table_schema = ?", (BASE,))
    otras = [f"{f['t']} ({f['e']})" for f in filas if (f["e"] or "").lower() != "innodb"]
    assert not otras, f"Tablas que no son InnoDB: {otras}"


def test_init_db_se_puede_ejecutar_otra_vez(app, bd):
    """CAM-03: init_db() corre en cada arranque; repetirlo no debe fallar ni cambiar las tablas."""
    from db import init_db
    antes = _tablas(bd)
    init_db()
    assert _tablas(bd) == antes


def test_catalogos_iniciales_cargados(bd):
    assert bd.contar("aseguradoras") > 0, "init_db() no cargó las aseguradoras"


@pytest.mark.xfail(reason="SOL-04 pendiente: hay llaves foráneas con ON DELETE CASCADE", strict=False)
def test_ninguna_llave_foranea_borra_en_cascada(bd):
    filas = bd.todos(
        "SELECT constraint_name AS c, table_name AS t FROM information_schema.referential_constraints "
        "WHERE constraint_schema = ? AND delete_rule = 'CASCADE'", (BASE,))
    assert not filas, "Llaves foráneas con CASCADE: " + ", ".join(f"{f['t']}.{f['c']}" for f in filas)


@pytest.mark.xfail(reason="SOL-06 pendiente: db.py declara collation en algunas tablas", strict=False)
def test_las_tablas_no_declaran_collation():
    """TIP-04: las tablas heredan la collation de la base. Si una tabla la declara, en un servidor
    con otra collation por defecto (como producción) quedan mezcladas. Se revisa en el código,
    porque en un MySQL local con la misma collation por defecto no se notaría."""
    import re
    from conftest import RAIZ
    codigo = (RAIZ / "db.py").read_text(encoding="utf-8")
    declaraciones = re.findall(r"COLLATE\s*=?\s*(\w+)", codigo, re.I)
    assert not declaraciones, f"db.py declara collation {len(declaraciones)} vez(veces): {sorted(set(declaraciones))}"
