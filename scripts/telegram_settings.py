# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Installation-owned Telegram settings. Secrets never appear in status responses."""
import json
import os
from pathlib import Path
import re
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts/lib'))
sys.path.insert(0, str(ROOT / 'v2'))
import file_lock
from telegram_worker import TelegramError, telegram, is_owner

KEYS = ('TELEGRAM_ENABLED', 'TELEGRAM_BOT_TOKEN', 'TELEGRAM_BOT_ID', 'TELEGRAM_BOT_USERNAME',
        'TELEGRAM_OWNER_ID', 'TELEGRAM_LANGUAGE', 'TELEGRAM_HEARTBEAT_MINUTES',
        'TELEGRAM_TRANSPORT', 'TELEGRAM_MIGRATION_HOLD')
TOKEN = re.compile(r'[0-9]+:[A-Za-z0-9_-]{25,}')


def read_values(path):
    result = {}
    if path.is_file():
        for line in path.read_text(encoding='utf-8').splitlines():
            key, separator, value = line.partition('=')
            if separator and not key.strip().startswith('#'):
                result[key.strip()] = value.strip().strip('\"\'')
    return result


def configuration(root=ROOT):
    root = Path(root)
    old = read_values(root / 'run/telegram/settings.env')
    env = read_values(root / '.env')
    result = {key: env.get(key, old.get(key, '')) for key in KEYS}
    token_file = root / 'run/telegram/token'
    if 'TELEGRAM_BOT_TOKEN' not in env and token_file.is_file():
        result['TELEGRAM_BOT_TOKEN'] = token_file.read_text(encoding='utf-8').strip()
    result['TELEGRAM_ENABLED'] = env.get('TELEGRAM_ENABLED', 'true' if result['TELEGRAM_OWNER_ID'] else 'false')
    result['TELEGRAM_LANGUAGE'] = result['TELEGRAM_LANGUAGE'] or 'en'
    result['TELEGRAM_HEARTBEAT_MINUTES'] = result['TELEGRAM_HEARTBEAT_MINUTES'] or '0'
    result['TELEGRAM_MIGRATION_HOLD'] = result['TELEGRAM_MIGRATION_HOLD'] or 'false'
    result['TELEGRAM_TRANSPORT'] = 'host'
    return result


def active(config):
    return (config.get('TELEGRAM_ENABLED') == 'true' and config.get('TELEGRAM_MIGRATION_HOLD') != 'true'
            and bool(config.get('TELEGRAM_BOT_TOKEN')) and bool(config.get('TELEGRAM_OWNER_ID')))


def atomic_write(path, value):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError('Telegram configuration must use local regular files.')
    fd, temporary = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(value)
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def merge_env(content, config):
    lines = content.splitlines()
    for key in KEYS:
        value = str(config.get(key, ''))
        if '\n' in value or '\r' in value:
            raise ValueError('Invalid Telegram setting.')
        lines = [line for line in lines if not re.match(r'^\s*' + key + r'\s*=', line)]
        lines.append(key + '=' + value)
    return '\n'.join(lines) + '\n'


def export_env(content, root=ROOT):
    """Include legacy private settings in the encrypted .env snapshot, without changing the source."""
    config = configuration(root)
    if not config['TELEGRAM_BOT_TOKEN'] and not config['TELEGRAM_OWNER_ID']:
        return content
    return merge_env(content, config)


def hold_restored(content):
    if re.search(r'^TELEGRAM_(?:BOT_TOKEN|OWNER_ID)=\S+', content, re.M):
        content = re.sub(r'^TELEGRAM_MIGRATION_HOLD=.*\n?', '', content, flags=re.M)
        content += '\nTELEGRAM_MIGRATION_HOLD=true\n'
    return content


def status(root=ROOT):
    config = configuration(root)
    import host_agent
    return {'configured': bool(config['TELEGRAM_BOT_TOKEN'] and config['TELEGRAM_OWNER_ID']),
            'has_token': bool(config['TELEGRAM_BOT_TOKEN']), 'enabled': config['TELEGRAM_ENABLED'] == 'true',
            'migration_hold': config['TELEGRAM_MIGRATION_HOLD'] == 'true',
            'bot_id': config['TELEGRAM_BOT_ID'], 'username': config['TELEGRAM_BOT_USERNAME'],
            'owner_id': config['TELEGRAM_OWNER_ID'], 'language': config['TELEGRAM_LANGUAGE'],
            'heartbeat': int(config['TELEGRAM_HEARTBEAT_MINUTES']) if config['TELEGRAM_HEARTBEAT_MINUTES'].isdigit() else 0,
            'running': bool(host_agent.running()) and active(config)}


def get_token(payload, root):
    token = str(payload.get('token') or configuration(root)['TELEGRAM_BOT_TOKEN']).strip()
    if not TOKEN.fullmatch(token):
        raise ValueError('Enter a valid BotFather token. / Ingresa un token válido de BotFather.')
    return token


def call(token, method, **payload):
    try:
        return telegram(token, method, **payload)
    except TelegramError:
        raise ValueError('Telegram could not validate this request. Check the token, connection and other pollers. / Telegram no pudo validar la solicitud. Revisa el token, la conexión y otros receptores.') from None


def inspect(payload, root=ROOT):
    token = get_token(payload, root)
    bot = call(token, 'getMe')
    if call(token, 'getWebhookInfo').get('url'):
        raise ValueError('This bot has a webhook. Use a dedicated bot. / Este bot tiene un webhook. Usa un bot dedicado.')
    return {'id': str(bot['id']), 'username': bot['username']}


def detect(payload, root=ROOT):
    token = get_token(payload, root)
    import host_agent
    config = configuration(root)
    if active(config) and token.split(':')[0] == config['TELEGRAM_BOT_ID'] and host_agent.running():
        raise ValueError('Disable Telegram before detecting another owner. / Desactiva Telegram antes de detectar otro propietario.')
    inspect(payload, root)
    updates = call(token, 'getUpdates', timeout=0, limit=100, allowed_updates=['message', 'callback_query'])
    found = {}
    for update in updates:
        message = update.get('message') or {}
        owner = (message.get('from') or {}).get('id')
        if type(owner) is int and owner > 0 and is_owner(message, owner) and message.get('text', '').strip() == '/start':
            found[str(owner)] = {'id': str(owner), 'name': (message['from'].get('first_name') or ''),
                                 'username': message['from'].get('username', '')}
    return {'owners': list(found.values())}


def commands(language):
    es = language == 'es'
    return [{'command': key, 'description': spanish if es else english} for key, english, spanish in (
        ('start', 'Open PostForge', 'Abrir PostForge'), ('new', 'New post or announcement', 'Nueva publicación o anuncio'),
        ('status', 'Check services', 'Revisar servicios'), ('cancel', 'Discard current plan', 'Descartar el plan actual'),
        ('help', 'Show the menu', 'Mostrar el menú'))]


def save(payload, root=ROOT):
    root = Path(root)
    import host_agent
    with file_lock.exclusive(str(root / 'run/telegram-settings.lock')):
        previous = configuration(root)
        enabled = payload.get('enabled') is True
        language = payload.get('language', 'en')
        try:
            minutes = int(payload.get('heartbeat', 0))
        except (TypeError, ValueError):
            minutes = -1
        if language not in ('en', 'es') or (minutes != 0 and not 5 <= minutes <= 1440):
            raise ValueError('Choose English or Spanish and heartbeat 0 or 5–1440 minutes. / Elige inglés o español y un intervalo de 0 o de 5 a 1440 minutos.')
        owner = str(payload.get('owner_id') or previous['TELEGRAM_OWNER_ID']).strip()
        token = str(payload.get('token') or previous['TELEGRAM_BOT_TOKEN']).strip()
        changed = token != previous['TELEGRAM_BOT_TOKEN'] or owner != previous['TELEGRAM_OWNER_ID']
        config = dict(previous, TELEGRAM_ENABLED=str(enabled).lower(), TELEGRAM_LANGUAGE=language,
                      TELEGRAM_HEARTBEAT_MINUTES=str(minutes), TELEGRAM_MIGRATION_HOLD='false')
        if enabled or changed:
            token = get_token(payload, root)
            if not owner.isdigit() or int(owner) < 1:
                raise ValueError('Choose your private Telegram owner ID. / Elige el ID de tu cuenta privada de Telegram.')
            bot = inspect(payload, root)
            chat = call(token, 'getChat', chat_id=int(owner))
            if chat.get('type') != 'private' or chat.get('id') != int(owner):
                raise ValueError('Only a private owner account is supported. / Solo se admite una cuenta privada como propietaria.')
            call(token, 'setMyCommands', commands=commands(language), scope={'type': 'chat', 'chat_id': int(owner)})
            config.update(TELEGRAM_BOT_TOKEN=token, TELEGRAM_BOT_ID=bot['id'], TELEGRAM_BOT_USERNAME=bot['username'], TELEGRAM_OWNER_ID=owner)
        path = root / '.env'
        if not path.is_file() or path.is_symlink():
            raise ValueError('Connect a configured PostForge project first. / Primero conecta un proyecto PostForge configurado.')
        old_text = path.read_text(encoding='utf-8')
        was_running = bool(host_agent.running())
        host_agent.stop()
        runtime = root / 'run/host-agent'
        tracked = list(runtime.glob('*.json')) + [root / 'run/telegram/token']
        previous_files = {path: path.read_text(encoding='utf-8') for path in tracked if path.is_file() and not path.is_symlink()}
        try:
            # A new owner/bot or restored host starts a fresh conversation and ignores old commands.
            if enabled and (changed or previous['TELEGRAM_MIGRATION_HOLD'] == 'true'):
                updates = call(token, 'getUpdates', offset=-1, limit=1, timeout=0, allowed_updates=['message', 'callback_query'])
                offset = updates[-1]['update_id'] + 1 if updates else 0
                state = root / 'run/host-agent/telegram.json'
                atomic_write(state, json.dumps({'offset': offset, 'heartbeat': 0, 'bot_id': token.split(':')[0], 'owner_id': int(owner)}))
                for conversation in state.parent.glob('conversation-*.json'):
                    conversation.unlink()
            atomic_write(path, merge_env(old_text, config))
            if enabled or was_running:
                host_agent.start()
        except Exception:
            atomic_write(path, old_text)
            for item in list(runtime.glob('*.json')) + [root / 'run/telegram/token']:
                if item.is_file() and item not in previous_files:
                    item.unlink()
            for item, content in previous_files.items():
                atomic_write(item, content)
            if was_running:
                host_agent.start()
            raise
        return status(root)
