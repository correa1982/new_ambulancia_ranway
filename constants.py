import os

TIPOS_DOCUMENTO = ["CC", "TI", "CE", "PA", "RC", "PEP", "NIT", "NN"]

TIPOS_AFILIACION = ["Contributivo", "Subsidiado", "Vinculado", "Excepción", "Especial", "No afiliado"]

ASEGURADORAS = [
    "Nueva EPS", "Sura", "Sanitas", "Salud Total", "Compensar",
    "Famisanar", "Coosalud", "Mutual SER", "Aliansalud",
    "Comfenalco Valle", "Capital Salud", "Otra"
]

PASB_OPCIONES = ["PASB-1", "PASB-2", "PASB-3", "PASB-4"]
PASM_OPCIONES = ["PASM-1", "PASM-2", "PASM-3", "PASM-4"]

REQUIRED_PATIENT_FIELDS = [
    ("identificacion_paciente", "Número de identificación"),
    ("tipo_documento",          "Tipo de documento"),
    ("primer_nombre",           "Primer nombre"),
    ("primer_apellido",         "Primer apellido"),
    ("fecha_nacimiento",        "Fecha de nacimiento"),
    ("sexo_biologico",          "Sexo biológico"),
    ("tipo_afiliacion",         "Tipo de afiliación"),
    ("aseguradora",             "Aseguradora (EPS)"),
    ("motivo_consulta",         "Motivo de consulta"),
    ("enfermedad_actual",       "Enfermedad actual"),
    ("diagnostico_cie10",       "Impresión diagnóstica (CIE10)"),
]

PATIENT_MCI_FIELDS = [
    "identificacion_paciente", "tipo_documento", "primer_apellido", "segundo_apellido",
    "primer_nombre", "segundo_nombre", "fecha_nacimiento", "edad",
    "telefono", "correo_electronico", "direccion",
    "departamento_residencia", "municipio_residencia", "barrio_residencia",
    "sexo_biologico", "identidad_genero", "estado_civil", "ocupacion",
    "nacionalidad", "habitante_calle", "pertenencia_etnica", "discapacidad",
    "tipo_afiliacion", "aseguradora",
    "presion_arterial", "saturacion_oxigeno", "frecuencia_cardiaca", "frecuencia_respiratoria", "glicemia",
    "antecedentes_personales", "antecedentes_quirurgicos", "antecedentes_toxicologicos",
    "antecedentes_alergicos", "antecedentes_ginecobstetricos", "medicamentos_actuales",
    "otros_antecedentes", "antecedentes_familiares",
    "motivo_consulta", "enfermedad_actual", "analisis", "plan",
    "diagnostico_cie10",
    "registrado_por", "registrado_por_identificacion",
    "registro_medico_registrador", "perfil_registrador", "firma_registrador",
    "fecha_inicio_atencion", "fecha_finalizacion_registro",
    "atencion_colectiva_id", "finalizado",
]

PATIENT_FULL_FIELDS = PATIENT_MCI_FIELDS + [
    "dolor",
    "aplica_acompanante", "acompanante_nombre", "acompanante_tipo_doc", "acompanante_doc",
    "acompanante_telefono", "acompanante_parentesco",
    "aplica_responsable", "responsable_nombre", "responsable_tipo_doc", "responsable_doc",
    "responsable_telefono", "responsable_parentesco",
    "primer_respondiente", "es_emergencia_medica", "detalle_emergencia_medica",
    "es_emergencia_traumatica", "detalle_emergencia_traumatica",
    "triage_fecha_hora", "triage_clasificacion",
    "glasgow_ocular", "glasgow_verbal", "glasgow_motora", "glasgow_total",
    "estado_consciencia", "cincinnati_facial", "cincinnati_brazo", "cincinnati_habla",
    "cincinnati_total", "rts_total",
    "examen_fisico", "datos_complementarios",
    "soat_aseguradora", "soat_vigencia",
    "hora_despacho", "hora_arribo", "nombre_evento", "tipo_servicio",
    "departamento", "municipio", "barrio", "direccion_atencion",
    "ambito_territorial", "entorno_atencion", "clasificacion",
    "causa_motiva_atencion", "tipo_traslado", "entorno_otro",
    "inmovilizacion", "otros_procedimientos", "ventilacion_mecanica",
    "torniquete", "x_items", "a_items", "b_items", "c_items", "d_items", "e_items"
]

EXAMEN_FISICO_KEYS = [
    "cabeza", "ojos", "nariz", "oidos", "boca", "cuello", "torax", "cardio",
    "pulmonar", "abdomen", "pelvis", "piel", "genito_urinario", "extremidades",
    "osteomuscular", "vascular_periferico", "neurologico", "estado_mental"
]

CHECKLIST_CONFIG = {
    "tam": {
        "titulo": "Check List TAM",
        "subtitulo": "Transporte Asistencial Medicalizado",
        "table": "checklist_tam",
        "template": "checklist_tam.html",
    },
    "tab": {
        "titulo": "Check List TAB",
        "subtitulo": "Transporte Asistencial Básico",
        "table": "checklist_tab",
        "template": "checklist_tab.html",
    },
    "avanzada": {
        "titulo": "Check List Avanzada",
        "subtitulo": "Avanzada",
        "table": "checklist_avanzada",
        "template": "checklist_avanzada.html",
    },
    "pasb": {
        "titulo": "Check List PASB",
        "subtitulo": "Puesto de Atención en Salud Básico",
        "table": "checklist_pasb",
        "template": "checklist_pasb.html",
    },
    "pasm": {
        "titulo": "Check List PASM",
        "subtitulo": "Puesto de Atención en Salud Medicalizado",
        "table": "checklist_pasm",
        "template": "checklist_pasm.html",
    },
    "equipos": {
        "titulo": "Preoperacional de Equipos",
        "subtitulo": "Preoperacional Equipos de Rescate",
        "table": "checklist_equipos",
        "template": "checklist_equipos.html",
    },
    "calif_atencion": {
        "titulo": "Calif. Atención",
        "subtitulo": "Califica La Atención",
        "table": "calif_atencion",
        "template": "checklist_calif_atencion.html",
    },
    "segur_paciente": {
        "titulo": "Seguridad del Paciente",
        "subtitulo": "Reporte de Seguridad del Paciente",
        "table": "segur_paciente",
        "template": "checklist_segur_paciente.html",
    },
}
