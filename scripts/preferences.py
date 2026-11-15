# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Portable non-secret defaults. Saving does not clean data or alter reviewed plans."""
from pathlib import Path
import re
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent/'lib'))
import pmlib
import operation_guard
from telegram_settings import atomic_write,read_values
ROOT=Path(__file__).resolve().parent.parent
MODEL=re.compile(r'[A-Za-z0-9][A-Za-z0-9._:/-]{0,119}')


def status():
    env=read_values(ROOT/'.env')
    try:days=int(env.get('PM_RETENTION_DAYS','30'))
    except ValueError:days=30
    model=env.get('LOCAL_LLM_MODEL') or 'llama3.2:3b'
    models=[];ready=None
    try:
        code,response=pmlib.http('GET',env.get('OLLAMA_HOST_URL','http://localhost:11434').rstrip('/')+'/api/tags',timeout=2)
        if code==200 and isinstance(response,dict):
            models=[item.get('name') for item in response.get('models',[]) if isinstance(item,dict) and isinstance(item.get('name'),str) and MODEL.fullmatch(item['name'])]
            ready=model in models or model+':latest' in models
    except (pmlib.PMError,OSError):pass
    return {'configured':(ROOT/'.env').is_file(),'retention_days':days if days>=1 else 30,'final_tag':env.get('CAPTION_FINAL_TAG',''),'model':model,'models':models,'model_ready':ready}


def save(payload):
    days=payload.get('retention_days');model=payload.get('model');tag=payload.get('final_tag','')
    if type(days) is not int or not 1<=days<=3650:
        raise ValueError('Choose 1–3650 history days. / Elige de 1 a 3650 días de historial.')
    if not isinstance(model,str) or not MODEL.fullmatch(model):
        raise ValueError('Enter an installed Ollama model name. / Ingresa el nombre de un modelo instalado en Ollama.')
    if not isinstance(tag,str):raise ValueError('Enter one optional business hashtag. / Ingresa un hashtag opcional del negocio.')
    tag=pmlib.final_tag(tag)
    path=ROOT/'.env'
    with operation_guard.maintenance(ROOT):
        if not path.is_file() or path.is_symlink():raise ValueError('Configure or restore this installation first. / Primero configura o restaura esta instalación.')
        content=path.read_text()
        for key,value in {'PM_RETENTION_DAYS':days,'CAPTION_FINAL_TAG':tag,'LOCAL_LLM_MODEL':model}.items():
            content=re.sub(r'(?m)^\s*'+key+r'\s*=.*\n?','',content)
            content=content.rstrip()+'\n'+key+'='+str(value)+'\n'
        atomic_write(path,content)
    return status()
