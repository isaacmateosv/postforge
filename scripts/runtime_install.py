# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Install public runtime code; private configuration and data are never payloads."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import secrets
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0,str(Path(__file__).resolve().parent/'lib'))
import file_lock

ROOT_FILES={'VERSION','.env.example','docker-compose.yml','postforge.sh','publish-machine.sh','install.sh','LICENSE','COPYRIGHT','NOTICE.md','README.md','SETUP.md','ROLLBACK.md'}
PREFIXES=('scripts/','v2/','patches/','config/','docs/help/')
MANIFEST='runtime-manifest.json'

def allowed(name):
    path=PurePosixPath(name)
    return (not path.is_absolute() and '\\' not in name and all(p not in ('','..','.') for p in path.parts)
            and (name in ROOT_FILES or name.startswith(PREFIXES))
            and not any(p in ('__pycache__','.git','.env','data','run','logs','exports','backups','tunnel') for p in path.parts)
            and not name.endswith(('.pyc','vip-list.txt')))

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def build(source,destination,paths=None):
    source=Path(source);destination=Path(destination);destination.mkdir(parents=True)
    if paths is None:paths=subprocess.check_output(['git','ls-files','-z'],cwd=source).decode().split('\0')
    files={}
    for name in sorted(set(paths)):
        if not allowed(name):continue
        original=source/name
        if original.is_symlink() or not original.is_file():continue
        target=destination/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(original,target)
        mode=0o755 if original.stat().st_mode&0o111 else 0o644;target.chmod(mode)
        files[name]={'sha256':digest(target),'mode':mode}
    required={'VERSION','scripts/desktop_bridge.py','scripts/runtime_install.py','postforge.sh'}
    if not required<=files.keys():raise ValueError('Runtime package is missing required code.')
    (destination/MANIFEST).write_text(json.dumps({'version':(source/'VERSION').read_text().strip(),'files':files},sort_keys=True))

def validate(source):
    manifest=json.loads((source/MANIFEST).read_text());files=manifest['files']
    if not isinstance(files,dict) or not 4<=len(files)<=5000:raise ValueError('Invalid runtime manifest.')
    if not {'VERSION','scripts/desktop_bridge.py','scripts/runtime_install.py','postforge.sh'}<=files.keys():raise ValueError('Incomplete runtime.')
    total=0
    for name,record in files.items():
        if not allowed(name):raise ValueError('Private or unsafe runtime path.')
        file=source/name
        if any(part.is_symlink() for part in [file,*file.parents] if part!=source.parent):raise ValueError('Runtime links are not allowed.')
        if not file.is_file() or digest(file)!=record['sha256'] or record['mode'] not in (0o644,0o755):raise ValueError('Runtime verification failed.')
        total+=file.stat().st_size
    if total>100*1024*1024:raise ValueError('Runtime exceeds the supported size.')
    if (source/'VERSION').read_text().strip()!=manifest['version']:raise ValueError('Runtime version mismatch.')
    return manifest

def apply(source,target,refresh=False,only_newer=False):
    source=Path(source).resolve();target=Path(target).absolute();manifest=validate(source)
    if any(p.is_symlink() for p in [target,*target.parents]):raise ValueError('Installation folder must not use symbolic links.')
    if only_newer and (target/'VERSION').is_file() and (target/'scripts/desktop_bridge.py').is_file():
        import desktop_updates
        current=desktop_updates.version((target/'VERSION').read_text().strip())
        incoming=desktop_updates.version(manifest['version'])
        if current is not None and incoming is not None and current>=incoming:return {'version':manifest['version'],'folder':str(target),'unchanged':True}
    target.mkdir(parents=True,exist_ok=True,mode=0o700)
    run=target/'run';run.mkdir(mode=0o700,exist_ok=True)
    if run.is_symlink():raise ValueError('Runtime state must be a regular directory.')
    with file_lock.exclusive(str(run/'runtime-install.lock'),blocking=False):
        pending=run/'whatsapp-pending.json'
        if refresh and pending.exists() and any(row.get('status')=='sending' for row in json.loads(pending.read_text())):
            raise ValueError('Wait for WhatsApp delivery to finish before updating. / Espera a que termine el envío de WhatsApp antes de actualizar.')
        recovery=run/('runtime-recovery-'+secrets.token_hex(8));recovery.mkdir(mode=0o700)
        replaced=[];created=[]
        try:
            for name,record in manifest['files'].items():
                file=target/name
                relative=file.relative_to(target)
                if any((target/Path(*relative.parts[:i])).is_symlink() for i in range(1,len(relative.parts)+1)):
                    raise ValueError('Installation code path is a symbolic link.')
                if file.exists():
                    if not file.is_file():raise ValueError('Installation code path is not a file.')
                    if digest(file)==record['sha256']:continue
                    saved=recovery/name;saved.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(file,saved);replaced.append(name)
                else:created.append(name)
                file.parent.mkdir(parents=True,exist_ok=True)
                fd,temporary=tempfile.mkstemp(dir=file.parent)
                try:
                    with os.fdopen(fd,'wb') as output:output.write((source/name).read_bytes())
                    os.chmod(temporary,record['mode']);os.replace(temporary,file)
                finally:Path(temporary).unlink(missing_ok=True)
            if refresh and (target/'.env').is_file():
                result=subprocess.run(['bash',str(target/'postforge.sh'),'refresh-installed-services'],cwd=target,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=600)
                log=run/'runtime-refresh.log';log.write_bytes(result.stdout);log.chmod(0o600)
                if result.returncode:raise ValueError('Service refresh failed; previous code was restored. Check runtime-refresh.log. / Falló la actualización de servicios; se recuperó el código anterior. Revisa runtime-refresh.log.')
            checkpoint=run/'runtime-installed.json';checkpoint.write_text(json.dumps({'version':manifest['version'],'recovery':str(recovery)}));checkpoint.chmod(0o600)
        except BaseException:
            for name in created:(target/name).unlink(missing_ok=True)
            for name in replaced:shutil.copy2(recovery/name,target/name)
            raise
        if not replaced:shutil.rmtree(recovery)
    return {'version':manifest['version'],'folder':str(target)}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--source',required=True);parser.add_argument('--target',required=True);parser.add_argument('--refresh',action='store_true');parser.add_argument('--upgrade-if-needed',action='store_true');args=parser.parse_args()
    try:print(json.dumps(apply(args.source,args.target,args.refresh,args.upgrade_if_needed)))
    except Exception as error:print(str(error),file=sys.stderr);sys.exit(1)
