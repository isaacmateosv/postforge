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
                                   'background': item.get('background','#128C7E')}
                                  for item in whatsapp_pending._read() if item.get('status') in ('pending','needs_review')]
    return result


def receipts(env):
    """Bounded aggregate receipt history; never return recipients or phone numbers."""
    import broadcast_story
    instance="'"+env.get('WA_INSTANCE','status-engine').replace("'","''")+"'"
    count='(SELECT count(DISTINCT u.participant) FROM evolution."MessageUpdate" u WHERE u."messageId"=m.id AND u.participant IS DISTINCT FROM i."ownerJid"%s)'
    rows=pmlib.psql('SELECT m."messageTimestamp", m."messageType", '+count%''+', '+count%" AND u.status='READ'"+' FROM evolution."Message" m JOIN evolution."Instance" i ON i.id=m."instanceId" WHERE i.name='+instance+' AND m.key->>\'remoteJid\'=\'status@broadcast\' AND (m.key->>\'fromMe\')::boolean ORDER BY m."messageTimestamp" DESC LIMIT 12;',env)
    return {'items':[{'at':int(row[0]),'kind':row[1],'received':int(row[2]) if int(row[0])>=broadcast_story.RECEIPTS_SINCE else None,'viewed':int(row[3]) if int(row[0])>=broadcast_story.RECEIPTS_SINCE else None} for row in rows]}
