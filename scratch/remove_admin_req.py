import re

# Remove @admin_required from routes_ths_trip.py
with open('routes/routes_ths_trip.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = re.sub(r'\s+@admin_required\s+@ths_trip_required', '\n    @ths_trip_required', content)

with open('routes/routes_ths_trip.py', 'w', encoding='utf-8') as f:
    f.write(content)

# Remove @admin_required from routes_ths_sga.py (just in case)
with open('routes/routes_ths_sga.py', 'r', encoding='utf-8') as f:
    content2 = f.read()

content2 = re.sub(r'\s+@admin_required\s+@ths_sga_required', '\n    @ths_sga_required', content2)

with open('routes/routes_ths_sga.py', 'w', encoding='utf-8') as f:
    f.write(content2)

print("Done")
