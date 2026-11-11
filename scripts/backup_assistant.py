# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Private, authenticated migration bundles and observable background tasks."""
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import secrets

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT/'scripts/lib'))
import pmlib
import file_lock
import postiz_transfer as transfer
import credentials
import telegram_settings
from gateway_backup import keys

MAGIC=b'PostForge private migration v1\n'
CHUNK=1024*1024
MEMBERS={'manifest.json','credentials.env.enc','gateway.enc','postiz.tar'}
JOBS=ROOT/'run/backup-jobs'


def seal(source, destination, password):
    destination=Path(destination)
    with tempfile.TemporaryDirectory(dir=destination.parent) as temporary:
        work=Path(temporary); salt=os.urandom(16); enc,auth=keys(password,salt)
        credentials.run_openssl('encrypt',enc,source,work/'cipher')
        header=MAGIC+salt; mac=hmac.new(auth,header,hashlib.sha256)
        with (work/'sealed').open('wb') as output,(work/'cipher').open('rb') as stream:
            output.write(header)
            for chunk in iter(lambda:stream.read(CHUNK),b''):
                mac.update(chunk);output.write(chunk)
            output.write(mac.digest())
        (work/'sealed').chmod(0o600)
        if destination.exists():raise ValueError('Choose a new backup file.')
        os.replace(work/'sealed',destination)


def unseal(source, destination, password):
    source=Path(source);destination=Path(destination)
    with source.open('rb') as stream:
        header=stream.read(len(MAGIC)+16)
        if not header.startswith(MAGIC) or source.stat().st_size<len(header)+49:
            raise ValueError('Invalid PostForge backup. / Respaldo de PostForge inválido.')
        enc,auth=keys(password,header[-16:]);mac=hmac.new(auth,header,hashlib.sha256)
        remaining=source.stat().st_size-len(header)-32
        with tempfile.TemporaryDirectory(dir=destination.parent) as temporary:
            cipher=Path(temporary)/'cipher'
            with cipher.open('wb') as output:
                while remaining:
                    chunk=stream.read(min(CHUNK,remaining))
                    if not chunk:raise ValueError('Incomplete backup.')
                    mac.update(chunk);output.write(chunk);remaining-=len(chunk)
            if not hmac.compare_digest(mac.digest(),stream.read(32)):
                raise ValueError('Wrong passphrase or damaged backup. / Contraseña incorrecta o respaldo dañado.')
            credentials.run_openssl('decrypt',enc,cipher,destination)
            destination.chmod(0o600)


def digest(path):
    value=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda:stream.read(CHUNK),b''):value.update(chunk)
    return value.hexdigest()


def extract(source, folder):
    with tarfile.open(source) as archive:
        entries=archive.getmembers();names=[entry.name for entry in entries]
        if len(names)!=len(set(names)) or not {'manifest.json','credentials.env.enc','postiz.tar'}<=set(names) or not set(names)<=MEMBERS or any(not entry.isfile() for entry in entries):
            raise ValueError('Unsupported backup contents.')
        transfer.safe_extract(archive,str(folder))


def write_status(identifier, **values):
    from composer import write_record
    path=JOBS/(identifier+'.json')
    current=json.loads(path.read_text()) if path.is_file() else {}
    current.update(values,updated=time.time());write_record(path,current)


def create_bundle(folder, password, progress):
    env=pmlib.load_env();stamp=time.strftime('%Y%m%d-%H%M%S')
    folder=Path(folder)
    if not folder.is_dir():raise ValueError('Choose an existing destination folder.')
    if folder.resolve().is_relative_to(Path(transfer.UPLOADS).resolve()):raise ValueError('Choose a destination outside the media folder.')
    estimate=transfer.upload_stats(transfer.UPLOADS)[1] if Path(transfer.UPLOADS).is_dir() else 0
    if min(shutil.disk_usage(folder).free,shutil.disk_usage(tempfile.gettempdir()).free)<estimate*6+256*1024*1024:raise ValueError('Not enough free space for a verified backup.')
    output=folder/('PostForge-'+stamp+'-'+secrets.token_hex(3)+'.pfbackup')
    with tempfile.TemporaryDirectory(prefix='postforge-backup-') as temporary:
        work=Path(temporary)
        progress('Protecting credentials and gateway / Protegiendo credenciales y acceso seguro',15)
        credentials.export_credentials(str(work/'credentials.env.enc'),True,password=password)
        progress('Exporting posts and media / Exportando publicaciones y archivos',30)
        transfer.export(env,str(work/'postiz.tar'))
        progress('Rehearsing restore in a disposable database / Verificando en una base temporal',55)
        transfer.rehearse(env,str(work/'postiz.tar'))
        manifest={'version':(ROOT/'VERSION').read_text().strip(),'created':time.time(),'gateway':(work/'gateway.enc').is_file()}
        (work/'manifest.json').write_text(json.dumps(manifest))
        with tarfile.open(work/'bundle.tar','w') as archive:
            for name in MEMBERS:
                if (work/name).is_file():archive.add(work/name,arcname=name)
        progress('Encrypting the entire backup / Cifrando todo el respaldo',80)
        seal(work/'bundle.tar',output,password)
        # Authenticate the completed envelope without retaining plaintext.
        unseal(output,work/'verified.tar',password)
    return {'file':str(output),'sha256':digest(output),'verified':True}


def inspect_bundle(path,password,progress,restore=False,replace=False,expected=None):
    path=Path(path)
    if not path.is_file() or path.is_symlink():raise ValueError('Choose a regular PostForge backup file.')
    fingerprint=digest(path)
    if expected and fingerprint!=expected:raise ValueError('Backup changed. Inspect it again before restoring.')
    with tempfile.TemporaryDirectory(prefix='postforge-restore-') as temporary:
        work=Path(temporary);progress('Authenticating and opening backup / Verificando y abriendo el respaldo',15)
        unseal(path,work/'bundle.tar',password);parts=work/'parts';parts.mkdir(mode=0o700);extract(work/'bundle.tar',parts)
        stage=work/'incoming.env';gateway=work/'gateway'
        credentials.import_credentials(str(parts/'credentials.env.enc'),output=str(stage),gateway_stage=str(gateway),password=password)
        unpacked,manifest=transfer.unpack(str(parts/'postiz.tar'))
        shutil.rmtree(unpacked)
        incoming=telegram_settings.read_values(stage)
        info={'fingerprint':fingerprint,'file':str(path),'tables':len(manifest['rows']),'rows':sum(manifest['rows'].values()),
              'media_files':manifest['upload_files'],'media_bytes':manifest['upload_bytes'],'gateway':gateway.is_dir(),
              'telegram':bool(incoming.get('TELEGRAM_OWNER_ID')),'created':manifest.get('created_at'),'restored':False}
        if not restore:return info
        initialized=(ROOT/'data/postgres/PG_VERSION').is_file()
        if initialized and not replace:raise ValueError('Existing data found. Explicit replacement approval is required. / Hay datos existentes. Debes confirmar su reemplazo.')
        current=pmlib.load_env()
        if initialized and any(incoming.get(k)!=current.get(k) for k in ('POSTGRES_USER','POSTGRES_DB','POSTGRES_PASSWORD')):
            raise ValueError('Destination database credentials differ. Restore into a fresh installation. / Las credenciales de la base de destino son distintas. Restaura en una instalación nueva.')
        rollback=None
        if initialized:
            progress('Saving automatic rollback backup / Guardando respaldo de recuperación',30)
            target=ROOT/'backups';target.mkdir(mode=0o700,exist_ok=True)
            rollback=create_bundle(target,password,lambda message,percent:progress(message,25+percent//5))
        progress('Stopping local publishing services / Deteniendo los servicios locales',50)
        import host_agent
        host_agent.stop()
        project=subprocess.run(['docker','inspect','-f','{{index .Config.Labels "com.docker.compose.project"}}','pm-postgres'],capture_output=True,text=True)
        project=project.stdout.strip() if project.returncode==0 else 'postforge'
        running=subprocess.run(['docker','ps','--filter','label=com.docker.compose.project='+project,'--format','{{.ID}} {{.Names}}'],capture_output=True,text=True,check=True)
        ids=[line.split()[0] for line in running.stdout.splitlines() if line.split()[-1]!='pm-postgres']
        if ids:subprocess.run(['docker','stop',*ids],check=True,capture_output=True,timeout=120)
        previous_env=(ROOT/'.env').read_bytes() if (ROOT/'.env').exists() else None
        previous_gateway=work/'previous-gateway';live_gateway=ROOT/'data/gateway';override=None;installed_gateway=False
        provider_override=ROOT/'docker-compose.override.yml'
        provider_previous=provider_override.read_bytes() if provider_override.exists() else None
        try:
            telegram_settings.atomic_write(ROOT/'.env',stage.read_text())
            if gateway.is_dir():
                if live_gateway.is_symlink():raise ValueError('Gateway destination must be a regular directory.')
                if live_gateway.exists():shutil.move(str(live_gateway),str(previous_gateway))
                live_gateway.parent.mkdir(parents=True,exist_ok=True);shutil.move(str(gateway),str(live_gateway));installed_gateway=True
                overrides=[ROOT/name for name in ('compose.override.yaml','compose.override.yml','docker-compose.override.yml','docker-compose.override.yaml')]
                if not any(file.exists() for file in overrides):
                    override=ROOT/'docker-compose.override.yml';shutil.copyfile(ROOT/'v2/compose.gateway.yml',override)
                from network_settings import restore_provider
                restore_provider(ROOT/".env")
                from tunnel_url import check_gateway_config,read_setting
                check_gateway_config(ROOT/'.env',read_setting(stage.read_text(),'NGROK_DOMAIN'))
            progress('Verifying and restoring posts and media / Verificando y restaurando datos',70)
            transfer.do_import(incoming,str(parts/'postiz.tar'),replace)
        except Exception:
            if previous_env is not None:telegram_settings.atomic_write(ROOT/'.env',previous_env.decode())
            elif (ROOT/'.env').exists():(ROOT/'.env').unlink()
            if installed_gateway and live_gateway.exists():shutil.rmtree(live_gateway)
            if previous_gateway.exists():shutil.move(str(previous_gateway),str(live_gateway))
            if override:override.unlink(missing_ok=True)
            if provider_previous is not None:
                from tunnel_url import private_write
                private_write(provider_override,provider_previous,work)
            else:provider_override.unlink(missing_ok=True)
            raise
        info.update(restored=True,rollback=rollback['file'] if rollback else None,services_stopped=True,telegram_paused=True)
        return info


def start(payload):
    operation=payload.get('action')
    if operation not in ('export','inspect','restore'):raise ValueError('Unknown backup action.')
    password=payload.get('password','')
    if not isinstance(password,str) or len(password)<12:raise ValueError('Use a passphrase of at least 12 characters. / Usa una contraseña de al menos 12 caracteres.')
    if operation=='restore' and (not payload.get('confirmed') or not re.fullmatch(r'[a-f0-9]{64}',payload.get('fingerprint',''))):
        raise ValueError('Inspect and confirm this backup first.')
    JOBS.mkdir(mode=0o700,parents=True,exist_ok=True);identifier=secrets.token_hex(16)
    write_status(identifier,state='running',stage='Starting / Iniciando',percent=0,action=operation)
    flags={'creationflags':subprocess.CREATE_NEW_PROCESS_GROUP|subprocess.DETACHED_PROCESS} if os.name=='nt' else {'start_new_session':True}
    child=subprocess.Popen([sys.executable,'-B',str(Path(__file__).resolve()),'--worker',identifier],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,cwd=ROOT,env=dict(os.environ,PYTHONUTF8='1',PYTHONIOENCODING='utf-8'),**flags)
    try:child.stdin.write(json.dumps(payload).encode());child.stdin.close()
    except Exception:write_status(identifier,state='error',error='Could not start backup worker.');raise
    return {'id':identifier}


def status(identifier):
    if not re.fullmatch(r'[a-f0-9]{32}',identifier):raise ValueError('Invalid backup task.')
    result=json.loads((JOBS/(identifier+'.json')).read_text())
    if result.get('state')=='running' and ((result.get('pid') and not pmlib.pid_alive(result['pid'])) or (not result.get('pid') and time.time()-result.get('updated',0)>30)):
        write_status(identifier,state='error',error='Task was interrupted. No automatic restore retry was started. / La tarea se interrumpió. No se inició un reintento automático.');result=json.loads((JOBS/(identifier+'.json')).read_text())
    return result


def worker(identifier):
    payload=json.loads(sys.stdin.buffer.read(1048576));password=payload.pop('password')
    try:
        with file_lock.exclusive(str(JOBS/'worker.lock'),blocking=False):
            write_status(identifier,pid=os.getpid())
            progress=lambda message,percent:write_status(identifier,stage=message,percent=percent)
            if payload['action']=='export':result=create_bundle(payload['folder'],password,progress)
            else:result=inspect_bundle(payload['file'],password,progress,restore=payload['action']=='restore',replace=payload.get('replace') is True,expected=payload.get('fingerprint'))
            write_status(identifier,state='done',percent=100,result=result)
    except Exception as error:
        message=str(error)[:700] if isinstance(error,(ValueError,pmlib.PMError)) else 'Backup task failed. Services may remain stopped after a restore failure. Review before retrying. / La tarea falló. Los servicios pueden quedar detenidos si falló la restauración. Revisa antes de reintentar.'
        write_status(identifier,state='error',error=message)

if __name__=='__main__' and len(sys.argv)==3 and sys.argv[1]=='--worker':worker(sys.argv[2])
