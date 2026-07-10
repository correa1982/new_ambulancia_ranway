/* ── formulario.js – HC Prehospitalario ── */

function toggleDesfibrilacion() {
    const sel = document.getElementById('desfibrilacion');
    const container = document.getElementById('desfibrilacion-container');
    if (!sel || !container) return;
    if (sel.value === 'SI') {
        container.style.display = 'block';
        document.getElementById('add-desf-btn').disabled = false;
        container.querySelectorAll('input').forEach(i=>i.disabled=false);
    } else {
        container.style.display = 'none';
        document.getElementById('add-desf-btn').disabled = true;
        container.querySelectorAll('input').forEach(i=>{ i.disabled = true; i.value = ''; });
    }
}

function addDesfibrilacionEntry(fecha='', joules=''){
    const container = document.getElementById('desfibrilacion-entries');
    if(!container) return;
    const div = document.createElement('div');
    div.className = 'df-entry';
    div.style.display = 'flex'; div.style.gap = '8px'; div.style.alignItems = 'center';
    div.innerHTML = '<input onclick="this.showPicker()" type="datetime-local" name="desfibrilacion_fecha[]" value="' + fecha + '" style="flex:1;min-width:200px;"><input type="number" name="desfibrilacion_joules[]" value="' + joules + '" min="0" step="1" style="width:120px;"><button type="button" class="remove-df" style="background:#fecaca;border:none;padding:6px 8px;border-radius:6px;">Eliminar</button>';
    container.appendChild(div);
}

function toggleSeguimiento() {
    const sel = document.getElementById('seguimiento_sv');
    const container = document.getElementById('seguimiento-container');
    const addBtn = document.getElementById('add-seg-btn');
    if (!sel || !container) return;
    if (sel.value === 'SI') {
        container.style.display = 'block';
        if (addBtn) addBtn.disabled = false;
        container.querySelectorAll('input').forEach(i=>i.disabled=false);
    } else {
        container.style.display = 'none';
        if (addBtn) addBtn.disabled = true;
        container.querySelectorAll('input').forEach(i=>{ i.disabled=true; i.value=''; });
    }
}

function addSeguimientoEntry(data){
    const container = document.getElementById('seguimiento-entries');
    if(!container) return;
    const d = data || {};
    const div = document.createElement('div');
    div.className = 'sv-entry';
    div.style.display = 'flex'; div.style.gap = '8px'; div.style.alignItems = 'center';
    div.innerHTML = '<input onclick="this.showPicker()" type="datetime-local" name="sv_fecha[]" value="' + (d.fecha||'') + '" style="flex:1;min-width:200px;"><input type="text" name="sv_pa[]" placeholder="PA (120/80)" value="' + (d.pa||'') + '" style="width:110px;"><input type="number" name="sv_spo2[]" placeholder="SpO2" value="' + (d.spo2||'') + '" style="width:80px;"><input type="number" name="sv_fc[]" placeholder="FC" value="' + (d.fc||'') + '" style="width:80px;"><input type="number" name="sv_fr[]" placeholder="FR" value="' + (d.fr||'') + '" style="width:80px;"><input type="number" name="sv_glic[]" placeholder="Glic (mg/dl)" value="' + (d.glic||'') + '" style="width:110px;"><button type="button" class="remove-sv" style="background:#fecaca;border:none;padding:6px 8px;border-radius:6px;">Eliminar</button>';
    container.appendChild(div);
}

function toggleEntrega() {
    const sel = document.getElementById('entrega_sv');
    const container = document.getElementById('entrega-container');
    const addBtn = document.getElementById('add-ent-btn');
    if (!sel || !container) return;
    if (sel.value === 'SI') {
        container.style.display = 'block';
        if (addBtn) addBtn.disabled = false;
        container.querySelectorAll('input').forEach(i=>i.disabled=false);
    } else {
        container.style.display = 'none';
        if (addBtn) addBtn.disabled = true;
        container.querySelectorAll('input').forEach(i=>{ i.disabled=true; });
    }
}

function addEntregaEntry(data){
    const container = document.getElementById('entrega-entries');
    if(!container) return;
    const d = data || {};
    const div = document.createElement('div');
    div.className = 'ent-entry';
    div.style.display = 'flex'; div.style.gap = '8px'; div.style.alignItems = 'center';
    div.innerHTML = '<input onclick="this.showPicker()" type="datetime-local" name="ent_fecha[]" value="' + (d.fecha||'') + '" style="flex:1;min-width:200px;"><input type="text" name="ent_pa[]" placeholder="PA (120/80)" value="' + (d.pa||'') + '" style="width:110px;"><input type="number" name="ent_spo2[]" placeholder="SpO2" value="' + (d.spo2||'') + '" style="width:80px;"><input type="number" name="ent_fc[]" placeholder="FC" value="' + (d.fc||'') + '" style="width:80px;"><input type="number" name="ent_fr[]" placeholder="FR" value="' + (d.fr||'') + '" style="width:80px;"><input type="number" name="ent_glic[]" placeholder="Glic (mg/dl)" value="' + (d.glic||'') + '" style="width:110px;"><button type="button" class="remove-ent" style="background:#fecaca;border:none;padding:6px 8px;border-radius:6px;">Eliminar</button>';
    container.appendChild(div);
}

function initFirmaCanvas(){
    const canvas = document.getElementById('firma-canvas');
    const clearBtn = document.getElementById('firma-clear');
    const saveBtn = document.getElementById('firma-guardar');
    const hiddenInput = document.getElementById('entrega_firma');
    if(!canvas) return;
    const ctx = canvas.getContext('2d');
    ctx.strokeStyle = '#111827';
    ctx.lineWidth = 2.5;
    ctx.lineCap = 'round';
    let drawing = false;
    let lastX = 0, lastY = 0;
    function getPos(e){
        const rect = canvas.getBoundingClientRect();
        if(e.touches && e.touches.length) e = e.touches[0];
        return { x: (e.clientX - rect.left) * (canvas.width / rect.width), y: (e.clientY - rect.top) * (canvas.height / rect.height) };
    }
    function start(e){ drawing = true; const p = getPos(e); lastX = p.x; lastY = p.y; e.preventDefault(); }
    function move(e){ if(!drawing) return; const p = getPos(e); ctx.beginPath(); ctx.moveTo(lastX,lastY); ctx.lineTo(p.x,p.y); ctx.stroke(); lastX = p.x; lastY = p.y; e.preventDefault(); }
    function end(e){ drawing = false; saveFirmaToInput(); }
    canvas.addEventListener('mousedown', start); canvas.addEventListener('mousemove', move); canvas.addEventListener('mouseup', end); canvas.addEventListener('mouseout', end);
    canvas.addEventListener('touchstart', start); canvas.addEventListener('touchmove', move); canvas.addEventListener('touchend', end);
    function clearCanvas(){ ctx.clearRect(0,0,canvas.width,canvas.height); hiddenInput.value = ''; }
    function saveFirmaToInput(){ if(!hiddenInput) return; try{ hiddenInput.value = canvas.toDataURL('image/png'); }catch(e){} }
    if(clearBtn) clearBtn.addEventListener('click', function(){ clearCanvas(); });
    if(saveBtn) saveBtn.addEventListener('click', function(){ saveFirmaToInput(); alert('Firma guardada en el registro (campo oculto actualizado).'); });
    if(hiddenInput && hiddenInput.value){ const img = new Image(); img.onload = function(){ ctx.drawImage(img,0,0,canvas.width,canvas.height); }; img.src = hiddenInput.value; }
}

function initSignatureCanvas(canvasId, clearBtnId, saveBtnId, hiddenInputId){
    const canvas = document.getElementById(canvasId);
    if(!canvas) return;
    const clearBtn = document.getElementById(clearBtnId);
    const saveBtn = document.getElementById(saveBtnId);
    const hiddenInput = document.getElementById(hiddenInputId);
    const ctx = canvas.getContext('2d');
    ctx.strokeStyle = '#111827';
    ctx.lineWidth = 2.5;
    ctx.lineCap = 'round';
    let drawing = false;
    let lastX=0,lastY=0;
    function getPos(e){ const rect = canvas.getBoundingClientRect(); if(e.touches && e.touches.length) e = e.touches[0]; return { x: (e.clientX - rect.left) * (canvas.width / rect.width), y: (e.clientY - rect.top) * (canvas.height / rect.height) }; }
    function start(e){ drawing=true; const p=getPos(e); lastX=p.x; lastY=p.y; e.preventDefault(); }
    function move(e){ if(!drawing) return; const p=getPos(e); ctx.beginPath(); ctx.moveTo(lastX,lastY); ctx.lineTo(p.x,p.y); ctx.stroke(); lastX=p.x; lastY=p.y; e.preventDefault(); }
    function end(e){ drawing=false; saveToInput(); }
    canvas.addEventListener('mousedown', start); canvas.addEventListener('mousemove', move); canvas.addEventListener('mouseup', end); canvas.addEventListener('mouseout', end);
    canvas.addEventListener('touchstart', start); canvas.addEventListener('touchmove', move); canvas.addEventListener('touchend', end);
    function clearCanvas(){ ctx.clearRect(0,0,canvas.width,canvas.height); if(hiddenInput) hiddenInput.value=''; }
    function saveToInput(){ if(!hiddenInput) return; try{ hiddenInput.value = canvas.toDataURL('image/png'); }catch(e){} }
    if(clearBtn) clearBtn.addEventListener('click', clearCanvas);
    if(saveBtn) saveBtn.addEventListener('click', function(){ saveToInput(); alert('Firma guardada.'); });
    if(hiddenInput && hiddenInput.value){ const img=new Image(); img.onload=function(){ ctx.drawImage(img,0,0,canvas.width,canvas.height); }; img.src = hiddenInput.value; }
}

function toggleDisentimientoType(){
    const sel = document.getElementById('disentimiento_tipo');
    const inf = document.getElementById('disentimiento-informado');
    const dif = document.getElementById('disentimiento-diferido');
    if(!sel) return;
    if(sel.value === 'informado'){
        if(inf) inf.style.display = '';
        if(dif) dif.style.display = 'none';
    } else if(sel.value === 'diferido'){
        if(inf) inf.style.display = 'none';
        if(dif) dif.style.display = '';
    } else {
        if(inf) inf.style.display = 'none';
        if(dif) dif.style.display = 'none';
    }
}

function toggleConsentimientoType(){
    const sel = document.getElementById('consentimiento_tipo');
    const inf = document.getElementById('consentimiento-informado');
    const dif = document.getElementById('consentimiento-diferido');
    if(!sel) return;
    if(sel.value === 'informado'){
        if(inf) inf.style.display = '';
        if(dif) dif.style.display = 'none';
    } else if(sel.value === 'diferido'){
        if(inf) inf.style.display = 'none';
        if(dif) dif.style.display = '';
    } else {
        if(inf) inf.style.display = 'none';
        if(dif) dif.style.display = 'none';
    }
}

function populateDisentimientoFromPatient(){
    const primerNombre = document.getElementById('primer_nombre');
    const primerApellido = document.getElementById('primer_apellido');
    const identificacion = document.getElementById('identificacion_paciente');
    const targetInformadoNombre = document.getElementById('disentimiento_paciente_nombre');
    const targetInformadoDoc = document.getElementById('disentimiento_paciente_documento');
    const targetDiferidoNombre = document.getElementById('disentimiento_d_paciente_nombre');
    const targetDiferidoDoc = document.getElementById('disentimiento_d_paciente_documento');
    const fullName = ((primerNombre && primerNombre.value)||'') + (primerApellido && primerApellido.value ? ' ' + (primerApellido && primerApellido.value) : '');
    const idVal = (identificacion && identificacion.value) || '';
    if(targetInformadoNombre && (!targetInformadoNombre.value || targetInformadoNombre.value.trim()==='')) targetInformadoNombre.value = fullName.trim();
    if(targetInformadoDoc && (!targetInformadoDoc.value || targetInformadoDoc.value.trim()==='')) targetInformadoDoc.value = idVal;
    if(targetDiferidoNombre && (!targetDiferidoNombre.value || targetDiferidoNombre.value.trim()==='')) targetDiferidoNombre.value = fullName.trim();
    if(targetDiferidoDoc && (!targetDiferidoDoc.value || targetDiferidoDoc.value.trim()==='')) targetDiferidoDoc.value = idVal;
    const targetCInfNombre = document.getElementById('consentimiento_paciente_nombre');
    const targetCInfDoc = document.getElementById('consentimiento_paciente_documento');
    const targetCDifNombre = document.getElementById('consentimiento_d_paciente_nombre');
    const targetCDifDoc = document.getElementById('consentimiento_d_paciente_documento');
    if(targetCInfNombre && (!targetCInfNombre.value || targetCInfNombre.value.trim()==='')) targetCInfNombre.value = fullName.trim();
    if(targetCInfDoc && (!targetCInfDoc.value || targetCInfDoc.value.trim()==='')) targetCInfDoc.value = idVal;
    if(targetCDifNombre && (!targetCDifNombre.value || targetCDifNombre.value.trim()==='')) targetCDifNombre.value = fullName.trim();
    if(targetCDifDoc && (!targetCDifDoc.value || targetCDifDoc.value.trim()==='')) targetCDifDoc.value = idVal;
}

function checkResultadoForSeguimiento(){
    const resultado = document.getElementById('resultado_atencion');
    const segFieldset = document.getElementById('seguimiento-fieldset');
    const segContainer = document.getElementById('seguimiento-container');
    const segSelect = document.getElementById('seguimiento_sv');
    const addSegBtn = document.getElementById('add-seg-btn');
    const entFieldset = document.getElementById('entrega-fieldset');
    const entContainer = document.getElementById('entrega-container');
    const entSelect = document.getElementById('entrega_sv');
    const addEntBtn = document.getElementById('add-ent-btn');
    const entregaInfo = document.getElementById('entrega-info-fieldset');
    const entregaInfoInputs = entregaInfo ? entregaInfo.querySelectorAll('input,textarea,select,button') : [];
    if(!resultado) return;
    const hide = resultado.value === 'Dado de alta en sitio' || resultado.value === 'Paciente niega atencion';
    if(segFieldset){
        if(hide){
            segFieldset.style.display = 'none';
            if(addSegBtn) addSegBtn.disabled = true;
            if(segSelect) segSelect.disabled = true;
            if(segContainer) segContainer.querySelectorAll('input').forEach(i=>{ i.disabled=true; });
        } else {
            segFieldset.style.display = '';
            if(segSelect) segSelect.disabled = false;
            if(addSegBtn) addSegBtn.disabled = false;
            if(segSelect) toggleSeguimiento();
        }
    }
    if(entFieldset){
        if(hide){
            entFieldset.style.display = 'none';
            if(addEntBtn) addEntBtn.disabled = true;
            if(entSelect) entSelect.disabled = true;
            if(entContainer) entContainer.querySelectorAll('input').forEach(i=>{ i.disabled=true; });
        } else {
            entFieldset.style.display = '';
            if(entSelect) entSelect.disabled = false;
            if(addEntBtn) addEntBtn.disabled = false;
            if(entSelect) toggleEntrega();
        }
    }
    if(entregaInfo){
        if(hide){
            entregaInfo.style.display = 'none';
            entregaInfoInputs.forEach(function(e){ e.disabled = true; });
        } else {
            entregaInfo.style.display = '';
            entregaInfoInputs.forEach(function(e){ e.disabled = false; });
        }
    }
    const indicField = document.getElementById('indicaciones-fieldset');
    const indicInput = document.getElementById('indicaciones_recomendaciones');
    if(indicField){
        if(resultado.value === 'Dado de alta en sitio'){
            indicField.style.display = '';
            if(indicInput) indicInput.disabled = false;
        } else {
            indicField.style.display = 'none';
            if(indicInput) indicInput.disabled = true;
        }
    }
    const disField = document.getElementById('disentimiento-fieldset');
    if(disField){
        if(resultado.value === 'Paciente niega atencion'){
            disField.style.display = '';
            disField.querySelectorAll('input,select,textarea,button').forEach(function(e){ e.disabled = false; });
            if(typeof toggleDisentimientoType === 'function') toggleDisentimientoType();
            setTimeout(populateDisentimientoFromPatient, 50);
        } else {
            disField.style.display = 'none';
            disField.querySelectorAll('input,select,textarea,button').forEach(function(e){ e.disabled = true; });
        }
    }
    const consentField = document.getElementById('consentimiento-fieldset');
    if(consentField){
        if(resultado.value !== 'Paciente niega atencion'){
            consentField.style.display = '';
            consentField.querySelectorAll('input,select,textarea,button').forEach(function(e){ e.disabled = false; });
            if(typeof toggleConsentimientoType === 'function') toggleConsentimientoType();
            setTimeout(populateDisentimientoFromPatient, 50);
        } else {
            consentField.style.display = 'none';
            consentField.querySelectorAll('input,select,textarea,button').forEach(function(e){ e.disabled = true; });
        }
    }
}

function toggleEmergenciaMedica() {
    const val = document.getElementById('es_emergencia_medica').value;
    const sec = document.getElementById('seccion_detalle_medica');
    const sel = document.getElementById('detalle_emergencia_medica');
    if (val === 'SI') {
        sec.style.display = 'block';
        sel.disabled = false;
    } else {
        sec.style.display = 'none';
        sel.disabled = true;
        sel.value = '';
    }
}

function toggleEmergenciaTraumatica() {
    const val = document.getElementById('es_emergencia_traumatica').value;
    const sec = document.getElementById('seccion_detalle_traumatica');
    const sel = document.getElementById('detalle_emergencia_traumatica');
    if (val === 'SI') {
        sec.style.display = 'block';
        sel.disabled = false;
    } else {
        sec.style.display = 'none';
        sel.disabled = true;
        sel.value = '';
    }
}
