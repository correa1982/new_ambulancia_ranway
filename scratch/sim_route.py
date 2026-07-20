import sys
sys.path.append('.')
from db import get_db
from datetime import datetime
from dateutil.relativedelta import relativedelta

def simulate():
    try:
        conn = get_db()
        records = conn.execute("SELECT * FROM ths_sga_records ORDER BY id DESC").fetchall()
        print(f"Got {len(records)} records")
        for record in records:
            for cert in ['bls', 'avvs', 'avaq']:
                fecha = record[f'{cert}_fecha']
                vigencia = record[f'{cert}_vigencia']
                unidad = record[f'{cert}_vigencia_unidad']
                
                if fecha and vigencia and unidad:
                    if isinstance(fecha, str):
                        try:
                            fecha_obj = datetime.strptime(fecha, '%Y-%m-%d').date()
                        except:
                            fecha_obj = None
                    else:
                        fecha_obj = fecha

                    if fecha_obj:
                        try:
                            v_int = int(vigencia)
                            if unidad == 'meses':
                                expira = fecha_obj + relativedelta(months=v_int)
                            elif unidad == 'años':
                                expira = fecha_obj + relativedelta(years=v_int)
                            else:
                                expira = None
                        except ValueError:
                            expira = None
                        
                        record[f'{cert}_expira'] = expira.strftime('%Y-%m-%d') if expira else 'N/A'
                        if expira:
                            record[f'{cert}_vencido'] = expira < datetime.now().date()
                        else:
                            record[f'{cert}_vencido'] = False
                else:
                    record[f'{cert}_expira'] = 'N/A'
                    record[f'{cert}_vencido'] = False
        print("Simulation successful")
    except Exception as e:
        import traceback
        traceback.print_exc()

simulate()
