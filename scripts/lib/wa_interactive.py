# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Owner-bound, expiring, one-use WhatsApp reply-button capabilities."""
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import tempfile
import time

import file_lock
import pmlib

TOKEN = re.compile(r'^pf1:([a-f0-9]{32})$')
RESPONSE_TYPES = ('interactiveResponseMessage', 'buttonsResponseMessage', 'templateButtonReplyMessage', 'listResponseMessage')
ALLOWED = {'review_approval','confirm_plan','rewrite','options','review_reject','confirm_reject','settings','interval_menu','interval_more','back',
           'probe','ping_0','ping_30','ping_60','ping_360','ping_1440'}


def response(message):
    """Read IDs only, never visible labels or arbitrary typed commands."""
    if not isinstance(message, dict):
        return None
    for _ in range(5):
        nested = next((message.get(k) for k in ('ephemeralMessage','viewOnceMessage','viewOnceMessageV2','viewOnceMessageV2Extension','deviceSentMessage') if isinstance(message.get(k),dict)), None)
        if not nested:
            break
        message = nested.get('message') or {}
        if not isinstance(message,dict):return None
    value = None
    item = message.get('interactiveResponseMessage')
    if isinstance(item,dict):
        flow=item.get('nativeFlowResponseMessage')
        raw=flow.get('paramsJson') if isinstance(flow,dict) else None
        if isinstance(raw,str) and len(raw) <= 4096:
            try:
                payload=json.loads(raw)
                value=payload.get('id') if isinstance(payload,dict) else None
            except (ValueError,TypeError):pass
    for kind,key in (('buttonsResponseMessage','selectedButtonId'),('templateButtonReplyMessage','selectedId')):
        if isinstance(message.get(kind),dict):value=message[kind].get(key)
    if isinstance(message.get('listResponseMessage'),dict):
        selection=message['listResponseMessage'].get('singleSelectReply')
        value=selection.get('selectedRowId') if isinstance(selection,dict) else None
    return value if isinstance(value,str) and TOKEN.fullmatch(value) else None


def fingerprint(record):
    return hashlib.sha256(json.dumps(record,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


class Registry:
    def __init__(self, path=None):
        self.path=Path(path or Path(pmlib.RUN_DIR)/'wa-interactive.json')

    def read(self):
        try:
            value=json.loads(self.path.read_text())
            return value if isinstance(value,dict) else {}
        except (OSError,ValueError):return {}

    def write(self,value):
        self.path.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
        fd,tmp=tempfile.mkstemp(dir=self.path.parent)
        try:
            with os.fdopen(fd,'w',encoding='utf-8') as handle:json.dump(value,handle,ensure_ascii=False)
            os.replace(tmp,self.path)
        finally:
            if os.path.exists(tmp):os.unlink(tmp)

    def issue(self, owner, choices, reference=None, plan_hash=None, now=None):
        if not 1 <= len(choices) <= 3 or any(action not in ALLOWED for _,action in choices):
            raise ValueError('Unsupported WhatsApp button choices.')
        now=time.time() if now is None else now
        group=secrets.token_hex(12)
        with file_lock.exclusive(str(self.path)+'.lock'):
            values={k:v for k,v in self.read().items() if isinstance(v,dict) and v.get('expires',0)>now}
            # Bound storage independently of log retention, retaining the newest menus.
            values=dict(sorted(values.items(),key=lambda x:x[1].get('expires',0))[-1197:])
            buttons=[]
            for label,action in choices:
                token=secrets.token_hex(16)
                values[token]={'owner':hashlib.sha256(owner.encode()).hexdigest(),'action':action,'reference':reference,
                               'plan_hash':plan_hash,'group':group,'expires':now+(86400 if reference else 1800),'used':False}
                buttons.append({'type':'reply','displayText':label,'id':'pf1:'+token})
            self.write(values)
        return buttons

    def consume(self, token, owner, now=None, dry_run=False):
        match=TOKEN.fullmatch(token or '')
        if not match:return 'invalid',None
        now=time.time() if now is None else now
        with file_lock.exclusive(str(self.path)+'.lock'):
            values=self.read();record=values.get(match[1])
            if not isinstance(record,dict) or record.get('owner')!=hashlib.sha256(owner.encode()).hexdigest():return 'invalid',None
            if record.get('expires',0)<=now:return 'expired',None
            if record.get('used'):return 'used',record
            if record.get('action') not in ALLOWED:return 'invalid',None
            if not dry_run:
                for value in values.values():
                    if isinstance(value,dict) and value.get('group')==record['group']:value['used']=True
                self.write(values)
            return 'ok',record
