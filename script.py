import json

DEPT_NAMES = {
    '05': 'ANTIOQUIA', '08': 'ATLANTICO', '11': 'BOGOTA, D.C.', '13': 'BOLIVAR', '15': 'BOYACA',
    '17': 'CALDAS', '18': 'CAQUETA', '19': 'CAUCA', '20': 'CESAR', '23': 'CORDOBA',
    '25': 'CUNDINAMARCA', '27': 'CHOCO', '41': 'HUILA', '44': 'LA GUAJIRA', '47': 'MAGDALENA',
    '50': 'META', '52': 'NARINO', '54': 'NORTE DE SANTANDER', '63': 'QUINDIO', '66': 'RISARALDA',
    '68': 'SANTANDER', '70': 'SUCRE', '73': 'TOLIMA', '76': 'VALLE DEL CAUCA', '81': 'ARAUCA',
    '85': 'CASANARE', '86': 'PUTUMAYO', '88': 'ARCHIPIELAGO DE SAN ANDRES, PROVIDENCIA Y SANTA CATALINA',
    '91': 'AMAZONAS', '94': 'GUAINIA', '95': 'GUAVIARE', '97': 'VAUPES', '99': 'VICHADA'
}

def process():
    try:
        with open('static/data/Listados_DIVIPOLA.json', encoding='utf-8') as f:
            data = json.load(f).get('Colombia Completo', [])
    except Exception as e:
        print('Error loading JSON', e)
        return

    # Build hierarchy
    tree = {}
    
    # First pass: find municipality names (cabeceras municipales end in 000)
    mun_names = {}
    for row in data:
        dept_code = str(row.get('Departamento', '')).strip()
        mun_code = str(row.get('Municipio', '')).strip()
        barrio_code = str(row.get('Barrio', '')).strip()
        name = str(row.get('', '')).strip()
        
        if not dept_code or not dept_code.isdigit(): continue
        
        if barrio_code.endswith('000'):
            mun_names[mun_code] = name

    # Second pass: build tree
    for row in data:
        dept_code = str(row.get('Departamento', '')).strip()
        mun_code = str(row.get('Municipio', '')).strip()
        barrio_code = str(row.get('Barrio', '')).strip()
        name = str(row.get('', '')).strip()
        
        if not dept_code or not dept_code.isdigit(): continue
        
        if dept_code not in tree:
            tree[dept_code] = {
                'codigo': dept_code,
                'nombre': DEPT_NAMES.get(dept_code, f'DEPT {dept_code}'),
                'municipios': {}
            }
            
        if mun_code not in tree[dept_code]['municipios']:
            tree[dept_code]['municipios'][mun_code] = {
                'codigo': mun_code,
                'nombre': mun_names.get(mun_code, f'MUNICIPIO {mun_code}'),
                'barrios': []
            }
            
        # Add barrio (skip cabeceras as barrios if you want, but RIPS might need the 000 code for the cabecera)
        # Actually DIVIPOLA treats 000 as Cabecera Municipal (Centro Poblado). It is useful to have it as a option for Barrio.
        tree[dept_code]['municipios'][mun_code]['barrios'].append({
            'codigo': barrio_code,
            'nombre': name
        })
        
    # Convert dicts to lists and sort
    final_tree = []
    for d_code in sorted(tree.keys()):
        d_obj = tree[d_code]
        muns_list = []
        for m_code in sorted(d_obj['municipios'].keys()):
            m_obj = d_obj['municipios'][m_code]
            # sort barrios by code
            m_obj['barrios'].sort(key=lambda x: x['codigo'])
            muns_list.append(m_obj)
        d_obj['municipios'] = muns_list
        final_tree.append(d_obj)
        
    with open('static/data/divipola_estructurado.json', 'w', encoding='utf-8') as f:
        json.dump(final_tree, f, ensure_ascii=False)
        
    print(f'Successfully generated divipola_estructurado.json with {len(final_tree)} departments.')

process()
