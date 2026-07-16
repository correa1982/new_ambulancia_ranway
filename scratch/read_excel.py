import openpyxl

wb = openpyxl.load_workbook(r'c:\Users\Danni Mejia\Documents\NOMINA.xlsx', read_only=True)
ws = wb.active
for i, row in enumerate(ws.rows):
    if i > 5:
        break
    print(f"Row {i}:", [cell.value for cell in row if cell.value is not None])
