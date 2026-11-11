# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Portable Status audience defaults; never changes an already queued audience."""
import os
from pathlib import Path
import re
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent/'lib'))
import pmlib
import file_lock
from telegram_settings import atomic_write
ROOT=Path(__file__).resolve().parent.parent

def snapshot(env):
    audience=env.get('WA_STATUS_AUDIENCE','all')
    return {'audience':audience,'recipients':env.get('WA_TEST_RECIPIENTS','') if audience=='test' else ''}

def status():
    env=pmlib.load_env()
    return {'audience':env.get('WA_STATUS_AUDIENCE','all'),'recipients':env.get('WA_TEST_RECIPIENTS','')}

def save(payload):
    audience=payload.get('audience');raw=payload.get('recipients','')
    if audience not in ('all','test') or not isinstance(raw,str) or len(raw)>15000:
        raise pmlib.PMError('Choose a valid WhatsApp audience. / Elige una audiencia válida para WhatsApp.')
    numbers=[part.strip().replace('+','') for part in re.split(r'[,\n;]+',raw) if part.strip()]
    if any(not re.fullmatch(r'[1-9][0-9]{6,14}',number) for number in numbers):
        raise pmlib.PMError('Use phone numbers with country code, separated by commas. / Usa números con código de país, separados por comas.')
    numbers=list(dict.fromkeys(numbers))
    if audience=='test' and not numbers:raise pmlib.PMError('Add at least one selected contact. / Añade al menos un contacto seleccionado.')
    import whatsapp_pending
    with file_lock.exclusive(str(Path(pmlib.RUN_DIR)/'wa-audience.lock')):
        env=pmlib.load_env()
        with whatsapp_pending._queue_lock():
            items=whatsapp_pending._read()
            if any(item.get('status')=='sending' for item in items):
                raise pmlib.PMError('A Status is being sent. Save audience changes after delivery. / Se está enviando un Estado. Guarda los cambios de audiencia después del envío.')
            previous=snapshot(env)
            for item in items:
                if item.get('status') in ('pending','needs_review') and 'audience' not in item:item.update(previous)
            whatsapp_pending._write(items)
            path=ROOT/'.env';content=path.read_text()
            for key,value in [('WA_STATUS_AUDIENCE',audience),('WA_TEST_RECIPIENTS',','.join(numbers))]:
                content=re.sub(r'^\s*'+key+r'\s*=.*\n?','',content,flags=re.M)
                content=content.rstrip()+'\n'+key+'='+value+'\n'
            atomic_write(path,content)
    return {'audience':audience,'recipients':','.join(numbers)}
