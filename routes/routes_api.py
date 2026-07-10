import json
import os
from datetime import datetime, date
from flask import render_template, request, redirect, url_for, session, flash, jsonify
from db import get_db
from utils import login_required, admin_required, calcular_edad, get_user_info, ahora
from itsdangerous import URLSafeSerializer, BadSignature

def register_routes(app, CIE10_DATA):
    @app.route("/api/cie10")
    @login_required
    def api_cie10():
        q = request.args.get("q", "").strip().upper()
        if len(q) < 2:
            return jsonify([])
        resultados = [
            c for c in CIE10_DATA
            if q in c["codigo"].upper() or q in c["nombre"].upper()
        ][:30]
        return jsonify(resultados)

    @app.route("/api/cie10_full")
    @login_required
    def api_cie10_full():
        return jsonify(CIE10_DATA)

    @app.route("/api/update_gps", methods=["POST"])
    @login_required
    def api_update_gps():
        data = request.get_json()
        if not data or 'lat' not in data or 'lng' not in data:
            return jsonify({"status": "error", "message": "Datos incompletos"}), 400
        
        conn = get_db()
        now_str = ahora().strftime("%Y-%m-%d %H:%M:%S")
        conn.execute("""
            UPDATE usuarios 
            SET ultima_latitud = ?, ultima_longitud = ?, ultima_actualizacion_gps = ? 
            WHERE identificacion = ?
        """, (str(data['lat']), str(data['lng']), now_str, session["usuario"]["identificacion"]))
        conn.commit()
        conn.close()
        
        return jsonify({"status": "success"})

    @app.route("/admin/api/locations")
    @admin_required
    def api_locations():
        conn = get_db()
        usuarios = conn.execute("""
            SELECT nombre, identificacion, perfil, ultima_latitud, ultima_longitud, ultima_actualizacion_gps 
            FROM usuarios 
            WHERE ultima_latitud IS NOT NULL AND ultima_latitud != ''
        """).fetchall()
        conn.close()
        return jsonify(usuarios)

    @app.route("/admin/api/perfiles")
    @admin_required
    def api_perfiles():
        conn = get_db()
        rows = conn.execute("SELECT perfil FROM usuarios WHERE perfil IS NOT NULL AND perfil != ''").fetchall()
        conn.close()
        unique = set()
        for r in rows:
            try:
                parsed = json.loads(r["perfil"])
                items = parsed if isinstance(parsed, list) else [parsed]
                for item in items:
                    unique.add(str(item))
            except (json.JSONDecodeError, TypeError):
                unique.add(str(r["perfil"]))
        sorted_unique = sorted(unique, key=str.casefold)
        palette = [
            "#ef4444","#3b82f6","#10b981","#f59e0b","#8b5cf6","#ec4899",
            "#14b8a6","#f97316","#06b6d4","#84cc16","#d946ef","#0ea5e9",
        ]
        colors = {}
        for i, p in enumerate(sorted_unique):
            colors[p] = palette[i % len(palette)]
        return jsonify(colors)

    @app.route("/estadisticas")
    @login_required
    def estadisticas():
        conn = get_db()
        
        fecha_inicio = request.args.get("fecha_inicio")
        fecha_fin = request.args.get("fecha_fin")
        
        where_pacientes = "1=1"
        where_eventos = "1=1"
        where_colectiva = "1=1"
        where_preoperacional = "1=1"
        where_calif = "1=1"
        where_segur = "1=1"
        
        params_pacientes = []
        params_eventos = []
        params_colectiva = []
        params_preoperacional = []
        params_calif = []
        params_segur = []
        
        if fecha_inicio:
            where_pacientes += " AND substr(fecha_registro, 1, 10) >= ?"
            where_eventos += " AND substr(fecha_registro, 1, 10) >= ?"
            where_colectiva += " AND substr(fecha_registro, 1, 10) >= ?"
            where_preoperacional += " AND substr(fecha_registro, 1, 10) >= ?"
            params_pacientes.append(fecha_inicio)
            params_eventos.append(fecha_inicio)
            params_colectiva.append(fecha_inicio)
            params_preoperacional.append(fecha_inicio)
            
        if fecha_fin:
            where_pacientes += " AND substr(fecha_registro, 1, 10) <= ?"
            where_eventos += " AND substr(fecha_registro, 1, 10) <= ?"
            where_colectiva += " AND substr(fecha_registro, 1, 10) <= ?"
            where_preoperacional += " AND substr(fecha_registro, 1, 10) <= ?"
            where_calif += " AND substr(fecha_registro, 1, 10) <= ?"
            where_segur += " AND substr(fecha_registro, 1, 10) <= ?"
            params_pacientes.append(fecha_fin)
            params_eventos.append(fecha_fin)
            params_colectiva.append(fecha_fin)
            params_preoperacional.append(fecha_fin)
            params_calif.append(fecha_fin)
            params_segur.append(fecha_fin)
        
        # KPIs
        tot_pacientes = conn.execute(f"SELECT COUNT(*) as c FROM pacientes WHERE {where_pacientes}", params_pacientes).fetchone()["c"]
        tot_eventos = conn.execute(f"SELECT COUNT(*) as c FROM eventos WHERE {where_eventos}", params_eventos).fetchone()["c"]
        tot_colectiva = conn.execute(f"SELECT COUNT(*) as c FROM atencion_colectiva WHERE {where_colectiva}", params_colectiva).fetchone()["c"]
        tot_preoperacional = conn.execute(f"SELECT COUNT(*) as c FROM preoperacional WHERE {where_preoperacional}", params_preoperacional).fetchone()["c"]
        tot_calif = conn.execute(f"SELECT COUNT(*) as c FROM calif_atencion WHERE {where_calif}", params_calif).fetchone()["c"]
        tot_segur = conn.execute(f"SELECT COUNT(*) as c FROM segur_paciente WHERE {where_segur}", params_segur).fetchone()["c"]
        
        # Pacientes por EPS
        eps_data = conn.execute(f"SELECT aseguradora, COUNT(*) as count FROM pacientes WHERE aseguradora IS NOT NULL AND aseguradora != '' AND {where_pacientes} GROUP BY aseguradora ORDER BY count DESC LIMIT 10", params_pacientes).fetchall()
        
        # Pacientes por Sexo
        sexo_data = conn.execute(f"SELECT sexo_biologico, COUNT(*) as count FROM pacientes WHERE sexo_biologico IS NOT NULL AND sexo_biologico != '' AND {where_pacientes} GROUP BY sexo_biologico", params_pacientes).fetchall()
        
        # Volumen
        if not fecha_inicio and not fecha_fin:
            vol_data = conn.execute("SELECT substr(fecha_registro, 1, 10) as fecha, COUNT(*) as count FROM pacientes WHERE fecha_registro IS NOT NULL AND fecha_registro != '' GROUP BY substr(fecha_registro, 1, 10) ORDER BY fecha DESC LIMIT 7").fetchall()
            vol_data = list(reversed(vol_data))
        else:
            vol_data = conn.execute(f"SELECT substr(fecha_registro, 1, 10) as fecha, COUNT(*) as count FROM pacientes WHERE fecha_registro IS NOT NULL AND fecha_registro != '' AND {where_pacientes} GROUP BY substr(fecha_registro, 1, 10) ORDER BY fecha ASC", params_pacientes).fetchall()
        
        conn.close()
        
        stats = {
            "kpis": {
                "pacientes": tot_pacientes,
                "eventos": tot_eventos,
                "colectiva": tot_colectiva,
                "preoperacional": tot_preoperacional,
                "calificaciones": tot_calif,
                "reportes_seguridad": tot_segur
            },
            "eps": {
                "labels": [row["aseguradora"] for row in eps_data],
                "values": [row["count"] for row in eps_data]
            },
            "sexo": {
                "labels": [row["sexo_biologico"] for row in sexo_data],
                "values": [row["count"] for row in sexo_data]
            },
            "volumen": {
                "labels": [row["fecha"] for row in vol_data],
                "values": [row["count"] for row in vol_data]
            },
            "filtros": {
                "fecha_inicio": fecha_inicio or "",
                "fecha_fin": fecha_fin or ""
            }
        }
        
        return render_template("estadisticas.html", stats=stats, usuario=session.get("usuario"))

    @app.route("/api/usuarios_por_cargo")
    @login_required
    def api_usuarios_por_cargo():
        """
        Returns active users whose perfil JSON array contains the requested cargo.
        Query param: ?cargo=Conductor
        Response: [{"nombre": "...", "identificacion": "..."}, ...]
        """
        import unicodedata

        def strip_accents(s):
            return ''.join(
                c for c in unicodedata.normalize('NFD', s)
                if unicodedata.category(c) != 'Mn'
            ).lower()

        cargo = request.args.get("cargo", "").strip()
        if not cargo:
            return jsonify([])

        cargo_norm = strip_accents(cargo)

        conn = get_db()
        rows = conn.execute(
            "SELECT nombre, identificacion, perfil FROM usuarios WHERE activo = 1 ORDER BY nombre"
        ).fetchall()
        conn.close()
        result = []
        for r in rows:
            try:
                perfil_raw = r["perfil"]
                perfiles = json.loads(perfil_raw) if perfil_raw else []
                if not isinstance(perfiles, list):
                    perfiles = [str(perfiles)]
            except (Exception,):
                perfiles = []
            for p in perfiles:
                if cargo_norm in strip_accents(str(p)):
                    result.append({
                        "nombre": r["nombre"],
                        "identificacion": r["identificacion"]
                    })
                    break
        return jsonify(result)

