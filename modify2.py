import sys

file_path = 'templates/ths_sga.html'
with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace Accordion 1
target1 = """<div class="accordion" id="sgaAccordion">
  
  <!-- Accordion: Agregar Persona -->
  <div class="accordion-item" style="border: 1px solid #e2e8f0; margin-bottom: 10px; border-radius: 8px; overflow: hidden;">
    <h2 class="accordion-header" id="headingAgregar">
      <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#collapseAgregar" aria-expanded="false" aria-controls="collapseAgregar" style="background-color: #f8fafc; color: #1e3a5f; font-weight: bold;">
        Agregar Persona
      </button>
    </h2>
    <div id="collapseAgregar" class="accordion-collapse collapse" aria-labelledby="headingAgregar" data-bs-parent="#sgaAccordion">
      <div class="accordion-body add-form" style="border: none; margin-bottom: 0; box-shadow: none;">"""

replace1 = """<div class="native-accordion-container">
  
  <!-- Accordion: Agregar Persona -->
  <details style="border: 1px solid #e2e8f0; margin-bottom: 15px; border-radius: 8px; overflow: hidden; background: white;">
    <summary style="padding: 15px; background-color: #f8fafc; color: #1e3a5f; font-weight: bold; cursor: pointer; border-bottom: 1px solid #e2e8f0; font-size: 16px;">
        Agregar Persona
    </summary>
    <div class="add-form" style="padding: 15px; border: none; margin-bottom: 0; box-shadow: none;">"""

content = content.replace(target1, replace1)

# Fix form grid from 2 rows of 2 cols to 1 row of 4 cols
target_form = """        <div class="row">
            <div class="col-md-6 form-group">
                <label>Identificación</label>
                <input type="text" name="identificacion" class="form-control" required>
            </div>
            <div class="col-md-6 form-group">
                <label>Nombre Completo</label>
                <input type="text" name="nombre_completo" class="form-control" placeholder="Ej: Juan Perez" required>
            </div>
        </div>

        <div class="row">
            <div class="col-md-6 form-group">
                <label>Registro (Resolución en Salud)</label>
                <input type="text" name="registro_salud" class="form-control">
            </div>
            <div class="col-md-6 form-group">
                <label>Contacto (Número)</label>
                <input type="text" name="contacto" class="form-control">
            </div>
        </div>"""

replace_form = """        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 15px;">
            <div class="form-group" style="margin-bottom: 0;">
                <label>Identificación</label>
                <input type="text" name="identificacion" class="form-control" required>
            </div>
            <div class="form-group" style="margin-bottom: 0;">
                <label>Nombre Completo</label>
                <input type="text" name="nombre_completo" class="form-control" placeholder="Ej: Juan Perez" required>
            </div>
            <div class="form-group" style="margin-bottom: 0;">
                <label>Registro (Resolución en Salud)</label>
                <input type="text" name="registro_salud" class="form-control">
            </div>
            <div class="form-group" style="margin-bottom: 0;">
                <label>Contacto (Número)</label>
                <input type="text" name="contacto" class="form-control">
            </div>
        </div>"""
content = content.replace(target_form, replace_form)

# Replace Accordion 2
target2 = """      </div>
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
      <div class="accordion-body">"""

replace2 = """      </div>
  </details>

  <!-- Accordion: Tabla de Registros Activos -->
  <details open style="border: 1px solid #e2e8f0; margin-bottom: 15px; border-radius: 8px; overflow: hidden; background: white;">
    <summary style="padding: 15px; background-color: #f8fafc; color: #1e3a5f; font-weight: bold; cursor: pointer; border-bottom: 1px solid #e2e8f0; font-size: 16px;">
        Tabla de Registros Activos
    </summary>
    <div style="padding: 15px;">"""
content = content.replace(target2, replace2)

# Replace Accordion 3
target3 = """      </div>
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
      <div class="accordion-body">"""

replace3 = """      </div>
  </details>
        
  <!-- Accordion: Tabla de Registros Inactivos -->
  <details style="border: 1px solid #e2e8f0; margin-bottom: 15px; border-radius: 8px; overflow: hidden; background: white;">
    <summary style="padding: 15px; background-color: #f8fafc; color: #1e3a5f; font-weight: bold; cursor: pointer; border-bottom: 1px solid #e2e8f0; font-size: 16px;">
        Tabla de Registros Inactivos
    </summary>
    <div style="padding: 15px;">"""
content = content.replace(target3, replace3)

# Replace end
target4 = """      </div>
    </div>
  </div>

</div>"""

replace4 = """      </div>
  </details>

</div>"""
content = content.replace(target4, replace4)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(content)

print('Success')
