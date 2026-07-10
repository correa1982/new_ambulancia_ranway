import json
from datetime import date, datetime
from flask import render_template, request, redirect, url_for, session
from db import get_db
from utils import login_required, hoy
from constants import CHECKLIST_CONFIG

# ─────────────────────────────────────────────────────────────
# Catalogue of all queryable form types.
# Each entry defines how to fetch and display records.
# ─────────────────────────────────────────────────────────────
FORM_TYPES = {
    "hc": {
        "label": "Historia Clínica Individual",
        "icon": "🚑",
        "color": "#3b82f6",
        "table": "pacientes",
        "date_col": "fecha_registro",
        "url_func": "ver_hc",           # uses token param
        "use_token": True,
    },
    "eventos": {
        "label": "Formulario de Eventos",
        "icon": "📅",
        "color": "#8b5cf6",
        "table": "eventos",
        "date_col": "fecha_registro",
        "url_func": "ver_evento",
        "url_param": "evento_id",
        "use_token": False,
    },
    "atencion_colectiva": {
        "label": "Atención Colectiva / MCI",
        "icon": "👥",
        "color": "#06b6d4",
        "table": "atencion_colectiva",
        "date_col": "fecha_registro",
        "url_func": "ver_atencion_colectiva",
        "url_param": "id",
        "use_token": False,
    },
    "preoperacional": {
        "label": "Preoperacional Conductores",
        "icon": "🚗",
        "color": "#f59e0b",
        "table": "preoperacional",
        "date_col": "fecha_registro",
        "url_func": "ver_preoperacional",
        "url_param": "record_id",
        "use_token": False,
    },
    "tam": {
        "label": "Check List TAM",
        "icon": "🏥",
        "color": "#10b981",
        "table": "checklist_tam",
        "date_col": "fecha_registro",
        "url_func": "ver_checklist",
        "url_param": "record_id",
        "use_token": False,
        "tipo_param": "tam",
    },
    "tab": {
        "label": "Check List TAB",
        "icon": "🩺",
        "color": "#0ea5e9",
        "table": "checklist_tab",
        "date_col": "fecha_registro",
        "url_func": "ver_checklist",
        "url_param": "record_id",
        "use_token": False,
        "tipo_param": "tab",
    },
    "pasb": {
        "label": "Check List PASB",
        "icon": "🧰",
        "color": "#f97316",
        "table": "checklist_pasb",
        "date_col": "fecha_registro",
        "url_func": "ver_checklist",
        "url_param": "record_id",
        "use_token": False,
        "tipo_param": "pasb",
    },
    "pasm": {
        "label": "Check List PASM",
        "icon": "🎒",
        "color": "#ec4899",
        "table": "checklist_pasm",
        "date_col": "fecha_registro",
        "url_func": "ver_checklist",
        "url_param": "record_id",
        "use_token": False,
        "tipo_param": "pasm",
    },
    "equipos": {
        "label": "Preoperacional Equipos",
        "icon": "🩺",
        "color": "#6366f1",
        "table": "checklist_equipos",
        "date_col": "fecha_registro",
        "url_func": "ver_checklist",
        "url_param": "record_id",
        "use_token": False,
        "tipo_param": "equipos",
    },
    "avanzada": {
        "label": "Check List Avanzada",
        "icon": "⚡",
        "color": "#0284c7",
        "table": "checklist_avanzada",
        "date_col": "fecha_registro",
        "url_func": "ver_checklist",
        "url_param": "record_id",
        "use_token": False,
        "tipo_param": "avanzada",
    },
    "atencion_vehiculo": {
        "label": "Atención Vehículo de Intervención",
        "icon": "🚒",
        "color": "#1e6fbf",
        "table": "atencion_vehiculo",
        "date_col": "fecha_registro",
        "url_func": "ver_atencion_vehiculo",
        "url_param": "id",
        "use_token": False,
    },
}


def _build_summary(row, tipo_key, cfg):
    """Build a human-readable one-line summary for a record."""
    r = dict(row)
    if tipo_key == "hc":
        nombre = f"{r.get('primer_nombre', '')} {r.get('primer_apellido', '')}".strip()
        return nombre or r.get("identificacion_paciente", "—")
    if tipo_key == "eventos":
        return r.get("tipo_evento") or r.get("municipio") or "—"
    if tipo_key == "atencion_colectiva":
        return r.get("lugar") or r.get("tipo_incidente") or "—"
    if tipo_key == "preoperacional":
        return r.get("placa") or r.get("conductor") or "—"
    if tipo_key in ("tam", "tab"):
        return r.get("placa") or r.get("turno") or "—"
    if tipo_key == "avanzada":
        return f"Ev: {r.get('evento') or '—'} · Bot: {r.get('botiquin') or '—'}"
    if tipo_key in ("pasb", "pasm"):
        return r.get("ubicacion") or "—"
    if tipo_key == "equipos":
        return r.get("grupo_equipos") or "—"
    if tipo_key == "atencion_vehiculo":
        consecutivo = f"Consecutivo #{r.get('consecutivo', '')}"
        tipo_serv = r.get('tipo', '')
        if tipo_serv:
            return f"{consecutivo} - {tipo_serv}"
        return consecutivo
    return "—"


def register_routes(app, serializer):

    @app.route("/pendientes")
    @login_required
    def ver_pendientes():
        user_ident = session["usuario"]["identificacion"]
        user_perfil = session["usuario"].get("perfil", "")
        conn = get_db()
        
        # 1. Historia Clínica Individual (pacientes where atencion_colectiva_id IS NULL and finalizado = 0)
        hcs = conn.execute(
            "SELECT * FROM pacientes WHERE atencion_colectiva_id IS NULL AND finalizado = 0 AND registrado_por_identificacion = ? AND perfil_registrador = ? ORDER BY id DESC",
            (user_ident, user_perfil)
        ).fetchall()
        
        # 2. Atención Colectiva (atencion_colectiva where finalizado = 0)
        acs = conn.execute(
            "SELECT * FROM atencion_colectiva WHERE finalizado = 0 AND registrado_por_identificacion = ? AND perfil_registrador = ? ORDER BY id DESC",
            (user_ident, user_perfil)
        ).fetchall()
        
        # Encode IDs / build edit URLs
        hc_list = []
        for r in hcs:
            r_dict = dict(r)
            r_dict["edit_url"] = url_for("formulario", id=serializer.dumps(r["id"]))
            hc_list.append(r_dict)
            
        ac_list = []
        ac_ids = [r["id"] for r in acs]
        count_map = {}
        if ac_ids:
            placeholders = ",".join("?" * len(ac_ids))
            for row in conn.execute(f"SELECT atencion_colectiva_id, COUNT(*) as count FROM pacientes WHERE atencion_colectiva_id IN ({placeholders}) GROUP BY atencion_colectiva_id", ac_ids).fetchall():
                count_map[row["atencion_colectiva_id"]] = row["count"]
        for r in acs:
            r_dict = dict(r)
            r_dict["edit_url"] = url_for("formulario_mci", atencion_colectiva_id=r["id"])
            r_dict["num_pacientes"] = count_map.get(r["id"], 0)
            ac_list.append(r_dict)
            
        conn.close()
        
        return render_template(
            "pendientes.html",
            hcs=hc_list,
            acs=ac_list,
            usuario=session["usuario"]
        )

    @app.route("/pendientes/checklists")
    @login_required
    def ver_pendientes_checklists():
        user_ident = session["usuario"]["identificacion"]
        user_perfil = session["usuario"].get("perfil", "")
        is_admin = (session["usuario"]["rol"] == "admin")
        conn = get_db()

        CL_TYPES = [
            ("tam",    "checklist_tam",    "Check List TAM",    "🏥", "placa",        "placa"),
            ("tab",    "checklist_tab",    "Check List TAB",    "🩺", "placa",        "placa"),
            ("avanzada","checklist_avanzada","Check List Avanzada","⚡", "placa",        "placa"),
            ("pasb",   "checklist_pasb",   "Check List PASB",   "🧰", "ubicacion",    "ubicacion"),
            ("pasm",   "checklist_pasm",   "Check List PASM",   "🎒", "ubicacion",    "ubicacion"),
            ("equipos","checklist_equipos","Preop. Equipos",    "🔧", "grupo_equipos","grupo_equipos"),
        ]

        cl_groups = []

        # Preoperacional Conductores — belongs in Checklists group
        try:
            if is_admin:
                preop_rows = conn.execute(
                    "SELECT * FROM preoperacional WHERE finalizado = 0 ORDER BY id DESC"
                ).fetchall()
            else:
                preop_rows = conn.execute(
                    "SELECT * FROM preoperacional WHERE finalizado = 0 AND registrado_por_identificacion = ? AND perfil_registrador = ? ORDER BY id DESC",
                    (user_ident, user_perfil)
                ).fetchall()
        except Exception:
            preop_rows = []

        if preop_rows:
            preop_items = []
            for r in preop_rows:
                r_dict = dict(r)
                r_dict["edit_url"] = url_for("form_preoperacional", id=r["id"])
                r_dict["summary_val"] = r_dict.get("placa_vehiculo") or "—"
                preop_items.append(r_dict)
            cl_groups.append({
                "tipo_key": "preoperacional",
                "label": "Preoperacional Conductores",
                "icon": "🚗",
                "registros": preop_items,
            })

        for tipo_key, table, label, icon, summary_col, _ in CL_TYPES:
            try:
                if is_admin:
                    rows = conn.execute(
                        f"SELECT * FROM {table} WHERE finalizado = 0 ORDER BY id DESC",
                    ).fetchall()
                else:
                    rows = conn.execute(
                        f"SELECT * FROM {table} WHERE finalizado = 0 AND registrado_por_identificacion = ? AND perfil_registrador = ? ORDER BY id DESC",
                        (user_ident, user_perfil)
                    ).fetchall()
            except Exception:
                rows = []

            items = []
            for r in rows:
                r_dict = dict(r)
                r_dict["edit_url"] = url_for("form_checklist", tipo=tipo_key, id=r["id"])
                r_dict["summary_val"] = r_dict.get(summary_col) or "—"
                items.append(r_dict)

            if items:
                cl_groups.append({
                    "tipo_key": tipo_key,
                    "label": label,
                    "icon": icon,
                    "registros": items,
                })

        conn.close()
        return render_template(
            "pendientes_checklists.html",
            cl_groups=cl_groups,
            usuario=session["usuario"],
            is_admin=is_admin,
        )

    @app.route("/registros/global")
    @login_required
    def registros_global():
        conn = get_db()
        is_admin = (session["usuario"]["rol"] == "admin")
        user_ident = session["usuario"]["identificacion"]

        # ── Filters ──────────────────────────────────────────────
        tipo_filtro   = request.args.get("tipo", "")          # form type key
        fecha_desde   = request.args.get("fecha_desde", "")
        fecha_hasta   = request.args.get("fecha_hasta", "")
        search_query  = request.args.get("search", "").strip()

        # Default: current month range when no dates provided
        today = hoy()
        if not fecha_desde and not fecha_hasta:
            fecha_desde = today.strftime("%Y-%m-01")
            fecha_hasta = today.strftime("%Y-%m-%d")

        # ── Determine which types to query ────────────────────────
        types_to_query = [tipo_filtro] if tipo_filtro and tipo_filtro in FORM_TYPES else list(FORM_TYPES.keys())

        results = []  # list of dicts to send to template

        for tipo_key in types_to_query:
            cfg = FORM_TYPES[tipo_key]
            table = cfg["table"]
            date_col = cfg["date_col"]

            # ── Build WHERE ───────────────────────────────────────
            conditions = ["1=1"]
            params = []

            if fecha_desde:
                conditions.append(f"{date_col} >= ?")
                params.append(fecha_desde + " 00:00:00")
            if fecha_hasta:
                conditions.append(f"{date_col} <= ?")
                params.append(fecha_hasta + " 23:59:59")

            # Non-admin users only see their own records
            if not is_admin and table != "atencion_colectiva":
                conditions.append("registrado_por_identificacion = ?")
                params.append(user_ident)

            # Search filter (only for HC, events, preoperacional)
            if tipo_key == "hc":
                conditions.append("atencion_colectiva_id IS NULL")
                if search_query:
                    like = f"%{search_query}%"
                    conditions.append("(primer_nombre LIKE ? OR primer_apellido LIKE ? OR identificacion_paciente LIKE ?)")
                    params.extend([like, like, like])
            elif tipo_key == "atencion_vehiculo":
                if search_query:
                    like = f"%{search_query}%"
                    conditions.append("(comandante_incidente LIKE ? OR registrado_por LIKE ? OR tipo LIKE ? OR subtipo LIKE ?)")
                    params.extend([like, like, like, like])

            where_clause = " AND ".join(conditions)

            try:
                rows = conn.execute(
                    f"SELECT * FROM {table} WHERE {where_clause} ORDER BY {date_col} DESC LIMIT 200",
                    tuple(params)
                ).fetchall()
            except Exception:
                rows = []

            for row in rows:
                r = dict(row)
                # Build view URL
                if cfg.get("use_token"):
                    view_url = url_for(cfg["url_func"], token=serializer.dumps(r["id"]))
                elif cfg.get("tipo_param"):
                    view_url = url_for(cfg["url_func"], tipo=cfg["tipo_param"], record_id=r["id"])
                else:
                    param = cfg.get("url_param", "id")
                    view_url = url_for(cfg["url_func"], **{param: r["id"]})

                finalizado_val = r.get("finalizado", 1)
                complete_url = None
                if finalizado_val == 0:
                    if tipo_key == "hc":
                        complete_url = url_for("formulario", id=serializer.dumps(r["id"]))
                    elif tipo_key == "preoperacional":
                        complete_url = url_for("form_preoperacional", id=r["id"])
                    elif tipo_key == "atencion_colectiva":
                        complete_url = url_for("formulario_mci", atencion_colectiva_id=r["id"])
                    elif tipo_key in ("tam", "tab", "pasb", "pasm", "equipos", "avanzada"):
                        complete_url = url_for("form_checklist", tipo=tipo_key, id=r["id"])
                    elif tipo_key == "atencion_vehiculo":
                        complete_url = url_for("editar_atencion_vehiculo", id=r["id"])

                results.append({
                    "tipo_key":   tipo_key,
                    "tipo_label": cfg["label"],
                    "tipo_icon":  cfg["icon"],
                    "tipo_color": cfg["color"],
                    "id":         r.get("id"),
                    "fecha":      r.get("fecha") or r.get("fecha_inicio", "—"),
                    "hora":       r.get("hora") or r.get("hora_inicio", ""),
                    "fecha_registro": r.get(date_col, ""),
                    "registrado_por": r.get("registrado_por", "—"),
                    "perfil_registrador": r.get("perfil_registrador", ""),
                    "summary":    _build_summary(row, tipo_key, cfg),
                    "view_url":   view_url,
                    "finalizado": finalizado_val,
                    "complete_url": complete_url,
                })

        conn.close()

        # Sort all results by fecha_registro descending
        results.sort(key=lambda x: x.get("fecha_registro") or "", reverse=True)

        return render_template(
            "registros_global.html",
            results=results,
            total=len(results),
            form_types=FORM_TYPES,
            tipo_filtro=tipo_filtro,
            fecha_desde=fecha_desde,
            fecha_hasta=fecha_hasta,
            search_query=search_query,
            usuario=session["usuario"],
        )
