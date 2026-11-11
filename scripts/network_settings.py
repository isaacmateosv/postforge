# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Transactional tunnel selection. Provider credentials live only in the private .env."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parent/'lib'))
import pmlib
import file_lock
from telegram_settings import atomic_write
import tunnel_url as tunnel
ROOT=Path(__file__).resolve().parent.parent
CLOUDFLARED='cloudflare/cloudflared@sha256:4955524aeaa379e154023d5a027c250f7b35041a2e7e950cf13f144bc9b9c5ba'
NGROK='ngrok/ngrok@sha256:ff3b5c3674432d14a786349908b7bdf28ee56c25662637afcbe7180d471993ef'
PROVIDERS=('trycloudflare','cloudflare','ngrok')
QUICK=re.compile(r'https://[a-z0-9]+(?:-[a-z0-9]+)*\.trycloudflare\.com(?=[\s/|"\']|$)')


def values(path=None):
    content=(path or ROOT/'.env').read_text()
    return {key:tunnel.read_setting(content,key) for key in ('PM_TUNNEL_PROVIDER','FRONTEND_URL','PM_CUSTOM_DOMAIN','CLOUDFLARE_TUNNEL_TOKEN','PM_NGROK_DOMAIN','NGROK_DOMAIN')}


def merge(content,settings):
    for key,value in settings.items():
        if not isinstance(value,str) or any(c in value for c in '\n\r\x00'):raise ValueError('Invalid network setting.')
        content=re.sub(r'(?m)^[ \t]*'+re.escape(key)+r'[ \t]*=.*\n?','',content)
        content=content.rstrip()+'\n'+key+'='+value+'\n'
    return content


def provider_block(provider):
    if provider not in PROVIDERS:raise ValueError('Choose a supported tunnel provider.')
    if provider=='ngrok':
        spec={'image':NGROK,'entrypoint':['ngrok'],'command':['http','--url=${NGROK_DOMAIN}','postforge-gateway:8080'],
              'environment':{'NGROK_AUTHTOKEN':'${NGROK_AUTHTOKEN}'}}
    else:
        command=['tunnel','--no-autoupdate','--protocol','http2']
        command+=['--url','http://postforge-gateway:8080','--metrics','0.0.0.0:2000'] if provider=='trycloudflare' else ['run']
        spec={'image':CLOUDFLARED,'entrypoint':['cloudflared'],'command':command,
              'environment':{'NGROK_AUTHTOKEN':'','TUNNEL_TOKEN':'${CLOUDFLARE_TUNNEL_TOKEN:-}' if provider=='cloudflare' else ''}}
    spec.update(depends_on=['postforge-gateway'],restart='unless-stopped',mem_limit='192m',pids_limit=64,
                cap_drop=['ALL'],security_opt=['no-new-privileges:true'],read_only=True,
                deploy={'resources':{'limits':{'memory':'192m','cpus':'0.5','pids':64}}})
    # JSON flow mappings are valid YAML, with no parser dependency on the host.
    return '  ngrok: '+json.dumps(spec)+'\n'


def render_override(content,provider):
    match=re.search(r'(?m)^  ngrok:\s*(?:\n|\{)',content)
    if not match:raise ValueError('The gateway override has no managed tunnel service.')
    start=match.start();following=re.search(r'(?m)^  [A-Za-z0-9_-]+:',content[match.end():])
    end=match.end()+following.start() if following else len(content)
    return content[:start]+provider_block(provider)+content[end:]


def restore_provider(path):
    """Rebuild the generated connector from encrypted portable settings, without starting it."""
    config=values(path);provider=config['PM_TUNNEL_PROVIDER'] or 'ngrok'
    (path.parent/'run').mkdir(mode=0o700,exist_ok=True)
    override=path.parent/'docker-compose.override.yml'
    template=override.read_text() if override.exists() else (path.parent/'v2/compose.gateway.yml').read_text()
    # Replace symlinks atomically; never modify the tracked gateway template.
    tunnel.private_write(override,render_override(template,provider).encode(),path.parent/'run')


def quick_url():
    result=subprocess.run(['docker','logs','--tail','180','pm-tunnel'],capture_output=True,text=True,timeout=5)
    matches=QUICK.findall(result.stdout+'\n'+result.stderr)
    return matches[-1] if result.returncode==0 and matches else None


def status(check=False,force=False):
    config=values();provider=config['PM_TUNNEL_PROVIDER'] or 'ngrok'
    result={'provider':provider,'url':config['FRONTEND_URL'],'custom_domain':config['PM_CUSTOM_DOMAIN'],
            'ngrok_domain':config['PM_NGROK_DOMAIN'] or config['NGROK_DOMAIN'],
            'has_token':bool(config['CLOUDFLARE_TUNNEL_TOKEN']),'temporary':provider=='trycloudflare'}
    if check:
        cache=ROOT/'run/network-health.json'
        if not force:
            try:
                saved=json.loads(cache.read_text())
                if saved.get('url')==result['url'] and time.time()-saved['checked_at']<60:
                    return dict(result,**{key:saved.get(key) for key in ('reachable','discovered_url','needs_sync','checked_at')})
            except (OSError,ValueError,KeyError):pass
        result['reachable']=tunnel.gateway_ready(result['url']) if result['url'] else False
        try:result['discovered_url']=quick_url() if provider=='trycloudflare' else None
        except (OSError,subprocess.SubprocessError):result['discovered_url']=None
        result['needs_sync']=bool(result['discovered_url'] and result['discovered_url']!=result['url'])
        result['checked_at']=time.time()
        atomic_write(cache,json.dumps(result))
    return result


def guard_idle(env):
    client=pmlib.Postiz(env)
    rows=pmlib.psql('SELECT count(*) FROM "Post" WHERE "organizationId"='+literal(client.org_id)+" AND state='QUEUE' AND \"deletedAt\" IS NULL",env)
    if int(rows[0][0]):raise ValueError('Cancel or finish scheduled posts before switching the public URL. / Cancela o completa las publicaciones programadas antes de cambiar la URL pública.')
    jobs=Path(pmlib.JOBS_DIR)
    if jobs.exists() and any(jobs.glob('*.json')):raise ValueError('Wait for active PostForge tasks before changing the public URL. / Espera a que terminen las tareas activas antes de cambiar la URL pública.')
    import whatsapp_pending
    with whatsapp_pending._queue_lock():
        if any(item.get("status")=="sending" for item in whatsapp_pending._read()):
            raise ValueError("Wait for the active WhatsApp Status delivery before changing networks. / Espera a que termine el envío activo de WhatsApp antes de cambiar la red.")
    return client.org_id


def literal(value):return "'"+value.replace("'","''")+"'"


def rebase_media(env,org,old,new):
    """Change media origins only. Never captions, credentials, post states or schedules."""
    if old==new:return
    old_upload=old.rstrip('/')+'/uploads/';new_upload=new.rstrip('/')+'/uploads/'
    old_signed=old.rstrip('/')+'/postforge-media/';new_signed=new.rstrip('/')+'/postforge-media/'
    def replace(column):
        return 'replace(replace('+column+','+literal(old_upload)+','+literal(new_upload)+'),'+literal(old_signed)+','+literal(new_signed)+')'
    pmlib.psql('BEGIN; UPDATE "Post" SET image='+replace('image')+', settings='+replace('settings')+' WHERE "organizationId"='+literal(org)+'; UPDATE "Media" SET path='+replace('path')+', thumbnail='+replace('thumbnail')+' WHERE "organizationId"='+literal(org)+'; COMMIT;',env)



def reload_agent():
    if not (ROOT/'run/host-agent/pid').is_file():return False
    import host_agent
    if host_agent.running():
        host_agent.stop();host_agent.start();return True
    return False


def apply(payload):
    provider=payload.get('provider')
    if provider not in PROVIDERS:raise ValueError('Choose a supported provider.')
    if payload.get('confirm') is not True:raise ValueError('Review and confirm the public URL change.')
    path=ROOT/'.env';work=ROOT/'run';work.mkdir(mode=0o700,exist_ok=True)
    with file_lock.exclusive(str(work/'tunnel-url.lock'),blocking=False):
        original=path.read_text();config=values(path);env=pmlib.load_env();org=guard_idle(env)
        gateway=ROOT/'data/gateway/configuration.yml';override=ROOT/'docker-compose.override.yml'
        if not gateway.is_file() or gateway.is_symlink():raise ValueError('Configure the protected gateway before publishing a tunnel. / Configura el gateway protegido antes de publicar un túnel.')
        previous_gateway=gateway.read_text();previous_override=override.read_text() if override.exists() else (ROOT/'v2/compose.gateway.yml').read_text()
        local=env.get('POSTIZ_LOCAL_URL','http://localhost:4200');expected=tunnel.probe(local)
        if expected is None:raise ValueError('Start Postiz and wait for its local API before changing networks. / Inicia Postiz y espera a que responda su API local antes de cambiar la red.')
        token=payload.get('token','') or config['CLOUDFLARE_TUNNEL_TOKEN']
        custom=payload.get('custom_domain',config['PM_CUSTOM_DOMAIN']).strip()
        if custom:custom=tunnel.normalize(custom)[1]
        if provider=='cloudflare' and (not custom or not re.fullmatch(r'[A-Za-z0-9_.+/=-]{20,8192}',token)):
            raise ValueError('Set your domain and a valid Cloudflare tunnel token. / Configura tu dominio y un token válido del túnel de Cloudflare.')
        settings={'PM_TUNNEL_PROVIDER':provider,'PM_CUSTOM_DOMAIN':custom,'CLOUDFLARE_TUNNEL_TOKEN':token,
                  'PM_NGROK_DOMAIN':config['PM_NGROK_DOMAIN'] or config['NGROK_DOMAIN']}
        if provider=='ngrok':target=tunnel.normalize(payload.get('ngrok_domain') or settings['PM_NGROK_DOMAIN'])[1]
        elif provider=='cloudflare':target=custom
        else:target=None
        recovery=work/('network-recovery-'+str(time.time_ns()));recovery.mkdir(mode=0o700)
        for name,content in [('env',original),('gateway',previous_gateway),('override',previous_override)]:atomic_write(recovery/name,content)
        rebased=False
        try:
            # Stop the publishing process before changing origin configuration.
            # Recheck after stopping to catch a calendar action racing the UI guard.
            tunnel.compose(path,"stop","postiz")
            guard_idle(env)
            atomic_write(path,merge(original,settings))
            tunnel.private_write(override,render_override(previous_override,provider).encode(),work)
            tunnel.compose(path,'config','--quiet')
            # Quick URLs change on process restart. Keep that same process alive
            # throughout origin synchronization; restarting it here loses the URL.
            changed=provider!=(config['PM_TUNNEL_PROVIDER'] or 'ngrok')
            args=['up','-d','--no-deps']+(['--force-recreate'] if changed or payload.get('rotate') else [])+['ngrok']
            tunnel.compose(path,*args)
            if provider=='trycloudflare':
                deadline=time.monotonic()+65
                while time.monotonic()<deadline:
                    target=quick_url()
                    if target:break
                    time.sleep(1)
                if not target:raise RuntimeError('Cloudflare did not supply a temporary URL in time. / Cloudflare no entregó una URL temporal a tiempo.')
            host,target=tunnel.normalize(target)
            atomic_write(path,merge(tunnel.updated_config(path.read_text(),host,target),{'POSTFORGE_GATEWAY_HOST':host}))
            from v2.gateway_setup import update_hostname
            atomic_write(gateway,json.dumps(update_hostname(json.loads(previous_gateway),host),indent=2)+'\n')
            tunnel.apply_services(path,True,host)
            tunnel.wait_until_ready(local,target,expected,gated=True)
            rebase_media(env,org,config['FRONTEND_URL'],target);rebased=True
            # Keep one recent private recovery set; no provider secrets enter responses.
            atomic_write(work/'network-last-change.json',json.dumps({'old_url':config['FRONTEND_URL'],'url':target,'at':time.time(),'provider':provider}))
            warning=None
            try:agent_reloaded=reload_agent()
            except Exception:
                agent_reloaded=False;warning='Public access is ready; restart the local agent to refresh bot links. / El acceso público está listo; reinicia el agente local para actualizar los enlaces de los bots.'
            return dict(status(),changed=True,callbacks=callbacks(target),previous_url=config['FRONTEND_URL'],agent_reloaded=agent_reloaded,warning=warning)
        except BaseException as failure:
            try:
                if rebased:rebase_media(env,org,target,config['FRONTEND_URL'])
                atomic_write(path,original);atomic_write(gateway,previous_gateway)
                tunnel.private_write(override,previous_override.encode(),work)
                tunnel.compose(path,'up','-d','--no-deps','--force-recreate','postforge-auth','postforge-gateway','postiz','ngrok')
            except BaseException:
                raise pmlib.PMError('Network switch failed and needs recovery. Private originals: '+str(recovery)+' / El cambio de red falló y requiere recuperación. Originales privados: '+str(recovery)) from None
            raise pmlib.PMError('Network switch failed; the previous configuration was restored. '+str(failure).split(' / ')[0][:250]+' / El cambio de red falló; se restauraron los ajustes anteriores. Comprueba el acceso público y aplica la URL de nuevo si cambió.') from None


def callbacks(url):
    return [{'network':name,'url':url+'/integrations/social/'+name} for name in ('youtube','facebook','instagram','threads','tiktok')]

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('provider',choices=PROVIDERS,nargs='?');parser.add_argument('--rotate',action='store_true');parser.add_argument('--prepare',action='store_true');args=parser.parse_args()
    if args.prepare:
        restore_provider(ROOT/'.env');print('Tunnel provider configuration prepared.')
    elif args.provider:print(json.dumps(apply({'provider':args.provider,'rotate':args.rotate,'confirm':True}),indent=2))
    else:parser.error('Choose a provider or --prepare')
