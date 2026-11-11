#!/usr/bin/env python3
# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Repair file-scoped links in stopped ERROR posts. Never publishes or reschedules."""
import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import re
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parent/'lib'))
import pmlib
import media_links


def literal(value):return "'"+str(value).replace("'","''")+"'"


def repair(env,identifiers,apply=False):
    identifiers=list(dict.fromkeys(identifiers))
    if not identifiers or len(identifiers)>50 or any(not re.fullmatch(r'[A-Za-z0-9_-]{10,50}',i) for i in identifiers):raise ValueError('Choose up to 50 valid failed post IDs.')
    client=pmlib.Postiz(env);key=media_links.load_key(Path(pmlib.ROOT)/'data/gateway/media-signing.key')
    if not key:raise pmlib.PMError('Secure media delivery is not configured.')
    sql='SELECT jsonb_build_object(\'id\',p.id,\'image\',p.image,\'network\',i."providerIdentifier")::text FROM "Post" p JOIN "Integration" i ON i.id=p."integrationId" WHERE p."organizationId"='+literal(client.org_id)+" AND p.state='ERROR' AND p.\"deletedAt\" IS NULL AND p.id IN ("+','.join(map(literal,identifiers))+')'
    rows=[json.loads(row[0]) for row in pmlib.psql(sql,env)];updates=[]
    for row in rows:
        items=json.loads(row['image'] or '[]')
        for item in items:
            path=item.get('path','')
            # Existing signed routes are already scoped and must not be double wrapped.
            if '/postforge-media/' not in path:
                item['path']=media_links.signed_url(key,env['FRONTEND_URL'],path,int(time.time()+2*86400))
        updates.append((row,json.dumps(items,separators=(',',':'))))
    result={'posts':[{'id':row['id'],'network':row['network']} for row,_ in updates],'applied':False}
    if not apply:return result
    folder=Path(pmlib.RUN_DIR)/'recovery';folder.mkdir(mode=0o700,parents=True,exist_ok=True)
    backup=folder/('media-links-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'.json')
    fd=os.open(backup,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as stream:json.dump(rows,stream)
    guards=[]
    for row,image in updates:
        where='id='+literal(row['id'])+' AND "organizationId"='+literal(client.org_id)+" AND state='ERROR' AND \"deletedAt\" IS NULL AND image="+literal(row['image'])
        guards.append('IF NOT EXISTS(SELECT 1 FROM "Post" WHERE '+where+') THEN RAISE EXCEPTION \'Post changed during review\'; END IF; UPDATE "Post" SET image='+literal(image)+' WHERE '+where+';')
    if guards:pmlib.psql('BEGIN; DO $repair$ BEGIN '+' '.join(guards)+' END; $repair$; COMMIT;',env)
    result.update(applied=True,backup=str(backup))
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--ids',nargs='+',required=True);parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    print(json.dumps(repair(pmlib.load_env(),args.ids,args.apply),indent=2))
