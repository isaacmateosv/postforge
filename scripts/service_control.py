# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Fixed, portable lifecycle actions for this installation's Compose stack."""
import json
import os
import re
from pathlib import Path
import signal
import shutil
from urllib.parse import urlsplit
import subprocess
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parent/'lib'))
import file_lock
import operation_guard
import pmlib
from telegram_settings import atomic_write
ROOT=Path(__file__).resolve().parent.parent


def command(args,timeout=15):
    try:
        return subprocess.run(args,cwd=ROOT,capture_output=True,text=True,timeout=timeout)
    except (OSError,subprocess.TimeoutExpired):
        raise pmlib.PMError('A local service command could not finish. Check Docker and try again. / No terminó un comando de servicios. Revisa Docker y vuelve a intentar.') from None


def progress(action,stage,percent,done=False,error=None):
    atomic_write(ROOT/'run/service-progress.json',json.dumps({'action':action,'stage':stage,'percent':percent,'pid':None if done else os.getpid(),'error':error,'updated':time.time()}))


def task():
    try:
        item=json.loads((ROOT/'run/service-progress.json').read_text());item['running']=pmlib.pid_alive(item.get('pid'));return item
    except (OSError,ValueError):return {'running':False}


def queue_counts(env):
    count=int(pmlib.psql('SELECT count(*) FROM "Post" WHERE state=\'QUEUE\' AND "deletedAt" IS NULL',env)[0][0])
    pending=ROOT/'run/whatsapp-pending.json'
    items=json.loads(pending.read_text()) if pending.is_file() else []
    approved=sum(item.get('status')=='pending' and item.get('approved') is True for item in items)
    return count,approved


def status():
    configured=(ROOT/'.env').is_file();result={'configured':configured,'engine_ready':False,'running':False,'queued':None,'approved_status':None,'queue_known':False,'task':task(),'platform':sys.platform}
    try:
        result['engine_ready']=command(['docker','info','--format','{{.ServerVersion}}'],8).returncode==0
        if not result['engine_ready']:return result
        live=command(['docker','ps','--format','{{.Names}}']).stdout.splitlines()
        result['running']='pm-postiz' in live or 'pm-evolution-api' in live
        if configured and 'pm-postgres' in live:
            result['queued'],result['approved_status']=queue_counts(pmlib.load_env());result['queue_known']=True
    except (pmlib.PMError,ValueError,IndexError):pass
    return result


def receiver_running():
    try:
        with file_lock.exclusive(str(ROOT/'run/wa-inbox.lock'),blocking=False):return False
    except (BlockingIOError,PermissionError):return True


def start_receiver(env):
    if env.get('PM_WA_DOOR','true')=='false' or receiver_running():return
    log=ROOT/'logs/wa-inbox.log';log.parent.mkdir(parents=True,exist_ok=True)
    with log.open('ab') as stream:
        flags={'creationflags':subprocess.CREATE_NEW_PROCESS_GROUP|subprocess.DETACHED_PROCESS} if os.name=='nt' else {'start_new_session':True}
        child=subprocess.Popen([sys.executable,'-B',str(ROOT/'scripts/lib/wa_inbox.py')],cwd=ROOT,stdin=subprocess.DEVNULL,stdout=stream,stderr=stream,**flags)
    atomic_write(ROOT/'run/wa-inbox.pid',str(child.pid)+'\n')


def stop_receiver():
    if not receiver_running():return
    try:pid=int((ROOT/'run/wa-inbox.pid').read_text())
    except (OSError,ValueError):raise pmlib.PMError('The WhatsApp receiver needs review before stopping. / Revisa el receptor de WhatsApp antes de detenerlo.') from None
    os.kill(pid,signal.SIGTERM)
    deadline=time.monotonic()+15
    while receiver_running() and time.monotonic()<deadline:time.sleep(.2)
    if receiver_running():raise pmlib.PMError('WhatsApp intake is finishing a request. Wait and try again. / WhatsApp está terminando una solicitud. Espera y vuelve a intentar.')


def ensure_ollama(env):
    if not shutil.which('ollama') or urlsplit(env.get('OLLAMA_HOST_URL','http://localhost:11434')).hostname not in ('localhost','127.0.0.1','::1'):return
    try:
        if pmlib.http('GET',env.get('OLLAMA_HOST_URL','http://localhost:11434').rstrip('/')+'/api/tags',timeout=2)[0]==200:return
    except pmlib.PMError:pass
    log=ROOT/'logs/ollama-service.log';log.parent.mkdir(parents=True,exist_ok=True)
    with log.open('ab') as stream:
        flags={'creationflags':subprocess.CREATE_NEW_PROCESS_GROUP|subprocess.DETACHED_PROCESS} if os.name=='nt' else {'start_new_session':True}
        subprocess.Popen(['ollama','serve'],cwd=ROOT,stdin=subprocess.DEVNULL,stdout=stream,stderr=stream,**flags)
    log.chmod(0o600)


def scheduler_ready():
    return command([sys.executable,'-B',str(ROOT/'scripts/lib/machine_state.py'),'--check-scheduler'],8).returncode==0


def wait_ready(env):
    deadline=time.monotonic()+150
    while time.monotonic()<deadline:
        try:
            postiz=pmlib.http('GET',env.get('POSTIZ_LOCAL_URL','http://localhost:4200').rstrip('/')+'/api/',timeout=2)[0]==200
            evolution=pmlib.http('GET','http://localhost:8080/',timeout=2)[0]==200
            if postiz and evolution and scheduler_ready():return
        except pmlib.PMError:pass
        time.sleep(2)
    raise pmlib.PMError('Services started but the API or scheduler is not ready. Check local service logs before publishing. / Los servicios arrancaron, pero la API o el planificador no están listos. Revisa los registros antes de publicar.')


def apply(payload):
    action=payload.get('action')
    if action not in ('start','stop') or payload.get('confirmed') is not True:raise ValueError('Review and confirm the service action. / Revisa y confirma la acción de servicios.')
    if not (ROOT/'.env').is_file():raise ValueError('Configure this installation or restore a backup first. / Primero configura esta instalación o restaura un respaldo.')
    with operation_guard.maintenance(ROOT):
        operation_guard.assert_idle(ROOT)
        env=pmlib.load_env();progress(action,'Checking local services / Revisando servicios locales',5)
        try:
            if command(['docker','info','--format','{{.ServerVersion}}'],8).returncode:
                raise pmlib.PMError('Start Docker Desktop or Docker Engine first, then check again. / Primero inicia Docker Desktop o Docker Engine; luego vuelve a comprobar.')
            if action=='stop':
                queued,approved=queue_counts(env)
                if queued or approved:raise ValueError('Finish or cancel scheduled posts and approved Status before stopping. / Completa o cancela las publicaciones programadas y los Estados aprobados antes de detener los servicios.')
            with pmlib.Job('service-'+action,'Start publishing services' if action=='start' else 'Stop publishing services'):
                if action=='start':
                    progress(action,'Starting configured containers / Iniciando contenedores configurados',25)
                    if (ROOT/'data/gateway/configuration.yml').is_file():
                        from network_settings import restore_provider
                        restore_provider(ROOT/'.env')
                    config=command(['docker','compose','config','--format','json'])
                    if config.returncode:raise ValueError('Check the local Compose configuration. / Revisa la configuración local de Compose.')
                    declared=json.loads(config.stdout).get('services',{})
                    profiles=set(filter(None,env.get('COMPOSE_PROFILES','').split(',')))
                    services=[name for name,spec in declared.items() if re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*',name) and name not in ('ngrok','postforge-telegram') and (not spec.get('profiles') or profiles.intersection(spec['profiles']))]
                    if not services:raise ValueError('No configured services found. / No se encontraron servicios configurados.')
                    first=command(['docker','compose','up','-d','--remove-orphans',*services],600)
                    connector=command(['docker','compose','up','-d','--no-deps','--no-recreate','ngrok'],120)
                    atomic_write(ROOT/'run/service-control.log',first.stdout+first.stderr+connector.stdout+connector.stderr)
                    if first.returncode or connector.returncode:raise pmlib.PMError('Docker could not start the stack. Review service-control.log. / Docker no pudo iniciar los servicios. Revisa service-control.log.')
                    progress(action,'Waiting for APIs and scheduler / Esperando las API y el planificador',60);wait_ready(env)
                    progress(action,'Resuming message receivers / Retomando los receptores de mensajes',90)
                    ensure_ollama(env)
                    start_receiver(env)
                    import host_agent
                    host_agent.start()
                    (ROOT/'run/idle-stop').unlink(missing_ok=True)
                    (ROOT/'run/publishing-paused').unlink(missing_ok=True)
                else:
                    progress(action,'Stopping WhatsApp intake / Deteniendo el ingreso por WhatsApp',25);stop_receiver()
                    progress(action,'Stopping this stack; keeping shared tools / Deteniendo esta instalación; conservando herramientas compartidas',55)
                    stopped=command(['docker','compose','stop'],120)
                    atomic_write(ROOT/'run/service-control.log',stopped.stdout+stopped.stderr)
                    if stopped.returncode:raise pmlib.PMError('Some services could not stop. Review service-control.log. / Algunos servicios no se detuvieron. Revisa service-control.log.')
                    atomic_write(ROOT/'run/idle-stop','')
                    atomic_write(ROOT/'run/publishing-paused','')
            progress(action,'Complete / Completado',100,done=True)
        except Exception as error:
            message=str(error) if isinstance(error,(ValueError,pmlib.PMError)) else 'Service control needs review. / Revisa el control de servicios.'
            progress(action,message,0,done=True,error=message);raise
    return status()
