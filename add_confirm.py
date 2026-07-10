import os, re

template_dir = r'd:\GITHUB\render_ambulancia1.1\ambulacia\templates'
onclick_str = r''' onclick="return confirm('¿Está seguro de finalizar este registro? Una vez finalizado no podrá ser editado.');"'''
onclick_validate = r''' onclick="if(validateAll()){ return confirm('¿Está seguro de finalizar este registro? Una vez finalizado no podrá ser editado.'); } else { return false; }"'''

for filename in os.listdir(template_dir):
    if not filename.endswith('.html'):
        continue
    filepath = os.path.join(template_dir, filename)
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    def repl_validate(m):
        return m.group(0).replace('onclick="return validateAll()"', onclick_validate)
    
    def repl_normal(m):
        tag = m.group(0)
        if 'onclick=' in tag:
            return tag
        return tag[:-1] + onclick_str + '>'

    orig_content = content
    
    content = re.sub(r'<button[^>]*value="finalizar"[^>]*onclick="return validateAll\(\)"[^>]*>', repl_validate, content)
    content = re.sub(r'<button[^>]*value="finalizar"[^>]*>', repl_normal, content)

    if content != orig_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f'Updated {filename}')
