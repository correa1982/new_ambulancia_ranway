import codecs

new_content = """<script>
// ── Soporte Offline para Atención Colectiva ─────────────────────
document.addEventListener("DOMContentLoaded", () => {
    const params = new URLSearchParams(window.location.search);
    const acId = params.get('atencion_colectiva_id');
    
    // Si estamos en modo offline (o si el template vino limpio del cache y no procesó el atencion_colectiva_id)
    if (acId) {
        let inputAc = document.querySelector('input[name="atencion_colectiva_id"]');
        if (!inputAc) {
            inputAc = document.createElement('input');
            inputAc.type = 'hidden';
            inputAc.name = 'atencion_colectiva_id';
            inputAc.value = acId;
            const form = document.getElementById('form-medico');
            if (form) form.appendChild(inputAc);
            
            // Recrear banner visual de que estamos en un evento masivo
            const header = document.querySelector('h1');
            if (header) {
                const banner = document.createElement('div');
                banner.style.cssText = "background: #eff6ff; border: 1.5px solid #bfdbfe; border-radius: 8px; padding: 14px 18px; margin-bottom: 20px; display: flex; align-items: center; justify-content: space-between; gap: 16px;";
                banner.innerHTML = `
                    <div>
                        <div style="font-weight: 700; color: #1e40af; font-size: 14px;">👥 Vinculado a Atención Colectiva / MCI (Modo Local/Offline)</div>
                        <p style="font-size: 13px; color: #1e40af; margin-top: 4px;">ID del Evento: ${acId} — Guardando en modo sin conexión.</p>
                    </div>
                `;
                header.insertAdjacentElement('afterend', banner);
            }

            // Cambiar "Guardar como Borrador" a "Guardar y Continuar"
            const borradorBtn = document.getElementById('borrador-btn');
            if (borradorBtn) {
                borradorBtn.name = "accion";
                borradorBtn.value = "guardar_continuar";
                borradorBtn.innerHTML = "💾 Guardar y Continuar";
                borradorBtn.style.background = "linear-gradient(135deg, #3b82f6, #1d4ed8)";
                borradorBtn.style.boxShadow = "0 4px 12px rgba(59,130,246,0.35)";
                borradorBtn.id = "guardar-continuar-btn";
                borradorBtn.title = "Guarda este registro localmente y permite continuar con el siguiente";
            }
        }
    }

    // ── CARGAR Y MOSTRAR REGISTROS OFFLINE EN EL PANEL ──
    async function cargarRegistrosOfflinePanel() {
        if (!acId || typeof PWA === 'undefined') return;
        try {
            const pendientes = await PWA.obtenerRegistrosPorMCI(acId);
            
            // Actualizar contadores
            const countBorradores = document.getElementById('count-borradores');
            const countTotal = document.getElementById('count-total');
            if (countBorradores && countTotal) {
                const baseB = parseInt(countBorradores.dataset.base || 0);
                const baseT = parseInt(countTotal.dataset.base || 0);
                countBorradores.textContent = baseB + pendientes.length;
                countTotal.textContent = baseT + pendientes.length;
            }

            const container = document.getElementById('lista-pacientes-container');
            const msgNoPacientes = document.getElementById('no-pacientes-msg');
            
            if (!container) return;

            // Limpiar tarjetas previas inyectadas por JS (las de la BD ya vienen por Jinja)
            container.querySelectorAll('.offline-injected').forEach(e => e.remove());

            if (pendientes.length > 0) {
                if (msgNoPacientes) msgNoPacientes.style.display = 'none';
                
                pendientes.forEach(r => {
                    const d = r.datos;
                    const nombre = (d.primer_nombre || d.primer_apellido) 
                        ? `${d.primer_nombre || ''} ${d.primer_apellido || ''}`
                        : '<span style="color:#94a3b8; font-style:italic;">Sin nombre</span>';
                    
                    const diag = d.diagnostico_cie10 ? `<span style="color:#7c3aed;">🔬 ${d.diagnostico_cie10.substring(0,25)}...</span>` : '';
                    const edadStr = d.edad_visual ? `<span>🎂 ${d.edad_visual}</span>` : '';
                    
                    const cardHTML = `
                    <div class="paciente-card offline-injected" style="background:#fffbeb; border:1.5px dashed #f59e0b; border-radius:8px; padding:10px 12px; display:flex; flex-direction:column; gap:5px; transition:all 0.15s;">
                        <div style="display:flex; align-items:flex-start; justify-content:space-between; gap:6px;">
                            <span style="font-weight:700; font-size:12px; color:#1e293b; line-height:1.3; flex:1;">
                                ${nombre}
                            </span>
                            <span style="background:#fef3c7; color:#92400e; font-size:9px; font-weight:700; padding:2px 6px; border-radius:12px; white-space:nowrap; flex-shrink:0;">
                                ⏳ PENDIENTE DE SYNC
                            </span>
                        </div>
                        <div style="font-size:10px; color:#64748b; display:flex; gap:8px; flex-wrap:wrap;">
                            <span>📋 ${d.identificacion_paciente || 'Sin ID'}</span>
                            ${edadStr}
                            ${diag}
                        </div>
                        <div style="display:flex; justify-content:flex-end; gap:6px; margin-top:4px; border-top:1px dashed #fde68a; padding-top:6px;">
                            <button type="button" onclick="editarRegistroOffline(${r.id})" style="display:inline-flex; align-items:center; gap:3px; background:#fffbeb; border:1px solid #fde68a; color:#b45309; padding:3px 8px; border-radius:4px; font-size:10px; font-weight:600; cursor:pointer;">
                                ✏️ Completar
                            </button>
                        </div>
                    </div>`;
                    container.insertAdjacentHTML('beforeend', cardHTML);
                });
            } else {
                if (container.children.length === 0 && msgNoPacientes) {
                    msgNoPacientes.style.display = 'block';
                }
            }
        } catch (e) {
            console.error("Error cargando registros offline para panel:", e);
        }
    }

    cargarRegistrosOfflinePanel();
    window.cargarRegistrosOfflinePanel = cargarRegistrosOfflinePanel;
});

// FUNCIONES GLOBALES PARA EDICION OFFLINE 
window.cancelarEdicionOffline = function() {
    const form = document.getElementById('form-medico');
    if (form) form.reset();
    document.getElementById('offline_id_input').value = '';
    
    const btnVolver = document.getElementById('btn-volver');
    const btnCancelar = document.getElementById('btn-cancelar-offline');
    if (btnVolver) btnVolver.style.display = 'inline-flex';
    if (btnCancelar) btnCancelar.style.display = 'none';

    const cie10 = document.getElementById('cie10-search');
    if (cie10) cie10.value = '';
    const edad = document.getElementById('edad');
    if (edad) edad.value = '';
    
    mostrarToast('Edición cancelada.', 'info');
};

window.editarRegistroOffline = async function(id) {
    if (typeof PWA === 'undefined') return;
    try {
        const registro = await PWA.obtenerRegistroPorId(id);
        if (!registro) return;

        const form = document.getElementById('form-medico');
        if (!form) return;

        const d = registro.datos;
        for (const key in d) {
            const el = form.elements[key];
            if (el) el.value = d[key];
        }

        document.getElementById('offline_id_input').value = id;
        
        const cie10Search = document.getElementById('cie10-search');
        if (cie10Search && d.diagnostico_cie10) {
            cie10Search.value = d.diagnostico_cie10;
        }

        const btnVolver = document.getElementById('btn-volver');
        const btnCancelar = document.getElementById('btn-cancelar-offline');
        if (btnVolver) btnVolver.style.display = 'none';
        if (btnCancelar) btnCancelar.style.display = 'inline-flex';

        form.scrollIntoView({ behavior: 'smooth' });
        mostrarToast(`Editando registro pendiente #${id}`, 'info');
        
    } catch (e) {
        console.error("Error al cargar registro offline para edición:", e);
        mostrarToast("No se pudo cargar el registro para edición", "error");
    }
};
</script>

<script>
// Save draft state (Auto-save) when typing
(function(){
    const form = document.getElementById('form-medico');
    if(!form) return;

    const pacienteIdInput = document.querySelector('input[name="id"]');
    const pacienteId = pacienteIdInput && pacienteIdInput.value ? pacienteIdInput.value : 'new';
    const acIdInput = document.querySelector('input[name="atencion_colectiva_id"]');
    const acId = acIdInput && acIdInput.value ? acIdInput.value : '';
    const storageKey = `autosave_hc_${pacienteId}_ac${acId}`;

    const inputs = Array.from(form.querySelectorAll('input:not([type="hidden"]), textarea, select'));

    // Restore from localStorage
    const savedData = localStorage.getItem(storageKey);
    if (savedData) {
        try {
            const data = JSON.parse(savedData);
            let restored = false;
            inputs.forEach(input => {
                if (data.hasOwnProperty(input.name)) {
                    if (input.type === 'checkbox' || input.type === 'radio') {
                        if (input.value === data[input.name]) input.checked = true;
                    } else {
                        input.value = data[input.name];
                    }
                    restored = true;
                    
                    const event = new Event('input', { bubbles: true });
                    input.dispatchEvent(event);
                    if(input.id === 'fecha_nacimiento' && typeof calcularEdad === 'function') calcularEdad();
                }
            });
            if (restored) console.log('Autosave restaurado desde localStorage.');
        } catch(e) {}
    }

    // Save to localStorage on changes
    function saveToLocal() {
        const data = {};
        inputs.forEach(input => {
            if (input.name) {
                if (input.type === 'checkbox' || input.type === 'radio') {
                    if (input.checked) data[input.name] = input.value;
                } else {
                    data[input.name] = input.value;
                }
            }
        });
        localStorage.setItem(storageKey, JSON.stringify(data));
    }

    form.addEventListener('input', saveToLocal);
    form.addEventListener('change', saveToLocal);

    form.addEventListener('submit', function() {
        localStorage.removeItem(storageKey);
    });

    const btnVolver = document.getElementById('btn-volver');
    if (btnVolver) {
        btnVolver.addEventListener('click', () => localStorage.removeItem(storageKey));
    }
})();
</script>
{% endblock %}
"""

with codecs.open('formulario.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, l in enumerate(lines):
    if l.strip() == '<script>' and 'Soporte Offline' in ''.join(lines[i:i+3]):
        lines = lines[:i]
        break
    if l.strip() == '// ── Soporte Offline para Atención Colectiva ─────────────────────':
        lines = lines[:i-1] # Remove the <script> too
        break

with codecs.open('formulario.html', 'w', encoding='utf-8') as f:
    f.writelines(lines)
    f.write(new_content)
