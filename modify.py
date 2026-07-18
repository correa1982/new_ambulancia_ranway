import sys

file_path = 'templates/ths_sga.html'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Chunk 1: Accordion start
target1 = """<div class="add-form">
    <h3>Agregar Persona</h3>
    <form action="{{ url_for('admin_ths_sga_agregar') }}" method="POST">"""
replace1 = """<div class="accordion" id="sgaAccordion">
  
  <!-- Accordion: Agregar Persona -->
  <div class="accordion-item" style="border: 1px solid #e2e8f0; margin-bottom: 10px; border-radius: 8px; overflow: hidden;">
    <h2 class="accordion-header" id="headingAgregar">
      <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#collapseAgregar" aria-expanded="false" aria-controls="collapseAgregar" style="background-color: #f8fafc; color: #1e3a5f; font-weight: bold;">
        Agregar Persona
      </button>
    </h2>
    <div id="collapseAgregar" class="accordion-collapse collapse" aria-labelledby="headingAgregar" data-bs-parent="#sgaAccordion">
      <div class="accordion-body add-form" style="border: none; margin-bottom: 0; box-shadow: none;">
        <form action="{{ url_for('admin_ths_sga_agregar') }}" method="POST">"""
content = content.replace(target1, replace1)

# Chunk 2: Activos Accordion
target2 = """        <div class="mt-3">
            <button type="submit" class="btn btn-primary">Agregar Registro</button>
        </div>
    </form>
</div>

<div class="tabs-container" style="margin-top: 20px;">
    <ul class="nav nav-tabs" id="sgaTabs" role="tablist">
        <li class="nav-item">
            <a class="nav-link active" id="activos-tab" data-bs-toggle="tab" href="#activos" role="tab">Activos</a>
        </li>
        <li class="nav-item">
            <a class="nav-link" id="inactivos-tab" data-bs-toggle="tab" href="#inactivos" role="tab">Inactivos</a>
        </li>
    </ul>
    
    <div class="tab-content" id="sgaTabsContent">
        <!-- Activos -->
        <div class="tab-pane fade show active" id="activos" role="tabpanel">
            <h4 style="margin-top: 15px; color: #1e3a5f;">Tabla de Registros Activos</h4>
            <div class="table-container mt-3">"""
replace2 = """        <div class="mt-3">
            <button type="submit" class="btn btn-primary">Agregar Registro</button>
        </div>
    </form>
      </div>
    </div>
  </div>

  <!-- Accordion: Tabla de Registros Activos -->
  <div class="accordion-item" style="border: 1px solid #e2e8f0; margin-bottom: 10px; border-radius: 8px; overflow: hidden;">
    <h2 class="accordion-header" id="headingActivos">
      <button class="accordion-button" type="button" data-bs-toggle="collapse" data-bs-target="#collapseActivos" aria-expanded="true" aria-controls="collapseActivos" style="background-color: #f8fafc; color: #1e3a5f; font-weight: bold;">
        Tabla de Registros Activos
      </button>
    </h2>
    <div id="collapseActivos" class="accordion-collapse collapse show" aria-labelledby="headingActivos" data-bs-parent="#sgaAccordion">
      <div class="accordion-body">
            <div class="table-container mt-3">"""
content = content.replace(target2, replace2)

# Chunk 3: Headers
target3 = """<th rowspan="2" style="vertical-align: middle; border: 1px solid #9ca3af;">NOMBRES Y APELLIDOS</th>
                            <th rowspan="2" style="vertical-align: middle; border: 1px solid #9ca3af;">CONTACTO</th>
                            <th rowspan="2" style="vertical-align: middle; border: 1px solid #9ca3af;">IDENTIFICACIÓN</th>
                            <th rowspan="2" style="vertical-align: middle; border: 1px solid #9ca3af;">REGISTRO</th>"""
replace3 = """<th rowspan="2" style="vertical-align: middle; border: 1px solid #9ca3af;">NOMBRES Y APELLIDOS</th>
                            <th rowspan="2" style="vertical-align: middle; border: 1px solid #9ca3af;">IDENTIFICACIÓN</th>
                            <th rowspan="2" style="vertical-align: middle; border: 1px solid #9ca3af;">REGISTRO</th>
                            <th rowspan="2" style="vertical-align: middle; border: 1px solid #9ca3af;">CONTACTO</th>"""
content = content.replace(target3, replace3)

# Chunk 4: Tarjeta Prof. -> Resolución
target4 = """<th rowspan="2" style="vertical-align: middle; border: 1px solid #9ca3af;">TARJETA PROF.</th>"""
replace4 = """<th rowspan="2" style="vertical-align: middle; border: 1px solid #9ca3af;">RESOLUCIÓN</th>"""
content = content.replace(target4, replace4)

# Chunk 5: Data rows
target5 = """<td style="border: 1px solid #d1d5db;">{{ r.nombres }} {{ r.apellidos }}</td>
                            <td style="border: 1px solid #d1d5db;">{{ r.contacto or '' }}</td>
                            <td style="border: 1px solid #d1d5db;">{{ r.identificacion }}</td>
                            <td style="border: 1px solid #d1d5db;">{{ r.registro_salud or '' }}</td>"""
replace5 = """<td style="border: 1px solid #d1d5db;">{{ r.nombres }} {{ r.apellidos }}</td>
                            <td style="border: 1px solid #d1d5db;">{{ r.identificacion }}</td>
                            <td style="border: 1px solid #d1d5db;">{{ r.registro_salud or '' }}</td>
                            <td style="border: 1px solid #d1d5db;">{{ r.contacto or '' }}</td>"""
content = content.replace(target5, replace5)

# Chunk 6: Inactivos Accordion
target6 = """            </div>
        </div>
        
        <!-- Inactivos -->
        <div class="tab-pane fade" id="inactivos" role="tabpanel">
            <h4 style="margin-top: 15px; color: #1e3a5f;">Tabla de Registros Inactivos</h4>
            <div class="table-container mt-3">"""
replace6 = """            </div>
      </div>
    </div>
  </div>
        
  <!-- Accordion: Tabla de Registros Inactivos -->
  <div class="accordion-item" style="border: 1px solid #e2e8f0; margin-bottom: 10px; border-radius: 8px; overflow: hidden;">
    <h2 class="accordion-header" id="headingInactivos">
      <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#collapseInactivos" aria-expanded="false" aria-controls="collapseInactivos" style="background-color: #f8fafc; color: #1e3a5f; font-weight: bold;">
        Tabla de Registros Inactivos
      </button>
    </h2>
    <div id="collapseInactivos" class="accordion-collapse collapse" aria-labelledby="headingInactivos" data-bs-parent="#sgaAccordion">
      <div class="accordion-body">
            <div class="table-container mt-3">"""
content = content.replace(target6, replace6)

# Chunk 7: End of file
target7 = """        </div>
    </div>
</div>

{% endblock %}"""
replace7 = """            </div>
      </div>
    </div>
  </div>

</div>

{% endblock %}"""
content = content.replace(target7, replace7)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print('Success')
