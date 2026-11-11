# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Read-only desktop overview and explicit, in-window WhatsApp pairing."""
import base64
import html
import json
import re
import sys
from pathlib import Path
from urllib.parse import quote

import pmlib


def whatsapp(env, connect=False):
    instance = quote(env.get('WA_INSTANCE', 'status-engine'), safe='')
    headers = {'apikey': env.get('AUTHENTICATION_API_KEY', '')}
    code, body = pmlib.http('GET', 'http://localhost:8080/instance/connectionState/' + instance, headers, timeout=4)
    state = (body.get('instance') or {}).get('state') if isinstance(body, dict) else None
    if state == 'open':
        return {'connected': True, 'state': 'open'}
    if not connect:
        return {'connected': False, 'state': state or 'unavailable'}
    if code == 404:
        code, body = pmlib.http('POST', 'http://localhost:8080/instance/create', headers,
                              body={'instanceName': env.get('WA_INSTANCE', 'status-engine'), 'integration': 'WHATSAPP-BAILEYS', 'qrcode': True}, timeout=15)
    else:
        code, body = pmlib.http('GET', 'http://localhost:8080/instance/connect/' + instance, headers, timeout=15)
    qr = (body.get('qrcode') or body) if isinstance(body, dict) else {}
    value = qr.get('base64', '')
    try:
        raw = base64.b64decode(value.split(',')[-1], validate=True)
        if not raw.startswith(b'\x89PNG\r\n\x1a\n') or len(raw) > 300000:
            raise ValueError
    except (ValueError, TypeError):
        raise pmlib.PMError('A QR code is not ready. Check Evolution and try again. / El QR aún no está listo. Revisa Evolution y vuelve a intentar.') from None
    return {'connected': False, 'state': 'pairing', 'qr': 'data:image/png;base64,' + base64.b64encode(raw).decode()}


def dashboard(env):
    import telegram_settings
    result = {'timezone': env.get('PM_TIMEZONE', 'America/Guayaquil'), 'available': False, 'postiz_online': False, 'drafts': 0, 'queue': 0, 'next': None, 'posts': [], 'telegram': telegram_settings.status()}
    try:
        client = pmlib.Postiz(env)
        org = "'" + client.org_id.replace("'", "''") + "'"
        rows = pmlib.psql('''SELECT json_build_object(
            'drafts', (SELECT count(*) FROM "Post" WHERE "organizationId"=''' + org + ''' AND state='DRAFT' AND "deletedAt" IS NULL AND "parentPostId" IS NULL),
            'queue', (SELECT count(*) FROM "Post" WHERE "organizationId"=''' + org + ''' AND state='QUEUE' AND "deletedAt" IS NULL AND "parentPostId" IS NULL),
            'next', (SELECT min("publishDate") FROM "Post" WHERE "organizationId"=''' + org + ''' AND state='QUEUE' AND "deletedAt" IS NULL),
            'posts', coalesce((SELECT json_agg(x) FROM (
              SELECT p.id, p.state, p."publishDate" AS at, i."providerIdentifier" AS network,
                     coalesce(i."customName",i.name) AS channel,
                     left(regexp_replace(p.content, '<[^>]*>', ' ', 'g'),160) AS text
              FROM "Post" p JOIN "Integration" i ON i.id=p."integrationId"
              WHERE p."organizationId"=''' + org + ''' AND p."deletedAt" IS NULL AND p."parentPostId" IS NULL
              AND p.state IN ('DRAFT','QUEUE','ERROR') ORDER BY p."createdAt" DESC,p.id DESC LIMIT 40) x), '[]'::json))::jsonb::text''', env)
        result.update(json.loads(rows[0][0]), available=True)
        for post in result["posts"]:
            post["text"] = html.unescape(post.get("text") or "")
    except (pmlib.PMError, OSError, ValueError, IndexError):
        pass
    try:
        code, _ = pmlib.http('GET', env.get('POSTIZ_LOCAL_URL', 'http://localhost:4200').rstrip('/') + '/api/', timeout=2)
        result['postiz_online'] = 200 <= code < 300 or code in (401, 403)
    except (pmlib.PMError, OSError):
        pass
    try:
        result['whatsapp'] = whatsapp(env)
    except (pmlib.PMError, OSError):
        result['whatsapp'] = {'connected': False, 'state': 'unavailable'}
    import whatsapp_pending
    with whatsapp_pending._queue_lock():
        result['status_items'] = [{'id': item['id'], 'caption': item.get('caption',''), 'when': item.get('when'),
                                   'status': item.get('status'), 'approved': bool(item.get('approved')),
                                   'media': [Path(file).name for file in item.get('media',[])],
                                   'background': item.get('background','#128C7E'),
                                   'audience':item.get('audience',env.get('WA_STATUS_AUDIENCE','all')),
                                   'recipient_count':len([p for p in item.get('recipients',env.get('WA_TEST_RECIPIENTS','')).split(',') if p]),
                                   'delivery_part':item.get('delivery_part'),'delivery_parts':item.get('delivery_parts'),'completed_parts':item.get('completed_parts',0)}
                                  for item in whatsapp_pending._read() if item.get('status') in ('pending','needs_review','sending')]
    return result


def receipts(env, payload=None):
    """Five rows per page; date/type filters; no recipient identities returned."""
    import broadcast_story
    payload=payload or {}
    page=payload.get('page',0);period=payload.get('period','30');kind=payload.get('kind','all')
    if type(page) is not int or not 0<=page<=10000 or period not in ('7','30','all') or kind not in ('all','video','image','text'):
        raise pmlib.PMError('Choose valid history filters. / Elige filtros válidos para el historial.')
    instance="'"+env.get('WA_INSTANCE','status-engine').replace("'","''")+"'"
    count='(SELECT count(DISTINCT u.participant) FROM evolution."MessageUpdate" u WHERE u."messageId"=m.id AND u.participant IS DISTINCT FROM i."ownerJid"%s)'
    where='i.name='+instance+" AND m.key->>'remoteJid'='status@broadcast' AND (m.key->>'fromMe')::boolean"
    if period!='all':where+=' AND m."messageTimestamp">=extract(epoch FROM now()-interval \''+period+' days\')'
    if kind!='all':where+=' AND m."messageType" '+({'video':"='videoMessage'",'image':"='imageMessage'",'text':"IN ('conversation','extendedTextMessage')"}[kind])
    sql='SELECT jsonb_build_object(\'at\',m."messageTimestamp",\'kind\',m."messageType",\'received\','+count%''+',\'viewed\','+count%" AND u.status='READ'"+',\'text\',left('+broadcast_story.STATUS_TEXT_SQL+',160))::text FROM evolution."Message" m JOIN evolution."Instance" i ON i.id=m."instanceId" WHERE '+where+' ORDER BY m."messageTimestamp" DESC,m.id DESC LIMIT 6 OFFSET '+str(page*5)
    rows=[json.loads(row[0]) for row in pmlib.psql(sql,env)]
    for item in rows:
        if int(item['at'])<broadcast_story.RECEIPTS_SINCE:item.update(received=None,viewed=None)
    return {'items':rows[:5],'page':page,'has_more':len(rows)>5}


def connections(env):
    from datetime import datetime,timezone
    client=pmlib.Postiz(env);org="'"+client.org_id.replace("'","''")+"'"
    sql='''SELECT jsonb_build_object('name',coalesce(i."customName",i.name),'network',i."providerIdentifier",
      'disabled',i.disabled,'refresh_needed',i."refreshNeeded",'has_token',length(coalesce(i.token,''))>0,
      'can_renew',length(coalesce(i."refreshToken",''))>0,'expires',i."tokenExpiration",'updated',i."updatedAt",
      'auth_error',(SELECT max(p."updatedAt") FROM "Post" p WHERE p."integrationId"=i.id AND p.state='ERROR' AND p.error LIKE '%refresh_token%'))::text
      FROM "Integration" i WHERE i."organizationId"='''+org+''' AND i."deletedAt" IS NULL ORDER BY i."providerIdentifier"'''
    result=[];now=datetime.now(timezone.utc)
    def date(value):
        if not value:return None
        value=re.sub(r'\.(\d{1,5})(?=[+-]|$)',lambda m:'.'+m.group(1).ljust(6,'0'),value.replace('Z','+00:00'))
        parsed=datetime.fromisoformat(value)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    for row in pmlib.psql(sql,env):
        item=json.loads(row[0]);item['can_renew']=bool(item['can_renew'] and item['network'] in ('youtube','tiktok','threads'));expiry=date(item.get('expires'));updated=date(item.get('updated'));error=date(item.get('auth_error'))
        state='connected'
        if item['refresh_needed'] or not item['has_token'] or (error and (not updated or error>=updated)):state='reconnect'
        elif item['disabled']:state='paused'
        elif expiry and expiry<=now:state='renewal' if item['can_renew'] else 'reconnect'
        result.append({key:item.get(key) for key in ('name','network','expires','updated')}|{'state':state,'can_renew':item['can_renew']})
    return {'items':result,'checked_at':now.isoformat()}
