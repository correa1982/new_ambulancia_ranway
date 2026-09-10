import sys, os, time

BASE = r"C:\Users\Danni Mejia\Documents\GitHub\new_ambulancia_ranway"
sys.path.insert(0, BASE)
os.chdir(BASE)

from dotenv import load_dotenv
load_dotenv(os.path.join(BASE, ".env"))

import app as app_module

def stub():
    print(f"[PROBE] job disparado a las {time.strftime('%H:%M:%S')}", flush=True)
    return True, "OK"

app_module.send_backup_email = stub

if app_module.scheduler.get_job("backup_job"):
    app_module.scheduler.reschedule_job("backup_job", trigger="interval", seconds=3)
    print("[PROBE] backup_job reprogramado a cada 3 segundos", flush=True)

worker_id = os.environ.get("PROBE_WORKER", "?")
print(f"[PROBE] worker {worker_id} importo el modulo; scheduler running={app_module.scheduler.running}", flush=True)

app = app_module.app