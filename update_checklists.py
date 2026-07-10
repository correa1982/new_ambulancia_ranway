import os
import re

files = [
    'checklist_tam.html', 'checklist_tab.html', 'checklist_pasb.html', 'checklist_pasm.html',
    'checklist_equipos.html', 'checklist_calif_atencion.html', 'checklist_segur_paciente.html',
    'preoperacional.html', 'eventos.html', 'atencion_vehiculo.html'
]

base_dir = r'd:\GITHUB\render_ambulancia1.1\ambulacia\templates'
for fname in files:
    fpath = os.path.join(base_dir, fname)
    if not os.path.exists(fpath): continue
    
    with open(fpath, 'r', encoding='utf-8') as f:
        text = f.read()
    
    if 'history.back()' in text:
        new_text = re.sub(r'href=[\"\']javascript:history\.back\(\)[\"\']', 'href="{{ url_for(\'dashboard\') }}"', text)
        if text != new_text:
            with open(fpath, 'w', encoding='utf-8') as f:
                f.write(new_text)
            print(f'Updated {fname}')
        else:
            print(f'No replace match in {fname} despite having history.back()')
