# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
"""Download and checksum-verify a compatible desktop release for in-app install.

Read-only network use: fetches the published release metadata, the matching
per-platform ZIP and its .sha256 sidecar, verifies the digest, and returns the
path to the verified archive. The Rust host performs the actual bundle swap and
relaunch. This module never executes anything it downloads and never pulls a
release that is not strictly newer or not built for this OS/architecture.
"""
import hashlib
import json
import sys
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path

import pmlib
import desktop_updates

ROOT = Path(__file__).resolve().parent.parent
RELEASES = desktop_updates.RELEASES
MAX_BYTES = 120 * 1024 * 1024  # a desktop ZIP is a few MB; bound the download hard.
CHUNK = 65536


def _open(url, accept):
    request = urllib.request.Request(url, headers={'User-Agent': 'PostForge-desktop', 'Accept': accept})
    scheme = urllib.parse.urlsplit(url).scheme
    if scheme != 'https':
        raise pmlib.PMError('Updates are fetched over HTTPS only.')
    return urllib.request.urlopen(request, timeout=20)


def _expected_name(tag):
    return desktop_updates.asset_name(tag)


def _bundle_name():
    if sys.platform == 'darwin':
        return 'PostForge Desktop.app'
    if sys.platform == 'win32':
        return 'postforge-desktop.exe'
    return 'PostForge Desktop'


def download():
    installed = (ROOT / 'VERSION').read_text().strip()
    with _open(RELEASES + '?per_page=40', 'application/vnd.github+json') as response:
        releases = json.load(response)
    release = desktop_updates.select_release(releases, installed)
    if not release:
        raise pmlib.PMError('No newer compatible update was found. / No se encontró una actualización más reciente.')
    tag = release.get('tag_name') or ''
    name = _expected_name(tag)
    assets = {asset.get('name'): asset.get('browser_download_url') for asset in release.get('assets', [])}
    if not assets.get(name) or not assets.get(name + '.sha256'):
        raise pmlib.PMError('This release has no build for your system. / Esta versión no tiene una instalación para tu sistema.')

    with _open(assets[name + '.sha256'], 'text/plain') as response:
        expected = response.read(200).decode('ascii', 'ignore').split()[0].strip().lower()
    if len(expected) != 64 or any(character not in '0123456789abcdef' for character in expected):
        raise pmlib.PMError('The update checksum could not be read. / No se pudo leer la suma de verificación.')

    directory = Path(tempfile.mkdtemp(prefix='postforge-update-'))
    archive = directory / name
    digest = hashlib.sha256()
    total = 0
    try:
        with _open(assets[name], 'application/octet-stream') as response, open(archive, 'wb') as output:
            while True:
                chunk = response.read(CHUNK)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_BYTES:
                    raise pmlib.PMError('The update is larger than expected and was stopped. / La actualización es más grande de lo previsto y se detuvo.')
                digest.update(chunk)
                output.write(chunk)
    except pmlib.PMError:
        archive.unlink(missing_ok=True)
        directory.rmdir()
        raise
    if digest.hexdigest().lower() != expected:
        archive.unlink(missing_ok=True)
        directory.rmdir()
        raise pmlib.PMError('The update failed verification and was discarded. / La actualización no pasó la verificación y se descartó.')
    return {'zip': str(archive), 'version': tag.lstrip('v'), 'bundle': _bundle_name(), 'bytes': total}
