import os
import time

BASE = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE)

from dotenv import load_dotenv
load_dotenv(os.path.join(BASE, ".env"))

import app as app_module

with app_module.app.app_context():
    app_module.init_scheduler()
    if not app_module.scheduler.running:
        app_module.scheduler.start()
    jobs = app_module.scheduler.get_jobs()
    for job in jobs:
        print(f"Worker de backups: job '{job.id}' programado, proxima ejecucion: {job.next_run_time}", flush=True)

while True:
    time.sleep(3600)