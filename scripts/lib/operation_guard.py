# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Read-only busy checks and a shared lease for disruptive maintenance."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import sys
import time
import threading
sys.path.insert(0,str(Path(__file__).resolve().parent))
import file_lock
import pmlib


def assert_idle(root):
    run=Path(root)/'run'
    pending=run/'whatsapp-pending.json'
    try:
        if pending.is_file() and any(item.get('status')=='sending' for item in json.loads(pending.read_text())):
            raise ValueError('Wait for WhatsApp delivery to finish before updating. / Espera a que termine el envío de WhatsApp antes de actualizar.')
        for path in (run/'backup-jobs').glob('*.json'):
            item=json.loads(path.read_text())
            if item.get('state')=='running' and (pmlib.pid_alive(item.get('pid')) or (not item.get('pid') and time.time()-item.get('updated',0)<30)):
                raise ValueError('Wait for backup or migration to finish before changing services or updating. / Espera a que termine el respaldo o la migración antes de cambiar servicios o actualizar.')
        for path in (run/'jobs').glob('*.json'):
            item=json.loads(path.read_text())
            if (item.get('pid')!=os.getpid() and pmlib.pid_alive(item.get('pid'))) or (item.get('until') or 0)>time.time():
                raise ValueError('Wait for the active publishing task to finish before maintenance. / Espera a que termine la tarea de publicación antes del mantenimiento.')
    except (OSError,TypeError,AttributeError,json.JSONDecodeError):
        raise ValueError('Could not verify active tasks. Check local task status before maintenance. / No se pudieron verificar las tareas activas. Revisa su estado antes del mantenimiento.') from None


_held=threading.local()

@contextmanager
def maintenance(root):
    key=str(Path(root).resolve())
    held=getattr(_held,'roots',set())
    if key in held:
        yield
        return
    path=Path(root)/'run/maintenance.lock';path.parent.mkdir(parents=True,exist_ok=True)
    try:
        with file_lock.exclusive(str(path),blocking=False):
            _held.roots=held|{key}
            try:yield
            finally:_held.roots=held
    except (BlockingIOError,PermissionError):
        raise ValueError('Another backup, migration or publishing task is running. Wait for it to finish. / Hay otro respaldo, migración o publicación en curso. Espera a que termine.') from None
